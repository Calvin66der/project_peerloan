# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.template.context_processors import csrf
#from django.core.mail import EmailMessage
from django.contrib.sessions.models import Session

import peerloan.peerloan_src.supporting_function as sup_fn

from peerloan.decorators import require_login

from peerloan.models import User
from peerloan.models import AdminUser
from peerloan.models import UserOperationRequest
import peerloan.emailing as emailing

import hashlib
import json
import string
import random
from datetime import datetime
from django.utils import timezone
import pytz

ACCOUNT_ATTEMPT_TIMES = 5
RESET_PW_EXPIRE_TIME = 30 # in minutes

def login(request):
	lang = sup_fn.get_lang(request)
	content = {
	'lang': lang,
	}
   	#content.update(csrf(request))
   	return render(request, "peerloan/general/login.html", content)

def sign_up(request):
	lang = sup_fn.get_lang(request)
	if request.method=='POST':
		email = request.POST.get('email')
		password = request.POST.get('register_password')
		receive_promotion = 'False' if request.POST.get('receive_promotion') == None else 'True'
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.POST.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if len(User.objects.filter(email=email, status='ACTIVE')) == 0:
			
			# create new usr model
			new_usr = User(
			email = email,
			password = hashlib.md5(password).hexdigest(),
			receive_promotion = receive_promotion,
			detail_info = '{}',
			type = 'B',
			status = 'WAIT FOR ACTIVATION',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_usr.save()
			
			# create new uor and send activation email
			# generate token
			def generate_unique_sequence64(size=64, chars=string.ascii_uppercase + string.digits):
				uor_list = UserOperationRequest.objects.filter(type='activate_account')
				token_list = [json.loads(uor.details)['token'] for uor in uor_list]
				while 1:
					rand_seq = ''.join(random.choice(chars) for _ in range(size))
					if rand_seq not in token_list:
						return rand_seq
			new_token = generate_unique_sequence64()
			details = {
				"token": new_token,
				"email": email
			}
			new_uor = UserOperationRequest(
			usr_id = new_usr.id,
			type = 'activate_account',
			details = json.dumps(details),
			status = 'ACTIVE',
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_uor.save()
			
			usr_emailing = emailing.GeneralEmail(email_addr=email)
			usr_emailing.account_activate(token=new_token)
			
			# avoid email too long and out of box
			email_arr = []
			for i in range(int(len(email)/15)):
				email_arr.append(email[i*15:(i+1)*15])
			email_arr.append(email[int(len(email)/15)*15:])
			email = '<br>'.join(email_arr)
			
			if lang == 'en':
				content = {
				'status': 'Success!',
				'header': 'Congratulation! You have signed up as <strong>%s</strong>.' % email,
				'content': 'An email with activation link has sent to your email address. Please activate your account before login.',
				}
			if lang == 'zh':
				content = {
				'status': '註冊成功！',
				'header': '恭喜！你已經註冊成為<strong>%s</strong>' % email.encode("utf8"),
				'content': '系統已發出一封附有啟用鏈接的郵件至你的郵箱。請先啟用你的賬戶再嘗試登入。',
				}
			content['lang'] = lang
		else:
			if lang == 'en':
				content = {
				'status': 'Failed!',
				'header': 'Your request to signed up as <strong>%s</strong> is failed.' % email,
				'content': 'Our system has detected that this email is already registered in the platform.',
				}
			if lang == 'zh':
				content = {
				'status': '註冊失敗!',
				'header': '你使用<strong>%s</strong>來註冊賬號已經失敗。' % email.encode("utf8"),
				'content': '我們系統檢測到該電郵地址已在平台被註冊。',
				}
			content['lang'] = lang
		return render(request, 'peerloan/general/general_ack.html', content)
	else:
		return HttpResponse('Invalid request method.')
		
def forget_password(request):
	lang = sup_fn.get_lang(request)
	email_addr = request.POST.get('email')
	if len(User.objects.filter(email=email_addr)) == 0:
		if lang == 'en':
			content = {
			'status': 'Request Failed!',
			'header': 'Email doesn\'t exist.',
			'content': 'You can go back to login page and try to enter again.',
				}
		if lang == 'zh':
			content = {
			'status': '請求失敗！',
			'header': '電子郵箱並不存在',
			'content': '你可以返回登入頁面并嘗試重新輸入。',
				}
		content['lang'] = lang
		
	else:
		#username = User.objects.filter(email=email_addr)[0].username
		# generate token
		def generate_unique_sequence64(size=64, chars=string.ascii_uppercase + string.digits):
			uor_list = UserOperationRequest.objects.filter(type='Forget Password', status="ACTIVE")
			token_list = [json.loads(uor.details)['token'] for uor in uor_list]
			while 1:
				rand_seq = ''.join(random.choice(chars) for _ in range(size))
				if rand_seq not in token_list:
					return rand_seq
		new_token = generate_unique_sequence64()
		details = {
			"token": new_token,
			"email": email_addr
		}
		new_uor = UserOperationRequest(
		usr_id = 0,
		type = 'Forget Password',
		details = json.dumps(details),
		status = 'ACTIVE',
		create_timestamp = timezone.localtime(timezone.now()),
		update_timestamp = timezone.localtime(timezone.now())
		)
		new_uor.save()
		
		usr_emailing = emailing.GeneralEmail(email_addr=email_addr)
		usr_emailing.reset_password(token=new_token)
		
		# avoid email too long and out of box
		email_arr = []
		for i in range(int(len(email_addr)/15)):
			email_arr.append(email_addr[i*15:(i+1)*15])
		email_arr.append(email_addr[int(len(email_addr)/15)*15:])
		email_addr = '<br>'.join(email_arr)
		if lang == 'en':
			content = {
			'status': 'Request Successfully Sent!',
			'header': 'An email for resetting password is sent to %s.'%(email_addr),
			'content': 'Please check your mailbox and reset the password.',
				}
		if lang == 'zh':
			content = {
			'status': '請求成功！',
			'header': '密碼重置電郵已發送至%s.'%(email_addr.encode("utf8")),
			'content': '請查閱你的電郵信箱並重設你的密碼',
				}
		content['lang'] = lang
	return render(request, 'peerloan/general/general_ack.html', content)

def password_reset(request):
	lang = sup_fn.get_lang(request)
	if request.method == 'POST':
		token = request.POST.get('token')
		new_password = request.POST.get('new_password')
		uor_list = UserOperationRequest.objects.filter(type='Forget Password', status="ACTIVE")
		
		email = None
		
		is_expired = False
		for uor in uor_list:
			details = json.loads(uor.details)
			if details["token"] == token:
				email = details["email"]
				
				diff_second = (timezone.localtime(timezone.now()) - uor.create_timestamp).seconds
				diff_minute = diff_second / 60
				if diff_minute > RESET_PW_EXPIRE_TIME:
					is_expired = True
					uor.status = 'EXPIRED'
					uor.save()
				
		if email == None or token == None or is_expired:
			if lang == 'en':
				content = {
				'status': 'Reset Password Failed!',
				'header': 'Token doesn\'t exist or expired.',
				'content': 'Please submit the reset password request again.',
					}
			if lang == 'zh':
				content = {
				'status': '重置密碼失敗!',
				'header': 'Token不存在或已經失效。',
				'content': '請重新提交重置密碼請求。',
					}
		else:
			usr_list = User.objects.filter(email=email)
			for usr in usr_list:
				usr.password = hashlib.md5(new_password).hexdigest()
				usr.status = 'ACTIVE'
				usr.save()
			if lang == 'en':
				content = {
				'status': 'Reset Password Successfully!',
				'header': 'Your password has been updated.',
				#'content': 'Now you can go back to login page and try to login.',
				'content': '',
					}
			if lang == 'zh':
				content = {
				'status': '重置密碼成功!',
				'header': '你的密碼已經更新。',
				#'content': '現在你可以嘗試重新登入。',
				'content': '',
					}
		content['lang'] = lang
		return render(request, 'peerloan/general/general_ack.html', content)
			
	token = request.GET.get('token')
	
	content = {
	'token': token,
	'lang': lang,
	}
	return render(request, 'peerloan/general/password_reset.html', content)

def email_request(request):
	lang = sup_fn.get_lang(request)
	type = request.META.get('PATH_INFO').split('/')[2]
	token = request.GET.get('token')
	
	uor_list = UserOperationRequest.objects.filter(type = type)
	
	if type == 'activate_account':
		res = 'FINDING'
		for uor in uor_list:
			details = json.loads(uor.details)
			if token == details['token']:
				try:
					usr = User.objects.get(id = uor.usr_id)
				except ObjectDoesNotExist:
					break
					
				usr.status = 'ACTIVE'
				usr.update_timestamp = timezone.localtime(timezone.now())
				usr.save()
				res = 'FOUND'
				
				# remove other activation requests
				other_usr_list = User.objects.filter(email=usr.email, status="WAIT FOR ACTIVATION")
				for other_usr in other_usr_list:
					other_usr.delete()
				
				break
				"""
				usr = User.objects.filter(email = details['email']).latest('update_timestamp')
				usr.status = 'ACTIVE'
				usr.update_timestamp = timezone.localtime(timezone.now())
				usr.save()
				res = 'FOUND'
				break
				"""
		# avoid email too long and out of box
		email_arr = []
		for i in range(int(len(details['email'])/15)):
			email_arr.append(details['email'][i*15:(i+1)*15])
		email_arr.append(details['email'][int(len(details['email'])/15)*15:])
		details['email'] = '<br>'.join(email_arr)
		if res == 'FOUND':
			if lang == 'en':
				content = {
				'status': 'Success!',
				'header': 'Congratulation! Your account <strong>%s</strong> is activated.' % details['email'],
				'content': 'You can return to login page and try to login.',
				}
			if lang == 'zh':
				content = {
				'status': '註冊成功！',
				'header': '恭喜！你的賬戶<strong>%s</strong>已成功啟用。' % details['email'].encode("utf8"),
				'content': '你可以返回登入頁面并嘗試登入。',
				}
		if res == 'FINDING':
			if lang == 'en':
				content = {
				'status': 'Activation Failed!',
				'header': 'Request token doesn\'t exist.',
				'content': 'Please try to sign up again and get a new token.',
				}
			if lang == 'zh':
				content = {
				'status': '激活失敗！',
				'header': 'Token並不存在。',
				'content': '請嘗試重新註冊和用新的Token激活。',
				}
	content['lang'] = lang
	return render(request, 'peerloan/general/general_ack.html', content)

def auth(request):
	lang = sup_fn.get_lang(request)
	if request.method=='POST':
		email = request.POST.get('email')
		password = request.POST.get('password')
	
	# admin login
	if 'pl_admin' in request.META.get('HTTP_REFERER').split('/'):
		if len(AdminUser.objects.filter(email=email)) == 0:
			return HttpResponse('Admin side: account doesn\'t exist.')
		else:
			usr = AdminUser.objects.filter(email=email)[0]
			if usr.password != hashlib.md5(password).hexdigest():
				return HttpResponse('Admin side: wrong password.')
			else:
				request.session['type'] = 'ADMIN'
				request.session['email'] = email
				request.session['handling_side'] = 'B'
				request.session['timestamp'] = datetime.strftime(timezone.localtime(timezone.now()), '%Y-%m-%d %H:%M:%S')
				request.session.save()
				
				# update last login
				usr = sup_fn.get_user(request)
				usr.this_login = timezone.localtime(timezone.now())
				usr.save()
				
				return redirect('/pl_admin/application')
	
	# user login
	if len(User.objects.filter(email=email, password=hashlib.md5(password).hexdigest(), status='ACTIVE')) == 0:
		# login failed
		if lang == 'en':
			content = {
			'status': 'Login Failed!',
			'content': 'You can go back to login page and try to login again.',
			}
			if len(User.objects.filter(email=email, status='ACTIVE')) == 0:
				content['header'] = 'Account doesn\'t exist or is locked.'
			else:
				content['header'] = 'The password is incorrect.'
				
		if lang == 'zh':
			content = {
			'status': '登入失敗！',
			'content': '你可以返回登入頁面并嘗試重新登入。',
			}
			if len(User.objects.filter(email=email, status='ACTIVE')) == 0:
				content['header'] = '用戶名不存在。'
			else:
				content['header'] = '密碼不正確。'
		
		usr_list = User.objects.filter(email=email, status='ACTIVE')
		for usr in usr_list:
			# accumulate both lender & borrower account
			usr.account_attempt += 1
			if usr.account_attempt >= ACCOUNT_ATTEMPT_TIMES:
				usr.status = 'LOCKED'
			usr.save()
		if len(usr_list) != 0:
			if usr_list[0].account_attempt >= ACCOUNT_ATTEMPT_TIMES:
				# generate token
				def generate_unique_sequence64(size=64, chars=string.ascii_uppercase + string.digits):
					uor_list = UserOperationRequest.objects.filter(type='Forget Password', status="ACTIVE")
					token_list = [json.loads(uor.details)['token'] for uor in uor_list]
					while 1:
						rand_seq = ''.join(random.choice(chars) for _ in range(size))
						if rand_seq not in token_list:
							return rand_seq
				new_token = generate_unique_sequence64()
				details = {
					"token": new_token,
					"email": email
				}
				new_uor = UserOperationRequest(
				usr_id = 0,
				type = 'Forget Password',
				details = json.dumps(details),
				status = 'ACTIVE',
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_uor.save()
				
				usr_emailing= emailing.GeneralEmail(email_addr=email)
				usr_emailing.unlock_account(token=new_token)
		content['lang'] = lang
		return render(request, 'peerloan/general/general_ack.html', content)
	else:
		# login successfully
		request.session['email'] = email
		request.session['timestamp'] = datetime.strftime(timezone.localtime(timezone.now()), '%Y-%m-%d %H:%M:%S')
		
		# check password case sensitively
		usr = User.objects.filter(email=email, status='ACTIVE')[0]
		
		if hashlib.md5(password).hexdigest() != usr.password:
			content = {
			'status': 'Login Failed!',
			'header': 'The password is incorrect.',
			'content': 'You can go back to login page and try to login again.',
			}
			return render(request, 'peerloan/general/general_ack.html', content)
		"""
		if len(User.objects.filter(email=email, password__exact=hashlib.md5(password).hexdigest(), status='ACTIVE')) == 1 and User.objects.filter(email=email, password__exact=password, status='ACTIVE')[0].type == 'ADMIN':
			request.session['type'] = 'ADMIN'
			request.session['handling_side'] = 'B'
			request.session.save()
			
			# update last login
			usr = sup_fn.get_user(request)
			usr.this_login = timezone.localtime(timezone.now())
			usr.save()
			
			return redirect('/pl_admin/application')
		"""
		if len(User.objects.filter(email=email, password__exact=hashlib.md5(password).hexdigest(), status='ACTIVE')) == 2:
			request.session['type'] = 'L'
			request.session.save()
			
			# update last login
			usr_list = User.objects.filter(email=email)
			for usr in usr_list:
				usr.account_attempt = 0
				usr.this_login = timezone.localtime(timezone.now())
				usr.save()
			
			return redirect('/portfolio/portfolio_summary')
		else:
			request.session['type'] = 'B'
			request.session.save()
			
			# update last login
			usr = sup_fn.get_user(request)
			usr.account_attempt = 0
			usr.this_login = timezone.localtime(timezone.now())
			usr.save()
			
			return redirect('/borrow_now')

def logout(request):
	
	# update last login
	cur_usr = sup_fn.get_user(request)
	sess = Session.objects.get(pk=request.COOKIES.get('sessionid'))
	if sess.get_decoded()['type'] == 'ADMIN':
		usr_list = AdminUser.objects.filter(email=cur_usr.email)
		
		try:
			del request.session['email']
			del request.session['timestamp']
			del request.session['type']
			del request.session['handling_side']
		except KeyError:
			pass
	else:
		usr_list = User.objects.filter(email=cur_usr.email, status='ACTIVE')
		for usr in usr_list:
			usr.last_login = cur_usr.this_login
			usr.save()
		try:
			del request.session['email']
			del request.session['timestamp']
			del request.session['type']
		except KeyError:
			pass
	
	sess.delete()
	return redirect('/login')