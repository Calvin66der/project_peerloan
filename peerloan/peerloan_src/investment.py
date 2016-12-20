# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from peerloan.decorators import require_login

from peerloan.models import Account
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import Product
from peerloan.models import Loan

from peerloan.decorators import require_login

import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
from django.utils import timezone
from collections import OrderedDict
import csv
import json

FLOAT_DATA_FORMAT = '{:,.2f}'

@require_login
def investment(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	action = request.META.get('PATH_INFO').split('/')[2]
	
	if action == 'invest_now':
		if 'product_details' in request.META.get('PATH_INFO').split('/'):
			prod_list = Product.objects.filter(status='ACTIVE')
			prod_list = [prod for prod in prod_list if prod.repayment_plan != 'Promotion Balloon Payment']
			
			if lang == 'en':
				thead_list = [
					'Product Name', 'Maximum Amount Per Loan (HK$)', 'Expected Annualised Return (%)', 'Repayment Period (months)',
					'Amount Per Unit (HK$/month)', 'Investment Unit Per Loan',
					'Expected Returning Schedule (Per Unit)'
				]
			elif lang == 'zh':
				thead_list = [
					'產品名稱', '每筆貸款的最高金額 (HK$)', '預期年回報 (%)', '還款期 (月)',
					'每單位金額 (HK$/月)', '每筆貸款的投資單位',
					'預計收回貸款時間表 (每單位)'
				]
				
			tdata_list = []
			
			for prod in prod_list:
				if lang == 'en':
					tdata = [
					prod.name_en, FLOAT_DATA_FORMAT.format(prod.total_amount), FLOAT_DATA_FORMAT.format(prod.APR_lender), 
					prod.repayment_period, FLOAT_DATA_FORMAT.format(prod.min_amount_per_loan), '1-' + str(int(prod.total_amount/prod.min_amount_per_loan)),
					'<a href=\'javascript:window.open("/loan_repay_schedule/?prod_id='+str(prod.id)+'","contestrules", "menubar=0,resizable=0,width=1000,height=800");\'><button class="btn green-jungle">Browse</button></a>'
					]
				elif lang == 'zh':
					tdata = [
					prod.name_zh, FLOAT_DATA_FORMAT.format(prod.total_amount), FLOAT_DATA_FORMAT.format(prod.APR_lender), 
					prod.repayment_period, FLOAT_DATA_FORMAT.format(prod.min_amount_per_loan), '1-' + str(int(prod.total_amount/prod.min_amount_per_loan)),
					'<a href=\'javascript:window.open("/loan_repay_schedule/?prod_id='+str(prod.id).encode('utf8')+'","contestrules", "menubar=0,resizable=0,width=1000,height=800");\'><button class="btn green-jungle">瀏覽</button></a>'
					]
				tdata_list.append(tdata)
			
			content = {
			'lang': lang,
			'caption': 'Product List',
			'thead_list': thead_list,
			'tdata_list': tdata_list
			}
			if lang == 'zh':
				content['caption'] = '產品列表'
			return render(request, 'peerloan/lender/table.html', content)
			
		acc = Account.objects.get(usr_id=usr.id)
		inv_list = Investment.objects.filter(usr_id=usr.id)
		prod_list = Product.objects.filter(status='ACTIVE')
		prod_list = [prod for prod in prod_list if prod.repayment_plan != 'Promotion Balloon Payment']
		
		rd_prod_list = []
		for prod in prod_list:
			try:
				inv = Investment.objects.get(usr_id=usr.id, prod_id=prod.id)
			except ObjectDoesNotExist:
				existed_investment = 0
				on_hold_investment = 0
				max_amt_per_loan = 'Not set'
			else:
				existed_investment = inv.usable_amount
				on_hold_investment = inv.on_hold_amount
				max_amt_per_loan = inv.max_amount_per_loan
			rd_prod_list.append({
				'id': str(prod.id),
				'name_en': str(prod.name_en),
				'name_zh': prod.name_zh.encode('utf8'),
				'min_amount_per_loan': str(prod.min_amount_per_loan),
				'total_amount': str(prod.total_amount),
				'existed_investment': existed_investment,
				'str_existed_investment': FLOAT_DATA_FORMAT.format(existed_investment),
				'on_hold_investment': on_hold_investment,
				'str_on_hold_investment': FLOAT_DATA_FORMAT.format(on_hold_investment),
				'max_amt_per_loan': FLOAT_DATA_FORMAT.format(max_amt_per_loan) if max_amt_per_loan !='Not set' else max_amt_per_loan,
			})
		
		disbursed_amount = 0
		for inv in inv_list:
			loan_list = Loan.objects.filter(inv_id=inv.id)
			disbursed_amount += sum([loan.remain_principal_lender for loan in loan_list if 'PAYBACK' in loan.status])
		
		content = {
		'lang': lang,
		'cate': 'investment',
		'sub_cate': 'invest_now',
		'title': 'Invest Now',
		#'account_balance': '%.2f'%(acc.balance + sum([inv.total_amount for inv in inv_list]) + disbursed_amount),
		'account_balance': '%.2f'%(acc.balance + sum([inv.usable_amount+inv.on_hold_amount for inv in inv_list]) + disbursed_amount),
		'str_account_balance': FLOAT_DATA_FORMAT.format(acc.balance + sum([inv.usable_amount+inv.on_hold_amount for inv in inv_list]) + disbursed_amount),
		'unallocated': '%.2f'%(acc.balance),
		'str_unallocated': FLOAT_DATA_FORMAT.format(acc.balance),
		'prod_list': rd_prod_list
		}
		if lang == 'zh':
			content['title'] = ' 開始投資'
		return render(request, 'peerloan/lender/invest_now.html', content)
	elif action == 'reallocate_fund':
		acc = Account.objects.get(usr_id=usr.id)
		inv_list = Investment.objects.filter(usr_id=usr.id)
		prod_list = Product.objects.filter(status='ACTIVE')
		prod_list = [prod for prod in prod_list if prod.repayment_plan != 'Promotion Balloon Payment']
		
		rd_prod_list = []
		for prod in prod_list:
			try:
				inv = Investment.objects.get(usr_id=usr.id, prod_id=prod.id)
			except ObjectDoesNotExist:
				existed_investment = 0
				on_hold_investment = 0
				investment_setting = '--'
				max_amount_per_loan = 0
			else:
				existed_investment = round(inv.usable_amount, 2)
				on_hold_investment = round(inv.on_hold_amount, 2)
				investment_setting = inv.option
				max_amount_per_loan = round(inv.max_amount_per_loan, 2)
			rd_prod_list.append({
				'id': str(prod.id),
				'name_en': str(prod.name_en),
				'name_zh': prod.name_zh.encode('utf8'),
				'min_amount_per_loan': str(prod.min_amount_per_loan),
				'total_amount': str(prod.total_amount),
				'existed_investment': existed_investment,
				'str_existed_investment': FLOAT_DATA_FORMAT.format(existed_investment),
				'on_hold_investment': on_hold_investment,
				'str_on_hold_investment': FLOAT_DATA_FORMAT.format(on_hold_investment),
				'investment_setting': str(investment_setting),
				'max_amount_per_loan': max_amount_per_loan,
				'str_max_amount_per_loan': FLOAT_DATA_FORMAT.format(max_amount_per_loan)
			})
		
		disbursed_amount = 0
		for inv in inv_list:
			loan_list = Loan.objects.filter(inv_id=inv.id)
			disbursed_amount += sum([loan.remain_principal_lender for loan in loan_list if 'PAYBACK' in loan.status])
		
		content = {
		'lang': lang,
		'cate': 'investment',
		'sub_cate': 'reallocate_fund',
		'title': 'Reallocate Fund',
		#'account_balance': '%.2f'%(acc.balance + sum([inv.total_amount for inv in inv_list]) + disbursed_amount),
		'account_balance': '%.2f'%(acc.balance + sum([inv.usable_amount+inv.on_hold_amount for inv in inv_list]) + disbursed_amount),
		'str_account_balance': FLOAT_DATA_FORMAT.format(acc.balance + sum([inv.usable_amount+inv.on_hold_amount for inv in inv_list]) + disbursed_amount),
		'unallocated': '%.2f'%(acc.balance),
		'str_unallocated': FLOAT_DATA_FORMAT.format(acc.balance),
		'prod_list': rd_prod_list
		}
		if lang == 'zh':
			content['title'] = '調配投資金額'
		return render(request, 'peerloan/lender/reallocate_fund.html', content)
	elif action == 'transfer_fund':
		inv_list = Investment.objects.filter(usr_id=usr.id)
		rd_prod_list = []
		for inv in inv_list:
			prod = Product.objects.get(id=inv.prod_id)
			if lang == 'en':
				rd_prod_list.append({'prod_id':str(prod.id), 'prod_name':str(prod.name_en), 'usable_amount':str(inv.usable_amount)})
			elif lang == 'zh':
				rd_prod_list.append({'prod_id':str(prod.id), 'prod_name':prod.name_zh.encode('utf8'), 'usable_amount':str(inv.usable_amount)})
				
		content = {
		'lang': lang,
		'prod_list': rd_prod_list,
		'cate': 'investment',
		'sub_cate': 'transfer_fund',
		}
		if lang == 'en':
			content['title'] = 'Transfer Fund Between Products'
			content['instruction'] = """Fund Transfer only applicable to the product which have your investment instruction record, 
			if you have not invested in such product before, please click "Invest Now" to set your investment instruction first. Fund Transfer instruction will be executed immediately."""
		if lang == 'zh':
			content['title'] = '調配資金'
			content['instruction'] = """調配資金只適用於已有投資紀錄的產品，如你從未投資於該產品，請即按入"現在投資"以設定該產品的投資指示，你的資金調配指示將會即時執行。"""
		return render(request, 'peerloan/lender/transfer_form.html', content)