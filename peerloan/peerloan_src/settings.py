# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

import peerloan.peerloan_src.supporting_function as sup_fn

from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest

from peerloan.decorators import require_login

from collections import OrderedDict

import json

@require_login
def settings(request):
	usr = sup_fn.get_user(request)
	lang = sup_fn.get_lang(request)
	
	sub_cate = request.META.get('PATH_INFO').split('/')[2]
	# lender side =============================================================================================
	if usr.type == 'L':
		if sub_cate == 'sms_email_notification':
			if lang == 'en':
				uri_list = UserInformation.objects.filter(info_type='Settings')
			elif lang == 'zh':
				uri_list = UserInformation.objects.filter(info_type='Settings')
				
			notification = json.loads(usr.notification)
			i = 0
			for uri in uri_list:
				uri.details = json.loads(uri.details, object_pairs_hook=OrderedDict)
				for k, v in uri.details.iteritems():
					v['no'] = i
					v['checked'] = notification[k]
					i += 1
			content = {
			'lang': lang,
			'cate': 'settings',
			'sub_cate': 'sms_email_notification',
			'title': 'SMS/Email Notification',
			'uri_list': uri_list,
			}
			if lang == 'zh':
				content['title'] = '手機短訊/電郵提示'
			return render(request, 'peerloan/lender/sms_email_notification.html' ,content)
		if sub_cate == 'account_information':
			# check last change acc info request
			try:
				uor = UserOperationRequest.objects.filter(usr_id=usr.id, type='Change Account Information', status='PENDING APPROVAL').latest('create_timestamp')
			except ObjectDoesNotExist:
				notice = ''
			else:
				if uor != None:
					notice = 'Your request has submitted. You can make another request after the current request is proceeded.'
			
			uri_list = UserInformation.objects.filter(section="Individual", info_type="Account Information")
			details = []
			for uri in uri_list:
				details.append((uri.section, json.loads(uri.details, object_pairs_hook=OrderedDict)))
			details = OrderedDict(details)
			existed_details = OrderedDict()
			
			for section, terms in details.iteritems():
				existed_details[section] = OrderedDict()
				for name, values in terms.iteritems():
					try:
						existed_details[section][name] = json.loads(usr.detail_info)[section][name]
					except KeyError:
						existed_details[section][name] = '--'
			buttons = []
			buttons.append({"name": "Submit", "type":"submit"})
			
			content = {
			'cate': 'settings',
			'sub_cate': sub_cate,
			'title': 'Account Information',
			'notice': notice,
			'details': details,
			'existed_details': existed_details,
			'form_action': '/ack/',
			'buttons': buttons,
			}
			return render(request, 'peerloan/lender/change_acc_info.html', content)