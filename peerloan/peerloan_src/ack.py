# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction

from peerloan.forms import CaptchaForm

from django.contrib.sessions.models import Session

from peerloan.models import Account
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import OTPMessage
from peerloan.models import Product
from peerloan.models import User
from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest
from peerloan.models import UserOperationHistory
from peerloan.models import UserTransaction

from peerloan.decorators import require_login

import peerloan.emailing as emailing
import peerloan.peerloan_src.supporting_function as sup_fn

from collections import OrderedDict
from datetime import datetime
from django.utils import timezone
import json
import urlparse

FLOAT_DATA_FORMAT = '{:,.2f}'

@require_login
@transaction.atomic
def ack_handler(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	# check XSS
	if sup_fn.checkHTMLtags([v for k, v in request.POST.iteritems()]):
		return HttpResponse('Invalid input.')
	
	#apply to be investor:
	if request.META.get('HTTP_REFERER').split('/')[3] == 'apply_to_be_investor':
		# sign agreement step
		uor_list = UserOperationRequest.objects.filter(usr_id=usr.id, type="Apply To Be Investor")
		if len(uor_list) != 0:
			# OTP verification
			user_input_OTP = request.POST.get('OTP')
			try:
				OTP_message_list = OTPMessage.objects.filter(usr_id=usr.id, action="Confirm agreement - Apply to be investor", status="ACTIVE")
				OTP_message = OTP_message_list.latest('generated_timestamp')
			except ObjectDoesNotExist:
				# receive OTP first
				return redirect('/apply_to_be_investor/?error=invalid_OTP')
			else:
				# check expiring
				if OTP_message.expiring_timestamp < timezone.localtime(timezone.now()):
					for item in OTP_message_list:
						item.status = 'EXPIRED'
						item.save()
					return redirect('/apply_to_be_investor/?error=OTP_expired')
				if user_input_OTP != OTP_message.sequence:
					for item in OTP_message_list:
						item.status = 'EXPIRED'
						item.save()
					return redirect('/apply_to_be_investor/?error=OTP_not_matched')
				
			for item in OTP_message_list:
				item.status = 'EXPIRED'
				item.save()
			
			
			uor = uor_list.latest('create_timestamp')
			
			if uor.status == 'AGREEMENT CONFIRMED':
				request.session['type'] = 'L'
				return redirect('/portfolio/portfolio_summary')
			
			uor.status = 'AGREEMENT CONFIRMED'
			details = json.loads(uor.details)
			details['Confirm Lender Agreement Date'] = datetime.strftime(timezone.localtime(timezone.now()), '%Y/%m/%d %H:%M:%S')
			details['OTP'] = user_input_OTP
			details['Lender No'] = sup_fn.generate_lender_no()
			uor.details = json.dumps(details)
			uor.update_timestamp = timezone.localtime(timezone.now())
			uor.save()
			
			# sync to usr
			sync_list  = ['Home Phone No.', 'Surname', 'Given Name', 'Mobile', 'Gender',
			'Residential Address', 'Date of Birth', 'HKID']
			sync_dict = {}
			for name in sync_list:
				try:
					sync_dict[name] = details['Individual'][name]
				except KeyError:
					continue
			sup_fn.sync_to_usr(usr_id=usr.id, dict=sync_dict)
			
			# create new lender account
			new_usr = User(
			email = usr.email,
			password = usr.password,
			receive_promotion = usr.receive_promotion,
			detail_info = uor.details,
			type = 'L',
			status = 'ACTIVE',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			
			new_usr.notification = json.dumps({
			"Fund Matching Completed (SMS)": "Every Day", 
			"Deposit Confirmed (SMS)": "Yes", 
			"Withdrawal Confirmed (SMS)": "Yes", 
			"All Fund Matched (SMS)": "Yes", 
			"Fund Matching Completed (Email)": "Every Loan", 
			"Deposit Confirmed (Email)": "Yes", 
			"Withdrawal Confirmed (Email)": "Yes", 
			"All Fund Matched (Email)": "Yes", 
			"Monthly Statement (Email)": "Yes", 
			})
			
			new_usr.this_login = timezone.localtime(timezone.now())
			new_usr.save()
			
			new_acc = Account(
			usr_id = new_usr.id,
			balance = 0,
			on_hold_amt = 0
			)
			new_acc.save()
			
			# create ledger
			inputs = {
				'usr_id': new_usr.id,
				'description': 'Begin Balance',
				'reference': '--',
				'debit': 0,
				'credit': 0,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			# update aut
			inputs = {
				'usr_id': usr.id,
				'description': 'Confirm lender agreement',
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Borrower: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
				'details': {
					'usr_ip': request.META.get('REMOTE_ADDR')
				},
				'action': 'modify',
				'type': 'Apply To Be Investor',
				'status': 'UNREAD',
			}
			sup_fn.update_aut(inputs)
			sup_fn.update_ptn(inputs)
			
			# send email notification
			ldr_emailing = emailing.LenderEmail(uor=uor)
			ldr_emailing.lender_agreement()
			
			request.session['type'] = 'L'
			return redirect('/portfolio/portfolio_summary')
			
			
		# submit application form step
		simplified_hkid = request.POST.get('HKID').replace('(','').replace(')','').lower()
		
		# check hkid cannot repeat from other lender
		other_ldr_list = UserOperationRequest.objects.filter((~Q(usr_id = usr.id)) & Q(simplified_hkid=simplified_hkid) & Q(type = 'Apply To Be Investor'))
		if len(other_ldr_list) != 0:
			return redirect('/ack_page/?action=apply_lender_rejected&reason=repeated_hkid')
			
		# check hkid should be consistent with the one in borrower's account
		details = json.loads(usr.detail_info)
		try:
			details['HKID']
		except KeyError:
			''
		else:
			bor_simplified_hkid = details['HKID'].replace('(','').replace(')','').lower()
			if simplified_hkid != bor_simplified_hkid:
				return redirect('/ack_page/?action=apply_lender_rejected&reason=hkid_not_matched')
		
		account_type = request.POST.get('Account Type')
		if account_type == 'Individual':
			info_list = ['Account Type','Surname','Given Name','Gender','Education Level','HKID',
			'Nationality','Date of Birth','Occupation','Type of Employment','Annual Income','Company Name',
			'Office Address','Office Tel','Residential Address','Home Phone No.','Mobile','Source of Fund',
			'Other Source of Fund', 'Customer Declaration']
			
			details = OrderedDict()
			details[account_type] = OrderedDict()
			ref_num = sup_fn.generate_ref_num('Apply To Be Investor', 'LDA')
			details[account_type]['Application No'] = ref_num
			for info in info_list:
				if request.POST.get(info) != '' and request.POST.get(info) != None:
					details[account_type][info] = request.POST.get(info)
			
			
			# generate supporting documents records
			details['File Uploaded'] = OrderedDict()
			for filetype, file in request.FILES.iteritems():
				# non-repeated rand 32 digits string
				rand_seq = sup_fn.generate_unique_sequence()
				postfix = file.name.split('.')[-1]
				new_fname = rand_seq + '.' + postfix
				def process(f):
					with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
						for chunk in f.chunks():
							destination.write(chunk)
				process(file)
				details['File Uploaded'][filetype] = new_fname
			
			# create new uor
			new_uor = UserOperationRequest(
			usr_id = usr.id,
			type = 'Apply To Be Investor',
			details = json.dumps(details),
			simplified_hkid = simplified_hkid,
			status = 'DOC UPLOADED',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_uor.save()
			
			# update aut
			inputs = {
				'usr_id': usr.id,
				'description': 'Submit lender application form',
				'ref_id': new_uor.id,
				'model': 'UserOperationRequest',
				'by': 'Borrower: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
				'details': {
					'usr_ip': request.META.get('REMOTE_ADDR')
				},
				'action': 'create',
				'status': 'UNREAD',
				'type': 'Apply To Be Investor',
			}
			sup_fn.update_aut(inputs)
			sup_fn.update_ptn(inputs)
			
			return redirect('/apply_to_be_investor')
		if account_type == 'Corporate':
			corporate_info_list = ['Company Name','Established at','CR NO.','Country','Office Address',
			'Company Size','Office Tel','Industry']
			individual_info_list = ['Surname','Given Name','Gender','Education Level','HKID',
			'Nationality','Date of Birth','Occupation','Type of Employment','Annual Income',
			'Residential Address','Home Phone No.','Mobile','Source of Fund','Other Source of Fund', 'Customer Declaration']
			
			details = OrderedDict()
			details['Corporate'] = OrderedDict()
			details['Individual'] = OrderedDict()
			ref_num = sup_fn.generate_ref_num('Apply To Be Investor', 'LDA')
			details['Individual']['Application No'] = ref_num
			for info in corporate_info_list:
				if request.POST.get(info) != '' and request.POST.get(info) != None:
					details['Corporate'][info] = request.POST.get(info)
			for info in individual_info_list:
				if request.POST.get(info) != '' and request.POST.get(info) != None:
					details['Individual'][info] = request.POST.get(info)
			details['Corporate']['Company Name'] = request.POST.getlist('Company Name')[0]
			details['Corporate']['Office Address'] = request.POST.getlist('Office Address')[0]
			details['Corporate']['Office Tel'] = request.POST.getlist('Office Tel')[0]
			
			# generate supporting documents records
			details['File Uploaded'] = OrderedDict()
			for filetype, file in request.FILES.iteritems():
				# non-repeated rand 32 digits string
				rand_seq = sup_fn.generate_unique_sequence()
				postfix = file.name.split('.')[-1]
				new_fname = rand_seq + '.' + postfix
				def process(f):
					with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
						for chunk in f.chunks():
							destination.write(chunk)
				process(file)
				details['File Uploaded'][filetype] = new_fname
			# create new uor
			new_uor = UserOperationRequest(
			usr_id = usr.id,
			type = 'Apply To Be Investor',
			details = json.dumps(details),
			simplified_hkid = simplified_hkid,
			status = 'DOC UPLOADED',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_uor.save()
			
			# sync to usr
			sync_list  = ['Home Phone No.', 'Surname', 'Given Name', 'Mobile', 'Gender',
			'Residential Address', 'Date of Birth', 'HKID']
			sync_dict = {}
			for name in sync_list:
				try:
					sync_dict[name] = details['Individual'][name]
				except KeyError:
					continue
			sup_fn.sync_to_usr(usr_id=usr.id, dict=sync_dict)
			
			# update aut
			inputs = {
				'usr_id': usr.id,
				'description': 'Submit lender application form',
				'ref_id': new_uor.id,
				'model': 'UserOperationRequest',
				'by': 'Borrower: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
				'details': {
					'usr_ip': request.META.get('REMOTE_ADDR')
				},
				'action': 'create',
				'status': 'UNREAD',
				'type': 'Apply To Be Investor',
			}
			sup_fn.update_aut(inputs)
			sup_fn.update_ptn(inputs)
			
			# send email notification
			ldr_emailing = emailing.LenderEmail(uor=new_uor)
			ldr_emailing.lender_application()
			
			return redirect('/apply_to_be_investor')
			
	# upload supply docs for bor req
	if request.META.get('HTTP_REFERER').split('/')[3] == 'my_account' and request.META.get('HTTP_REFERER').split('/')[4] == 'laas' and request.META.get('HTTP_REFERER').split('/')[5] == 'view_detail':
		bor_id = int(request.META.get('HTTP_REFERER').split('/?bor_id=')[-1])
		
		# generate supporting documents records
		for filetype, file in request.FILES.iteritems():
			
			# non-repeated rand 32 digits string
			rand_seq = sup_fn.generate_unique_sequence()
			postfix = file.name.split('.')[-1]
			new_fname = rand_seq + '.' + postfix
			def process(f):
				with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
					for chunk in f.chunks():
						destination.write(chunk)
			process(file)
			
			new_bod = BorrowRequestDocument(
			bor_id = bor_id,
			type = request.POST.get('supply_doc_descri'),
			detail = new_fname,
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_bod.save()
			
		action = 'upload_supply_doc&bor_id='+str(bor_id)
	# deposit money
	#if request.META.get('HTTP_REFERER').split('/')[3] == 'trans_records' and request.META.get('HTTP_REFERER').split('/')[4] == 'deposit_money':
	if request.META.get('HTTP_REFERER').split('/')[3] == 'my_account' and request.META.get('HTTP_REFERER').split('/')[4] == 'deposit_money':
		# generate supporting documents records
		for filetype, file in request.FILES.iteritems():
			
			# non-repeated rand 32 digits string
			rand_seq = sup_fn.generate_unique_sequence()
			postfix = file.name.split('.')[-1]
			new_fname = rand_seq + '.' + postfix
			def process(f):
				with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
					for chunk in f.chunks():
						destination.write(chunk)
			process(file)
		ref_num = sup_fn.generate_ref_num('Deposit', 'PLD')
		# create utrx record
		new_trx = UserTransaction(
		usr_id = usr.id,
		type = 'Deposit Money - Fund Receive',
		amount_in = request.POST.get("transfer_amt"),
		amount_out = 0,
		internal_ref = ref_num,
		#cust_ref = request.POST.get('ur_ref'),
		cust_ref = '--',
		href = '/file/' + new_fname,
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_trx.save()
		
		details = {
		"transferred_amount": request.POST.get("transfer_amt"),
		"file": new_fname,
		"ref_num": ref_num,
		"customer_reference": request.POST.get('ur_ref'),
		'trx_id': new_trx.id,
		}
		
		new_uor = UserOperationRequest(
		usr_id = usr.id,
		type = 'Deposit Money',
		details = json.dumps(details),
		status = 'PENDING APPROVAL',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uor.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Submit deposit $' + request.POST.get("transfer_amt"),
			'ref_id': new_uor.id,
			'model': 'UserOperationRequest',
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now()),
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'action': 'create',
			'type': 'Deposit Money',
			'status': 'UNREAD',
		}
		sup_fn.update_aut(inputs)
		sup_fn.update_ptn(inputs)
		
		action = 'deposit_money'
	# withdraw money
	#if request.META.get('HTTP_REFERER').split('/')[3] == 'trans_records' and request.META.get('HTTP_REFERER').split('/')[4] == 'withdraw_money':
	if request.META.get('HTTP_REFERER').split('/')[3] == 'my_account' and request.META.get('HTTP_REFERER').split('/')[4] == 'withdraw_money':
		# OTP verification
		user_input_OTP = request.POST.get('OTP')
		try:
			OTP_message_list = OTPMessage.objects.filter(usr_id=usr.id, action="Withdraw Money", status="ACTIVE")
			OTP_message = OTP_message_list.latest('generated_timestamp')
		except ObjectDoesNotExist:
			# receive OTP first
			return redirect('/my_account/withdraw_money/?error=invalid_OTP')
		else:
			if OTP_message.expiring_timestamp < timezone.localtime(timezone.now()):
				for item in OTP_message_list:
					item.status = 'EXPIRED'
					item.save()
				return redirect('/my_account/withdraw_money/?error=OTP_expired')
			if user_input_OTP != OTP_message.sequence:
				for item in OTP_message_list:
					item.status = 'EXPIRED'
					item.save()
				return redirect('/my_account/withdraw_money/?error=OTP_not_matched')
		
		for item in OTP_message_list:
			item.status = 'EXPIRED'
			item.save()
		
		ref_num = sup_fn.generate_ref_num('Withdraw', 'PLW')
		withdraw_amt = float(request.POST.get('withdraw_amt').split(';')[-1])
		
		acc = Account.objects.get(usr_id=usr.id)
		acc.balance -= withdraw_amt
		acc.on_hold_amt += withdraw_amt
		acc.save()
		
		# create utrx record
		new_trx = UserTransaction(
		usr_id = usr.id,
		type = 'Withdraw Money - Request Receive',
		amount_in = 0,
		amount_out = withdraw_amt,
		internal_ref = ref_num,
		#cust_ref = request.POST.get('Your Reference'),
		cust_ref = '--',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_trx.save()
		
		details = {
		'ref_num': ref_num,
		'withdraw_amt': withdraw_amt,
		'customer_reference': request.POST.get('Your Reference'),
		'trx_id': new_trx.id,
		'bank_acc_no': request.POST.get('Bank Account'),
		}
		new_uor = UserOperationRequest(
		usr_id = usr.id,
		type = 'Withdraw Money',
		details = json.dumps(details),
		status = 'PENDING APPROVAL',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uor.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Request withdraw $' + str(withdraw_amt),
			'ref_id': new_uor.id,
			'model': 'UserOperationRequest',
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now()),
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'action': 'create',
			'type': 'Withdraw Money',
			'status': 'UNREAD',
		}
		sup_fn.update_aut(inputs)
		sup_fn.update_ptn(inputs)
		
		action = 'withdraw_money'
	if request.META.get('HTTP_REFERER').split('/')[3] == 'my_account' and request.META.get('HTTP_REFERER').split('/')[4] == 'repayment_and_settlement':
		# generate supporting documents records
		for filetype, file in request.FILES.iteritems():
			# non-repeated rand 32 digits string
			rand_seq = sup_fn.generate_unique_sequence()
			postfix = file.name.split('.')[-1]
			new_fname = rand_seq + '.' + postfix
			def process(f):
				with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
					for chunk in f.chunks():
						destination.write(chunk)
			process(file)
		details = {
			'fname': new_fname,
			'Deposit Amount': request.POST.get('Deposit Amount'),
			'Deposit Date': request.POST.get('Deposit Date'),
			'Deposit Method': request.POST.get('Deposit Method'),
			'Repayment Type': request.POST.get('Repayment Type'),
			
			'bor_id': request.POST.get('bor_id')
		}
		new_uor = UserOperationRequest(
		usr_id = usr.id,
		type = 'Repayment',
		details = json.dumps(details),
		status = 'PENDING APPROVAL',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uor.save()
		
		# update aut
		bor = BorrowRequest.objects.get(id=request.POST.get('bor_id'))
		inputs = {
			'usr_id': usr.id,
			'description': 'Submitted repayment of %s instalment $%s'%(str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month),request.POST.get('Deposit Amount')),
			'ref_id': request.POST.get('bor_id'),
			'model': 'BorrowRequest',
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'by': 'Borrower: '+usr.email,
			'datetime': timezone.localtime(timezone.now())
		}
		if request.POST.get('Repayment Type') == 'Early Settlement':
			inputs['description'] = 'Submitted Early Settlement $%s'%(request.POST.get('Deposit Amount'))
		sup_fn.update_aut(inputs)
		
		# update ptn
		inputs = {
			'ref_id': request.POST.get('bor_id'),
			'model': 'BorrowRequest',
			'type': 'Repayment',
			'description': 'Borrower repayment (%s): Amount %s'%(request.POST.get('Repayment Type'),request.POST.get('Deposit Amount')),
			'status': 'UNREAD',
			'datetime': timezone.localtime(timezone.now()),
			
			'action': 'modify'
		}
		sup_fn.update_ptn(inputs)
		action = 'repayment_and_settlement'
	#if request.META.get('HTTP_REFERER').split('/')[3] == 'product' and request.META.get('HTTP_REFERER').split('/')[4] == 'invest':
	if request.META.get('HTTP_REFERER').split('/')[3] == 'investment' and request.META.get('HTTP_REFERER').split('/')[4] == 'invest_now':
		#prod_id = int(request.META.get('HTTP_REFERER').split('/?prod_id=')[-1])
		prod_id = int(request.POST.get('prod_id'))
		try:
			inv = Investment.objects.get(prod_id=prod_id, usr_id=usr.id)
		except ObjectDoesNotExist:
			# create new inv
			invest_amt = float(request.POST.get('investment_amount').split(';',2)[-1])
			inv = Investment(
			usr_id = usr.id,
			prod_id = prod_id,
			total_amount = float(request.POST.get('investment_amount').split(';',2)[-1]),
			usable_amount = float(request.POST.get('investment_amount').split(';',2)[-1]),
			used_amount = 0,
			on_hold_amount = 0,
			max_amount_per_loan = float(request.POST.get('max_amount_per_loan').split(';',2)[-1]),
			option = request.POST.get('investment_setting'),
			ack = 'True',
			status = 'ACTIVE',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			inv.save()
			
			acc = Account.objects.get(usr_id=usr.id)
			acc.balance -= inv.total_amount
			acc.save()
		else:
			# add investment
			acc = Account.objects.get(usr_id = usr.id)
			invest_amt = float(request.POST.get('investment_amount').split(';',2)[-1])
			inv.total_amount += invest_amt
			inv.usable_amount += invest_amt
			acc.balance -= invest_amt
			acc.save()
			
			inv.option = request.POST.get('investment_setting')
			inv.update_timestamp = timezone.localtime(timezone.now())
			inv.save()
		
		# create user operation history
		new_uoh = UserOperationHistory(
		usr_id = usr.id,
		type = 'allocate_fund',
		details = '{"prod_id":%s,"inv_id":%s,"allocate_amount":%s}' % 
		(prod_id, inv.id, float(request.POST.get('investment_amount').split(';',2)[-1])),
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uoh.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		prod = Product.objects.get(id=prod_id)
		inputs = {
			'usr_id': usr.id,
			'description': 'Allocated $%s to "%s"'%(str(invest_amt), prod.name_en),
			'ref_id': inv.id,
			'model': 'Investment',
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now())
		}
		sup_fn.update_aut(inputs)
		action = 'set_inv'
	if request.META.get('HTTP_REFERER').split('/')[3] == 'investment' and request.META.get('HTTP_REFERER').split('/')[4] == 'reallocate_fund':
		prod_id = int(request.POST.get('prod_id'))
		acc = Account.objects.get(usr_id=usr.id)
		try:
			inv = Investment.objects.get(usr_id=usr.id, prod_id=prod_id)
		except ObjectDoesNotExist:
			return redirect(request.META.get('HTTP_REFERER'))
			
		target_amt = float(request.POST.get('investment_amount').split(';',2)[-1])
		
		withdraw_amt = inv.usable_amount - target_amt
		acc.balance += withdraw_amt
		inv.total_amount -= withdraw_amt
		inv.usable_amount = target_amt
		
		max_amount_per_loan = float(request.POST.get('max_amount_per_loan').split(';',2)[-1])
		inv.max_amount_per_loan = max_amount_per_loan
		inv.option = request.POST.get('investment_setting')
		inv.update_timestamp = timezone.localtime(timezone.now())
		
		acc.save()
		inv.save()
		
		# create user operation history
		new_uoh = UserOperationHistory(
		usr_id = usr.id,
		type = 'reallocate_fund',
		details = '{"prod_id":%s,"inv_id":%s,"withdraw_amount":%s}' % 
		(prod_id, inv.id, str(withdraw_amt)),
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uoh.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		prod = Product.objects.get(id=prod_id)
		inputs = {
			'usr_id': usr.id,
			'description': 'Reduced $%s from "%s"'%(str(withdraw_amt), prod.name_en),
			'ref_id': inv.id,
			'model': 'Investment',
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now())
		}
		sup_fn.update_aut(inputs)
		
		action = 'set_inv'
	#if request.META.get('HTTP_REFERER').split('/')[3] == 'product' and request.META.get('HTTP_REFERER').split('/')[4] == 'transfer':
	if request.META.get('HTTP_REFERER').split('/')[3] == 'investment' and request.META.get('HTTP_REFERER').split('/')[4] == 'transfer_fund':
		from_prod_id = request.POST.get('from_prod')
		from_prod = Product.objects.get(id = from_prod_id)
		from_inv = Investment.objects.get(usr_id = usr.id, prod_id = from_prod_id)
		to_prod_id  = request.POST.get('to_prod')
		to_prod = Product.objects.get(id = to_prod_id)
		to_inv = Investment.objects.get(usr_id = usr.id, prod_id = to_prod_id)
		transfer_amount = float(request.POST.get('investment_amount').split(';',2)[-1]) - float(request.POST.get('investment_amount').split(';',2)[-2])
		
		from_inv.total_amount -= transfer_amount
		from_inv.usable_amount -= transfer_amount
		to_inv.total_amount += transfer_amount
		to_inv.usable_amount += transfer_amount
		from_inv.update_timestamp = timezone.localtime(timezone.now())
		to_inv.update_timestamp = timezone.localtime(timezone.now())
		from_inv.save()
		to_inv.save()
		
		# create user operation history
		new_uoh = UserOperationHistory(
		usr_id = usr.id,
		type = 'transfer_fund',
		details = '{"from_prod_id":%s,"from_inv_id":%s,"to_prod_id":%s,"to_inv_id":%s,"transfer_amount":%s}' % 
		(from_prod.id,from_inv.id,to_prod.id,to_inv.id,str(transfer_amount)),
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uoh.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Transferred $%s from "%s" to "%s"'%(str(transfer_amount),from_prod.name_en,to_prod.name_en),
			'ref_id': new_uoh.id,
			'model': 'UserOperationHistory',
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now())
		}
		sup_fn.update_aut(inputs)
		
		action = 'transfer_inv'
	if request.META.get('HTTP_REFERER').split('/')[3] == 'product' and request.META.get('HTTP_REFERER').split('/')[4] == 'upload_docs':
		prod_id = int(request.META.get('HTTP_REFERER').split('/?prod_id=')[-1])
		bor = BorrowRequest.objects.filter(usr_id=usr.id, prod_id=prod_id, status="AUTO APPROVED").latest('update_timestamp')
		bor.verify_identity = request.POST.get('optionsRadios')
		bor_detail = json.loads(bor.detail_info)
		
		bank_acc_info_list = ['Bank Code', 'Account Number']
		for item in bank_acc_info_list:
			if request.POST.get(item) != '' and request.POST.get(item) != None:
				bor_detail[item] = request.POST.get(item)
		
		bor_detail['Additional Condition Declaration'] = {}
		
		addit_condit_decla_list = ['has_third_party', 'Name of Third Party', 'HKID No. / Company No.', 'Residential Address / Registered Office Address']
		for item in addit_condit_decla_list:
			if request.POST.get(item) != '' and request.POST.get(item) != None:
				bor_detail['Additional Condition Declaration'][item] = request.POST.get(item)
		bor.detail_info = json.dumps(bor_detail)
		bor.save()
		
		with transaction.atomic():
			# update photo files
			for filetype, file in request.FILES.iteritems():
				
				# non-repeated rand 32 digits string
				rand_seq = sup_fn.generate_unique_sequence()
				postfix = file.name.split('.')[-1]
				new_fname = rand_seq + '.' + postfix
				def process(f):
					with open('/home/ubuntu/project_peerloan/supporting_documents/' + new_fname, 'wb+') as destination:
						for chunk in f.chunks():
							destination.write(chunk)
				process(file)
				
				new_bod = BorrowRequestDocument(
				bor_id = bor.id,
				type = filetype,
				detail = new_fname,
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_bod.save()
			
			# update bor status
			bor.status = 'DOC UPLOADED'
			bor.update_timestamp = timezone.localtime(timezone.now())
			bor.save()
			
			# update aut
			inputs = {
				'usr_id': usr.id,
				'description': 'Submitted loan documents',
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Borrower: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
				'details': {
					'usr_ip': request.META.get('REMOTE_ADDR')
				},
				'action': 'modify',
				'type': 'Application',
				'status': 'UNREAD',
			}
			sup_fn.update_aut(inputs)
			sup_fn.update_ptn(inputs)
		
		return redirect('/product/confirm_agreement/?prod_id='+str(prod_id))
	if request.META.get('HTTP_REFERER').split('/')[3] == 'product' and request.META.get('HTTP_REFERER').split('/')[4] == 'confirm_agreement':
		url = request.META.get('HTTP_REFERER')
		parsed = urlparse.urlparse(url)
		prod_id = int(urlparse.parse_qs(parsed.query)['prod_id'][0])
		user_input_OTP = request.POST.get('OTP')
		
		inputs = {
			'usr_id': usr.id,
			'usr_input_OTP': user_input_OTP,
			'return_link': '/product/confirm_agreement/?prod_id=%s'%(prod_id),
			'OTP_action': 'Confirm agreement - Loan application'
		}
		result, return_link = sup_fn.check_OTP_match(inputs)
		if result == False:
			return redirect(return_link)
		
		bor = BorrowRequest.objects.filter(usr_id=usr.id, prod_id=prod_id, status="DOC UPLOADED").latest('update_timestamp')
		bor.status = 'AGREEMENT CONFIRMED'
		details = json.loads(bor.detail_info)
		details['Confirm Loan Agreement Date'] = datetime.strftime(timezone.localtime(timezone.now()), '%Y/%m/%d %H:%M:%S')
		details['OTP'] = user_input_OTP
		
		# record the info borrower agree
		agreement_info_list = ['Surname', 'Given Name', 'HKID', 'Residential Address', 'Amount', 'Bank Code', 'Account Number']
		agreement_info_dict = {}
		for name in agreement_info_list:
			try:
				agreement_info_dict[name] = details[name]
			except KeyError:
				continue
		details['Agreement Info'] = agreement_info_dict
		
		bor.detail_info = json.dumps(details)
		bor.update_timestamp = timezone.localtime(timezone.now())
		bor.save()
		
		# sync to usr
		sync_list  = ['Home Phone No.', 'Surname', 'Given Name', 'Account Number', 'Mobile', 'Gender', 
		'Residential Address', 'Bank Code', 'Living Status', 'Living with', 'Date of Birth', 'HKID', 
		'Studying University', 'Subject']
		sync_dict = {}
		for name in sync_list:
			try:
				sync_dict[name] = details[name]
			except KeyError:
				continue
		sup_fn.sync_to_usr(usr_id=usr.id, dict=sync_dict)
		
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Signed loan agreement with OTP%s'%(user_input_OTP),
			'ref_id': bor.id,
			'model': 'BorrowRequest',
			'by': 'Borrower: ' + usr.email,
			'datetime': timezone.localtime(timezone.now()),
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'action': 'modify',
			'type': 'Application',
			'status': 'UNREAD',
		}
		sup_fn.update_aut(inputs)
		sup_fn.update_ptn(inputs)
		
		# send email notification
		bor_emailing = emailing.BorrowerEmail(bor=bor)
		bor_emailing.copy_of_loan_agreement()
		
		action = 'confirm_agreement'
	if request.META.get('HTTP_REFERER').split('/')[3] == 'settings' and request.META.get('HTTP_REFERER').split('/')[4] == 'sms_email_notification':
		notification = json.loads(usr.notification)
		for k, v in request.POST.iteritems():
			if str(k)[0].isupper():
				notification[k] = str(v)
		usr.notification = json.dumps(notification)
		usr.save()
		return redirect(request.META.get('HTTP_REFERER'))
	if request.META.get('HTTP_REFERER').split('/')[3] == 'settings' and request.META.get('HTTP_REFERER').split('/')[4] == 'account_information':
		uri_list = UserInformation.objects.filter(info_type="Account Information", section="Individual")
		details = []
		for uri in uri_list:
			details.append((uri.section, json.loads(uri.details, object_pairs_hook=OrderedDict)))
		details = OrderedDict(details)
		
		existed_details = json.loads(usr.detail_info, object_pairs_hook=OrderedDict)
		#return HttpResponse(json.dumps(existed_details))
		# remain the history of user's detail info?
		
		# create new detail info
		new_details = OrderedDict()
		for section, terms in details.iteritems():
			new_details[section] = OrderedDict()
			for name, values in terms.iteritems():
				if request.POST.get(name) != '' and request.POST.get(name) != None:
					new_details[section][name] = request.POST.get(name)
				else:
					try:
						new_details[section][name] = existed_details[section][name]
					except KeyError:
						continue
		# create new uor
		new_uor = UserOperationRequest(
		usr_id = usr.id,
		type = 'Change Account Information',
		details = json.dumps(new_details),
		status = 'PENDING APPROVAL',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uor.save()
		
		usr_detail = json.loads(usr.detail_info)
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Submit change account information request',
			'ref_id': new_uor.id,
			'model': 'UserOperationRequest',
			'details': {
				'usr_ip': request.META.get('REMOTE_ADDR')
			},
			'by': 'Lender: ' + usr_detail['Lender No'],
			'datetime': timezone.localtime(timezone.now())
		}
		sup_fn.update_aut(inputs)
		
		action = 'change_acc_info'
		return redirect('/settings/account_information')
	return redirect('/ack_page/?action='+action)
	
@require_login
def ack_page(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	action = request.GET.get('action')
	
	if action == 'upload_supply_doc':
		bor_id = request.GET.get('bor_id')
		bor = BorrowRequest.objects.get(id=bor_id)
		bod = BorrowRequestDocument.objects.filter(bor_id=bor_id).latest('create_timestamp')
		
		content = {
		'title': 'Upload Supplementary Document - Acknowledgement',
		'instruction': """Thank you for you instruction. Your document will be appended to your borrowing application.""",
		'data':[['Borrow Application Reference Number',bor.ref_num], ['Supplementary Document', '<a href="/file/'+bod.detail+'" target="_blank">Click Here</a>'],
		['Document Description', bod.type]]
		}
	if action == 'deposit_money':
		uor = UserOperationRequest.objects.filter(usr_id=usr.id, type='Deposit Money').latest('create_timestamp')
		details = json.loads(uor.details)
		if lang == 'en':
			content = {
			'lang': lang,
			'title': 'Deposit Money - Acknowledgement',
			'instruction': """Thank you for your instruction. Zwap will validate your bank transfer and your 
			receipt within 1 working day. After validation, your transferred amount will be injected to your Zwap account.""",
			'data': [['Reference Number',details["ref_num"]], 
			['Date/Time', datetime.strftime(uor.create_timestamp, "%Y-%m-%d %H:%M")],
			['Bank Deposit Slip', '<a href="/file/'+details["file"]+'" target="_blank">Click Here</a>'],
			['Deposit Amount', FLOAT_DATA_FORMAT.format(float(details['transferred_amount']))],
			#['Your Reference', details['customer_reference']]
			]
			}
		elif lang == 'zh':
			content = {
			'lang': lang,
			'title': '確認通知 - 存入資金',
			'instruction': """我們已收到你的指示，當資金存入於你的Zwap帳戶後，我們將會以立即以手機短訊及電郵通知你。""",
			'data': [['參考編號',details["ref_num"]], 
			['日期/時間', datetime.strftime(uor.create_timestamp, "%Y-%m-%d %H:%M")],
			['銀行存款單據', '<a href="/file/'+details["file"].encode('utf8')+'" target="_blank">點擊此處</a>'],
			['存入金額', FLOAT_DATA_FORMAT.format(float(details['transferred_amount']))],
			#['Your Reference', details['customer_reference']]
			]
			}
	if action == 'withdraw_money':
		uor = UserOperationRequest.objects.filter(usr_id=usr.id, type='Withdraw Money').latest('create_timestamp')
		details = json.loads(uor.details)
		if lang == 'en':
			content = {
			'lang': lang,
			'title': 'Withdraw Money - Acknowledgement',
			'instruction': """Please specify the amount you would like to withdraw from your Zwap's account. 
			We will deposit the request amount to your registered bank account by cheque within 1 business day 
			after validation.
			""",
			'data': [
			['Reference Number',details["ref_num"]],
			['Date/Time', datetime.strftime(uor.create_timestamp, "%Y-%m-%d %H:%M")],
			['Withdrawal Amount', FLOAT_DATA_FORMAT.format(float(details['withdraw_amt']))],
			['Bank Account', details['bank_acc_no']],
			#['Your Reference', details['customer_reference']]
			],
			}
		elif lang == 'zh':
			content = {
			'lang': lang,
			'title': '確認通知 - 提取資金',
			'instruction': """請註明你要從你的Zwap帳戶提取的金額，經核實後我們將於一個工作天內以支票形式存入
			你已登記的銀行戶口內。
			""",
			'data': [
			['參考編號',details["ref_num"]],
			['日期/時間', datetime.strftime(uor.create_timestamp, "%Y-%m-%d %H:%M")],
			['提取金額', FLOAT_DATA_FORMAT.format(float(details['withdraw_amt']))],
			['銀行戶口', details['bank_acc_no']],
			#['Your Reference', details['customer_reference']]
			],
			}
	if action == 'set_inv':
		inv = Investment.objects.filter(usr_id=usr.id).latest('update_timestamp')
		prod = Product.objects.get(id = inv.prod_id)
		
		if lang == 'en':
			content = {
			'lang': lang,
			'title': 'Allocate Investment to '+prod.name_en+' - Acknowledgement',
			'instruction': """Thank you for your instruction. Your investment setting is updated.""",
			'data': [
			['Investment Product', prod.name_en],
			['Investment Amount', FLOAT_DATA_FORMAT.format(inv.usable_amount + inv.on_hold_amount)],
			['Maximum Amount Per Loan', FLOAT_DATA_FORMAT.format(inv.max_amount_per_loan)],
			['Option', inv.option],
			],
			}
		elif lang == 'zh':
			content = {
			'lang': lang,
			'title': '確認通知 - 分配投資到'+prod.name_zh.encode('utf8'),
			'instruction': """你的投資設定已更新。""",
			'data': [
			['投資產品', prod.name_zh],
			['投資金額', FLOAT_DATA_FORMAT.format(inv.usable_amount + inv.on_hold_amount)],
			['每筆貸款的最高金額', FLOAT_DATA_FORMAT.format(inv.max_amount_per_loan)],
			['選項', inv.option],
			],
			}
	if action == 'transfer_inv':
		uoh = UserOperationHistory.objects.filter(usr_id = usr.id, type = 'transfer_fund').latest('create_timestamp')
		details = json.loads(uoh.details)
		to_prod = Product.objects.get(id=details['to_prod_id'])
		from_prod = Product.objects.get(id=details['from_prod_id'])
		if lang == 'en':
			content = {
			'lang': lang,
			'title': 'Transfer Fund - Acknowledgement',
			'instruction': """Thank you for your instruction. Your investment setting is updated.""",
			'data': [['Transferred Amount', FLOAT_DATA_FORMAT.format(float(details['transfer_amount']))], ['Transfer from', from_prod.name_en],
			['Transfer to', to_prod.name_en],]
			}
		if lang == 'zh':
			content = {
			'lang': lang,
			'title': '資金轉賬 - 確認頁面',
			'instruction': """感謝您的指示。你的投資設置已更新。""",
			'data': [['轉賬金額', FLOAT_DATA_FORMAT.format(float(details['transfer_amount']))], ['轉賬從', from_prod.name_zh],
			['轉賬到', to_prod.name_zh],]
			}
	if action == 'apply_loan_rejected':
		reason = request.GET.get('reason')
		if lang == 'en':
			content = {
				'title': 'Application Rejected',
			}
			if reason == 'repeated_hkid':
				content['instruction'] = """Sorry, our system detected that your HKID is repeated from other loan application. Your application is rejected."""
			elif reason == 'hkid_not_matched':
				content['instruction'] = """Sorry, our system detected that your HKID is not matched with your current record. Your application is rejected."""
			else:
				content['instruction'] = """Thank you for your application of our loan services. Your loan application is not successful in this stage. You are welcome to submit your loan application again at any time after one month from now."""
		elif lang == 'zh':
			content = {
				'title': '申請已被拒絕!',
			}
			if reason == 'repeated_hkid':
				content['instruction'] = """系統檢測到你的香港身份證號碼與其他貸款申請的身份證重複，你的申請已被拒絕。"""
			elif reason == 'hkid_not_matched':
				content['instruction'] = """系統檢測到你的香港身份證號碼與你現時記錄不符合，你的申請已被拒絕。"""
			else:
				content['instruction'] = """感謝你申請我們的貸款服務。你的申請暫時未能成功批核。歡迎你於一個月後再次提交你的申請。"""
	if action == 'apply_lender_rejected':
		reason = request.GET.get('reason')
		if lang == 'en':
			content = {
				'title': 'Application Rejected - Acknowledgement'
			}
			if reason == 'repeated_hkid':
				content['instruction'] = """Sorry, our system detected that your HKID is repeated from other loan application. Your application is rejected."""
			elif reason == 'hkid_not_matched':
				content['instruction'] = """Sorry, our system detected that your HKID is not matched with your current record. Your application is rejected."""
			else:
				content['instruction'] = """Sorry, your application is rejected."""
		elif lang == 'zh':
			content = {
				'title': '確認通知 - 貸方申請失敗',
			}
			if reason == 'repeated_hkid':
				content['instruction'] = """系統檢測到你的香港身份證號碼與其他貸款申請的身份證重複，你的申請已被拒絕。"""
			elif reason == 'hkid_not_matched':
				content['instruction'] = """系統檢測到你的香港身份證號碼與你現時記錄不符合，你的申請已被拒絕。"""
			else:
				content['instruction'] = """感謝你申請我們的貸方服務。你的申請暫時未能成功批核。歡迎你於一個月後再次提交你的申請。"""
	if action == 'confirm_agreement':
		if lang == 'en':
			content = {
			'title': 'Application Received - Acknowledgement',
			'instruction': """Thank you! Your signature have been received and we will validate your information before fund matching. We will notify you by SMS and email before disbursement.""",
			}
		if lang == 'zh':
			content = {
			'title': '確認通知 - 申請已經收到',
			'instruction': """感謝! 你的簽署已經收到，進行資金配對前我們會先核實你的資料。放款前我們會以手機短訊及電郵通知你。""",
			}
	if action == 'confirm_memorandum':
		if lang == 'en':
			content = {
			'title': 'Memorandum of Agreement - Acknowledgement',
			'instruction': """Your application process is completed! We will disburse the amount to your registered bank account within 2 working hours, thank you for your support!""",
			}
		if lang == 'zh':
			content = {
			'title': '確認通知 - 協議備忘錄',
			'instruction': """你的申請流程已經完成！我們將會在2個工作小時內發放貸款到你的銀行賬戶，感謝你的支持！""",
			}
	if action == 'repayment_and_settlement':
		uor = UserOperationRequest.objects.filter(usr_id = usr.id, type = 'repayment').latest('create_timestamp')
		details = json.loads(uor.details)
		bor = BorrowRequest.objects.get(id=details['bor_id'])
		en2zh_dict = {
			'Instalment': '分期還款',
			'Early Settlement': '提早還款',
			'Transfer': '轉賬',
			'Cheque': '支票',
			'Cash': '現金',
		}
		if lang == 'en':
			content = {
			'title': 'Repayment and Settlement - Acknowledgement',
			'instruction': """Thank you for your instruction. We will validate your request within 1 business day.
			""",
			'data': [
			['Loan Reference Number', bor.ref_num],
			['Repayment Type', details['Repayment Type']],
			['Deposit Amount', details['Deposit Amount']],
			['Deposit Date', details['Deposit Date']],
			['Deposit Method', details['Deposit Method']],
			['Deposit Slip', '<a href="/file/'+details["fname"]+'" target="_blank">Click Here</a>'],
			],
			}
		elif lang == 'zh':
			content = {
			'title': '確認通知 - 申請已經收到',
			'instruction': """你的指示已經收到，我們將於一個工作天內進行核實。
			""",
			'data': [
			['貸款存款編號', bor.ref_num],
			['供款類型', en2zh_dict[details['Repayment Type']]],
			['存入金額', details['Deposit Amount']],
			['存款日期', details['Deposit Date']],
			['存款方法', en2zh_dict[details['Deposit Method']]],
			['存款單', '<a href="/file/'+details["fname"].encode('utf8')+'" target="_blank">點擊此處</a>'],
			],
			}
	if usr.type == 'L':
		return render(request, 'peerloan/lender/acknowledgement.html', content)
	if usr.type == 'B':
		return render(request, 'peerloan/borrower/acknowledgement.html', content)