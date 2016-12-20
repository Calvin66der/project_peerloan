# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from peerloan.models import Account
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import Product
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest

from peerloan.decorators import require_login

import peerloan.peerloan_src.supporting_function as sup_fn

import json
import datetime as dt
from datetime import datetime
import pytz
from django.utils import timezone
from collections import OrderedDict

FLOAT_DATA_FORMAT = '{:,.2f}'

@require_login
def my_account(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	sub_cate = request.META.get('PATH_INFO').split('/')[2]
	# borrower side =============================================================================================
	if usr.type == 'B':
		if sub_cate == 'all_application_listing':
			if 'detail' in request.META.get('PATH_INFO').split('/'):
				# bor detail
				bor_id = request.GET.get('bor_id')
				bor = BorrowRequest.objects.get(id=bor_id)
				prod = Product.objects.get(id=bor.prod_id)
				
				los_list = LoanSchedule.objects.filter(bor_id=bor.id, status='OVERDUE')
				basic_info = {
					'product': prod.name_en,
					'total_amount': 'HK$'+FLOAT_DATA_FORMAT.format(bor.amount),
					'instalment': 'HK$'+FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
					'draw_down_date': bor.draw_down_date.strftime('%Y/%m/%d'),
					'expected_end_date': bor.expected_end_date.strftime('%Y/%m/%d'),
					'overdue_loan_payment': 'HK$'+FLOAT_DATA_FORMAT.format(sum([los.overdue_interest_accumulated for los in los_list])),
					'tenor': str(prod.repayment_period)+' months',
					'status': ''.join([i for i in bor.status if (not i.isdigit())])
				}
				if prod.repayment_plan == 'Promotion Balloon Payment':
					basic_info['tenor'] = str(9)+' months'
				if lang == 'zh':
					basic_info['product'] = prod.name_zh
					basic_info['tenor'] = str(prod.repayment_period)+' 月'
					if prod.repayment_plan == 'Promotion Balloon Payment':
						basic_info['tenor'] = str(9)+' 月'
				
				# create repayment table
				los_list = LoanSchedule.objects.filter(bor_id=bor.id)
				repayment_table = []
				repayment_history = []
				remain_balance = bor.amount
				for i in range(prod.repayment_period):
					los = los_list[i]
					remain_balance -= los.principal
					if remain_balance <= 0.02:
						remain_balance = 0
					row = {
						'tenor': str(i+1),
						'due_date': los.due_date,
						'instalment_amount': FLOAT_DATA_FORMAT.format(los.instalment),
						'interest': FLOAT_DATA_FORMAT.format(los.interest),
						'principal': FLOAT_DATA_FORMAT.format(los.principal),
						'outstanding_principal': FLOAT_DATA_FORMAT.format(remain_balance),
					}
					repayment_table.append(row)
					
					if 'PAID' in los.status or 'PAYBACK COMPLETED' in los.status:
						row = {
							'due_date': los.due_date,
							'repayment_date': timezone.localtime(los.repayment_date).strftime('%Y/%m/%d'),
							'overdue_day': los.overdue_days,
							'overdue_interest': FLOAT_DATA_FORMAT.format(los.overdue_interest_accumulated),
							'payment_amount': FLOAT_DATA_FORMAT.format(los.received_amount),
							'repayment_method': los.repayment_method,
							'repayment_type': los.repayment_type,
						}
						repayment_history.append(row)
				
				# calculate early settle
				loan_list = Loan.objects.filter(bor_id = bor.id)
				if bor.repaid_month == 0:
					last_pay_date = bor.draw_down_date
				else:
					los = LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month)
					last_pay_date = datetime.strptime(los.due_date, '%Y/%m/%d')
					last_pay_date = pytz.timezone('Asia/Hong_Kong').localize(last_pay_date)
				days = (timezone.localtime(timezone.now()) - last_pay_date).days
				if days < 0:
					days = 0
				rate_per_day = prod.APR_borrower * 0.01 / 360
				remain_principal = sum([loan.remain_principal for loan in loan_list])
				early_settlement_amount = remain_principal *  (1 + rate_per_day * days)
				early_settle = {
					'date': timezone.localtime(timezone.now()).strftime('%Y/%m/%d')+' (as today)',
					'amount': 'HK$'+FLOAT_DATA_FORMAT.format(early_settlement_amount)
				}
				if lang == 'zh':
					early_settle['date'] = timezone.localtime(timezone.now()).strftime('%Y/%m/%d')+' (在今日)'
				
				content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'all_application_listing',
				'title': 'Loan - ' + bor.ref_num,
				'form_action': 'javascript:;',
				'basic_info': basic_info,
				'repayment_table': repayment_table,
				'repayment_history': repayment_history,
				'early_settle': early_settle,
				'bod_list': BorrowRequestDocument.objects.filter(bor_id=bor.id),
				}
				if lang == 'zh':
					content['title'] = '貸款 - %s' % bor.ref_num.encode("utf8")
				return render(request, 'peerloan/borrower/all_application_listing_detail.html', content)
			else:
				# bor table
				status_list = ['All', 'AUTO APPROVED', 'DOC UPLOADED', 'AGREEMENT CONFIRMED', 'PENDING DOC/IV',
				'DISBURSED', 'PAYBACK', 'PAYBACK OVERDUE', 'PAYBACK COMPLETED']
				content = {
					'lang': lang,
					'cate': 'my_account',
					'sub_cate': 'all_application_listing',
					'title': 'Application Listing',
					'status_list': status_list,
				}
				if lang == 'zh':
					content['title'] = '申請列表'
				return render(request, 'peerloan/borrower/all_application_listing.html', content)
		if sub_cate == 'active_loan':
			if 'repayment_details' in request.META.get('PATH_INFO').split('/'):
				# repay detail page
				bor_list = BorrowRequest.objects.filter(usr_id=usr.id)
				bor_list = [bor for bor in bor_list if bor.status == 'DISBURSED' or 'PAYBACK' in bor.status]
				rd_bor_list = [['all', 'All Active Loan']]
				for bor in bor_list:
					rd_bor_list.append([bor.id, 'Loan Ref No.: '+ bor.ref_num])
				content = {
				'cate': 'my_account',
				'sub_cate': 'active_loan',
				'bor_list': rd_bor_list,
				}
				return render(request, 'peerloan/borrower/repayment_details.html', content)
			else:
				# active loan page
				bor_list = BorrowRequest.objects.filter(usr_id=usr.id)
				bor_list = [bor for bor in bor_list if bor.status == 'DISBURSED' or 'PAYBACK' in bor.status]
				detail_list = []
				app_list = []
				for bor in bor_list:
					detail = {}
					prod = Product.objects.get(id = bor.prod_id)
					loan_list = Loan.objects.filter(bor_id = bor.id)
					detail['prod_name'] = prod.name_en
					detail['total_amount'] = prod.total_amount
					detail['installment'] = round(bor.instalment_borrower, 2)
					detail['draw_down_date'] = loan_list[0].draw_down_date.strftime("%d/%m/%Y")
					detail['expected_end_date'] = loan_list[0].expected_end_date.strftime("%d/%m/%Y")
					detail['overdue_loan_payment'] = sum([loan.overdue_principal+loan.overdue_interest for loan in loan_list])
					
					detail['bor_ref_num'] = bor.ref_num
					detail['repayment_period'] = prod.repayment_period
					detail['APR'] = prod.APR_borrower
					detail_list.append(detail)
					
					bod_list = BorrowRequestDocument.objects.filter(bor_id = bor.id)
					
					app_list.append(bod_list)
				content = {
				'cate': 'my_account',
				'sub_cate': 'active_loan',
				'bor_list': bor_list,
				'detail_list': detail_list,
				'app_list': app_list,
				}
				return render(request, 'peerloan/borrower/active_loan.html', content)
		if sub_cate == 'loan_status':
			if 'view_detail' in request.META.get('PATH_INFO').split('/'):
				# bor detail
				bor_id = request.GET.get('bor_id')
				bor = BorrowRequest.objects.get(id=bor_id)
				prod = Product.objects.get(id=bor.prod_id)
				if bor.status == 'APPLIED':
					fields = []
					fields.append({'name':'Product Name','value':prod.name_en})
					fields.append({'name':'Total Applied Amount','value':prod.total_amount})
					fields.append({'name':'APR','value':prod.APR_borrower})
					fields.append({'name':'Upload Supplementary Documents','type':'upload_file', 'value':'supply_doc'})
					fields.append({'name':'Supplementaty Documents Description', 'type':'input','value':'supply_doc_descri'})
					fields.append({'name':'Applicaton Date','value':bor.create_timestamp.strftime('%Y-%m-%d')})
					fields.append({'name':'Status','value':bor.status})
					
					buttons = []
					buttons.append({'name':'Submit', 'type':'submit'})
					buttons.append({'name':'Close', 'type':'button', 'onclick':'window.close()'})
				elif bor.status == 'VALIDATED' or 'MATCHING' in bor.status:
					fields = []
					loan_list = Loan.objects.filter(bor_id = bor.id)
					if len(loan_list) == 0:
						fields.append({'name':'Matched Amount', 'value':0})
					else:
						fields.append({'name':'Matched Amount', 'value':sum([loan.initial_amount for loan in loan_list])})
					fields.append({'name':'Total Applied Amount','value':prod.total_amount})
					fields.append({'name':'Application Date','value':bor.create_timestamp.strftime('%Y-%m-%d')})
					fields.append({'name':'Matching Starting Date','value':bor.update_timestamp.strftime('%Y-%m-%d')})
					fields.append({'name':'Matching Expiring Date','value':(bor.update_timestamp+dt.timedelta(days=7)).strftime('%Y-%m-%d')})
					fields.append({'name':'APR','value':prod.APR_borrower})
					fields.append({'name':'Status','value':bor.status})
					
					buttons= []
					buttons.append({'name':'Close', 'type':'button', 'onclick':'window.close()'})
				elif 'PAYBACK' in bor.status or bor.status == 'DRAWN DOWN':
					return redirect('/my_account/active_loan')
				elif bor.status == 'COMPLETED':
					fields = []
					loan_list = Loan.objects.filter(bor_id = bor.id)
					fields.append({'name':'Borrowed Principal', 'value': sum([loan.remain_principal for loan in loan_list])})
					fields.append({'name':'Total Interest', 'value': sum([loan.remain_interest_borrower for loan in loan_list])})
					fields.append({'name':'Total Overdue Interest', 'value':sum([loan.overdue_interest for loan in loan_list])})
					fields.append({'name':'APR', 'value':prod.APR_borrower})
					
					total_interest = prod.total_amount * prod.APR_borrower * 0.01 * prod.repayment_period / 12 + sum([loan.paid_overdue_interest for loan in loan_list])
					effective_APR = (total_interest / prod.total_amount) * (12 / prod.repayment_period) * 100
					fields.append({'name':'Effective APR', 'value':effective_APR})
					fields.append({'name':'Effective Flat Rate', 'value': 'PENDING'})
					
					buttons= []
					buttons.append({'name':'Close', 'type':'button', 'onclick':'window.close()'})
				content = {
				'title': 'Loan Reference Number - ' + bor.ref_num,
				'cate': 'my_account',
				'sub_cate': 'loan_status',
				'form_action': '/ack/',
				'fields': fields,
				'buttons': buttons,
				}
				return render(request, 'peerloan/borrower/form.html', content)
			else:
				# bor table
				status_list = ['All', 'AUTO APPROVED', 'DOC UPLOADED', 'AGREEMENT CONFIRMED', 'PENDING DOC/IV',
				'PENDING VERIFIED', 'VALIDATED', 'FUND MATCHING', 'FUND MATCHING COMPLETED', 'DISBURSED',
				'PAYBACK', 'PAYBACK OVERDUE', 'PAYBACK COMPLETED']
				content = {
				'cate': 'my_account',
				'sub_cate': 'loan_status',
				'status_list': status_list,
				}
				return render(request, 'peerloan/borrower/loan_status.html', content)
		if sub_cate == 'change_acc_info':
			details = json.loads(usr.detail_info)
			usr_info = {
				'usr_id': usr.id,
				'password': '********',
				'mobile': sup_fn.try_KeyError(details, 'Mobile'),
				'address': sup_fn.try_KeyError(details, 'Residential Address'),
			}
			content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'change_acc_info',
				'title': 'Change Account Information',
				'form_action': 'javascript:;',
				'usr_info': usr_info,
			}
			if lang == 'zh':
				content['title'] = '更換賬戶資料'
			return render(request, 'peerloan/borrower/change_acc_info.html', content)
		if sub_cate == 'repayment_and_settlement':
			usr = sup_fn.get_user(request)
			bor_list = BorrowRequest.objects.filter(usr_id=usr.id)
			bor_list = [bor for bor in bor_list if ('PAYBACK' in bor.status or 'DISBURSED' in bor.status) and 'COMPLETED' not in bor.status]
			content = {
			'lang': lang,
			'cate': 'my_account',
			'sub_cate': 'repayment_and_settlement',
			'title': 'Repayment and Settlement',
			}
			if lang == 'zh':
				content['title'] = '供款及提早還款'
				
			if len(bor_list) != 0:
				bor = bor_list[0]
				
				inputs = {
					'bor_id': bor.id,
					'type': 'instalment'
				}
				outputs = sup_fn.calculate_repay_amount(inputs)
				content['instalment_month'] = outputs['instalment_month']
				total_amount = max(0, outputs['instalment_amount']+outputs['overdue_interest']+outputs['late_charge']-outputs['overpay_amount'])
				content['instalment_amount'] = 'HK$%s, included: <br>instalment: HK$%s;<br>overdue interest: HK$%s;<br>late charge: HK$%s;<br>overpay amount: HK$%s.'%(
				FLOAT_DATA_FORMAT.format(total_amount),FLOAT_DATA_FORMAT.format(outputs['instalment_amount']),
				FLOAT_DATA_FORMAT.format(outputs['overdue_interest']),FLOAT_DATA_FORMAT.format(outputs['late_charge']),FLOAT_DATA_FORMAT.format(outputs['overpay_amount']))
				if lang == 'zh':
					content['instalment_amount'] = 'HK$%s, 包含: <br>分期還款金額: HK$%s;<br>逾期利息: HK$%s;<br>逾期收費: HK$%s;<br>多繳金額: HK$%s。'%(
					FLOAT_DATA_FORMAT.format(total_amount),FLOAT_DATA_FORMAT.format(outputs['instalment_amount']),
					FLOAT_DATA_FORMAT.format(outputs['overdue_interest']),FLOAT_DATA_FORMAT.format(outputs['late_charge']),FLOAT_DATA_FORMAT.format(outputs['overpay_amount']))
				# calculate early settlement
				inputs = {
					'bor_id': bor.id,
					'type': 'early_settlement'
				}
				outputs = sup_fn.calculate_repay_amount(inputs)
				total_amount = max(0, outputs['early_settlement_amount']+outputs['late_charge']-outputs['overpay_amount'])
				content['early_settlement_amount'] = 'HK$%s, included: <br>principal: HK$%s;<br>interest: HK$%s;<br>late charge: HK$%s;<br>overpay amount: HK$%s.'%(
				FLOAT_DATA_FORMAT.format(total_amount),FLOAT_DATA_FORMAT.format(outputs['principal']),
				FLOAT_DATA_FORMAT.format(outputs['interest']),FLOAT_DATA_FORMAT.format(outputs['late_charge']),FLOAT_DATA_FORMAT.format(outputs['overpay_amount']))
				if lang == 'zh':
					content['early_settlement_amount'] = 'HK$%s, 包含: <br>本金: HK$%s;<br>利息: HK$%s;<br>逾期收費: HK$%s;<br>多繳金額: HK$%s。'%(
					FLOAT_DATA_FORMAT.format(total_amount),FLOAT_DATA_FORMAT.format(outputs['principal']),
					FLOAT_DATA_FORMAT.format(outputs['interest']),FLOAT_DATA_FORMAT.format(outputs['late_charge']),FLOAT_DATA_FORMAT.format(outputs['overpay_amount']))
				
				content['bor_id'] = bor.id
				content['bor_ref_num'] = bor.ref_num
			
				return render(request, 'peerloan/borrower/repayment_and_settlement.html', content)
			else:
				if lang == 'en':
					content['instruction'] = 'No record, you can apply a loan first. Click <a href="/borrow_now" style="color:#fff;"><u>here</u></a>'
				elif lang == 'zh':
					content['instruction'] = '沒有找到記錄，請先申請貸款。<a href="/borrow_now" style="color:#fff;">點擊此處</a>'
					
				return render(request, 'peerloan/borrower/acknowledgement.html', content)
				
	# borrower side end =======================================================================================
	# lender side =============================================================================================
	elif usr.type == 'L':
		if sub_cate == 'deposit_money':
			if lang == 'en':
				fields = []
				fields.append({'name': 'Bank Name', 'value': 'Hang Seng Bank'})
				fields.append({'name': 'Bank Account Number', 'value': '239-498-348883'})
				fields.append({'name': 'Name of Account Holder', 'value': 'P L Technology Limited'})
				fields.append({'name': 'Bank Deposit Slip', 'value': 'receipt','type': 'upload_file', 'additional_text': 'Please keep your original bank slip at least 3 months (from upload date) for record.', 'required':'True'})
				fields.append({'name': 'Deposit Amount', 'value': 'transfer_amt', 'type': 'input', 'required':'True'})
				#fields.append({'name': 'Your Reference', 'value': 'ur_ref', 'type': 'input'})
				
				
				buttons = []
				buttons.append({'name': 'Submit', 'type': 'submit'})
				buttons.append({'name': 'Cancel', 'type': 'button', 'onclick':'window.history.back()'})
				
				content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'deposit_money',
				'title': 'Deposit Money',
				'instruction': """Zwap only accept cheque deposit or bank transfer from a local bank account under 
				your own name, please upload the deposit slip here, the fund will be ready in your Zwap's account 
				within 1 business day for bank transfer, and 2 business days for cheque deposit.
				""",
				'form_action': '/ack/',
				'fields': fields,
				'buttons': buttons,
				}
			elif lang == 'zh':
				fields = []
				fields.append({'name': '銀行名稱', 'value': '恒生銀行'})
				fields.append({'name': '戶口號碼', 'value': '239-498-348883'})
				fields.append({'name': '戶口持有人名稱', 'value': 'P L Technology Limited'})
				fields.append({'name': '銀行存款單據', 'value': 'receipt','type': 'upload_file', 'additional_text': '請保留你的正本收據三個月(從上傅日起計)以作紀錄。', 'required':'True'})
				fields.append({'name': '存入金額', 'value': 'transfer_amt', 'type': 'input', 'required':'True'})
				#fields.append({'name': 'Your Reference', 'value': 'ur_ref', 'type': 'input'})
				
				buttons = []
				buttons.append({'name': '提交', 'type': 'submit'})
				buttons.append({'name': '取消', 'type': 'button', 'onclick':'window.history.back()'})
				
				content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'deposit_money',
				'title': '存入資金',
				'instruction': """Zwap只接受以你名下之本地銀行戶口發出之支票存款，或銀行轉賬形式存款，請上載你的銀行
				存款收據，經核實後我們將於一個工作天內存入資金至你的Zwap帳戶，如以支票形式存款，則須兩個工作天核實。
				""",
				'form_action': '/ack/',
				'fields': fields,
				'buttons': buttons,
				}
			return render(request, 'peerloan/lender/form.html', content)
		elif sub_cate == 'withdraw_money':
			acc = Account.objects.get(usr_id = usr.id)
			
			if lang == 'en':
				fields = []
				if acc.balance == 0:
					fields.append({'name': 'Withdrawal Amount', 'value': '/my_account/deposit_money', 'text': 'Please deposit money first', 'type': 'href', 'required': 'True'})
				else:
					fields.append({'name': 'Withdrawal Amount', 'value': 'withdraw_amt', 'type': 'ion-slider', 'required': 'True'})
				
				details = json.loads(usr.detail_info)
				bank_acc = sup_fn.try_KeyError(details['Individual'], 'Bank Account')
				if bank_acc == '--':
					fields.append({'name': 'Bank Account', 'value': '/my_account/change_acc_info', 'text': 'Please input your bank account information first', 'type': 'href'})
				else:
					fields.append({'name': 'Bank Account', 'value': 'Bank Account', 'hidden_value': bank_acc, 'type': 'text_and_hidden'})
					
				#fields.append({'name': 'Your Reference', 'value': 'Your Reference', 'type': 'input'})
				fields.append({'name': 'One Time Password', 'value': 'OTP', 'type': 'OTP', 'required':'True'})
				
				buttons = []
				if acc.balance == 0 or bank_acc == '--':
					buttons.append({'name': 'Submit', 'type': 'submit', 'disabled':'disabled'})
				else:
					buttons.append({'name': 'Submit', 'type': 'submit'})
				buttons.append({'name': 'Cancel', 'type': 'button', 'onclick':'window.history.back()'})
				
				content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'withdraw_money',
				'title': 'Withdraw Money',
				'instruction': """Please specify the amount you would like to withdraw from your Zwap's account. We will deposit 
				the request amount to your registered bank account by cheque within 1 business day after validation.
				""",
				'form_action': '/ack/',
				'usr_id': usr.id,
				'fields': fields,
				'buttons': buttons,
				'acc_balance': acc.balance,
				'OTP_action': 'Withdraw Money',
				'mobile': json.loads(usr.detail_info)['Individual']['Mobile']
				}
			elif lang == 'zh':
				fields = []
				if acc.balance == 0:
					fields.append({'name': '提取金額', 'value': '/my_account/deposit_money', 'text': '請先存入資金', 'type': 'href', 'required': 'True'})
				else:
					fields.append({'name': '提取金額', 'value': 'withdraw_amt', 'type': 'ion-slider', 'required': 'True'})
				
				details = json.loads(usr.detail_info)
				bank_acc = sup_fn.try_KeyError(details['Individual'], 'Bank Account')
				if bank_acc == '--':
					fields.append({'name': '銀行戶口', 'value': '/my_account/change_acc_info', 'text': '請先輸入你的銀行戶口資料', 'type': 'href'})
				else:
					fields.append({'name': '銀行戶口', 'value': 'Bank Account', 'hidden_value': bank_acc, 'type': 'text_and_hidden'})
					
				#fields.append({'name': 'Your Reference', 'value': 'Your Reference', 'type': 'input'})
				fields.append({'name': '一次性密碼', 'value': 'OTP', 'type': 'OTP', 'required':'True'})
				
				buttons = []
				if acc.balance == 0 or bank_acc == '--':
					buttons.append({'name': '提交', 'type': 'submit', 'disabled':'disabled'})
				else:
					buttons.append({'name': '提交', 'type': 'submit'})
				buttons.append({'name': '取消', 'type': 'button', 'onclick':'window.history.back()'})
				
				content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'withdraw_money',
				'title': '提取資金',
				'instruction': """請註明你要從你的Zwap帳戶提取的金額，經核實後我們將於一個工作天內以支票形式存入你已登記的銀行戶口內。
				""",
				'form_action': '/ack/',
				'usr_id': usr.id,
				'fields': fields,
				'buttons': buttons,
				'acc_balance': acc.balance,
				'OTP_action': 'Withdraw Money',
				'mobile': json.loads(usr.detail_info)['Individual']['Mobile']
				}
			
			error = request.GET.get('error')
			if lang == 'en':
				if error == 'invalid_OTP':
					content['error_msg'] = 'Please input a valid OTP'
				if error == 'OTP_not_matched':
					content['error_msg'] = 'The OTP doesn\'t match to our record, please try again'
				if error == 'OTP_expired':
					content['error_msg'] = 'The OTP is expired, please receive a new OTP first'
			elif lang == 'zh':
				if error == 'invalid_OTP':
					content['error_msg'] = '請輸入一個有效的OTP'
				if error == 'OTP_not_matched':
					content['error_msg'] = '你輸入的OTP與我們的記錄不符合，請重新操作'
				if error == 'OTP_expired':
					content['error_msg'] = '你的OTP已經逾期，請重新獲取OTP'
			
			
			return render(request, 'peerloan/lender/form.html', content)
		elif sub_cate == 'transaction_records':
			content = {
			'lang': lang,
			'cate': 'my_account',
			'sub_cate': 'transaction_records',
			'title': 'Transaction Records',
			}
			if lang == 'zh':
				content['title'] = '交易記錄'
				
			return render(request, 'peerloan/lender/trans_records.html', content)
		elif sub_cate == 'change_acc_info':
			details = json.loads(usr.detail_info)
			usr_info = {
				'usr_id': usr.id,
				'password': '********',
				'mobile': sup_fn.try_KeyError(details['Individual'], 'Mobile'),
				'address': sup_fn.try_KeyError(details['Individual'], 'Residential Address'),
				'bank_account': sup_fn.try_KeyError(details['Individual'], 'Bank Account'),
			}
			if sup_fn.try_KeyError(details, 'Corporate') != '--':
				usr_info['office_address'] = sup_fn.try_KeyError(details['Corporate'], 'Office Address')
			content = {
				'lang': lang,
				'cate': 'my_account',
				'sub_cate': 'change_acc_info',
				'title': 'Change Account Information',
				'form_action': 'javascript:;',
				'usr_info': usr_info,
			}
			if lang == 'zh':
				content['title'] = '更改帳戶資料'
			return render(request, 'peerloan/lender/change_acc_info.html', content)