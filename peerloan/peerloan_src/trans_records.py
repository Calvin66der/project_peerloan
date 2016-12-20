# This Python file uses the following encoding: utf-8
from django.shortcuts import render
from django.http import HttpResponse

from peerloan.models import Account

from peerloan.decorators import require_login

import peerloan.peerloan_src.supporting_function as sup_fn
#from .supporting_function import sup_fn.get_user
#from .supporting_function import sup_fn.get_lang

@require_login
def trans_records(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	if usr.type == 'B':
		content = {
		'lang': lang,
		'cate': 'trans_records',
		'title': 'Transaction Records',
		}
		if lang == 'zh':
			content['title'] = '交易紀錄'
		return render(request, 'peerloan/borrower/trans_records.html', content)