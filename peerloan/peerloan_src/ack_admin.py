# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from peerloan.forms import CaptchaForm

from peerloan.models import Account
from peerloan.models import AdminMemo
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import Product
from peerloan.models import User
from peerloan.models import UserTransaction
from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest
from peerloan.models import UserOperationHistory

from peerloan.decorators import require_login

import peerloan.emailing as emailing
import peerloan.classes as classes
import peerloan.smsing as smsing
import peerloan.peerloan_src.supporting_function as sup_fn

from collections import OrderedDict
from django.utils import timezone
from datetime import datetime
import pytz
import json
import urlparse
from urllib import urlencode

@require_login
@transaction.atomic
def ack_handler(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	adm_role = sup_fn.get_admin_role(usr.type)
	
	# admin handles application:
	if request.META.get('HTTP_REFERER').split('/')[3] == 'pl_admin' and request.META.get('HTTP_REFERER').split('/')[4] == 'application':
		if request.session['handling_side'] == 'B':
			url = request.META.get('HTTP_REFERER')
			parsed = urlparse.urlparse(url)
			bor_ref_num = urlparse.parse_qs(parsed.query)['bor_ref_num'][0]
			
			bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
			
			# special case: re-sign agreement
			if request.GET.get('action') == 're-sign_agreement':
				if bor.status == 'AGREEMENT CONFIRMED' or bor.status == 'PENDING DOC/IV':
					bor.status = 'DOC UPLOADED'
					bor.save()
					return redirect(request.META.get('HTTP_REFERER'))
			
			allow_edit = False
			allow_disburse_edit = False
			allow_state_list = []
			
			if bor.status == 'AUTO APPROVED':
				allow_edit = False
				allow_state_list = ['CANCELLED', 'REJECTED']
			elif bor.status == 'DOC UPLOADED':
				allow_edit = True
				allow_disburse_edit = True
				allow_state_list = ['CANCELLED', 'REJECTED']
			elif bor.status == 'AGREEMENT CONFIRMED':
				allow_edit = True
				allow_disburse_edit = True
				allow_state_list = ['PENDING DOC/IV', 'VALIDATED', 'REJECTED']
			elif bor.status == 'PENDING DOC/IV':
				allow_edit = True
				allow_disburse_edit = True
				allow_state_list = ['CANCELLED', 'REJECTED', 'VALIDATED']
			elif bor.status in ['VALIDATED', 'FUND MATCHING', 'FUND MATCHING COMPLETED', 'MEMORANDUM CONFIRMED']:
				allow_disburse_edit = True
			
			src = request.GET.get('src')
			if src == 'preface':
				if allow_edit:
					details = json.loads(bor.detail_info)
					description = ''
					if details['Loan Purpose'] != request.POST.get('Loan Purpose'):
						description += '%s "%s" changed to "%s".<br>'%('Loan Purpose', details['Loan Purpose'], request.POST.get('Loan Purpose'))
					details['Loan Purpose'] = request.POST.get('Loan Purpose')
					bor.detail_info = json.dumps(details)
					
					prod = Product.objects.get(id=bor.prod_id)
					amount = float(request.POST.get('Approve Loan Amount'))
					if bor.amount != amount:
						description += '%s "%s" changed to "%s".<br>'%('Approve Loan Amount', str(bor.amount), str(amount))
					bor.amount = amount
					if prod.repayment_plan == 'Instalment':
						rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
						bor.instalment_borrower = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
						rate_per_month = prod.APR_lender * 0.01 / 12
						bor.instalment_lender = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
					elif prod.repayment_plan == 'Balloon Payment':
						rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
						bor.instalment_borrower = amount * rate_per_month
						rate_per_month = prod.APR_lender * 0.01 / 12
						bor.instalment_lender = amount * rate_per_month
				
					# update bor status
					new_status = request.POST.get('Application State')
					if new_status in allow_state_list:
						# access control
						if not adm_role.has_perm('change loan state'):
							return HttpResponse('Permission denied.')
						else:
							if new_status not in adm_role.get_allowed_loan_state_list():
								return HttpResponse('Permission denied.')
							
						if new_status == 'VALIDATED':
							# check admin confirmed document checklist
							bod_list = BorrowRequestDocument.objects.filter(bor_id=bor.id)
							bod_checklist = ['HKID', 'Bank Account Proof', 'Student Card', 'GPA', 'Address Proof']
							for bod in bod_list:
								if bod.type not in bod_checklist:
									continue
								if bod.confirm == 'F':
									params = {'require_tick_all_checklist':'True'}
									
									url_parts = list(urlparse.urlparse(request.META.get('HTTP_REFERER')))
									query = dict(urlparse.parse_qsl(url_parts[4]))
									query.update(params)
									
									url_parts[4] = urlencode(query)
									
									return redirect(urlparse.urlunparse(url_parts))
							
							# check information consistent to what user agreed
							details = json.loads(bor.detail_info)
							agreement_info = details['Agreement Info']
							for k , v in agreement_info.iteritems():
								if k == 'Amount':
									if v != bor.amount:
										return redirect(request.META.get('HTTP_REFERER'))
								else:
									if v != details[k]:
										return redirect(request.META.get('HTTP_REFERER'))
						
						if bor.status != new_status:
							description += '%s "%s" changed to "%s".<br>'%('Application State', bor.status, new_status)
						bor.status = new_status
						bor.update_timestamp = timezone.localtime(timezone.now())
						bor.save()
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
					# send email notification
					if bor.status == 'REJECTED':
						bor_emailing = emailing.BorrowerEmail(bor=bor)
						bor_emailing.reject_loan_application()
					elif bor.status == 'CANCELLED':
						bor_emailing = emailing.BorrowerEmail(bor=bor)
						bor_emailing.cancel_loan_application()
				#return redirect(request.META.get('HTTP_REFERER'))
			if src == 'summary':
				if allow_edit:
					# update bor detail
					details = json.loads(bor.detail_info)
					description = ''
					for k, v in details.iteritems():
						if request.POST.get(k) != '' and request.POST.get(k) != None:
							if request.POST.get(k) != details[k]:
								description += '%s "%s" changed to "%s".<br>'%(k, details[k], request.POST.get(k))
							details[k] = request.POST.get(k)
					#details['Confirmed Identity'] = request.POST.get('Confirmed Identity')
					#details['Disbursement Method'] = request.POST.get('Disbursement Method')
					#details['Chq No'] = request.POST.get('Chq No')
					bor.detail_info = json.dumps(details)
					bor.verify_identity = request.POST.get('Identity Verification')
					bor.save()
					
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
				
				if allow_disburse_edit:
					# update bor detail
					details = json.loads(bor.detail_info)
					description = ''
					key_list = ['Confirmed Identity', 'Disbursement Method', 'Chq No']
					for k in key_list:
						if request.POST.get(k) != '' and request.POST.get(k) != None:
							try:
								details[k]
							except KeyError:
								details[k] = request.POST.get(k)
								description += '%s set to "%s".<br>'%(k, details[k])
							else:
								if request.POST.get(k) != details[k]:
									description += '%s "%s" changed to "%s".<br>'%(k, details[k], request.POST.get(k))
								details[k] = request.POST.get(k)
					bor.detail_info = json.dumps(details)
					bor.save()
					
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
				
				# update memo
				memo_content_list = request.POST.getlist('memo_content[]')
				memo_updated_by_list = request.POST.getlist('memo_updated_by[]')
				len_of_existed_memo = len(AdminMemo.objects.filter(model='BorrowRequest',identifier=bor_ref_num))
				for i in range(len(memo_content_list)):
					new_memo = AdminMemo(
					model='BorrowRequest',
					no=(i+1),
					identifier=bor_ref_num,
					content=memo_content_list[i],
					updated_by=memo_updated_by_list[i],
					create_timestamp=timezone.localtime(timezone.now()),
					update_timestamp=timezone.localtime(timezone.now())
					)
					new_memo.save()
				
				#return redirect(request.META.get('HTTP_REFERER'))
			if src == 'information':
				if not allow_edit:
					return redirect(request.META.get('HTTP_REFERER'))
					
				details = json.loads(bor.detail_info)
				
				# update loan amount status
				fs = classes.FriendlyScore()
				fs.getToken()
				code, fs_usr_details = fs.get(endpoint='users/partner-id/%s/show'%(usr.id), params={})
				
				social_total_score = 0
				social_fraud_risk_score = 0
				if code == 200:
					social_total_score = float(fs_usr_details['score_points'])
					social_fraud_risk_score = float(fs_usr_details['risk_score'])
					
				
				inputs = {
				'major': request.POST.get('Subject'),
				'resident': request.POST.get('Living Status'),
				'living_with': request.POST.get('Living with'),
				'university': request.POST.get('Studying University'),
				'GPA': request.POST.get('Overall GPA'),
				'date_of_birth': request.POST.get('Date of Birth'),
				'year': request.POST.get('Currently Studying'),
				
				'social_total_score': '>400' if social_total_score > 400 else '0-400',
				'social_fraud_risk_score': '>1' if social_fraud_risk_score > 1 else '0-1'
				}
				result = sup_fn.calculate_loan_amount(inputs)
				
				if result['status'] == 'REJECT':
					bor.status = 'REJECTED'
					bor.amount = 0
				else:
					bor.amount = result['amount']
					prod = Product.objects.get(id=bor.prod_id)
					amount = result['amount']
					bor.amount = amount
					if prod.repayment_plan == 'Instalment':
						rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
						bor.instalment_borrower = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
						rate_per_month = prod.APR_lender * 0.01 / 12
						bor.instalment_lender = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
					elif prod.repayment_plan == 'Balloon Payment':
						rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
						bor.instalment_borrower = amount * rate_per_month
						rate_per_month = prod.APR_lender * 0.01 / 12
						bor.instalment_lender = amount * rate_per_month
						
				# update detail info
				#details = json.loads(bor.detail_info)
				description = ''
				for k, v in details.iteritems():
					if request.POST.get(k) != '' and request.POST.get(k) != None:
						if request.POST.get(k) != details[k]:
							description += '%s "%s" changed to "%s".<br>'%(k, details[k], request.POST.get(k))
						details[k] = request.POST.get(k)
				bor.detail_info = json.dumps(details)
				bor.save()
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
					type = request.POST.get('Photo Description'),
					detail = new_fname,
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_bod.save()
				
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
				
				#return redirect(request.META.get('HTTP_REFERER'))
				
			if src == 'documents':
				file_name = request.POST.get('fileName')
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
					type = file_name,
					detail = new_fname,
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_bod.save()
			"""
			# send email notification
			if bor.status == 'REJECTED':
				bor_emailing = emailing.BorrowerEmail(bor=bor)
				bor_emailing.reject_loan_application()
			elif bor.status == 'CANCELLED':
				bor_emailing = emailing.BorrowerEmail(bor=bor)
				bor_emailing.cancel_loan_application()
			"""
			return redirect(request.META.get('HTTP_REFERER'))
		if 	request.session['handling_side'] == 'L':
			parsed = urlparse.urlparse(request.META.get('HTTP_REFERER'))
			uor_id = urlparse.parse_qs(parsed.query)['uor_id'][0]
			uor = UserOperationRequest.objects.get(id=uor_id)
			
			allow_edit = False
			allow_state_list = []
			if uor.status == 'DOC UPLOADED':
				allow_edit = True
				allow_state_list = ['APPROVED', 'PENDING DOC/IV', 'REJECTED']
			elif uor.status == 'PENDING DOC/IV':
				allow_edit = True
				allow_state_list = ['APPROVED', 'CANCELLED', 'REJECTED']
			
			src = request.GET.get('src')
			
			if src == 'preface':
				#uor_id = int(request.META.get('HTTP_REFERER').split('?uor_id=')[-1])
				#uor = UserOperationRequest.objects.get(id=uor_id)
				
				if allow_edit:
					# update detail info
					details = json.loads(uor.details)
					details['Individual']['Source of Fund'] = request.POST.get('Source of Fund')
					details['Individual']['Other Source of Fund'] = request.POST.get('Other Source of Fund')
					uor.details = json.dumps(details)
					
					# remainder: not handling account type
					
					new_status = request.POST.get('Application State')
					if new_status in allow_state_list:
						# access control
						if not adm_role.has_perm('change lender app state'):
							return HttpResponse('Permission denied.')
						else:
							if new_status not in adm_role.get_allowed_lender_app_state_list():
								return HttpResponse('Permission denied.')
							
						if new_status == 'APPROVED':
							# checklist should all be ticked
							params = {'require_tick_all_checklist':'True'}
							
							url_parts = list(urlparse.urlparse(request.META.get('HTTP_REFERER')))
							query = dict(urlparse.parse_qsl(url_parts[4]))
							query.update(params)
							
							url_parts[4] = urlencode(query)
							
							try:
								details['Confirm File Uploaded']
							except KeyError:
								details['Confirm File Uploaded'] = {}
							if len(details['File Uploaded']) != len(details['Confirm File Uploaded']):
								return redirect(urlparse.urlunparse(url_parts))
							else:
								for k, v in details['Confirm File Uploaded'].iteritems():
									if v == 'F':
										return redirect(urlparse.urlunparse(url_parts))
									
						uor.status = new_status
						uor.save()
					
					# update aut
					if uor.status == 'PENDING DOC/IV':
						inputs = {
							'usr_id': uor.usr_id,
							'description': 'Request additional supporting documents',
							'ref_id': uor.id,
							'model': 'UserOperationRequest',
							'by': 'Admin: ' + usr.email,
							'datetime': timezone.localtime(timezone.now()),
						}
						sup_fn.update_aut(inputs)
					elif uor.status == 'REJECTED':
						inputs = {
							'usr_id': uor.usr_id,
							'description': 'Reject lender application',
							'ref_id': uor.id,
							'model': 'UserOperationRequest',
							'by': 'Admin: ' + usr.email,
							'datetime': timezone.localtime(timezone.now()),
						}
						sup_fn.update_aut(inputs)
					elif uor.status == 'APPROVED':
						inputs = {
							'usr_id': uor.usr_id,
							'description': 'Approve lender application',
							'ref_id': uor.id,
							'model': 'UserOperationRequest',
							'by': 'Admin: ' + usr.email,
							'datetime': timezone.localtime(timezone.now()),
						}
						sup_fn.update_aut(inputs)
					elif uor.status == 'AGREEMENT CONFIRMED':
						inputs = {
							'usr_id': uor.usr_id,
							'description': 'Confirm lender agreement',
							'ref_id': uor.id,
							'model': 'UserOperationRequest',
							'by': 'Admin: ' + usr.email,
							'datetime': timezone.localtime(timezone.now()),
						}
						sup_fn.update_aut(inputs)
					
					# send email notification
					if uor.status == 'REJECTED':
						ldr_emailing = emailing.LenderEmail(uor=uor)
						ldr_emailing.reject_lender_application()
					elif uor.status == 'CANCELLED':
						ldr_emailing = emailing.LenderEmail(uor=uor)
						ldr_emailing.cancel_lender_application()
					
					# send sms / email notification
					if uor.status == 'APPROVED':
						ldr_smsing = smsing.LenderSMS()
						ldr_smsing.approved(uor=uor)
						
						ldr_emailing = emailing.LenderEmail(uor=uor)
						ldr_emailing.approved_lender_application()
				
				return redirect(request.META.get('HTTP_REFERER'))
			if src == 'information':
				#uor_id = int(request.META.get('HTTP_REFERER').split('?uor_id=')[-1])
				#uor = UserOperationRequest.objects.get(id=uor_id)
				
				if allow_edit:
					# update detail info
					details = json.loads(uor.details)
					for k, v in details['Individual'].iteritems():
						if request.POST.get(k) != '' and request.POST.get(k) != None:
							details['Individual'][k] = request.POST.get(k)
					try:
						details['Corporate']
					except KeyError:
						''
					else:
						for k, v in details['Corporate'].iteritems():
							if request.POST.get(k) != '' and request.POST.get(k) != None:
								details['Corporate'][k] = request.POST.get(k)
					uor.details = json.dumps(details)
					uor.save()
					
					# update memo
					memo_content_list = request.POST.getlist('memo_content[]')
					memo_updated_by_list = request.POST.getlist('memo_updated_by[]')
					len_of_existed_memo = len(AdminMemo.objects.filter(model='UserOperationRequest',identifier=uor_id))
					for i in range(len(memo_content_list)):
						new_memo = AdminMemo(
						model='UserOperationRequest',
						no=(i+1),
						identifier=uor_id,
						content=memo_content_list[i],
						updated_by=memo_updated_by_list[i],
						create_timestamp=timezone.localtime(timezone.now()),
						update_timestamp=timezone.localtime(timezone.now())
						)
						new_memo.save()
					
					# update aut
					inputs = {
						'usr_id': uor.usr_id,
						'description': 'Modify application information',
						'ref_id': uor.id,
						'model': 'UserOperationRequest',
						'by': 'Admin: ' + usr.email,
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
				
				return redirect(request.META.get('HTTP_REFERER'))
			if src == 'documents':
				file_name = request.POST.get('fileName')
				details = json.loads(uor.details)
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
					
					details['File Uploaded'][file_name] = new_fname
				uor.details = json.dumps(details)
				uor.save()
					
				return redirect(request.META.get('HTTP_REFERER'))
				
	# admin handles borrower repayment:
	if request.META.get('HTTP_REFERER').split('/')[3] == 'pl_admin' and request.META.get('HTTP_REFERER').split('/')[4] == 'repayment':
		bor_ref_num = request.META.get('HTTP_REFERER').split('?bor_ref_num=')[-1]
		bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
		
		# access control
		if not adm_role.has_perm('confirm repayment'):
			return HttpResponse('Permission denied.')
			
		
		if request.POST.get('Repayment Type') == 'Instalment':
			initial_repayment_amount = float(request.POST.get('Repayment Amount'))
			repayment_method = request.POST.get('Repayment Method')
			repayment_time = pytz.timezone('Asia/Hong_Kong').localize(datetime.strptime(request.POST.get('Repayment Time'),'%Y/%m/%d'))
			
			repayment_amount = initial_repayment_amount + bor.overpay_amount
			bor.overpay_amount = 0
			flag = True
			while flag:
				# update los
				los_list = LoanSchedule.objects.filter(bor_id=bor.id,status='OVERDUE')
				num_of_overdue = len(los_list)
				los_list = LoanSchedule.objects.filter(bor_id=bor.id)
				los_list = [los for los in los_list if los.status == 'OPEN' or los.status == 'OVERDUE']
				earliest_los = los_list[0]
				
				due_date = pytz.timezone('Asia/Hong_Kong').localize(datetime.strptime(earliest_los.due_date, '%Y/%m/%d'))
				overdue_days = (repayment_time - due_date).days
				
				# check pre-pay
				if overdue_days < 0:
					
					bor.overpay_amount += repayment_amount
					bor.save()
					
					# create trx
					new_trx = UserTransaction(
					usr_id = bor.usr_id,
					type = 'Deposit Overpay Repayment',
					amount_in = initial_repayment_amount,
					amount_out = 0,
					internal_ref = bor.ref_num,
					cust_ref = '--',
					href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_trx.save()
					
					# create aut
					inputs = {
						'usr_id': bor.usr_id,
						'description': 'Deposit overpay repayment: Amount $%s'%(initial_repayment_amount),
						'ref_id': bor.id,
						'model': 'BorrowRequest',
						'by': 'Admin: '+str(usr.email),
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
					
					# create ledger
					inputs = {
						'bor_id': bor.id,
						'description': 'Deposit overpay repayment: Amount $%s'%(initial_repayment_amount),
						'reference': bor.ref_num,
						'debit': initial_repayment_amount,
						'credit': 0,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_ledger(inputs)
					
					return redirect(request.META.get('HTTP_REFERER'))
					
				prod = Product.objects.get(id=bor.prod_id)
				loan_list = Loan.objects.filter(bor_id=bor.id)
				
				rate_per_day = bor.getBorAPR(prod.APR_borrower) * 0.01 / 360
					
				overdue_interest_remained = los.instalment * rate_per_day * (overdue_days - earliest_los.overdue_interest_paid_days)
				
				# pay late charge
				remain_late_charge = max(0, earliest_los.late_charge - earliest_los.paid_late_charge)
				if remain_late_charge > 0:
					paying_late_charge = min(repayment_amount, remain_late_charge)
					repayment_amount -= paying_late_charge
					earliest_los.paid_late_charge += paying_late_charge
					earliest_los.save()
					
					# update P L interest
					new_trx = UserTransaction(
					usr_id = 0,
					type = 'P L interest (late charge)',
					amount_in = paying_late_charge,
					amount_out = 0,
					internal_ref = bor.ref_num,
					cust_ref = '--',
					href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_trx.save()
					
					# update borrower ledger
					inputs = {
						'bor_id': bor.id,
						'description': 'Pay %s%s late charge by Borrower: Amount $%s'%(str(bor.repaid_month+1),sup_fn.date_postfix(bor.repaid_month+1),paying_late_charge),
						'reference': bor.ref_num,
						'debit': paying_late_charge,
						'credit': 0,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_ledger(inputs)
					
					# update PL ledger
					inputs = {
						'usr_id': 0,
						'description': 'Receive %s%s late charge by P L Account: Amount $%s'%(str(bor.repaid_month+1),sup_fn.date_postfix(bor.repaid_month+1),str(paying_late_charge)),
						'reference': bor.ref_num,
						'debit': 0,
						'credit': paying_late_charge,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_ledger(inputs)
					
					# update aut
					inputs = {
						'usr_id': bor.usr_id,
						'description': 'Confirmed late charge of %s%s instalment $%s'%(bor.repaid_month+1,sup_fn.date_postfix(bor.repaid_month+1),paying_late_charge),
						'ref_id': bor.id,
						'model': 'BorrowRequest',
						'by': 'Admin: '+str(usr.email),
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
					
					if repayment_amount <= 0:
						return redirect(request.META.get('HTTP_REFERER'))
				
				# borrower part
				remain_principal = earliest_los.principal - earliest_los.paid_principal
				remain_interest = earliest_los.interest - earliest_los.paid_interest
				remain_overdue_interest = overdue_interest_remained + earliest_los.overdue_interest_unpay_paid
				overpay_amount = 0
				this_instalment_amount_b = min(remain_principal+remain_interest+remain_overdue_interest, repayment_amount)
				
				if repayment_amount <= remain_overdue_interest:
					
					earliest_los.overdue_interest_unpay_paid = remain_overdue_interest
					earliest_los.overdue_interest_unpay_paid -= repayment_amount
					earliest_los.paid_overdue_interest += repayment_amount
					earliest_los.overdue_interest_paid_days = overdue_days
					earliest_los.overdue_interest_remained = 0
					earliest_los.overdue_interest_accumulated = earliest_los.overdue_interest_remained + earliest_los.overdue_interest_unpay_paid + earliest_los.paid_overdue_interest
				
				elif remain_overdue_interest < repayment_amount and repayment_amount <= remain_overdue_interest+remain_interest:
					
					repayment_amount -= remain_overdue_interest
					earliest_los.paid_overdue_interest += remain_overdue_interest
					earliest_los.overdue_interest_unpay_paid = 0
					earliest_los.overdue_interest_paid_days = overdue_days
					earliest_los.overdue_interest_remained = 0
					earliest_los.overdue_interest_accumulated = earliest_los.overdue_interest_remained + earliest_los.overdue_interest_unpay_paid + earliest_los.paid_overdue_interest
					
					earliest_los.paid_interest += repayment_amount
				elif remain_overdue_interest+remain_interest < repayment_amount and repayment_amount <= remain_overdue_interest+remain_interest+remain_principal:
					# overpay balloon loan would not enter here
					repayment_amount -= remain_overdue_interest
					earliest_los.paid_overdue_interest += remain_overdue_interest
					earliest_los.overdue_interest_unpay_paid = 0
					earliest_los.overdue_interest_paid_days = overdue_days
					earliest_los.overdue_interest_remained = 0
					earliest_los.overdue_interest_accumulated = earliest_los.overdue_interest_remained + earliest_los.overdue_interest_unpay_paid + earliest_los.paid_overdue_interest
					
					repayment_amount -= remain_interest
					earliest_los.paid_interest += remain_interest
					
					earliest_los.paid_principal += repayment_amount
				elif repayment_amount > remain_overdue_interest+remain_interest+remain_principal:
					# overpay
					repayment_amount -= remain_overdue_interest
					earliest_los.paid_overdue_interest += remain_overdue_interest
					earliest_los.overdue_interest_unpay_paid = 0
					earliest_los.overdue_interest_paid_days = overdue_days
					earliest_los.overdue_interest_remained = 0
					earliest_los.overdue_interest_accumulated = earliest_los.overdue_interest_remained + earliest_los.overdue_interest_unpay_paid + earliest_los.paid_overdue_interest
					
					repayment_amount -= remain_interest
					earliest_los.paid_interest += remain_interest
					
					repayment_amount -= remain_principal
					earliest_los.paid_principal += remain_principal
					
					#bor.overpay_amount += repayment_amount
					overpay_amount = repayment_amount
					
					
				if (earliest_los.principal - earliest_los.paid_principal+earliest_los.interest - earliest_los.paid_interest+earliest_los.overdue_interest_unpay_paid) <= 0.02:
					if repayment_time < due_date:
						earliest_los.status = 'PAID'
					else:
						earliest_los.status = 'PAID OVERDUE'
				
				if overpay_amount > 0:
					if len(los_list) > 1:
						next_los = los_list[1]
						if next_los.status == 'OVERDUE':
							repayment_amount = overpay_amount
							flag = True
						else:
							bor.overpay_amount += round(overpay_amount, 2)
							flag = False
					else:
						# last instalment but with overpay_amount
						bor.overpay_amount += round(overpay_amount, 2)
						flag = False
				else:
					flag = False
				bor.save()
				
				# lender part
				remain_principal_l = earliest_los.principal_l - earliest_los.paid_principal_l
				remain_interest_l = earliest_los.interest_l - earliest_los.paid_interest_l
				#repayment_amount = float(request.POST.get('Repayment Amount'))
				
				instalment_ratio = earliest_los.instalment_l / earliest_los.instalment
				
				if this_instalment_amount_b  <= remain_overdue_interest:
					this_instalment_amount_l = 0
				else:
					this_instalment_amount_l = (this_instalment_amount_b - remain_overdue_interest) * instalment_ratio
					if this_instalment_amount_l <= remain_interest_l:
						earliest_los.paid_interest_l += this_instalment_amount_l
					elif remain_interest_l < this_instalment_amount_l and this_instalment_amount_l <= remain_interest_l+remain_principal_l:
						this_instalment_amount_l -= remain_interest_l
						earliest_los.paid_interest_l += remain_interest_l
						
						earliest_los.paid_principal_l += this_instalment_amount_l
						if earliest_los.paid_principal >= earliest_los.principal_l:
							''#earliest_los.status = 'PAID OVERDUE' check consistent!!!!!!!!!!!
					elif this_instalment_amount_l > remain_interest_l +remain_principal_l:
						# overpay
						this_instalment_amount_l -= remain_interest_l
						earliest_los.paid_interest_l += remain_interest_l
						
						this_instalment_amount_l -= remain_principal_l
						earliest_los.paid_principal_l += remain_principal_l
				this_instalment_amount_l = max(0,this_instalment_amount_b - remain_overdue_interest) * instalment_ratio
				# other part
				#repayment_amount = float(request.POST.get('Repayment Amount'))
				earliest_los.received_amount += this_instalment_amount_b
				earliest_los.repayment_method = repayment_method
				earliest_los.repayment_type = request.POST.get('Repayment Type')
				earliest_los.repayment_date = repayment_time
				#earliest_los.status = 'PAID OVERDUE'
				earliest_los.save()
				
				this_instalment_amount_l = round(this_instalment_amount_l, 2)
				this_instalment_amount_b = round(this_instalment_amount_b, 2)
				# update borrower ledger
				inputs = {
					'bor_id': bor.id,
					'description': 'Pay %s%s repayment by Borrower: Amount $%s'%(str(bor.repaid_month+1),sup_fn.date_postfix(bor.repaid_month+1),this_instalment_amount_b),
					'reference': bor.ref_num,
					'debit': this_instalment_amount_b,
					'credit': 0,
					'datetime': timezone.localtime(timezone.now())
				}
				#return HttpResponse(this_instalment_amount_b)
				sup_fn.update_ledger(inputs)
				
				# update aut
				inputs = {
					'usr_id': bor.usr_id,
					'description': 'Confirmed repayment of %s%s instalment $%s'%(bor.repaid_month+1,sup_fn.date_postfix(bor.repaid_month+1),this_instalment_amount_b),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
				
				#repayment_amount -= overpay_amount
				if this_instalment_amount_b <= remain_overdue_interest:
					principal = 0
					interest = 0
					overdue_interest = this_instalment_amount_b
				elif this_instalment_amount_b > remain_overdue_interest and this_instalment_amount_b <= remain_overdue_interest + remain_interest:
					principal = 0
					interest = this_instalment_amount_b - remain_overdue_interest
					overdue_interest = remain_overdue_interest
				elif this_instalment_amount_b > remain_overdue_interest + remain_interest:
					principal = this_instalment_amount_b - (remain_overdue_interest + remain_interest)
					interest = remain_interest
					overdue_interest = remain_overdue_interest
				
				# lender part

				#repayment_amount = (repayment_amount - remain_overdue_interest) * instalment_ratio
				if this_instalment_amount_l <= remain_interest_l:
					principal_l = 0
					interest_l = this_instalment_amount_l
					#overdue_interest = remain_overdue_interest
				elif this_instalment_amount_l > remain_interest_l:
					principal_l = this_instalment_amount_l - remain_interest_l
					interest_l = remain_interest_l
				
				# update pl ledger
				prod = Product.objects.get(id=bor.prod_id)
				
				pl_ratio = (bor.getBorAPR(prod.APR_borrower) - prod.APR_lender) / bor.getBorAPR(prod.APR_borrower)
				
				pl_amount = round( (principal+interest)-(principal_l+interest_l) + overdue_interest * pl_ratio, 2)
				#return HttpResponse(pl_amount)
				inputs = {
					'usr_id': 0,
					'description': 'Receive income from %s%s repayment by P L Account: Amount $%s'%(str(bor.repaid_month+1),sup_fn.date_postfix(bor.repaid_month+1),str(pl_amount)),
					'reference': bor.ref_num,
					'debit': 0,
					'credit': pl_amount,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				
				# update P L interest
				new_trx = UserTransaction(
				usr_id = 0,
				type = 'P L interest',
				amount_in = pl_amount,
				amount_out = 0,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# update bor
				prev_status = bor.status
				if 'PAID' in earliest_los.status:
					bor.repaid_month += 1
					if num_of_overdue > 1:
						bor.status = 'PAYBACK OVERDUE ' + str(bor.repaid_month + 1)
					else:
						bor.status = 'PAYBACK ' + str(bor.repaid_month)
					bor.save()
				
				# update status aut
				if prev_status != bor.status:
					inputs = {
						'usr_id': bor.usr_id,
						'description': 'State "%s" changed to "%s"'%(prev_status, bor.status),
						'ref_id': bor.id,
						'model': 'BorrowRequest',
						'by': 'Admin: '+str(usr.email),
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
				
				# update borrower trx record
				new_trx = UserTransaction(
				usr_id = bor.usr_id,
				type = 'Repayment',
				amount_in = 0,
				amount_out = this_instalment_amount_b,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# update loan_list
				loan_list = Loan.objects.filter(bor_id=bor.id)
				total_remain_principal = sum([loan.remain_principal_lender for loan in loan_list])
				#total_interest_l = interest * (1 - pl_ratio)
				#return HttpResponse('total_interest: %s, interest: %s, pl_ratio: %s'%(total_interest_l, interest,pl_ratio))
				total_overdue_interest_l = overdue_interest * (1 - pl_ratio)
				for loan in loan_list:
					# update ledger
					inv = Investment.objects.get(id=loan.inv_id)
					inv_usr = User.objects.get(id=inv.usr_id)
					lender_no = sup_fn.try_KeyError(json.loads(inv_usr.detail_info), 'Lender No')
					l_ratio = loan.remain_principal_lender / total_remain_principal
					amount_l = (interest_l + principal_l +total_overdue_interest_l) * l_ratio
					amount_l = round(amount_l,2)
					
					inputs = {
						'usr_id': inv.usr_id,
						'description': 'Receive %s%s repayment by Lender %s: Amount $%s'%(str(bor.repaid_month),sup_fn.date_postfix(bor.repaid_month),lender_no,str(amount_l)),
						'reference': bor.ref_num,
						'debit': 0,
						'credit': amount_l,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_ledger(inputs)
					
					# update aut
					inputs = {
						'usr_id': inv.usr_id,
						'description': 'Confirm %s%s repayment (receive): Amount $%s'%(bor.repaid_month,sup_fn.date_postfix(bor.repaid_month),amount_l),
						'ref_id': bor.id,
						'model': 'BorrowRequest',
						'by': 'Admin: '+str(usr.email),
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
					
					# return amount to lender
					if inv.option == 'Reinvest':
						inv.total_amount += amount_l
						inv.usable_amount += amount_l
						inv.save()
					elif inv.option == 'Not Reinvest':
						acc = Account.objects.get(usr_id=inv.usr_id)
						acc.balance += amount_l
						acc.save()
					
					# update loan info
					#interest_borrower = loan.remain_principal * bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
					#interest_lender = interest_borrower * (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
					#principal = loan.instalment_borrower - interest_borrower
					loan.remain_principal -= principal * l_ratio
					loan.remain_principal_lender -= principal_l * l_ratio
					loan.remain_interest_borrower -= interest * l_ratio
					loan.remain_interest_lender -= interest_l * l_ratio
					#loan.paid_overdue_interest += earliest_los.interest
					#return HttpResponse('remain_principal: %s, remain_principal_l: %s, remain_interest_b: %s, remain_interest_l: %s, pl_amount: %s, overdue_interest: %s'%(principal * l_ratio,principal_l * l_ratio,interest * l_ratio,interest_l * l_ratio,pl_amount,remain_overdue_interest))
					
					if num_of_overdue > 1:
						loan.status = 'PAYBACK OVERDUE ' + str(bor.repaid_month + 1)
					else:
						loan.status = 'PAYBACK ' + str(bor.repaid_month)
					loan.save()
					
					# update lender trx record
					inv = Investment.objects.get(id=loan.inv_id)
					new_trx = UserTransaction(
					usr_id = inv.usr_id,
					type = 'Loan Return',
					amount_in = amount_l,
					amount_out = 0,
					internal_ref = bor.ref_num,
					cust_ref = '--',
					href = '/loan_repay_schedule/?loan_id=' + str(loan.id),
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_trx.save()
				
				
		if request.POST.get('Repayment Type') == 'Early Settlement':
			# assume received amount > early settle amount - overpay amount
			initial_repayment_amount = float(request.POST.get('Repayment Amount'))
			repayment_method = request.POST.get('Repayment Method')
			repayment_time = pytz.timezone('Asia/Hong_Kong').localize(datetime.strptime(request.POST.get('Repayment Time'),'%Y/%m/%d'))
			
			initial_repayment_amount += bor.overpay_amount
			# so initial_repayment_amount = early settle amount + late charge + overpay
			
			bor.overpay_amount = 0
			# add late charge
			
			inputs = {
				'bor_id': bor.id,
				'type': 'early_settlement',
				'date': request.POST.get('Repayment Time')
			}
			outputs = sup_fn.calculate_repay_amount(inputs)
			repayment_amount = round(max(0, outputs['early_settlement_amount']), 2)
			
			# if amount < early settle amount
			if initial_repayment_amount < repayment_amount:
				return redirect(request.META.get('HTTP_REFERER'))
			
			# pay late charge
			paying_late_charge = outputs['late_charge']
			if outputs['late_charge'] > 0:
				paying_late_charge = outputs['late_charge']
				initial_repayment_amount -= paying_late_charge
				# so initial_repayment_amount = early settle amount + overpay
				
				# update PL ledger
				inputs = {
					'usr_id': 0,
					'description': 'Receive late charge of early settlement by P L Account: Amount $%s'%(paying_late_charge),
					'reference': bor.ref_num,
					'debit': 0,
					'credit': paying_late_charge,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				
				# update aut
				inputs = {
					'usr_id': bor.usr_id,
					'description': 'Confirmed late charge of early settlement $%s'%(paying_late_charge),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
				
			
			overpay_amount = initial_repayment_amount - repayment_amount
			
			if 1:
				# update status aut
				inputs = {
					'usr_id': bor.usr_id,
					'description': 'State "%s" changed to "%s" (early settlement)'%(bor.status, 'PAYBACK COMPLETED'),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
				
				# update borrower part
				bor.status = 'PAYBACK COMPLETED'
				# how abt overpay amount??
				bor.overpay_amount = overpay_amount
				bor.update_timestamp = timezone.localtime(timezone.now())
				bor.save()
				
				# update los
				los = LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
				los.received_amount = repayment_amount
				los.repayment_method = repayment_method
				los.repayment_type = request.POST.get('Repayment Type')
				los.repayment_date = repayment_time
				los.status = 'PAYBACK COMPLETED'
				los.save()
				
				# update borrower ledger
				inputs = {
					'bor_id': bor.id,
					'description': 'Pay early settlement by Borrower: Amount $%s'%(repayment_amount+paying_late_charge),
					'reference': bor.ref_num,
					'debit': repayment_amount+paying_late_charge,
					'credit': 0,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				
				# update aut
				inputs = {
					'usr_id': bor.usr_id,
					'description': 'Confirmed early settlement $%s'%(repayment_amount),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Admin: '+str(usr.email),
					'datetime': timezone.localtime(timezone.now()),
				}
				sup_fn.update_aut(inputs)
				
				# update borrower trx record
				new_trx = UserTransaction(
				usr_id = bor.usr_id,
				type = 'Early Settlement',
				amount_in = 0,
				amount_out = repayment_amount,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# update lender part
				prod = Product.objects.get(id = bor.prod_id)
				#rate_per_day = prod.APR_lender * 0.01 / 360
				rate_per_day = bor.getBorAPR(prod.APR_borrower) * 0.01 / 360
				# get last pay date
				if bor.repaid_month == 0:
					last_pay_date = bor.draw_down_date
				else:
					los = LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month)
					last_pay_date = datetime.strptime(los.due_date, '%Y/%m/%d')
					last_pay_date = pytz.timezone('Asia/Hong_Kong').localize(last_pay_date)
				days = (repayment_time - last_pay_date).days
				days = max(0, days)
				loan_list = Loan.objects.filter(bor_id = bor.id)
				
				total_interest = repayment_amount - sum([loan.remain_principal for loan in loan_list])
				pl_ratio = (bor.getBorAPR(prod.APR_borrower) - prod.APR_lender) / bor.getBorAPR(prod.APR_borrower)
				PL_interest = total_interest * pl_ratio
				PL_interest = round(PL_interest, 2)
				# update P L interest ===========================================
				new_trx = UserTransaction(
				usr_id = 0,
				type = 'P L interest (early settle)',
				amount_in = PL_interest,
				amount_out = 0,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# update pl ledger
				inputs = {
					'usr_id': 0,
					'description': 'Receive income from early settlement by P L Account: Amount $%s'%(PL_interest),
					'reference': bor.ref_num,
					'debit': 0,
					'credit': PL_interest,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				# update P L interest end ========================================
				
				total_interest_bor = total_interest - PL_interest
				total_principal_bor = sum([loan.remain_principal for loan in loan_list])
				#return HttpResponse('%s|%s|%s'%(PL_interest,total_interest_bor,total_interest))
				
				for loan in loan_list:
					interest_bor = total_interest_bor * loan.remain_principal / total_principal_bor
					#early_settlement_amount = loan.remain_principal_lender *  (1 + rate_per_day * days)
					early_settlement_amount = loan.remain_principal + interest_bor
					early_settlement_amount = round(early_settlement_amount, 2)
					#repayment_amount -= early_settlement_amount
					
					
					# update loan
					loan.remain_principal = 0
					loan.remain_principal_lender = 0
					loan.remain_interest_lender = 0
					loan.remain_interest_borrower = 0
					loan.status = 'PAYBACK COMPLETED'
					loan.save()
					
					inv = Investment.objects.get(id = loan.inv_id)
					inv_usr = User.objects.get(id=inv.usr_id)
					lender_no = sup_fn.try_KeyError(json.loads(inv_usr.detail_info), 'Lender No')
					# return amount to lender
					if inv.option == 'Reinvest':
						inv.total_amount += early_settlement_amount
						inv.usable_amount += early_settlement_amount
						inv.save()
					elif inv.option == 'Not Reinvest':
						acc = Account.objects.get(usr_id=inv.usr_id)
						acc.balance += early_settlement_amount
						acc.save()
					
					# update lender ledger
					inputs = {
						'usr_id': inv.usr_id,
						'description': 'Receive early settlement by Lender %s: Amount $%s'%(lender_no, early_settlement_amount),
						'reference': bor.ref_num,
						'debit': 0,
						'credit': early_settlement_amount,
						'datetime': timezone.localtime(timezone.now())
					}
					sup_fn.update_ledger(inputs)
					
					# update aut
					inputs = {
						'usr_id': inv.usr_id,
						'description': 'Receive early settlement: Amount $%s'%(early_settlement_amount),
						'ref_id': bor.id,
						'model': 'BorrowRequest',
						'by': 'Admin: '+str(usr.email),
						'datetime': timezone.localtime(timezone.now()),
					}
					sup_fn.update_aut(inputs)
					
					# update lender trx record
					inv = Investment.objects.get(id=loan.inv_id)
					new_trx = UserTransaction(
					usr_id = inv.usr_id,
					type = 'Loan Early Settlement',
					amount_in = early_settlement_amount,
					amount_out = 0,
					internal_ref = bor.ref_num,
					cust_ref = '--',
					href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_trx.save()
				
				"""
				# update P L interest
				new_trx = UserTransaction(
				usr_id = 0,
				type = 'P L interest (early settle)',
				amount_in = repayment_amount,
				amount_out = 0,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# update pl ledger
				inputs = {
					'usr_id': 0,
					'description': 'Receive income from early settlement by P L Account: Amount $%s'%(repayment_amount),
					'reference': bor.ref_num,
					'debit': 0,
					'credit': repayment_amount,
					'datetime': timezone.localtime(timezone.now())
				}
				sup_fn.update_ledger(inputs)
				"""
		return redirect(request.META.get('HTTP_REFERER'))