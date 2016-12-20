from django.http import HttpResponse
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

from .peerloan_src.supporting_function import get_user
from .models import User
from .models import Loan
#from .models import Investment
from .models import BorrowRequest

from datetime import datetime
from django.utils import timezone
import pytz

AUTO_LOGOUT_TIMEOUT_IN_MINS = 30

def require_login(view_fn):
	def inner_require_login(request, *args, **kwargs):
		sess = Session.objects.get(pk=request.COOKIES.get('sessionid'))
		try:
			sess.get_decoded()['email']
		except KeyError:
		   	return redirect('/login')
		else:
			last_active_time = datetime.strptime(request.session['timestamp'], '%Y-%m-%d %H:%M:%S')
			last_active_time = pytz.timezone('Asia/Hong_Kong').localize(last_active_time)
			# check timeout
			if (timezone.localtime(timezone.now())-last_active_time).seconds > 60*AUTO_LOGOUT_TIMEOUT_IN_MINS:
				sess.delete()
				return redirect('/login')
			else:
				request.session['timestamp'] = datetime.strftime(timezone.localtime(timezone.now()), '%Y-%m-%d %H:%M:%S')
		return view_fn(request, *args, **kwargs)
	return inner_require_login
"""
def access_right(view_fn):
	def inner_access_right(request, *args, **kargs):
		cur_usr_id = get_user(request).id
		cur_usr_type = User.objects.get(id = cur_usr_id).type
		
		http_referer = request.META.get('PATH_INFO')
		case = http_referer.split('/')[1]
		loan_id = None
		if case == 'loan':
			if http_referer.split('/')[2] != 'overall':
				loan_id = int(http_referer.split('/')[2])

		if case == 'product':
			action = http_referer.split('/',4)[3]
			if action == 'loan':
				loan_id = int(http_referer.split('/')[4])
		
		if loan_id != None:
			loan = Loan.objects.get(id = loan_id)
			req_usr_id = ''
			if cur_usr_type == 'L':
				req_usr_id = Investment.objects.get(id = loan.inv_id).usr_id
			if cur_usr_type == 'B':
				req_usr_id = BorrowRequest.objects.get(id = loan.bor_id).usr_id
			if cur_usr_id != req_usr_id and cur_usr_type !='admin':
				return HttpResponse('Access Denied')
			else:
				return view_fn(request, *args, **kargs)
		else:
			return view_fn(request, *args, **kargs)
	return inner_access_right
"""