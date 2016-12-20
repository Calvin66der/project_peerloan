# This Python file uses the following encoding: utf-8

from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ObjectDoesNotExist

import peerloan.peerloan_src.supporting_function as sup_fn

from peerloan.models import BorrowRequest
from peerloan.models import Investment
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import Product

from peerloan.decorators import require_login

from django.utils import timezone
from datetime import datetime

@require_login
def portfolio(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	# return schedule
	if 'active_investment' in request.META.get('PATH_INFO').split('/'):
		# active investment page
		prod_list = Product.objects.filter(status='ACTIVE')
		if lang == 'en':
			rd_prod_list = [['all', 'All Products']]
		elif lang == 'zh':
			rd_prod_list = [['all', '全部產品']]
			
		for prod in prod_list:
			if lang == 'en':
				rd_prod_list.append([prod.id, prod.name_en])
			elif lang == 'zh':
				rd_prod_list.append([prod.id, prod.name_zh.encode('utf8')])
				
		content = {
		'lang': lang,
		'cate': 'portfolio',
		'sub_cate': 'active_investment',
		'prod_list': rd_prod_list,
		}
		return render(request, 'peerloan/lender/active_inv.html', content)
	elif 'estimated_returning_schedule' in request.META.get('PATH_INFO').split('/'):
		content = {
		'lang': lang,
		'prod_list': Product.objects.filter(status='ACTIVE')
		}
		return render(request, 'peerloan/lender/estimated_returning_schedule.html', content)
	
	this_month = datetime.strftime(timezone.localtime(timezone.now()), '%m/%Y')
	search_month_list = []
	search_start_date = {'year': 2016, 'month': 06}
	for i in range(12):
		month = (search_start_date['month']+i)%12
		if month == 0:
			month = 12
		year = search_start_date['year'] + (search_start_date['month']+i-1)/12
		date = datetime.strptime(str(month)+'/'+str(year), '%m/%Y')
		search_month_list.append({'name':date.strftime('%B %Y'), 'value': date.strftime('%m/%Y')})
	
	content = {
	'lang': lang,
	'cate': 'portfolio',
	'sub_cate': 'portfolio_summary',
	'title': 'Portfolio Summary',
	'this_month': this_month,
	'search_month_list': search_month_list,
	'today': datetime.strftime(timezone.localtime(timezone.now()), '%Y/%m/%d')
	}
	if lang == 'zh':
		content['title'] = '投資總覽'
	
	return render(request, 'peerloan/lender/portfolio_summary.html', content)
