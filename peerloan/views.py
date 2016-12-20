from django.shortcuts import render_to_response
from django.template import RequestContext
from django.shortcuts import render
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.db import transaction

from .models import Product
from .models import Ledger
from .models import Loan
from .models import LoanSchedule
from .models import Investment
from .models import Account
from .models import BorrowRequest
from .models import BorrowRequestDocument
from .models import OTPMessage
from .models import PendingTaskNotification
from .models import User
from .models import AdminUser
from .models import UserInformation
from .models import UserOperationHistory
from .models import UserOperationRequest
from .models import UserTransaction

import peerloan.emailing as emailing
import peerloan.smsing as smsing
import peerloan.peerloan_src.supporting_function as sup_fn

from .decorators import require_login

from captcha.models import CaptchaStore 
from captcha.helpers import captcha_image_url

from twilio.rest import TwilioRestClient

from collections import OrderedDict
import json
import random
from datetime import datetime
import datetime as dt
from django.utils import timezone
import pytz
from docx import Document
import hashlib
# Create your views here.


def tmp(request):
	return HttpResponse(timezone.localtime(timezone.now()))
	# create loan schedule
	bor = BorrowRequest.objects.get(id=4)
	prod = Product.objects.get(id=bor.prod_id)
	remain_balance = bor.amount
	rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
	start_date_day = 5
	start_date_month = 6
	start_date_year = 2016
	for i in range(prod.repayment_period):
		day = start_date_day
		month = (start_date_month + i-1) % 12 + 1
		year = start_date_year + ((start_date_month+i-1) / 12)
		try:
			date = datetime.strptime(str(day)+'/'+str(month)+'/'+str(year), '%d/%m/%Y')
		except ValueError:
			date = datetime.strptime('1/'+str((month%12)+1)+'/'+str(year), '%d/%m/%Y') - dt.timedelta(days=1)
			
		interest = remain_balance * rate_per_month
		principal = bor.instalment_borrower - interest
		remain_balance -= principal
		
		new_los = LoanSchedule(
		bor_id = bor.id,
		tenor = (i+1),
		instalment = bor.instalment_borrower,
		principal = principal,
		interest = interest,
		due_date = date,
		overdue_day = 0,
		overdue_interest = 0,
		collection_fees = 0,
		repayment_method = 'Auto Pay',
		status = 'OPEN',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_los.save()
	return HttpResponse('ok')

@require_login
def loan_repay_schedule(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	loan_id = request.GET.get('loan_id')
	prod_id = request.GET.get('prod_id')
	bor_id = request.GET.get('bor_id')
	
	if bor_id != None:
		bor = BorrowRequest.objects.get(id = bor_id)
		prod = Product.objects.get(id = bor.prod_id)
		
		remain_balance = bor.amount
		"""
		if usr.type == 'L':
			rate_per_month = prod.APR_lender * 0.01 / 12
			instalment = bor.instalment_lender
		if usr.type == 'B' or usr.type == 'ADMIN':
			rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
			instalment = bor.instalment_borrower
		"""
		rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
		instalment = bor.instalment_borrower
		# get draw down date
		draw_down_date = bor.draw_down_date
	
	if loan_id != None:
		loan = Loan.objects.get(id = loan_id)
		inv = Investment.objects.get(id = loan.inv_id)
		prod = Product.objects.get(id = inv.prod_id)
		bor = BorrowRequest.objects.get(id=loan.bor_id)
		remain_balance = loan.initial_amount
		"""
		if usr.type == 'L':
			rate_per_month = prod.APR_lender * 0.01 / 12
			instalment = loan.instalment_lender
		if usr.type == 'B':
			rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
			instalment = loan.instalment_borrower
		"""
		rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
		instalment = loan.instalment_borrower
		# get draw down date
		draw_down_date = BorrowRequest.objects.get(id=loan.bor_id).draw_down_date
	
	if prod_id != None:
		prod = Product.objects.get(id=prod_id)
		
		remain_balance = prod.min_amount_per_loan
		"""
		if usr.type == 'L':
			rate_per_month = prod.APR_lender * 0.01 / 12
			instalment = prod.min_amount_per_loan * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
		if usr.type == 'B':
			rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
			instalment = prod.min_amount_per_loan * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
		"""
		rate_per_month = prod.APR_borrower * 0.01 / 12
		instalment = remain_balance * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
		
	
	inputs = {
		'start_balance': remain_balance,
		'rate_per_month': rate_per_month,
		'instalment': instalment,
		'repayment_plan': prod.repayment_plan,
		'repayment_period': prod.repayment_period,
	}
	if loan_id != None or bor_id != None:
			if draw_down_date != None:
				inputs['start_date'] = {
					'day': draw_down_date.day,
					'month': draw_down_date.month,
					'year': draw_down_date.year,
				}
				inputs['date_type'] = 'exact datetime'
	try:
		inputs['start_date']
	except KeyError:
		inputs['date_type'] = 'month only'
	
	if usr.type == 'L' and prod_id != None:
		inputs['rate_per_month_bor'] = prod.APR_borrower * 0.01 / 12
		inputs['rate_per_month_ldr'] = prod.APR_lender * 0.01 / 12
		
		repayment_table = sup_fn.generate_ldr_instalment_repayment_schedule(inputs)
	elif usr.type == 'L' and (loan_id != None or bor_id != None):
		inputs['rate_per_month_bor'] = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
		inputs['rate_per_month_ldr'] = prod.APR_lender * 0.01 / 12
		
		repayment_table = sup_fn.generate_ldr_instalment_repayment_schedule(inputs)
	else:
		repayment_table = sup_fn.generate_repayment_schedule(inputs)

	content = {
	'lang': lang,
	'caption': 'Repayment Schedule',
	'repayment_table': repayment_table,
	'show_declaration': True if prod_id != None else False,
	}
	if lang == 'zh':
		content['caption'] = '還款時間表'
	if usr.type == 'L':
		return render(request, 'peerloan/lender/loan_repay_schedule.html', content)
	if usr.type == 'B' or usr.type == 'ADMIN':
		return render(request, 'peerloan/borrower/loan_repay_schedule.html', content)

@require_login
@transaction.atomic
def uor_handler(request):
	action = request.GET.get('action')
	usr = sup_fn.get_user(request)
	adm_role = sup_fn.get_admin_role(usr.type)
	uor_id = request.GET.get('uor_id')
	uor = UserOperationRequest.objects.get(id=uor_id)
	
	if uor.type == 'Deposit Money':
		confirm = request.GET.get('confirm')
		bank_in_date = request.GET.get('bank_in_date')
		bank_in_time = request.GET.get('bank_in_time')
		details = json.loads(uor.details)
		
		# access control
		if not adm_role.has_perm('confirm deposit'):
			return HttpResponse('Permission denied.')
		
		if confirm == 'True':
			uor.status = 'CONFIRMED'
			acc = Account.objects.get(usr_id = uor.usr_id)
			acc.balance += float(details['transferred_amount'])
			acc.save()
			
			details['bank_in_date'] = bank_in_date
			details['bank_in_time'] = bank_in_time
			uor.details = json.dumps(details)
			
			# update utrx record
			trx = UserTransaction.objects.get(internal_ref=details['ref_num'])
			trx.type = 'Deposit Money - Fund Confirmed'
			trx.update_timestamp = timezone.localtime(timezone.now())
			trx.save()
			
			# update ledger
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Deposit Money',
				'reference' : details['ref_num'],
				'debit': 0,
				'credit': float(details['transferred_amount']),
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			# update aut
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Confirm lender deposit money: Amount $'+str(details['transferred_amount']),
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Admin: '+ usr.email,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_aut(inputs)
			
			# send email notification
			usr = User.objects.get(id=uor.usr_id)
			notification = json.loads(usr.notification)
			if notification['Deposit Confirmed (Email)'] == 'Yes':
				ldr_emailing = emailing.LenderEmail(uor=uor)
				ldr_emailing.deposit_amount_confirmed()
			if notification['Deposit Confirmed (SMS)'] == 'Yes':
				ldr_smsing = smsing.LenderSMS()
				ldr_smsing.confirmed_deposit(uor=uor)
				
		if confirm == 'False':
			uor.status = 'REJECTED'
			
			# update aut
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Reject lender deposit money: Amount $'+str(details['transferred_amount']),
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Admin: '+ usr.email,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_aut(inputs)
			
			# update utrx record
			trx = UserTransaction.objects.get(internal_ref=details['ref_num'])
			trx.type = 'Deposit Money - Fund Rejected'
			trx.update_timestamp = timezone.localtime(timezone.now())
			trx.save()
			
			# send SMS notification
			usr = User.objects.get(id=uor.usr_id)
			notification = json.loads(usr.notification)
			if notification['Deposit Confirmed (SMS)'] == 'Yes':
				ldr_smsing = smsing.LenderSMS()
				ldr_smsing.rejected_deposit(uor=uor)
				
	if uor.type == 'Withdraw Money':
		confirm = request.GET.get('confirm')
		bank_in_date = request.GET.get('bank_in_date')
		bank_in_time = request.GET.get('bank_in_time')
		chq_no = request.GET.get('chq_no')
		confirm_date = request.GET.get('confirm_date')
		
		# access control
		if not adm_role.has_perm('confirm withdrawal'):
			return HttpResponse('Permission denied.')
		
		if confirm == 'True':
			uor.status = 'CONFIRMED'
			details = json.loads(uor.details)
			acc = Account.objects.get(usr_id = uor.usr_id)
			acc.on_hold_amt -= float(details['withdraw_amt'])
			acc.save()
			
			details['bank_in_date'] = bank_in_date
			details['bank_in_time'] = bank_in_time
			details['chq_no'] = chq_no
			details['confirm_date'] = confirm_date
			uor.details = json.dumps(details)
			uor.save()
			
			# update utrx record
			trx = UserTransaction.objects.get(internal_ref=details['ref_num'])
			trx.type = 'Withdraw Money - Request Confirmed'
			trx.update_timestamp = timezone.localtime(timezone.now())
			trx.save()
			
			# update ledger
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Withdraw Money',
				'reference' : details['ref_num'],
				'debit': float(details['withdraw_amt']),
				'credit': 0,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			# update aut
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Confirm lender withdraw money: Amount $'+str(details['withdraw_amt']),
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Admin: '+ usr.email,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_aut(inputs)
			
			# send email notification
			usr = User.objects.get(id=uor.usr_id)
			notification = json.loads(usr.notification)
			if notification['Withdrawal Confirmed (Email)'] == 'Yes':
				ldr_emailing = emailing.LenderEmail(uor=uor)
				ldr_emailing.withdraw_amount_confirmed()
			if notification['Withdrawal Confirmed (SMS)'] == 'Yes':
				ldr_smsing = smsing.LenderSMS()
				ldr_smsing.withdrawn_confirmed(uor=uor)
				
		if confirm == 'False':
			uor.status = 'REJECTED'
			details = json.loads(uor.details)
			acc = Account.objects.get(usr_id = uor.usr_id)
			acc.on_hold_amt -= float(details['withdraw_amt'])
			acc.balance += float(details['withdraw_amt'])
			acc.save()
			
			# update aut
			inputs = {
				'usr_id': uor.usr_id,
				'description': 'Reject lender withdraw money: Amount $'+str(details['withdraw_amt']),
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Admin: '+ usr.email,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_aut(inputs)
			
			# update utrx record
			trx = UserTransaction.objects.get(internal_ref=details['ref_num'])
			trx.type = 'Withdraw Money - Request Rejected'
			trx.update_timestamp = timezone.localtime(timezone.now())
			trx.save()
			
			# send email notification
			usr = User.objects.get(id=uor.usr_id)
			notification = json.loads(usr.notification)
			if notification['Withdrawal Confirmed (SMS)'] == 'Yes':
				ldr_smsing = smsing.LenderSMS()
				ldr_smsing.withdrawn_rejected(uor=uor)
			
	if uor.type == 'Repayment':
		confirm = request.GET.get('confirm')
		if confirm == 'True':
			uor.status = 'CONFIRMED'
		if confirm == 'False':
			uor.status = 'REJECTED'
	
	if action == "checklist":
		details = json.loads(uor.details)
		try:
			details['Confirm File Uploaded']
		except KeyError:
			details['Confirm File Uploaded'] = {}
		
		description = ''
		for key, value in request.POST.iteritems():
			try:
				details['Confirm File Uploaded'][key]
			except KeyError:
				cur_confirm = 'F'
			else:
				cur_confirm = details['Confirm File Uploaded'][key]
				
			if value == 'true' and cur_confirm == 'F':
				# check perm
				if not adm_role.has_perm('tick checklist'):
					return HttpResponse('Permission denied.')
				
				# update confirm aut
				description += 'Confirmed %s.<br>'%(key)
			elif value == 'false' and cur_confirm == 'T':
				# check perm
				if not adm_role.has_perm('un-tick checklist'):
					return HttpResponse('Permission denied.')
				
				# update revoke aut
				description += 'Revoked %s.<br>'%(key)
			
			if value == 'true':
				details['Confirm File Uploaded'][key] = 'T'
				
			elif value == 'false':
				details['Confirm File Uploaded'][key] = 'F'
		uor.details = json.dumps(details)
		uor.save()
		
		# update aut
		if description != '':
			inputs = {
				'usr_id': uor.usr_id,
				'description': description,
				'ref_id': uor.id,
				'model': 'UserOperationRequest',
				'by': 'Admin: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
		return HttpResponse('document confirmation status are updated successfully.')
	
	uor.update_timestamp = timezone.localtime(timezone.now())
	uor.save()
	return HttpResponse('OK')

@require_login
@transaction.atomic
def bor_handler(request):
	usr = sup_fn.get_user(request)
	adm_role = sup_fn.get_admin_role(usr.type)
	
	bor_ref_num = request.GET.get('bor_ref_num')
	action = request.GET.get('action')
	if action == 'disburse':
		bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
		if bor.status == 'MEMORANDUM CONFIRMED':
			
			prod = Product.objects.get(id = bor.prod_id)
			bor.status = 'DISBURSED'
			details = json.loads(bor.detail_info)
			
			# access control
			if not adm_role.has_perm('confirm disbursement'):
				return HttpResponse('Permission denied.')
			
			# check today is business day or not
			public_holidays = sup_fn.import_public_holiday()
			
			# Test case
			#draw_down_date = sup_fn.find_earliest_business_day(date=timezone.localtime(timezone.now()), cut_off=15)
			#draw_down_date = datetime.strptime(details['Confirm Memorandum Date'], '%Y/%m/%d %H:%M:%S') - dt.timedelta(days=400)
			#draw_down_date = datetime.strptime('2016/05/31', '%Y/%m/%d')
			
			draw_down_date = datetime.strptime(details['Confirm Memorandum Date'], '%Y/%m/%d %H:%M:%S')
			draw_down_date = pytz.timezone('Asia/Hong_Kong').localize(draw_down_date)
			bor.draw_down_date = draw_down_date
			
			# deprecated? ======================================
			start_date = sup_fn.check_future_date_exists(draw_down_date, months=1)
			end_date = sup_fn.check_future_date_exists(draw_down_date, months=prod.repayment_period)
			
			start_date_day = start_date.day
			start_date_month = start_date.month
			start_date_year = start_date.year
			end_day = end_date.day
			end_month = end_date.month
			end_year = end_date.year
			# ===================================================
			bor.expected_end_date = pytz.timezone('Asia/Hong_Kong').localize(end_date)
			bor.save()
			
			# update ledger
			inputs = {
				'bor_id': bor.id,
				'description': 'Loan disbursement: Amount $%s' %(bor.amount),
				'reference': bor.ref_num,
				'debit': 0,
				'credit': bor.amount,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			# update admin aut
			inputs = {
				'usr_id': bor.usr_id,
				'description': 'State "%s" changed to "%s"'%('FUND MATCHING COMPLETED', bor.status),
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Admin: '+str(usr.email),
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
			
			# update bor aut
			inputs = {
				'usr_id': bor.usr_id,
				'description': 'Received loan disbursement $%s'%(bor.amount),
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Admin: '+str(usr.email),
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
			
			# update borrower trx record
			new_trx = UserTransaction(
			usr_id = bor.usr_id,
			type = 'Loan Disbursement (receive)',
			amount_in = bor.amount,
			amount_out = 0,
			internal_ref = bor.ref_num,
			cust_ref = '--',
			href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_trx.save()
			
			# update loan info
			loan_list = Loan.objects.filter(bor_id = bor.id)
			for loan in loan_list:
				loan.status = 'DISBURSED'
				loan.save()
				
				# release inv on hold amt
				inv = Investment.objects.get(id = loan.inv_id)
				inv.total_amount -= loan.initial_amount
				inv.on_hold_amount -= loan.initial_amount
				inv.save()
				
				# update ledger
				inputs = {
					'usr_id': inv.usr_id,
					'description': 'Loan Disbursement',
					'reference': bor.ref_num,
					'debit': loan.initial_amount,
					'credit': 0,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				
				# update aut
				inputs = {
					'usr_id': inv.usr_id,
					'description': 'Paid loan disbursement $%s (total: %s)'%(loan.initial_amount, bor.amount),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
				
				# update borrower trx record
				new_trx = UserTransaction(
				usr_id = inv.usr_id,
				type = 'Loan Disbursement (pay)',
				amount_in = 0,
				amount_out = loan.initial_amount,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# send email notification
				inv_usr = User.objects.get(id=inv.usr_id)
				notification = json.loads(inv_usr.notification)
				if notification['Fund Matching Completed (Email)'] == 'Every Loan':
					ldr_emailing = emailing.LenderEmail(loan=loan)
					ldr_emailing.fund_matching_notification_every_loan()
				if notification['All Fund Matched (Email)'] == 'Yes' and inv.usable_amount < 100:
					ldr_emailing = emailing.LenderEmail(loan=loan)
					ldr_emailing.fund_matching_notification_all_fund_matched()
				
				if notification['Fund Matching Completed (SMS)'] == 'Every Loan':
					ldr_smsing = smsing.LenderSMS()
					ldr_smsing.fund_matching_completed_every_loan(loan=loan)
				if notification['All Fund Matched (SMS)'] == 'Yes' and inv.usable_amount < 100:
					ldr_smsing = smsing.LenderSMS()
					ldr_smsing.fund_matching_completed_all_fund_matched(loan=loan)
					
			# create loan schedule
			# get repayment table
			inputs = {
				'date_type': 'exact datetime',
				'start_date': {
						'day': draw_down_date.day,
						'month': draw_down_date.month,
						'year': draw_down_date.year,
					},
				'start_balance': bor.amount,
				#'rate_per_month': prod.APR_lender * 0.01 / 12,
				'rate_per_month_bor': bor.getBorAPR(prod.APR_borrower) * 0.01 / 12,
				'rate_per_month_ldr': prod.APR_lender * 0.01 / 12,
				'instalment': bor.instalment_borrower,
				'repayment_plan': prod.repayment_plan,
				'repayment_period': prod.repayment_period,
			}
				
			repayment_table_l = sup_fn.generate_ldr_instalment_repayment_schedule(inputs)
			inputs = {
				'date_type': 'exact datetime',
				'start_date': {
						'day': draw_down_date.day,
						'month': draw_down_date.month,
						'year': draw_down_date.year,
					},
				'start_balance': bor.amount,
				'rate_per_month': bor.getBorAPR(prod.APR_borrower) * 0.01 / 12,
				'instalment': bor.instalment_borrower,
				'repayment_plan': prod.repayment_plan,
				'repayment_period': prod.repayment_period,
			}
				
			repayment_table_b = sup_fn.generate_repayment_schedule(inputs)
			
			period = prod.repayment_period
				
			for i in range(period):
				new_los = LoanSchedule(
				bor_id = bor.id,
				tenor = (i+1),
				instalment = float(repayment_table_b[i]['Instalment'].replace(',','')),
				principal = float(repayment_table_b[i]['Returning Principal'].replace(',','')),
				interest = float(repayment_table_b[i]['Returning Interest'].replace(',','')),
				instalment_l = float(repayment_table_l[i]['Instalment'].replace(',','')),
				principal_l = float(repayment_table_l[i]['Returning Principal'].replace(',','')),
				interest_l = float(repayment_table_l[i]['Returning Interest'].replace(',','')),
				due_date = repayment_table_b[i]['Date'],
				repayment_method = 'Auto Pay',
				status = 'OPEN',
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				
				new_los.save()
			
			# send email notification
			bor_emailing = emailing.BorrowerEmail(bor=bor)
			bor_emailing.autopay_authorization_required()
			
			# send SMS notification
			bor_smsing = smsing.BorrowerSMS()
			bor_smsing.disbursed_final_confirmation_SMS(bor=bor)
			
			return HttpResponse('Application status is updated successfully.')
		else:
			return HttpResponse('Failed to update application status.')
	if action == 'return':
		bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
		#if 'PAYBACK' in bor.status and 'OVERDUE' not in bor.status and 'COMPLETED' not in bor.status and bor.repaid_month >= 1:
		if 'PAYBACK' in bor.status and 'OVERDUE' not in bor.status and bor.repaid_month >= 1:
			
			prev_status = bor.status
			bor.status = 'PAYBACK OVERDUE ' + str(bor.repaid_month)
			prod = Product.objects.get(id=bor.prod_id)
			
			# if is promotion and month < 4
			if prod.repayment_plan == 'Promotion Balloon Payment' and bor.repaid_month < 4:
				return HttpResponse('Cannot return promotion product in the first 3 months.')
			
			# if early settlement, cannot return
			if bor.status == 'PAYBACK COMPLETED' and bor.repaid_month != prod.repayment_period:
				return HttpResponse('Cannot return a early settled loan.')
			
			loan_list = Loan.objects.filter(bor_id = bor.id)
			
			# update ledger
			# reject autopay(not confirm) record
			led_list = Ledger.objects.filter(bor_id=bor.id, status='Pending Confirm')
			for led in led_list:
				if str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month) in led.description:
					led.description = led.description.replace('(Pending confirm)', '')
					led.status = 'Rejected'
					led.update_timestamp = timezone.localtime(timezone.now())
					led.save()
			# generate return record
			inputs = {
				'bor_id': bor.id,
				'description': 'Reject the %s%s autopay repayment: Amount $%.2f' %(bor.repaid_month,sup_fn.date_postfix(bor.repaid_month),bor.instalment_borrower),
				'reference': bor.ref_num,
				'debit': 0,
				'credit': round(bor.instalment_borrower,2),
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			# update aut
			inputs = {
				'usr_id': bor.usr_id,
				'description': 'Repayment returned - %s instalment $%.2f'%(str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month),bor.instalment_borrower),
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Admin: '+str(usr.email),
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
			
			inputs = { # update status change
				'usr_id': bor.usr_id,
				'description': 'State "%s" changed to "%s"'%(prev_status, bor.status),
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Admin: '+str(usr.email),
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
			
			# update loan status
			
			for loan in loan_list:
				if prod.repayment_plan == 'Instalment':
					remain_balance_b = loan.initial_amount
					remain_balance_l = loan.initial_amount
					remain_interest_b = loan.instalment_borrower * prod.repayment_period - loan.initial_amount
					remain_interest_l = remain_interest_b * (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
					rate_per_month_b = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
					#rate_per_month_l = prod.APR_lender * 0.01 / 12
					
					for i in range(bor.repaid_month - 1):
						return_interest_b = remain_balance_b * rate_per_month_b
						return_principal_b = loan.instalment_borrower - return_interest_b
						remain_balance_b -= return_principal_b
						remain_interest_b -= return_interest_b
						
						#return_interest_l = remain_balance_l * rate_per_month_l
						#return_principal_l = loan.instalment_lender - return_interest_l
						return_interest_l = return_interest_b * (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
						return_principal_l = return_principal_b
						remain_balance_l -= return_principal_l
						remain_interest_l -= return_interest_l
						
				elif prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment':
					remain_balance_b = loan.initial_amount
					remain_balance_l = loan.initial_amount
					remain_interest_b = loan.instalment_borrower * prod.repayment_period
					remain_interest_l = loan.instalment_lender * prod.repayment_period
					
					rate_per_month_b = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
					rate_per_month_l = prod.APR_lender * 0.01 / 12
					
					for i in range(bor.repaid_month - 1):
						return_interest_b = remain_balance_b * rate_per_month_b
						#return_principal_b = loan.instalment_borrower - return_interest_b
						#remain_balance_b -= return_principal_b
						remain_interest_b -= return_interest_b
						
						return_interest_l = remain_balance_l * rate_per_month_l
						#return_principal_l = loan.instalment_lender - return_interest_l
						#remain_balance_l -= return_principal_l
						remain_interest_l -= return_interest_l
					
				loan.remain_principal = remain_balance_b
				loan.remain_principal_lender = remain_balance_l
				loan.remain_interest_borrower = remain_interest_b
				loan.remain_interest_lender = remain_interest_l
				loan.status = 'PAYBACK OVERDUE ' + str(bor.repaid_month)
				loan.save()
				
				# update ledger
				inv = Investment.objects.get(id=loan.inv_id)
				inv_usr = User.objects.get(id=inv.usr_id)
				lender_no = sup_fn.try_KeyError(json.loads(inv_usr.detail_info), 'Lender No')
				
				#instalment = round(loan.instalment_lender, 2)
				return_interest_b = loan.remain_principal * rate_per_month_b
				return_principal_b = loan.instalment_borrower - return_interest_b
				
				
				ratio = (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
				return_interest_l = return_interest_b * ratio
				
				return_principal_l = return_principal_b
				
				if prod.repayment_plan == 'Instalment':
					instalment = return_interest_l + return_principal_l
				elif (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month != prod.repayment_period:
					instalment = return_interest_l
				elif (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month == prod.repayment_period:
					instalment = return_interest_l + loan.remain_principal
				
				instalment = round(instalment, 2)
				
				# reject autopay(not confirm) record
				led_list = Ledger.objects.filter(usr_id=inv.usr_id, status='Pending Confirm')
				for led in led_list:
					if str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month) in led.description:
						led.description = led.description.replace('(Pending confirm)', '')
						led.status = 'Rejected'
						led.update_timestamp = timezone.localtime(timezone.now())
						led.save()
				inputs = {
					'usr_id': inv.usr_id,
					'description': 'Return the %s%s repayment from Lender <a href="/pl_admin/account/ledger/?usr_id=%s" target="_blank">%s</a>: Amount $%s' %(str(bor.repaid_month),sup_fn.date_postfix(bor.repaid_month), inv_usr.id, lender_no, str(instalment)),
					'reference': bor.ref_num,
					'debit': instalment,
					'credit': 0,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				
				# update aut
				inputs = {
					'usr_id': inv.usr_id,
					'description': 'The %s%s repayment returned: Amount $%.2f'%(bor.repaid_month,sup_fn.date_postfix(bor.repaid_month),instalment),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
			
			# update los status
			los = LoanSchedule.objects.get(bor_id = bor.id, tenor = bor.repaid_month)
			los.status = 'OVERDUE'
			
			now = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
			now = pytz.timezone('Asia/Hong_Kong').localize(now)
			overdue_days = (timezone.localtime(timezone.now()) - pytz.timezone('Asia/Hong_Kong').localize(datetime.strptime(los.due_date, '%Y/%m/%d'))).days
			rate_per_day = bor.getBorAPR(prod.APR_borrower) * 0.01 / 360
			#remain_principal = sum([loan.remain_principal for loan in loan_list])
			#overdue_interest_remained = remain_principal * rate_per_day * overdue_days
			#overdue_interest_accumulated = remain_principal * rate_per_day * overdue_days
			overdue_interest_remained = los.instalment * rate_per_day * overdue_days
			#overdue_interest_accumulated = los.instalment * rate_per_day * overdue_days
			los.overdue_days = overdue_days
			los.overdue_interest_remained = overdue_interest_remained
			
			los.overdue_interest_paid_days = 0
			los.overdue_interest_unpay_paid = 0
			los.paid_principal = 0
			los.paid_interest = 0
			los.paid_overdue_interest = 0
			los.paid_principal_l = 0
			los.paid_interest_l = 0
			los.received_amount = 0
			
			los.late_charge = 200
			los.paid_late_charge = 0
			
			los.overdue_interest_accumulated = los.overdue_interest_remained + los.overdue_interest_unpay_paid + los.paid_overdue_interest
			
			los.save()
			
			# update pl ledger
			amount = round(los.instalment - los.instalment_l, 2)
			# reject autopay(not confirm) record
			led_list = Ledger.objects.filter(usr_id=0, status='Pending Confirm')
			for led in led_list:
				if str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month) in led.description:
					led.description = led.description.replace('(Pending confirm)', '')
					led.status = 'Rejected'
					led.update_timestamp = timezone.localtime(timezone.now())
					led.save()
			inputs = {
				'usr_id': 0,
				'description': 'Return income from %s%s repayment from P L Account: Amount $%s' %(str(bor.repaid_month),sup_fn.date_postfix(bor.repaid_month),str(amount)),
				'reference': bor.ref_num,
				'debit': amount,
				'credit': 0,
				'datetime': timezone.localtime(timezone.now())
			}
			sup_fn.update_ledger(inputs)
			
			bor.repaid_month -= 1
			bor.save()
			return HttpResponse('Application status is updated successfully.')
		return HttpResponse('Failed to update application status.')
	if action == "checklist":
		
		bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
		description = ''
		for key, value in request.POST.iteritems():
			try:
				bod = BorrowRequestDocument.objects.get(bor_id=bor.id, type=key)
			except ObjectDoesNotExist:
				continue
			else:
				if bod != None:
					if value == 'true' and bod.confirm == 'F':
						# check perm
						if not adm_role.has_perm('tick checklist'):
							return HttpResponse('Permission denied.')
						
						# update confirm aut
						description += 'Confirmed %s.<br>'%(key)
					elif value == 'false' and bod.confirm == 'T':
						# check perm
						if not adm_role.has_perm('un-tick checklist'):
							return HttpResponse('Permission denied.')
						
						# update revoke aut
						description += 'Revoked %s.<br>'%(key)
					
					if value == 'true':
						bod.confirm = 'T'
						
					elif value == 'false':
						bod.confirm = 'F'
						
					bod.save()
		# update aut
		if description != '':
			inputs = {
				'usr_id': bor.usr_id,
				'description': description,
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'Admin: ' + usr.email,
				'datetime': timezone.localtime(timezone.now()),
			}
			sup_fn.update_aut(inputs)
		return HttpResponse('bod status are updated successfully.')
	return HttpResponse('Failed to update application status.')

@require_login
def ptn_handler(request):
	uor_id = request.GET.get('uor_id')
	bor_id = request.GET.get('bor_id')
	if uor_id != None:
		ptn = PendingTaskNotification.objects.get(ref_id=uor_id, model='UserOperationRequest', status='UNREAD')
		ptn.status = 'READ'
		ptn.save()
		
		return HttpResponse('OK')
	if bor_id != None:
		ptn = PendingTaskNotification.objects.get(ref_id=bor_id, model='BorrowRequest', status='UNREAD')
		ptn.status = 'READ'
		ptn.save()
		
		return HttpResponse('OK')
@require_login
def late_charge_handler(request):
	bor_ref_num = request.GET.get('bor_ref_num')
	tenor = request.GET.get('tenor')
	amount = request.GET.get('amount')
	
	bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
	los = LoanSchedule.objects.get(bor_id=bor.id, tenor=tenor)
	los.late_charge = amount
	los.save()
	return HttpResponse('OK')

@require_login
def ledger_table_handler(request):
	usr_id = request.GET.get('usr_id')
	ref_num = request.GET.get('ref_num')
	
	led_list = Ledger.objects.filter(usr_id=usr_id, reference=ref_num)
	
	ledger_table = []
	for led in led_list:
		ledger = {
			'Date': led.create_timestamp.strftime('%Y/%m/%d %H:%M'),
			'Description': led.description,
			'Reference': led.reference,
			'Debit': led.debit,
			'Credit': led.credit,
			'Balance': led.balance,
		}
		ledger_table.append(ledger)
	content = {
	'caption': 'Ledger Table',
	'ledger_table': ledger_table,
	
	}
	return render(request, 'peerloan/admin/borrower/ledger_table.html', content)

@require_login
def upload_file(request):
	if request.method == 'POST':
		model = request.POST.get('Model')
		model_id = request.POST.get('Model Id')
		
		if model == 'UserOperationRequest':
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
			uor = UserOperationRequest.objects.get(id = model_id)
			details = json.loads(uor.details)
			details['file'] = new_fname
			uor.details = json.dumps(details)
			uor.save()
			trx = UserTransaction.objects.get(id = details['trx_id'])
			trx.href = '/file/' + new_fname
			trx.save()
			
			http_content = """
Uploaded successfully.
<a href="/file/%s">View</a>
""" % (new_fname)
			return HttpResponse(http_content)
	uor_id = request.GET.get('uor_id')
	
	if uor_id != None:
		src = {
		'model': 'UserOperationRequest',
		'id': uor_id,
		}
	content = {
	'src': src
	}
	return render(request, 'peerloan/upload_file_form.html', content)

@require_login
def generate_OTP(request):
	if request.method == 'POST':
		usr = sup_fn.get_user(request)
		mobile = request.POST.get('mobile')
		action = request.POST.get('action')
		send_to = request.POST.get('send_to')
		sequence = str(random.randint(1,999999)).zfill(6)
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.POST.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if send_to == 'email':
			if action == 'Change Account Information - Change Mobile':
				to_usr = User.objects.get(id=request.POST.get('usr_id'))
				to_email = to_usr.email
				
				usr_emailing = emailing.GeneralEmail(email_addr=to_email)
				usr_emailing.OTP_email(OTP_code=sequence, subject='Zwap: OTP Code for Changing Mobile', type='change account mobile')
			elif action == 'Confirm agreement - Apply to be investor':
				uor = UserOperationRequest.objects.get(id=request.POST.get('uor_id'))
				to_email = User.objects.get(id=uor.usr_id).email
				
				usr_emailing = emailing.GeneralEmail(email_addr=to_email)
				usr_emailing.OTP_email(OTP_code=sequence, subject='Zwap: OTP Code for Lender Agreement', type='sign lender agreement')
			elif action == 'Confirm agreement - Loan application':
				bor = BorrowRequest.objects.get(id=request.POST.get('bor_id'))
				to_email = User.objects.get(id=bor.usr_id).email
				
				usr_emailing = emailing.GeneralEmail(email_addr=to_email)
				usr_emailing.OTP_email(OTP_code=sequence, subject='Zwap: OTP Code for Loan Agreement', type='sign loan agreement')
			elif action == 'Withdraw Money':
				to_usr = User.objects.get(id=request.POST.get('usr_id'))
				to_email = to_usr.email
				
				usr_emailing = emailing.GeneralEmail(email_addr=to_email)
				usr_emailing.OTP_email(OTP_code=sequence, subject='Zwap: OTP Code for Withdraw Money', type='withdraw money')
				
				
			mobile = 0
		if mobile != None and mobile != 0:
			usr_smsing = smsing.GeneralSMS()
			usr_smsing.send_OTP(OTP=sequence, mobile=str(mobile))
			
		new_OTP = OTPMessage(
		usr_id = usr.id,
		sequence = sequence,
		mobile_no = mobile,
		action = action,
		status = 'ACTIVE',
		generated_timestamp = timezone.localtime(timezone.now()),
		expiring_timestamp = timezone.localtime(timezone.now()) + dt.timedelta(seconds=300),
		)
		new_OTP.save()
		return HttpResponse('OK')
	else:
		return HttpResponse('Wrong request method.')

@require_login
@transaction.atomic
def change_acc_info_handler(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	action = request.GET.get('action')
	
	if action == 'change_password':
		if usr.password == hashlib.md5(request.POST.get('Current Password')).hexdigest():
			#return HttpResponse(usr.password==request.POST.get('Current Password'))
			if request.POST.get('New Password') == request.POST.get('Retype New Password'):
				usr_list = User.objects.filter(email=usr.email)
				for usr in usr_list:
					usr.password = hashlib.md5(request.POST.get('New Password')).hexdigest()
					usr.save()
					details = json.loads(usr.detail_info)
					
					# update aut
					inputs = {
						'usr_id': usr.id,
						'description': 'Change password.',
						'ref_id': 0,
						'model': '',
						'by': 'Borrower: '+usr.email if usr.type == 'B' else 'Lender: '+details['Lender No'],
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_aut(inputs)
				
				if len(usr_list) == 0: # admin account
					usr.password = hashlib.md5(request.POST.get('New Password')).hexdigest()
					usr.save()
					
					# update aut
					"""
					inputs = {
						'usr_id': usr.id,
						'description': 'Change password.',
						'ref_id': 0,
						'model': '',
						'by': usr.email,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_aut(inputs)
					"""
					
				if lang == 'en':
					msg = 'Your password is updated successfully.'
				elif lang == 'zh':
					msg = '更改密碼成功。'
				return HttpResponse(msg)
			else:
				if lang == 'en':
					msg = 'Your two new passwords are not matched.'
				elif lang == 'zh':
					msg = '你的新密碼兩次輸入不一致'
				return HttpResponse(msg)
		else:
			if lang == 'en':
				msg = 'Your input on current password is incorrect.'
			elif lang == 'zh':
				msg = '你的當前密碼輸入有誤。'
			return HttpResponse(msg)
	elif action == 'change_mobile':
		# do sth to check the email OTP code
		try:
			OTP_list = OTPMessage.objects.filter(usr_id=usr.id, action='Change Account Information - Change Mobile', status='ACTIVE')
			OTP = OTP_list.latest('generated_timestamp')
		except ObjectDoesNotExist:
			if lang == 'en':
				msg = 'Please generate OTP code first.'
			elif lang == 'zh':
				msg = '請先接收OTP。'
			return HttpResponse(msg)
		
		# check expiring
		if OTP.expiring_timestamp < timezone.localtime(timezone.now()):
			for item in OTP_list:
				item.status = 'EXPIRED'
				item.save()
			if lang == 'en':
				msg = 'Your OTP is expired, please try again.'
			elif lang == 'zh':
				msg = '你的OTP已經逾期，請重新操作。'
			return HttpResponse(msg)
		
		if OTP.sequence == request.POST.get('Email OTP Code'):
			# expire all the OTP records
			for item in OTP_list:
				item.status = 'EXPIRED'
				item.save()
			
			# record old mobile
			# create uoh
			if usr.type == 'B':
				details = json.loads(usr.detail_info)
				old_mobile = sup_fn.try_KeyError(details, 'Mobile')
			elif usr.type == 'L':
				details = json.loads(usr.detail_info)
				old_mobile = sup_fn.try_KeyError(details['Individual'], 'Mobile')
			new_uoh = UserOperationHistory(
			usr_id=usr.id,
			type='Change Account Information - Change Mobile',
			details=json.dumps({'old_mobile':old_mobile,'new_mobile':request.POST.get('New Mobile')}),
			create_timestamp=timezone.localtime(timezone.now()),
			update_timestamp=timezone.localtime(timezone.now())
			)
			new_uoh.save()
			
			# update aut
			inputs = {
				'usr_id': usr.id,
				'description': 'Change mobile from "%s" to "%s"'%(old_mobile, request.POST.get('New Mobile')),
				'ref_id': new_uoh.id,
				'model': 'UserOperationHistory',
				'by': 'Borrower: '+usr.email if usr.type == 'B' else 'Lender: '+details['Lender No'],
				'datetime': timezone.localtime(timezone.now()),
				
			}
			sup_fn.update_aut(inputs)
			
			# update new mobile
			usr_list = User.objects.filter(email=usr.email)
			for usr in usr_list:
				details = json.loads(usr.detail_info)
				individual_info = sup_fn.try_KeyError(details,'Individual')
				if individual_info == '--':
					# borrower acc
					details['Mobile'] = request.POST.get('New Mobile')
					usr.detail_info = json.dumps(details)
					usr.save()
				else:
					# lender acc
					individual_info['Mobile'] = request.POST.get('New Mobile')
					details['Individual'] = individual_info
					usr.detail_info = json.dumps(details)
					usr.save()
			if lang == 'en':
				msg = 'Your mobile is updated successfully.'
			elif lang == 'zh':
				msg = '你的手提電話已經更新成功。'
			return HttpResponse(msg)
		else:
			for item in OTP_list:
				item.status = 'EXPIRED'
				item.save()
			if lang == 'en':
				msg = 'Your input on OTP code is incorrect, please try again.'
			elif lang == 'zh':
				msg = '你輸入的OTP有誤，請重新操作。'
			return HttpResponse(msg)
	elif action == 'change_address':
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
		# create uoh
		if usr.type == 'B':
			details = json.loads(usr.detail_info)
			old_address = sup_fn.try_KeyError(details, 'Residential Address')
		elif usr.type == 'L':
			details = json.loads(usr.detail_info)
			old_address = sup_fn.try_KeyError(details['Individual'], 'Residential Address')
			
		new_uoh = UserOperationHistory(
		usr_id=usr.id,
		type='Change Account Information - Change Address',
		details=json.dumps({'old_address':old_address,'new_address':request.POST.get('New Address'),'fname':new_fname}),
		create_timestamp=timezone.localtime(timezone.now()),
		update_timestamp=timezone.localtime(timezone.now())
		)
		new_uoh.save()
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Change address from "%s" to "%s"'%(old_address, request.POST.get('New Address')),
			'ref_id': new_uoh.id,
			'model': 'UserOperationHistory',
			'by': 'Borrower: '+usr.email if usr.type == 'B' else 'Lender: '+details['Lender No'],
			'datetime': timezone.localtime(timezone.now()),
			
		}
		sup_fn.update_aut(inputs)
		
		# update new address
		usr_list = User.objects.filter(email=usr.email)
		for usr in usr_list:
			details = json.loads(usr.detail_info)
			individual_info = sup_fn.try_KeyError(details,'Individual')
			if individual_info == '--':
				# borrower acc
				details['Residential Address'] = request.POST.get('New Address')
				usr.detail_info = json.dumps(details)
				usr.save()
			else:
				# lender acc
				individual_info['Residential Address'] = request.POST.get('New Address')
				details['Individual'] = individual_info
				usr.detail_info = json.dumps(details)
				usr.save()
		if lang == 'en':
			msg = 'Your address is updated successfully.'
		elif lang == 'zh':
			msg = '你的地址已經更新成功。'
		return HttpResponse(msg)
	elif action == 'change_bank_account':
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
		# create uoh
		details = json.loads(usr.detail_info)
		old_bank_account = sup_fn.try_KeyError(details['Individual'], 'Bank Account')
			
		new_uoh = UserOperationHistory(
		usr_id=usr.id,
		type='Change Account Information - Change Bank Account',
		details=json.dumps({'old_bank_account':old_bank_account,'new_bank_account':request.POST.get('New Bank Account'),'fname':new_fname}),
		create_timestamp=timezone.localtime(timezone.now()),
		update_timestamp=timezone.localtime(timezone.now())
		)
		new_uoh.save()
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Change bank account from "%s" to "%s"'%(old_bank_account, request.POST.get('New Bank Account')),
			'ref_id': new_uoh.id,
			'model': 'UserOperationHistory',
			'by': 'Borrower: '+usr.email if usr.type == 'B' else 'Lender: '+details['Lender No'],
			'datetime': timezone.localtime(timezone.now()),
			
		}
		sup_fn.update_aut(inputs)
		
		# update new address
		details = json.loads(usr.detail_info)
		individual_info = sup_fn.try_KeyError(details,'Individual')
		# lender acc
		individual_info['Bank Account'] = str(request.POST.get('New Bank Account'))
		details['Individual'] = individual_info
		usr.detail_info = json.dumps(details)
		usr.save()
		if lang == 'en':
			msg = 'Your bank account is updated successfully.'
		elif lang == 'zh':
			msg = '你的銀行賬號已經更新成功。'
		return HttpResponse(msg)
	elif action == 'change_office_address':
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
		# create uoh
		details = json.loads(usr.detail_info)
		old_office_address = sup_fn.try_KeyError(details['Corporate'], 'Office Address')
			
		new_uoh = UserOperationHistory(
		usr_id=usr.id,
		type='Change Account Information - Change Bank Account',
		details=json.dumps({'old_office_address':old_office_address,'new_office_address':request.POST.get('New Office Address'),'fname':new_fname}),
		create_timestamp=timezone.localtime(timezone.now()),
		update_timestamp=timezone.localtime(timezone.now())
		)
		new_uoh.save()
		# update aut
		inputs = {
			'usr_id': usr.id,
			'description': 'Change office address from "%s" to "%s"'%(old_office_address, request.POST.get('New Office Address')),
			'ref_id': new_uoh.id,
			'model': 'UserOperationHistory',
			'by': 'Borrower: '+usr.email if usr.type == 'B' else 'Lender: '+details['Lender No'],
			'datetime': timezone.localtime(timezone.now()),
			
		}
		sup_fn.update_aut(inputs)
		
		# update new address
		details = json.loads(usr.detail_info)
		corporate_info = sup_fn.try_KeyError(details,'Corporate')
		# lender acc
		corporate_info['Office Address'] = str(request.POST.get('New Office Address'))
		details['Corporate'] = corporate_info
		usr.detail_info = json.dumps(details)
		usr.save()
		if lang == 'en':
			msg = 'Your office address is updated successfully.'
		elif lang == 'zh':
			msg = '你的辦公地址已經更新成功。'
		return HttpResponse(msg)

@require_login
def calculate_repayment_amount(request):
	bor_ref_num = request.GET.get('bor_ref_num')
	repayment_type = request.GET.get('repayment_type')
	repayment_time = request.GET.get('repayment_time')
	
	bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
	amount = 'N/A'
	if repayment_type == 'Instalment':
		inputs = {
			'bor_id': bor.id,
			'type': 'instalment',
			'date': repayment_time,
		}
		outputs = sup_fn.calculate_repay_amount(inputs)
		amount = max(0, outputs['instalment_amount']+outputs['overdue_interest']+outputs['late_charge']-outputs['overpay_amount'])
		amount = '%.2f'%(amount)
	elif repayment_type == 'Early Settlement':
		inputs = {
			'bor_id': bor.id,
			'type': 'early_settlement',
			'date': repayment_time,
		}
		outputs = sup_fn.calculate_repay_amount(inputs)
		amount = max(0, outputs['early_settlement_amount']+outputs['late_charge']-outputs['overpay_amount'])
		amount = '%.2f'%(amount)
	return HttpResponse(amount)

@require_login
def file(request):
	http_referer = request.META.get('PATH_INFO')
	fname = http_referer.split('/')[2]
	postfix = fname.split('.')[-1]
	fpath = '/home/ubuntu/project_peerloan/supporting_documents/' + fname
	try:
		with open(fpath, "rb") as f:
			return HttpResponse(f.read(), content_type='image/jpeg')
	except:
		return HttpResponse('File not exists.')

#@require_login
def document(request):
	http_referer = request.META.get('PATH_INFO')
	fname = request.GET.get('fname')
	postfix = fname.split('.')[-1]
	fpath = '/home/ubuntu/project_peerloan/document_peerloan/' + fname
	if postfix == 'pdf':
		with open(fpath, 'r') as pdf:
			response = HttpResponse(pdf.read(), content_type='application/pdf')
			response['Content-Disposition'] = 'inline;filename='+fname
			return response
	elif postfix == 'jpg':
		with open(fpath, "rb") as f:
			return HttpResponse(f.read(), content_type='image/jpeg')

@require_login
def refresh_captcha(request):
    to_json_response = dict()
    to_json_response['status'] = 1
    to_json_response['new_cptch_key'] = CaptchaStore.generate_key()
    to_json_response['new_cptch_image'] = captcha_image_url(to_json_response['new_cptch_key'])
    return HttpResponse(json.dumps(to_json_response), content_type='application/json')

@require_login
def generate_pdf_file(request):
	uor_id = request.GET.get('uor_id')
	bor_id = request.GET.get('bor_id')
	doc_type = request.GET.get('doc_type')
	if uor_id != None:
		pdf_path = sup_fn.generate_docx(id=uor_id,model='UserOperationRequest',doc_type=doc_type)
	if bor_id != None:
		if doc_type == 'Repayment Schedule':
			pdf_path = sup_fn.generate_xlsx(id=bor_id,model='BorrowRequest',doc_type=doc_type)
		else:
			pdf_path = sup_fn.generate_docx(id=bor_id,model='BorrowRequest',doc_type=doc_type)
	with open(pdf_path, 'r') as pdf:
		response = HttpResponse(pdf.read(), content_type='application/pdf')
		response['Content-Disposition'] = 'inline;filename='+doc_type+'.pdf'
		return response
	