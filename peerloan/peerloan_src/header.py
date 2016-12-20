# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

import peerloan.peerloan_src.supporting_function as sup_fn

from peerloan.decorators import require_login
from peerloan.models import BorrowRequest
from peerloan.models import Product
from peerloan.models import PendingTaskNotification
from peerloan.models import User
from peerloan.models import AdminUser
from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest

import csv
import json
from collections import OrderedDict
from datetime import datetime
from django.utils import timezone
import pytz

FLOAT_DATA_FORMAT = '{:,.2f}'

@require_login
def header(request):
	user = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	http_referer = request.META.get('PATH_INFO')
	# get category and sub-category to active the button
	if len(http_referer.split('/')) > 2:
		cate = http_referer.split('/')[2]
		if len(http_referer.split('/')) > 3:
			sub_cate = http_referer.split('/')[3]
		else:
			sub_cate = ''
	else:
		cate, sub_cate = '', ''
	
	last_login = user.last_login
	if last_login == None:
		last_login = user.this_login
	last_login = timezone.localtime(last_login)
	
	content = {
	'usr':user,
	'cate': cate,
	'sub_cate': sub_cate,
	'lang':lang,
	'last_login': last_login.strftime('%Y/%m/%d %H:%M'),
	}
	if user.type == 'L':
		return render(request, 'peerloan/lender/header.html', content)
	elif user.type == 'B':
		return render(request, 'peerloan/borrower/header.html', content)
	elif len(AdminUser.objects.filter(email=user.email)) != 0:
		side = request.session['handling_side']
		
		ptn_list = PendingTaskNotification.objects.filter(status='UNREAD')
		
		if side == 'B':
			application_ptn_no = 0
			disburse_ptn_no = 0
			repayment_ptn_no = 0
			for ptn in ptn_list:
				if ptn.type == 'Application':
					application_ptn_no += 1
				elif ptn.type == 'Disburse':
					disburse_ptn_no += 1
				elif ptn.type == 'Repayment':
					repayment_ptn_no += 1
					
			ptn_cnt = {
			'application': application_ptn_no,
			'disbursement': disburse_ptn_no,
			'repayment': repayment_ptn_no
			}
			for k, v in ptn_cnt.iteritems():
				if v == 0:
					ptn_cnt[k] = ''
			content['ptn_cnt'] = ptn_cnt
			return render(request, 'peerloan/admin/borrower/header.html', content)
		if side == 'L':
			ptn_cnt = {
			'application': len([ptn for ptn in ptn_list if ptn.type == 'Apply To Be Investor']),
			'deposit': len([ptn for ptn in ptn_list if ptn.type == 'Deposit Money']),
			'cash_out': len([ptn for ptn in ptn_list if ptn.type == 'Withdraw Money']),
			}
			for k, v in ptn_cnt.iteritems():
				if v == 0:
					ptn_cnt[k] = ''
			content['ptn_cnt'] = ptn_cnt
			return render(request, 'peerloan/admin/lender/header.html', content)

@require_login
def footer(request):
	user = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	if user.type == 'L':
		content = {'lang': lang,}
		return render(request, 'peerloan/lender/footer.html', content)
		
	if user.type == 'B':
		content = {'lang': lang,}
		return render(request, 'peerloan/borrower/footer.html', content)

@require_login
def borrow_now(request):
	user = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	prod_list = Product.objects.filter(status='ACTIVE')
	rd_prod_list = []
	for prod in prod_list:
		# calculate the installment
		rate_per_month = prod.APR_borrower * 0.01 / 12
		
		if prod.repayment_plan == 'Instalment':
			instalment_borrower = prod.min_amount * (rate_per_month / (1- (1 + rate_per_month)**(-(prod.repayment_period/12)*12)))
		
		if prod.repayment_plan == 'Balloon Payment':
			instalment_borrower = prod.min_amount * rate_per_month
		
		# check num of applied prod
		bor_list = BorrowRequest.objects.filter(usr_id=user.id)
		bor_list = [bor for bor in bor_list if bor.status not in ['PAYBACK COMPLETED', 'REJECTED', 'CANCELLED']]
		num_of_applied_prod = len(bor_list)
		
		# check which step
		if num_of_applied_prod != 0:
			step = 'auto_reject'
		else:
			try:
				bor = BorrowRequest.objects.filter(usr_id=user.id, prod_id=prod.id).latest('update_timestamp')
			except ObjectDoesNotExist:
				if num_of_applied_prod == 0:
					step = 'apply'
				else:
					step = 'auto_reject'
			else:
				if bor.status == 'AUTO APPROVED':
					step = 'upload_docs'
				elif bor.status == 'DOC UPLOADED':
					step = 'confirm_agreement'
				elif bor.status == 'PAYBACK COMPLETED' or bor.status == 'REJECTED' or bor.status == 'CANCELLED':
					step = 'apply'
				elif bor.status == 'FUND MATCHING COMPLETED':
					step = 'confirm_memorandum'
				else: # status = draw down, repay, ...
					step = 'auto_reject'
					
		if lang == 'en':
			prod_name = prod.name_en
		elif lang == 'zh':
			prod_name = prod.name_zh
		
		rd_prod_list.append({
		'id': prod.id,
		'name': prod_name,
		#'min_amount': int(prod.min_amount),
		'min_amount': FLOAT_DATA_FORMAT.format(prod.min_amount),
		
		'total_amount': FLOAT_DATA_FORMAT.format(prod.total_amount),
		'APR_borrower': FLOAT_DATA_FORMAT.format(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower),
		'repayment_period': prod.repayment_period if prod.fake_repayment_period == None else prod.fake_repayment_period,
		'instalment_borrower': FLOAT_DATA_FORMAT.format(instalment_borrower),
		'step': step,
		})
	content = {
	'lang': lang,
	'cate': 'borrow_now',
	'prod_list': rd_prod_list,
	}
	return render(request, 'peerloan/borrower/borrow_now.html', content)

@require_login
def invest_now(request):
	user = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	if 'start_investing' in request.META.get('PATH_INFO').split('/'):
		rd_prod_list = [['all','All Products']]
		prod_list = Product.objects.filter(status='ACTIVE')
		for prod in prod_list:
			rd_prod_list.append([prod.id,prod.name_en])
		content = {
		'cate': 'invest_now',
		'prod_list': rd_prod_list,
		}
		return render(request, 'peerloan/lender/start_invest.html', content)
	
	prod_list = Product.objects.filter(status='ACTIVE')
	rd_prod_list = []
	
	for prod in prod_list:
		details = {
		'prod_name': prod.name_en,
		'total_amount': prod.total_amount,
		'APR': prod.APR_lender,
		'flat_rate': prod.flat_rate_lender,
		'repayment_period': prod.repayment_period,
		'amount_per_unit': prod.min_amount_per_loan,
		'min_inv_unit_per_loan': 1,
		'max_inv_unit_per_loan': int(prod.total_amount / prod.min_amount_per_loan),
		'prod_id': prod.id,
		}
		rd_prod_list.append(details)
	
	
	content = {
	'cate': 'invest_now',
	'prod_list': rd_prod_list,
	}
	return render(request, 'peerloan/lender/invest_now.html', content)

@require_login
def switch_role(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	if usr.type == 'L':
		request.session['type'] = 'B'
		
		# upate borrower last login
		b_usr = User.objects.get(email=usr.email,type='B')
		b_usr.this_login = timezone.localtime(timezone.now())
		b_usr.save()
		return redirect('/borrow_now')
	elif usr.type == 'B':
		if len(User.objects.filter(email = usr.email, status = 'ACTIVE')) == 2:
			request.session['type'] = 'L'
			return redirect('/portfolio/portfolio_summary')
		else:
			return redirect('/apply_to_be_investor')
	elif len(AdminUser.objects.filter(email=usr.email)) != 0:
		if request.session['handling_side'] == 'L':
			request.session['handling_side'] = 'B'
		elif request.session['handling_side'] == 'B':
			request.session['handling_side'] = 'L'
		return redirect('/pl_admin/application')
		
#@require_login
def change_lang(request):
	lang = request.GET.get('lang')
	request.session['language'] = lang
	return redirect(request.META.get('HTTP_REFERER'))

@require_login
def apply_to_be_investor(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	try:
		uor = UserOperationRequest.objects.filter(usr_id=usr.id, type="Apply To Be Investor").latest('create_timestamp')
	except ObjectDoesNotExist:
		# the first time apply
		
		nationality_list = []
		f = open('/home/ubuntu/project_peerloan/peerloan/peerloan_src/nationality.csv', 'r')
		for row in csv.DictReader(f):
			nationality_list.append(row['Nationality'])
		f.close()
		
		country_list = []
		f = open('/home/ubuntu/project_peerloan/peerloan/peerloan_src/countries_of_the_world.csv', 'r')
		for row in csv.DictReader(f):
			country_list.append(row['Country'])
		f.close()
		"""
		buttons = []
		buttons.append({"name": "Submit", "type":"submit"})
		buttons.append({"name": "Back", "type":"button", "onclick":"window.history.back()"})
		"""
		
		content = {
		'lang': lang,
		'title': 'Lender Application Form',
		'form_action': '/ack/',
		'nationality_list': nationality_list,
		'country_list': country_list,
		'usr_details': sup_fn.sync_from_usr(usr.id),
		'gender_list': OrderedDict(
			(
				('Male', 'Male'),
				('Female', 'Female')
			)
		),
		#'buttons': buttons,
		}
		if lang == 'zh':
			content['title'] = '貸方申請表'
			additional_content = {
				'gender_list':OrderedDict(
					(
						('Male', '男性'), 
						('Female', '女性')
					)
				),
			}
			content.update(additional_content)
		return render(request, 'peerloan/borrower/investor_application_form.html', content)
	else:
		# approved
		if uor.status == 'APPROVED':
			details = json.loads(uor.details)
			content = {
			'lang': lang,
			'title': 'Agreement',
			'form_action': '/ack/',
			'mobile': details['Individual']['Mobile'],
			'uor_id': uor.id,
			}
			if lang == 'zh':
				content['title'] = '合約'
			
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
			
			return render(request, 'peerloan/borrower/investor_agreement_form.html', content)
			
		# wait for approval
		elif uor.status == 'DOC UPLOADED' or uor.status == 'PENDING DOC/IV':
			if lang == 'en':
				details = json.loads(uor.details, object_pairs_hook=OrderedDict)
				for k, v in details['File Uploaded'].iteritems():
					details['File Uploaded'][k] = '<a href="/file/'+v+'" target="_blank">View</a>'
				buttons = []
				buttons.append({"name": "Print Acknowledgement", "type":"button", "onclick":"javascript:window.print()"})
				
				content = {
				'lang': lang,
				'title': 'Lender Application - Acknowledgement',
				'form_action': 'javascript:;',
				'instruction': """Thank you for your application. We will process your application within 1 business day and notice you the application result by SMS and email.""",
				'details': details,
				'buttons': buttons,
				}
			elif lang == 'zh':
				en2zh_dict = {
					'Account Type': '戶口類型',
					'Individual': '個人',
					'Corporate': '企業',
					'File Uploaded': '上載文件',
					
					'Company Name': '公司名稱',
					'Established at': '成立日期',
					'CR NO.': '公司註冊號碼',
					'Office Address': '公司地址',
					'Company Size': '公司規模',
					'more than 500': '多於 500',
					'Office Tel': '公司電話',
					'Industry': '行業',
					
					'Surname': '姓氏',
					'Given Name': '名',
					'Gender': '性別',
					'Male': '男性',
					'Female': '女性',
					
					'Education Level': '教育程度',
					'Primary School': '小學',
					'Secondary School': '中學',
					'Tertiary': '專上學院',
					'Bachelors': '大學',
					'Masters or above': '碩士或以上',
					
					'HKID': '香港身份證號碼',
					'Nationality': '國籍',
					'Date of Birth': '出生日期',
					'Occupation': '職業',
					'Type of Employment': '受僱類型',
					'Full Time Employed': '全職',
					'Part Time Employed': '兼職',
					'Self-Employed': '自僱',
					'Unemployed': '待業',
					'Housewife': '家庭主婦',
					'Retired': '退休',
					
					'Annual Income': '年收入',
					'Residential Address': '住宅地址',
					'Home Phone No.': '住宅電話',
					'Mobile': '手提電話',
					'Source of Fund': '資金來源',
					'Salary': '薪金',
					'Business': '生意',
					'Investment': '投資',
					'Others': '其他',
					
					'Other Source of Fund': '其他資金來源',
					'Customer Declaration': '顧客聲明',
					'Application No': '申請編號',
					
					'HKID Proof': '香港身份證證明',
					'Address Proof': '住址證明',
					'BR/CR': '商業登記證/公司註冊證明書',
				}
				details = json.loads(uor.details, object_pairs_hook=OrderedDict)
				for k, v in details['File Uploaded'].iteritems():
					details['File Uploaded'][k] = '<a href="/file/'+v.encode('utf8')+'" target="_blank">瀏覽</a>'
				
				zh_details = OrderedDict()
				for section, fields in details.iteritems():
					zh_details[en2zh_dict[section]] = OrderedDict()
					for k, v in details[section].iteritems():
						zh_v = sup_fn.try_KeyError(en2zh_dict, v)
						if zh_v != '--':
							zh_details[en2zh_dict[section]][en2zh_dict[k]] = zh_v
						else:
							zh_details[en2zh_dict[section]][en2zh_dict[k]] = v
							
				
				buttons = []
				buttons.append({"name": "列印通知", "type":"button", "onclick":"javascript:window.print()"})
				
				content = {
				'lang': lang,
				'title': '確認通知 - 貸方申請已收到',
				'form_action': 'javascript:;',
				'instruction': """感謝你的申請，我們會於一個工作天內處理你的申請，並以手機短訊及電郵通知你申請結果。""",
				'details': zh_details,
				'buttons': buttons,
				}
			return render(request, 'peerloan/borrower/form_with_section.html', content)
		elif uor.status == 'REJECTED' or uor.status == 'CANCELLED':
			content = {
			'lang': lang,
			'title': 'Application State Changed - Acknowledgement',
			'instruction': """Thank you for your application. Unfortunately, we are sorry to inform you that your application have been %s. Please contact
			admin for more information.""" % (uor.status),
			}
			if lang == 'zh':
				content = {
				'lang': lang,
				'title': '確認通知 - 申請狀態更變',
				'instruction': """感謝你的申請， 我們很遺憾地通知你，你的申請未能成功批核。""",
				}
			return render(request, 'peerloan/borrower/acknowledgement.html', content)

@require_login
def lender_agreement(request):
	int2word = {
		1:'First', 2:'Second', 3:'Third', 4:'Fourth', 5:'Fifth',
		6:'Sixth', 7:'Seventh', 8:'Eighth', 9:'Ninth', 10:'Tenth',
		11:'Eleventh', 12:'Twelfth', 13:'Thirteenth', 14:'Fourteenth', 15:'Fifteenth',
		16:'Sixteenth', 17:'Seventeenth', 18:'Eighteenth', 19:'Nineteenth', 20:'Twentieth',
		21:'Twenty-First', 22:'Twenty-Second', 23:'Twenty-Third', 24:'Twenty-Fourth', 25:'Twenty-Fifth',
		26:'Twenty-Sixth', 27:'Twenty-Seventh', 28:'Twenty-Eighth', 29:'Twenty-Ninth', 30:'Thirtieth', 31:'Thirty-First',
	}
	date = {
		'day': str(datetime.now().day)+sup_fn.date_postfix(datetime.now().day),
		'month': datetime.now().strftime('%B'),
		'year': str(datetime.now().year)
	}
	
	uor_id = request.GET.get('uor_id')
	uor = UserOperationRequest.objects.get(id=uor_id)
	details = json.loads(uor.details)
	
	try: # check which type of application
		details['Corporate']
	except KeyError:
		infos = {
			'account_type': 'Individual',
			'name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'hkid': details['Individual']['HKID'],
			'address': details['Individual']['Residential Address'],
		}
	else:
		infos = {
			'account_type': 'Corporate',
			'company_name': details['Corporate']['Company Name'],
			'company_no': details['Corporate']['CR NO.'],
			'address': details['Corporate']['Office Address'],
		}
	content = {
	'date': date,
	'infos': infos,
	}
	return render(request, 'peerloan/borrower/lender_agreement.html', content)

@require_login
def loan_agreement(request):
	lang = sup_fn.get_lang(request)
	bor_ref_num = request.GET.get('bor_ref_num')
	bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
	prod = Product.objects.get(id=bor.prod_id)
	content = {
		'lang': lang,
		'LOAN_AMOUNT': FLOAT_DATA_FORMAT.format(bor.amount),
		'MONTH_RATE': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower)/12)+'%',
	}
	return render(request, 'peerloan/borrower/loan_agreement.html', content)