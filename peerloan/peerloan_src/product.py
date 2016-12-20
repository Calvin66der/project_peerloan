# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db import transaction

from peerloan.decorators import require_login

from peerloan.models import Account
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import Product
from peerloan.models import User

from peerloan.decorators import require_login

import peerloan.classes as classes
import peerloan.emailing as emailing
import peerloan.peerloan_src.supporting_function as sup_fn

from peerloan.forms import CaptchaForm
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url

from datetime import datetime
from django.utils import timezone
from collections import OrderedDict
import csv
import json

FLOAT_DATA_FORMAT = '{:,.2f}'

@require_login
@transaction.atomic
def product(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	action = request.META.get('PATH_INFO').split('/')[2]
	if action == 'apply':
		bor_list = BorrowRequest.objects.filter(usr_id=usr.id)
		bor_list = [bor for bor in bor_list if bor.status not in ['PAYBACK COMPLETED', 'REJECTED', 'CANCELLED']]
		num_of_applied_prod = len(bor_list)
		
		# check which step
		if num_of_applied_prod != 0:
			return redirect('/borrow_now')
		
		
		prod_id = request.GET.get('prod_id')
		prod = Product.objects.get(id = prod_id)
		
		if request.method == 'POST':
			form = CaptchaForm(request.POST)
			if form.is_valid():
				# check hkid cannot repeat from other loan application
				simplified_hkid = request.POST.get('HKID').replace('(','').replace(')','').lower()
				other_bor_list = BorrowRequest.objects.filter((~Q(usr_id = usr.id)) & Q(simplified_hkid=simplified_hkid))
				if len(other_bor_list) != 0:
					return redirect('/ack_page/?action=apply_loan_rejected&reason=repeated_hkid')
				
				# check hkid should be consistent with the one on he's lender account
				try:
					ldr_usr = User.objects.get(email=usr.email, type='L')
				except ObjectDoesNotExist:
					''
				else:
					ldr_details = json.loads(ldr_usr.detail_info)
					ldr_simplified_hkid = ldr_details['Individual']['HKID'].replace('(','').replace(')','').lower()
					if simplified_hkid != ldr_simplified_hkid:
						return redirect('/ack_page/?action=apply_loan_rejected&reason=hkid_not_matched')
					
				# check social score
				fs = classes.FriendlyScore()
				fs.getToken()
				code, fs_usr_details = fs.get(endpoint='users/partner-id/%s/show'%(usr.id), params={})
				
				social_total_score = 0
				social_fraud_risk_score = 0
				if code == 200:
					social_total_score = float(fs_usr_details['score_points'])
					social_fraud_risk_score = float(fs_usr_details['risk_score'])
				
				prod_id = int(request.META.get('HTTP_REFERER').split('/?prod_id=')[-1])
				prod = Product.objects.get(id = prod_id)
				
				inputs = {
				'major': request.POST.get('Subject'),
				'resident': request.POST.get('Living Status'),
				'living_with': request.POST.get('Living with'),
				'university': request.POST.get('Studying University'),
				'GPA': float(request.POST.get('Overall GPA')),
				'date_of_birth': request.POST.get('Date of Birth'),
				'year': request.POST.get('Currently Studying'),
				
				'social_total_score': '>400' if social_total_score > 400 else '0-400',
				'social_fraud_risk_score': '>1' if social_fraud_risk_score > 1 else '0-1',
				
				'repayment_plan': prod.repayment_plan,
				}
				
				result = sup_fn.calculate_loan_amount(inputs)
				
				discount_rate = 0
				if code == 200:
					if float(fs_usr_details['score_points']) > 431:
						discount_rate = 0.1
				
				
				ref_num = sup_fn.generate_ref_num('borrow_request', 'LOA')
				amount = min(result['amount'], float(request.POST.get('Applied Amount')))
				
				if prod.repayment_plan == 'Instalment':
					rate_per_month = prod.APR_borrower * (1-discount_rate) * 0.01 / 12
					instalment_borrower = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
					rate_per_month = prod.APR_lender * 0.01 / 12
					instalment_lender = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
				elif prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment':
					rate_per_month = prod.APR_borrower * (1-discount_rate) * 0.01 / 12
					instalment_borrower = amount * rate_per_month
					rate_per_month = prod.APR_lender * 0.01 / 12
					instalment_lender = amount * rate_per_month
				
				bor_detail_info = OrderedDict()
				for name, value in request.POST.iteritems():
					if len(name) != 0:
						if str(name)[0].isupper() and value != '':
							bor_detail_info[name] = value
				
				approval_records = {
					1: {
						'approval_amount': amount,
						'APR': prod.APR_borrower * (1-discount_rate),
						'tenor': prod.repayment_period,
					}
				}
				bor_detail_info['Approval Records'] = approval_records
				
				# if year 1 hasn't GPA
				if request.POST.get('No GPA') == 'on':
					bor_detail_info['Overall GPA'] = 2
				
				
				if result['status'] == 'REJECT':
					status = 'REJECTED'
				else:
					status = 'AUTO APPROVED'
				new_bor = BorrowRequest(
				amount = amount,
				prod_id = prod_id,
				usr_id = usr.id,
				ref_num = ref_num,
				repaid_month = 0,
				instalment_lender = instalment_lender,
				instalment_borrower = instalment_borrower,
				simplified_hkid = simplified_hkid,
				detail_info = json.dumps(bor_detail_info),
				discount_rate = discount_rate,
				status = status,
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_bor.save()
				
				# update aut
				inputs = {
					'usr_id': usr.id,
					'description': 'Submitted "%s" application, apply amount $%s'%(prod.name_en, request.POST.get('Applied Amount')),
					'ref_id': new_bor.id,
					'model': 'BorrowRequest',
					'by': 'Borrower: ' + usr.email,
					'datetime': timezone.localtime(timezone.now()),
					
					'action': 'create',
					'type': 'Application',
					'status': 'UNREAD',
				}
				sup_fn.update_aut(inputs)
				
				inputs = {
					'usr_id': usr.id,
					'description': 'Auto approved $%s, tenor %s, interest rate %s%s'%(amount, prod.repayment_period, prod.APR_borrower * (1-discount_rate), '%'),
					'ref_id': new_bor.id,
					'model': 'BorrowRequest',
					'by': 'Borrower: ' + usr.email,
					'datetime': timezone.localtime(timezone.now()),
					'details': {
						'usr_ip': request.META.get('REMOTE_ADDR')
					},
					'action': 'create',
					'type': 'Application',
					'status': 'UNREAD',
				}
				sup_fn.update_aut(inputs)
				sup_fn.update_ptn(inputs)
				
				# sync to usr
				sync_list  = ['Home Phone No.', 'Surname', 'Given Name', 'Account Number', 'Mobile', 'Gender', 
				'Residential Address', 'Bank Code', 'Living Status', 'Living with', 'Date of Birth', 'HKID', 
				'Studying University', 'Subject']
				sync_dict = {}
				for name in sync_list:
					try:
						sync_dict[name] = bor_detail_info[name]
					except KeyError:
						continue
				sup_fn.sync_to_usr(usr_id=usr.id, dict=sync_dict)
				
				if result['status'] == 'REJECT':
					return redirect('/ack_page/?action=apply_loan_rejected')
				return redirect('/product/upload_docs/?prod_id='+str(prod_id))
			# if form is not valid
			hashkey = CaptchaStore.generate_key()
			image_url = captcha_image_url(hashkey)
			
			usr_details = {}
			for k, v in request.POST.iteritems():
				usr_details[k] = v
		else:
			# Captcha
			form = ''
			hashkey = CaptchaStore.generate_key()
			image_url = captcha_image_url(hashkey)
			usr_details = sup_fn.sync_from_usr(usr.id)
		
		#if lang == 'en':
		content = {
			'lang': lang,
			'cate': 'borrow_now',
			'title': prod.name_en + ' - Application Form',
			'form_action': '?prod_id='+str(prod_id),
			'prod': prod,
			'usr_id': usr.id,
			'usr_details': usr_details,
			#'applied_amount_list': ['5000', '10000', '15000', '20000', '25000', '30000', '35000', '40000'],
			'applied_amount_list': OrderedDict(
				(
					('5000', FLOAT_DATA_FORMAT.format(5000)),
					('10000', FLOAT_DATA_FORMAT.format(10000)),
					('15000', FLOAT_DATA_FORMAT.format(15000)),
					('20000', FLOAT_DATA_FORMAT.format(20000)),
					('25000', FLOAT_DATA_FORMAT.format(25000)),
					('30000', FLOAT_DATA_FORMAT.format(30000)),
					('35000', FLOAT_DATA_FORMAT.format(35000)),
					('40000', FLOAT_DATA_FORMAT.format(40000)),
				)
			),
			'loan_purpose_list': OrderedDict(
				(
					('Tuition', 'Tuition'), 
					('Investment', 'Investment'), 
					('Travel', 'Travel'), 
					('Debt payment', 'Debt payment'), 
					('Others', 'Others')
				)
			),
			'gender_list': OrderedDict(
				(
					('Male', 'Male'), 
					('Female', 'Female')
				)
			),
			'living_status_list': OrderedDict(
				(
					('Public Housing', 'Public Housing'), 
					('Owned by Family', 'Owned by Family'), 
					('Rent', 'Rent'), 
					('Quarter', 'Quarter'), 
					('Student Hall of Residence', 'Student Hall of Residence')
				)
			),
			'living_with_list': OrderedDict(
				(
					('Parents', 'Parents'), 
					('Relatives','Relatives'), 
					('Friends or Classmates', 'Friends or Classmates'), 
					('Others', 'Others')
				)
			),
			'university_list': OrderedDict(
				(
					('The University of Hong Kong', 'The University of Hong Kong'), 
					('The Chinese University of Hong Kong', 'The Chinese University of Hong Kong'), 
					('The Hong Kong University of Science and Technology', 'The Hong Kong University of Science and Technology'), 
					('The Hong Kong Polytechnic University', 'The Hong Kong Polytechnic University'), 
					('City University of Hong Kong', 'City University of Hong Kong'), 
					('Hong Kong Baptist University', 'Hong Kong Baptist University'), 
					('The Hong Kong Institute of Education', 'The Hong Kong Institute of Education'), 
					('Lingnan University', 'Lingnan University'), 
					('The Open University of Hong Kong', 'The Open University of Hong Kong')
				)
			),
			'study_year_list': ['Year 1', 'Year 2', 'Year 3', 'Year 4'],
			'subject_list': OrderedDict(
				(
					('Medical/Health', 'Medical/Health'), 
					('Law', 'Law'), 
					('Accounting', 'Accounting'), 
					('Construction and Environment', 'Construction and Environment'), 
					('Engineering', 'Engineering'), 
					('Design', 'Design'), 
					('Business/Finance/Economic', 'Business/Finance/Economic'), 
					('Education and Language', 'Education and Language'), 
					('Information Technology/Computing', 'Information Technology/Computing'), 
					('Social Sciences', 'Social Sciences'), 
					('Hotel and Tourism', 'Hotel and Tourism'), 
					('Others', 'Others')
				)
			),
			'form': form,
			'hashkey': hashkey,
			'image_url': image_url,
		}
		
		# if prod is promotion, only allow to apply $10000
		if prod.repayment_plan == 'Promotion Balloon Payment':
			content['applied_amount_list'] = OrderedDict(
				(
					('10000', FLOAT_DATA_FORMAT.format(10000)),
				)
			)
		if lang == 'zh':
			additional_content = {
			#'cate': 'borrow_now',
			'title': prod.name_zh.encode("utf8") + ' - 申請表',
			#'form_action': '?prod_id='+str(prod_id),
			#'prod': prod,
			#'usr_id': usr.id,
			#'usr_details': usr_details,
			#'applied_amount_list': ['5000', '10000', '15000', '20000', '25000', '30000', '35000', '40000'],
			'loan_purpose_list': OrderedDict(
				(
					('Tuition', '學費'), 
					('Investment', '投資'), 
					('Travel', '旅遊'), 
					('Debt payment', '還款'), 
					('Others', '其他')
				)
			),
			'gender_list': OrderedDict(
				(
					('Male', '男性'), 
					('Female', '女性')
				)
			),
			'living_status_list': OrderedDict(
				(
					('Public Housing', '公共房屋'), 
					('Owned by Family', '私人住宅'), 
					('Rent', '租住'), 
					('Quarter', '宿舍'), 
					('Student Hall of Residence', '學生宿舍')
				)
			),
			'living_with_list': OrderedDict(
				(
					('Parents', '父母'), 
					('Relatives', '親戚'), 
					('Friends or Classmates', '朋友/同學'), 
					('Others', '其他')
				)
			),
			'university_list': OrderedDict(
				(
					('The University of Hong Kong', '香港大學'), 
					('The Chinese University of Hong Kong', '香港中文大學'), 
					('The Hong Kong University of Science and Technology', '香港科技大學'), 
					('The Hong Kong Polytechnic University', '香港理工大學'), 
					('City University of Hong Kong', '香港城市大學'), 
					('Hong Kong Baptist University', '香港浸會大學'), 
					('The Hong Kong Institute of Education', '香港教育大學'), 
					('Lingnan University','嶺南大學'), 
					('The Open University of Hong Kong', '香港公開大學')
				)
			),
			'study_year_list': ['Year 1', 'Year 2', 'Year 3', 'Year 4'],
			'subject_list': OrderedDict(
				(
					('Medical/Health', '醫療/健康'), 
					('Law', '法律'), 
					('Accounting', '會計'), 
					('Construction and Environment', '建築及環境'), 
					('Engineering', '工程'), 
					('Design', '設計'), 
					('Business/Finance/Economic', '商業/財務/經濟'), 
					('Education and Language','教育及語言'), 
					('Information Technology/Computing','資訊科技/電子計算'), 
					('Social Sciences', '社會科學'), 
					('Hotel and Tourism', '酒店及旅遊'), 
					('Others', '其他')
				)
			),
			#'form': form,
			#'hashkey': hashkey,
			#'image_url': image_url,
			}
			content.update(additional_content)
		
		return render(request, 'peerloan/borrower/loan_application_form.html', content)
	if action == 'upload_docs':
		prod_id = request.GET.get('prod_id')
		prod = Product.objects.get(id=prod_id)
		bor = BorrowRequest.objects.filter(usr_id=usr.id, prod_id=prod_id, status="AUTO APPROVED").latest('update_timestamp')
		
		# get repayment table
		inputs = {
			'date_type': 'month only',
			'start_balance': bor.amount,
			'rate_per_month': bor.getBorAPR(prod.APR_borrower) * 0.01 / 12,
			'instalment': bor.instalment_borrower,
			'repayment_plan': prod.repayment_plan,
			'repayment_period': prod.repayment_period,
		}
			
		repayment_table = sup_fn.generate_repayment_schedule(inputs)
		
		bank_code_list = {}
		f = open('/home/ubuntu/project_peerloan/peerloan/peerloan_src/bank_code_list.csv', 'r')
		for row in csv.DictReader(f):
			bank_code_list[str(row['Bank_Code']).zfill(3)] = row['Bank_Name_in_English']
		f.close()
		bank_code_list = OrderedDict(sorted(bank_code_list.items(), key=lambda kv: kv[1]))
		
		content = {
		'lang': lang,
		'cate': 'borrow_now',
		'title': prod.name_en + ' - Upload Supporting Documents',
		'form_action': '/ack/',
		'prod': prod,
		'usr_details': sup_fn.sync_from_usr(usr.id),
		'bor': bor,
		'bor_amount': FLOAT_DATA_FORMAT.format(bor.amount),
		'APR': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower)),
		'monthly_repayment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
		'repayment_table': repayment_table,
		'bank_code_list': bank_code_list,
		}
		if lang == 'zh':
			content['title'] = prod.name_zh.encode("utf8") + ' - 上載申請文件'
		return render(request, 'peerloan/borrower/loan_upload_docs_form.html', content)
	if action == 'confirm_agreement':
		prod_id = request.GET.get('prod_id')
		prod = Product.objects.get(id=prod_id)
		bor = BorrowRequest.objects.filter(prod_id=prod_id, usr_id=usr.id, status='DOC UPLOADED').latest('update_timestamp')
		details = json.loads(bor.detail_info)
		
		if prod.repayment_plan == 'Promotion Balloon Payment':
			start_month = 4
		else:
			start_month = 1
		
		end_month = prod.repayment_period
		start_date = sup_fn.check_future_date_exists(timezone.localtime(timezone.now()), months=start_month)
		end_date = sup_fn.check_future_date_exists(timezone.localtime(timezone.now()), months=end_month)
		
		if prod.repayment_plan == 'Instalment':
			last_instalment_amount = round(bor.instalment_borrower, 2)
		elif prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment':
			last_instalment_amount = round(bor.instalment_borrower + bor.amount, 2)
			
		info = {
		'loan_agreement_date': datetime.strftime(bor.create_timestamp, '%d/%m/%Y'),
		'loan_drawdown_date': datetime.strftime(timezone.localtime(timezone.now()), '%d/%m/%Y'),
		'lender': 'P L Technology Limited',
		'lender_licence_no': '0741/2016',
		'address': 'Unit 1306, Lucky Centre, 165-171 Wanchai Road, Wanchai',
		'borrower': '%s %s' % (details['Surname'], details['Given Name']),
		'HKID': details['HKID'],
		'residential_address': details['Residential Address'],
		'loan_principal_amount': FLOAT_DATA_FORMAT.format(bor.amount),
		'interest_rate': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower)),
		'instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
		'due_date': str(timezone.localtime(timezone.now()).day) + sup_fn.date_postfix(timezone.localtime(timezone.now()).day) + ' day of each calendar',
		'first_instalment': start_date.strftime('%Y/%m/%d'),
		'first_instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
		'last_instalment': end_date.strftime('%Y/%m/%d'),
		'last_instalment_amount': FLOAT_DATA_FORMAT.format(last_instalment_amount),
		'bank_name': details['Bank Code'] + ' ' + sup_fn.bank_code_name_converter(details['Bank Code']),
		'account_number': details['Account Number'],
		'account_holder': '%s %s' % (details['Surname'], details['Given Name']),
		'mobile': details['Mobile'],
		}
		if lang == 'zh':
			info['due_date'] = '每月的第'+str(timezone.localtime(timezone.now()).day).encode("utf8")+'天'
		
		content = {
		'lang': lang,
		'cate': 'borrow_now',
		'title': 'Key Terms of Personal Loan Agreement',
		'form_action': '/ack/',
		'info': info,
		'bor_id': bor.id,
		'bor_ref_num': bor.ref_num
		}
		if lang == 'zh':
			content['title'] = '私人貸款協議之主要條款'
		
		error = request.GET.get('error')
		if lang == 'en':
			if error == 'invalid_OTP':
				content['error_msg'] = 'Please input a valid OTP'
			if error == 'OTP_not_matched':
				content['error_msg'] = 'The OTP doesn\'t match to our record, please receive a new OTP and try again'
			if error == 'OTP_expired':
				content['error_msg'] = 'The OTP is expired, please receive a new OTP first'
		elif lang == 'zh':
			if error == 'invalid_OTP':
				content['error_msg'] = '請輸入一個有效的OTP'
			if error == 'OTP_not_matched':
				content['error_msg'] = '你輸入的OTP與我們的記錄不符合，請重新操作'
			if error == 'OTP_expired':
				content['error_msg'] = '你的OTP已經逾期，請重新獲取OTP'
		
		return render(request, 'peerloan/borrower/loan_agreement_form.html', content)
	if action == 'confirm_memorandum':
		prod_id = request.GET.get('prod_id')
		prod = Product.objects.get(id=prod_id)
		bor = BorrowRequest.objects.filter(prod_id=prod_id, usr_id=usr.id, status='FUND MATCHING COMPLETED').latest('update_timestamp')
		if request.method == 'POST':
			form = CaptchaForm(request.POST)
			if form.is_valid():
				draw_down_date = sup_fn.find_earliest_business_day(date=timezone.localtime(timezone.now()), cut_off=16)
				details = json.loads(bor.detail_info)
				details['Confirm Memorandum Date'] = datetime.strftime(draw_down_date, '%Y/%m/%d %H:%M:%S')
				details['Memorandum Captcha'] = str(request.POST.get('captcha_1'))
				bor.detail_info = json.dumps(details)
				bor.status = 'MEMORANDUM CONFIRMED'
				bor.update_timestamp = timezone.localtime(timezone.now())
				bor.save()
				
				# update aut
				inputs = {
					'usr_id': usr.id,
					'description': 'Confirmed memorandum with Captcha%s'%(request.POST.get('captcha_1')),
					'ref_id': bor.id,
					'model': 'BorrowRequest',
					'by': 'Borrower: ' + usr.email,
					'datetime': timezone.localtime(timezone.now()),
					
					'action': 'modify',
					'type': 'Disburse',
					'status': 'UNREAD',
				}
				sup_fn.update_aut(inputs)
				sup_fn.update_ptn(inputs)
				action = 'confirm_memorandum'
				
				return redirect('/ack_page/?action='+action)
				
			hashkey = CaptchaStore.generate_key()
			image_url = captcha_image_url(hashkey)
		else:
			# Captcha
			form = ''
			hashkey = CaptchaStore.generate_key()
			image_url = captcha_image_url(hashkey)
		
		details = json.loads(bor.detail_info)
		
		draw_down_date = sup_fn.find_earliest_business_day(date=timezone.localtime(timezone.now()), cut_off=16)
		
		if prod.repayment_plan == 'Promotion Balloon Payment':
			start_month = 4
		else:
			start_month = 1
		
		end_month = prod.repayment_period
		start_date = sup_fn.check_future_date_exists(draw_down_date, months=start_month)
		end_date = sup_fn.check_future_date_exists(draw_down_date, months=end_month)
		
		if prod.repayment_plan == 'Instalment':
			last_instalment_amount = round(bor.instalment_borrower, 2)
		elif prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment':
			last_instalment_amount = round(bor.instalment_borrower + bor.amount, 2)
			
		info = {
		'loan_agreement_date': datetime.strftime(bor.create_timestamp, '%d/%m/%Y'),
		'loan_drawdown_date': datetime.strftime(draw_down_date, '%d/%m/%Y'),
		'lender': 'P L Technology Limited',
		'lender_licence_no': '0741/2016',
		'address': 'Unit 1306, Lucky Centre, 165-171 Wanchai Road, Wanchai',
		'borrower': '%s %s' % (details['Surname'], details['Given Name']),
		'HKID': details['HKID'],
		'residential_address': details['Residential Address'],
		'loan_principal_amount': FLOAT_DATA_FORMAT.format(bor.amount),
		'interest_rate': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower)),
		'instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
		'due_date': str(draw_down_date.day) + sup_fn.date_postfix(draw_down_date.day) + ' day of each calendar',
		'first_instalment': start_date.strftime('%Y/%m/%d'),
		'first_instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
		'last_instalment': end_date.strftime('%Y/%m/%d'),
		'last_instalment_amount': FLOAT_DATA_FORMAT.format(last_instalment_amount),
		'bank_name': details['Bank Code'] + ' ' + sup_fn.bank_code_name_converter(details['Bank Code']),
		'account_number': details['Account Number'],
		'account_holder': '%s %s' % (details['Surname'], details['Given Name']),
		'mobile': details['Mobile'],
		}
		if lang == 'zh':
			info['due_date'] = '每月的第'+str(draw_down_date.day).encode("utf8")+'天'
		
		content = {
		'lang': lang,
		'cate': 'borrow_now',
		'title': 'Memorandum of Agreement',
		'form_action': '?prod_id='+str(prod_id),
		'info': info,
		
		'form': form,
		'hashkey': hashkey,
		'image_url': image_url,
		}
		if lang == 'zh':
			content['title'] = '協議備忘錄'
		return render(request, 'peerloan/borrower/loan_memorandum_form.html', content)
	if action == 'invest':
		prod_id = request.GET.get('prod_id')
		prod = Product.objects.get(id=prod_id)
		acc = Account.objects.get(usr_id=usr.id)
		total_usable_amount = acc.balance
		try:
			inv = Investment.objects.get(usr_id=usr.id, prod_id=prod_id)
		except ObjectDoesNotExist:
			# set up new inv
			inv = {'total_amount': total_usable_amount, 'used_amount': 0}
			content = {
			'prod': prod,
			'total_usable_amount': total_usable_amount,
			'inv': inv,
			'sub_cate': prod_id,
			'used_percentage': 0,
			'lang': lang,
			}
			if lang == 'en':
				content['title'] = 'Setting Up Your Investment - ' + prod.name_en
				content['instruction'] = """The below investment settings define how you invest the money in this product. After 
				you filled up the below form, Peerloan will allocate your investment fund to the selected product automatically."""
			if lang == 'zh':
				content['title'] = '設置你的投資 - ' + prod.name_zh_hk
				content['instruction'] = """以下投資設置詳述你將如何投資該產品。在你完成以下表格之後，點點眾貸將會自動地分配你的投資資金到該產品。"""
		else:
			# change inv settings
			total_usable_amount += inv.usable_amount + inv.on_hold_amount
			
			try:
				used_percentage = round(( (inv.on_hold_amount/prod.min_amount_per_loan) / int(total_usable_amount/prod.min_amount_per_loan) )*100+1, 1)
			except ZeroDivisionError:
				used_percentage = 0
			content = {
			'prod': prod,
			'total_usable_amount': total_usable_amount,
			'inv': inv,
			'used_percentage': used_percentage,
			'lang': lang,
			}
			if lang == 'en':
				content['title'] = 'Change Your Investment Setting - ' + prod.name_en
				content['instruction'] = """The below investment settings define how you invest the money in this product. After 
				you filled up the below form, Peerloan will allocate your investment fund to the selected product automatically."""
			if lang == 'zh':
				content['title'] = '更換你的投資設置 - ' + prod.name_zh_hk
				content['instruction'] = """以下投資設置詳述你將如何投資該產品。在你完成以下表格之後，點點眾貸將會自動地分配你的投資資金到該產品。"""
		return render(request, 'peerloan/lender/invest_form.html', content)
	if action == 'transfer':
		inv_list = Investment.objects.filter(usr_id=usr.id)
		rd_prod_list = []
		for inv in inv_list:
			prod = Product.objects.get(id=inv.prod_id)
			rd_prod_list.append({'prod_id':str(prod.id), 'prod_name':str(prod.name_en), 'usable_amount':str(inv.usable_amount)})
		content = {
		'prod_list': rd_prod_list,
		
		}
		if lang == 'en':
			content['title'] = 'Transfer Fund Between Products'
			content['instruction'] = """Please specify the amount of fund you would like to switch from this portfolio to another portfolio. 
			The instruction will be executed immediately."""
		if lang == 'zh':
			content['title'] = '資金轉賬'
			content['instruction'] = """請說明你希望的轉賬金額及收賬的投資組合。該指示將會被立即執行。"""
		return render(request, 'peerloan/lender/transfer_form.html', content)