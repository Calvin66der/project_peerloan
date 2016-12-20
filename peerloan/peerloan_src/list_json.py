# This Python file uses the following encoding: utf-8
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django_datatables_view.base_datatable_view import BaseDatatableView

from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework.response import Response

from django.http import HttpResponse

from peerloan.models import Account
from peerloan.models import BorrowRequest
from peerloan.models import Investment
from peerloan.models import Product
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import UserOperationRequest
from peerloan.models import UserTransaction
from peerloan.models import MonthlyPortfolioSummary

from peerloan.serializers import LaasSerializer
from peerloan.serializers import LoanLenderSerializer
from peerloan.serializers import KeyValueSerializer
from peerloan.serializers import XYSerializer
from peerloan.serializers import RepayTableSerializer
from peerloan.serializers import RepayPieSerializer

from peerloan.serializers import ActiveInvSerializer

import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
import datetime as dt
from django.utils import timezone
import pytz
import json

FLOAT_DATA_FORMAT = '{:,.2f}'

class trans_list_json(BaseDatatableView):
	model = UserTransaction

	columns = ['create_timestamp', 'internal_ref', 'amount_in', 'amount_out', 'type','href']

	order_columns = ['create_timestamp', 'internal_ref', 'amount_in', 'amount_out', 'type','href']
	
	def get_initial_queryset(self):
		user = sup_fn.get_user(self.request)
		trx_list = UserTransaction.objects.filter(usr_id=user.id)
		return trx_list
	
	def prepare_results(self, qs):
		json_data = []
		for item in qs:
			json_data.append([
				item.create_timestamp,
				item.create_timestamp.strftime('%Y/%m/%d'),
				item.internal_ref,
				FLOAT_DATA_FORMAT.format(item.amount_out),
				FLOAT_DATA_FORMAT.format(item.amount_in),
				item.type,
				item.href,
			])
		return json_data
		

class loan_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		if request.method == 'GET':
			usr = sup_fn.get_user(request)
			lang = sup_fn.get_lang(request)
			status = request.GET.get('status')
			start_date = request.GET.get('start_date')
			
			# check XSS
			if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
				return HttpResponse('Invalid input.')
				
			if usr.type == 'B':
				bor_list = BorrowRequest.objects.filter(usr_id=usr.id)
				if status != 'All':
					if status == 'AGREEMENT CONFIRMED':
						bor_list = [bor for bor in bor_list if 'AGREEMENT CONFIRMED' in bor.status or 'VALIDATED' in bor.status or 'FUND MATCHING' in bor.status]
					else:
						bor_list = [bor for bor in bor_list if status.upper() in bor.status]
				if start_date != 'All':
					start_date = datetime.strptime(start_date, '%m/%d/%Y')
					bor_list = [bor for bor in bor_list if datetime.strptime(timezone.localtime(bor.create_timestamp).strftime('%m/%d/%Y'), '%m/%d/%Y')>= start_date]
					
				data_list = []
				for bor in bor_list:
					details = {}
					prod = Product.objects.get(id=bor.prod_id)
					details['shadow_datetime'] = timezone.localtime(bor.update_timestamp)
					details['updated_date'] = datetime.strftime(timezone.localtime(bor.update_timestamp), '%Y/%m/%d')
					details['prod_name'] = prod.name_en
					if lang == 'zh':
						details['prod_name'] = prod.name_zh
					details['ref_num'] = bor.ref_num
					details['amount'] = FLOAT_DATA_FORMAT.format(bor.amount)
					details['APR'] = FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower))
					details['apply_date'] = datetime.strftime(timezone.localtime(bor.create_timestamp), '%Y/%m/%d')
					details['repayment_progress'] = str(bor.repaid_month)+'/'+str(prod.repayment_period)
					details['status'] = ''.join([i for i in bor.status if (not i.isdigit())])
					details['bor_id'] = bor.id
					
					if bor.status == 'AUTO APPROVED':
						details['href'] = '/product/upload_docs/?prod_id='+str(prod.id)
					elif bor.status == 'DOC UPLOADED':
						details['href'] = '/product/confirm_agreement/?prod_id='+str(prod.id)
					elif bor.status == 'AGREEMENT CONFIRMED' or bor.status == 'VALIDATED' or bor.status == 'FUND MATCHING':
						details['href'] = '/ack_page/?action=confirm_agreement'
					elif bor.status == 'DISBURSED' or 'PAYBACK' in bor.status:
						details['href'] = '/my_account/all_application_listing/detail/?bor_id='+str(bor.id)
					elif bor.status == 'FUND MATCHING COMPLETED':
						details['href'] = '/product/confirm_memorandum/?prod_id='+str(prod.id)
					else:
						details['href'] = 'javascript:;'
						
					data_list.append(details)
				#serialized_data_list = LaasSerializer(data_list, many=True)
				content = {'data': data_list}
				return Response(content)
			if usr.type == 'L':
				inv_list = Investment.objects.filter(usr_id = usr.id)
				loan_list = []
				for inv in inv_list:
					loans = Loan.objects.filter(inv_id = inv.id)
					for loan in loans:
						loan_list.append(loan)
				if status != 'All':
					loan_list = [loan for loan in loan_list if status.upper() in loan.status]
				if start_date != 'All':
					start_date = datetime.strptime(start_date, '%m/%d/%Y')
					loan_list = [loan for loan in loan_list if datetime.strptime(timezone.localtime(loan.create_timestamp).strftime('%m/%d/%Y'), '%m/%d/%Y')>= start_date]
				data_list = []
				for loan in loan_list:
					details = {}
					bor = BorrowRequest.objects.get(id=loan.bor_id)
					prod = Product.objects.get(id=bor.prod_id)
					details['updated_date'] = datetime.strftime(timezone.localtime(loan.update_timestamp), '%d/%m/%Y')
					details['prod_name'] = prod.name_en
					details['ref_num'] = bor.ref_num
					details['amount'] = loan.initial_amount
					details['APR'] = prod.APR_lender
					details['draw_down_date'] = datetime.strftime(timezone.localtime(loan.draw_down_date), '%d/%m/%Y')
					details['status'] = bor.status
					data_list.append(details)
				serialized_data_list = LoanLenderSerializer(data_list, many=True)
			content = {'data': serialized_data_list.data}
			return Response(content)
		else:
			return HttpResponse('Wrong request method.')

class repayboard_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		bor_id = request.GET.get('bor_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		data_list = []
		if bor_id == 'all':
			bor_list = BorrowRequest.objects.filter(usr_id = usr.id)
			bor_list = [bor for bor in bor_list if bor.status == 'DISBURSED' or 'PAYBACK' in bor.status]
		else:
			bor_list = BorrowRequest.objects.filter(id = bor_id)
		total_principal = 0
		paid_principal = 0
		paid_interest = 0
		outstanding_principal = 0
		outstanding_interest = 0
		overdue_principal = 0
		overdue_amount = 0
		
		for bor in bor_list:
			prod = Product.objects.get(id = bor.prod_id)
			loan_list = Loan.objects.filter(bor_id = bor.id)
			total_principal += sum([loan.initial_amount for loan in loan_list])
			paid_principal += sum([loan.initial_amount - loan.remain_principal for loan in loan_list])
			paid_interest += sum([loan.initial_amount for loan in loan_list]) * prod.APR_borrower * 0.01 * (prod.repayment_period /12) - sum([loan.remain_interest_borrower for loan in loan_list])
			outstanding_principal += sum([loan.remain_principal for loan in loan_list])
			outstanding_interest += sum([loan.remain_interest_borrower for loan in loan_list])
			overdue_principal += sum([loan.overdue_principal for loan in loan_list])
			overdue_amount += sum([loan.overdue_principal+loan.overdue_interest for loan in loan_list])
		total_principal = round(total_principal, 1)
		paid_principal = round(paid_principal, 1)
		paid_interest = round(paid_interest, 1)
		outstanding_principal = round(outstanding_principal, 1)
		outstanding_interest = round(outstanding_interest, 1)
		overdue_principal = round(overdue_principal, 1)
		overdue_amount = round(overdue_amount, 1)
		
		data_list.append({'key': 'Total Principal', 'value':'$'+str(total_principal)})
		data_list.append({'key': 'Paid Principal', 'value':'$'+str(paid_principal)})
		data_list.append({'key': 'Paid Interest', 'value':'$'+str(paid_interest)})
		data_list.append({'key': 'Outstanding Principal', 'value':'$'+str(outstanding_principal)})
		data_list.append({'key': 'Outstanding Interest', 'value':'$'+str(outstanding_interest)})
		data_list.append({'key': 'Overdue Principal', 'value':'$'+str(overdue_principal)})
		data_list.append({'key': 'Overdue Amount (included interest)', 'value':'$'+str(overdue_amount)})
		
		serialized_data_list = KeyValueSerializer(data_list, many=True)
		content = {'data': serialized_data_list.data}
		return Response(content)

class returnboard_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		prod_id = request.GET.get('prod_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if prod_id == 'all':
			inv_list = Investment.objects.filter(usr_id=usr.id)
		else:
			inv_list = Investment.objects.filter(usr_id=usr.id, prod_id=prod_id)
		data_list = []
		total_principal = 0
		returned_principal = 0
		returned_interest = 0
		returning_principal = 0
		returning_interest = 0
		overdue_principal = 0
		overdue_amount = 0
		
		for inv in inv_list:
			loan_list = Loan.objects.filter(inv_id=inv.id)
			total_principal += sum([loan.initial_amount for loan in loan_list])
			returned_principal += sum([loan.initial_amount - loan.remain_principal for loan in loan_list])
			prod = Product.objects.get(id=inv.prod_id)
			returned_interest += sum([loan.initial_amount * prod.APR_lender * 0.01 * (prod.repayment_period/12) - loan.remain_interest_lender for loan in loan_list])
			returning_principal += sum([loan.remain_principal for loan in loan_list])
			returning_interest += sum([loan.remain_interest_lender for loan in loan_list])
			overdue_principal += sum([loan.overdue_principal for loan in loan_list])
			overdue_amount += sum([loan.overdue_principal+loan.overdue_interest for loan in loan_list])
		returned_principal = round(returned_principal, 1)
		returned_interest = round(returned_interest, 1)
		returning_principal = round(returning_principal, 1)
		returning_interest = round(returning_interest, 1)
		overdue_principal = round(overdue_principal, 1)
		overdue_amount = round(overdue_amount, 1)
		
		data_list.append({'key': 'Total Principal', 'value':'$'+str(total_principal)})
		data_list.append({'key': 'Returned Principal', 'value':'$'+str(returned_principal)})
		data_list.append({'key': 'Returned Interest', 'value':'$'+str(returned_interest)})
		data_list.append({'key': 'Returning Principal', 'value':'$'+str(returning_principal)})
		data_list.append({'key': 'Returning Interest', 'value':'$'+str(returning_interest)})
		data_list.append({'key': 'Overdue Principal', 'value':'$'+str(overdue_principal)})
		data_list.append({'key': 'Overdue Amount (included interest)', 'value':'$'+str(overdue_amount)})
		
		serialized_data_list = KeyValueSerializer(data_list, many=True)
		content = {'data': serialized_data_list.data}
		return Response(content)

class repaytable_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		bor_id = request.GET.get('bor_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if bor_id == 'all':
			bor_list = BorrowRequest.objects.filter(usr_id = usr.id)
			bor_list = [bor for bor in bor_list if bor.status == 'DISBURSED' or 'PAYBACK' in bor.status]
		else:
			bor_list = BorrowRequest.objects.filter(id = bor_id)
			
		schedule_list = []
		min_start_date = None
		max_end_date = None
		
		for bor in bor_list:
			loan_list = Loan.objects.filter(bor_id = bor.id)
			prod = Product.objects.get(id = bor.prod_id)
			bor.draw_down_date = timezone.localtime(bor.draw_down_date)
			start_date_day = bor.draw_down_date.day
			start_date_month = bor.draw_down_date.month + 1
			start_date_year = bor.draw_down_date.year
			amount_per_month = prod.total_amount / prod.repayment_period
			interest_per_month = prod.total_amount * prod.APR_borrower * 0.01 * (prod.repayment_period / 12) / prod.repayment_period
			for i in range(prod.repayment_period):
				day = start_date_day
				month = (start_date_month + i-1) % 12 + 1
				year = start_date_year + ((start_date_month+i-1) / 12)
				try:
					date = datetime.strptime(str(day)+'/'+str(month)+'/'+str(year), '%d/%m/%Y')
				except ValueError:
					date = datetime.strptime('1/'+str((month%12)+1)+'/'+str(year), '%d/%m/%Y') - dt.timedelta(days=1)
				today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%d/%m/%Y'), '%d/%m/%Y')
				if date < today and bor.repaid_month >= (i+1):
					status = 'PAID'
				elif date < today and bor.repaid_month < (i+1):
					status = 'OVERDUE'
				elif date >= today:
					status = 'OPEN'
				schedule = {
				'date': timezone.localtime(date).strftime('%d/%m/%Y'),
				'os_principal': round(prod.total_amount - amount_per_month * (i+1),1), 
				'os_interest': round(prod.total_amount * prod.APR_borrower * 0.01 * (prod.repayment_period / 12) - interest_per_month * (i+1),1), 
				'os_balance': round(prod.total_amount - amount_per_month * (i+1),1)+round(prod.total_amount * prod.APR_borrower * 0.01 * (prod.repayment_period / 12) - interest_per_month * (i+1),1),
				'paid_principal': round(amount_per_month, 1) if status == 'PAID' else 0,
				'paid_interest': round(interest_per_month, 1) if status == 'PAID' else 0,
				'ref_num': bor.ref_num,
				'prod_name': prod.name_en,
				'installment': round(amount_per_month+interest_per_month, 1),
				'status': status,
				
				}
				schedule_list.append(schedule)
		serialized_table_list = RepayTableSerializer(schedule_list, many=True)
		content = {'data': serialized_table_list.data}
		return Response(content)

class returntable_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		prod_id = request.GET.get('prod_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if prod_id == 'all':
			inv_list = Investment.objects.filter(usr_id=usr.id)
		else:
			inv_list = Investment.objects.filter(usr_id=usr.id, prod_id=prod_id)
			
		schedule_list = []
		schedule2_list = []
		min_start_date = None
		max_end_date = None
		
		for inv in inv_list:
			loan_list = Loan.objects.filter(inv_id = inv.id)
			loan_list = [loan for loan in loan_list if 'DISBURSED' in loan.status or 'PAYBACK' in loan.status]
			prod = Product.objects.get(id = inv.prod_id)
			rate_per_month = prod.APR_lender * 0.01 / 12
			for loan in loan_list:
				try:
					bor = BorrowRequest.objects.get(id=loan.bor_id)
				except:
					continue
				bor.draw_down_date = timezone.localtime(bor.draw_down_date)
				start_date_day = bor.draw_down_date.day
				start_date_month = bor.draw_down_date.month + 1
				start_date_year = bor.draw_down_date.year
				
				remain_principal = loan.initial_amount
				#remain_interest = loan.total_repay_amount_lender - loan.initial_amount
				ratio = prod.APR_lender / bor.getBorAPR(prod.APR_borrower)
				remain_interest = (loan.total_repay_amount_lender - loan.initial_amount) * ratio
				
				for i in range(prod.repayment_period):
					day = start_date_day
					month = (start_date_month + i-1) % 12 + 1
					year = start_date_year + ((start_date_month+i-1) / 12)
					
					interest = remain_principal * rate_per_month
					interest_ldr = interest * ratio
					principal = loan.instalment_lender - interest
					remain_interest -= interest_ldr
					remain_principal -= principal
					
					try:
						date = datetime.strptime(str(day)+'/'+str(month)+'/'+str(year), '%d/%m/%Y')
					except ValueError:
						date = datetime.strptime('1/'+str((month%12)+1)+'/'+str(year), '%d/%m/%Y') - dt.timedelta(days=1)
					today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%d/%m/%Y'), '%d/%m/%Y')
					if date < today and bor.repaid_month >= (i+1):
						status = 'PAID'
					elif date < today and bor.repaid_month < (i+1):
						status = 'OVERDUE'
					elif date >= today:
						status = 'OPEN'
					schedule = {
					#'date': timezone.localtime(date).strftime('%d/%m/%Y'),
					'date': date,
					'initial_principal': loan.initial_amount,
					'os_principal': remain_principal,
					'os_interest': remain_interest, 
					'os_balance': remain_principal + remain_interest,
					'paid_principal': principal if status == 'PAID' else 0,
					'paid_interest': interest if status == 'PAID' else 0,
					'ref_num': loan.ref_num,
					'prod_name': prod.name_en,
					'installment': loan.instalment_lender,
					'status': status,
					}
					schedule_list.append(schedule)
				
		# month base view
		date_set = set()
		for schedule in schedule_list:
			date = datetime.strptime(datetime.strftime(schedule['date'], '%m/%Y'), '%m/%Y')
			date_set.add(date)
		for date in date_set:
			schedule_sub_list = [schedule for schedule in schedule_list if schedule['date'].month == date.month and schedule['date'].year == date.year]
			
			schedule = {
			'shadow_datetime': date,
			'date': datetime.strftime(date, '%Y/%m'),
			'initial_principal': FLOAT_DATA_FORMAT.format(sum([s['initial_principal'] for s in schedule_sub_list])),
			'os_principal': FLOAT_DATA_FORMAT.format(abs(sum([s['os_principal'] for s in schedule_sub_list]))),
			'os_interest': FLOAT_DATA_FORMAT.format(abs(sum([s['os_interest'] for s in schedule_sub_list]))),
			'os_balance': FLOAT_DATA_FORMAT.format(abs(sum([s['os_balance'] for s in schedule_sub_list]))),
			'paid_principal': FLOAT_DATA_FORMAT.format(sum([s['paid_principal'] for s in schedule_sub_list])),
			'paid_interest': FLOAT_DATA_FORMAT.format(sum([s['paid_interest'] for s in schedule_sub_list])),
			'ref_num': '',
			'prod_name': '',
			'installment': FLOAT_DATA_FORMAT.format(sum([s['installment'] for s in schedule_sub_list])),
			'status': '',
			}
			schedule2_list.append(schedule)
		
		serialized_table_list = schedule2_list
		content = {'data': serialized_table_list}
		return Response(content)

class repaypie_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		bor_id = request.GET.get('bor_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if bor_id == 'all':
			bor_list = BorrowRequest.objects.filter(usr_id = usr.id)
			bor_list = [bor for bor in bor_list if bor.status == 'DISBURSED' or 'PAYBACK' in bor.status]
		else:
			bor_list = BorrowRequest.objects.filter(id = bor_id)
		
		# assume user applies not more than 3 loans
		color_lib = {'red':['#E08283','#E7505A','#D91E18'],'green':['#36D7B7','#4DB3A2','#26C281'],'yellow':['#F4D03F','#F7CA18','#F3C200']}
		data_list = []
		i = 0
		for bor in bor_list:
			loan_list = Loan.objects.filter(bor_id = bor.id)
			prod = Product.objects.get(id = bor.prod_id)
			
			paid_principal = sum([loan.initial_amount - loan.remain_principal for loan in loan_list])
			outstanding_principal = sum([loan.remain_principal for loan in loan_list])
			overdue_principal = sum([loan.overdue_principal for loan in loan_list])
			
			if paid_principal != 0:
				data_list.append({'name':'Paid Principal ('+prod.name_en+')','amount':paid_principal,'color':color_lib['green'][i]})
			if outstanding_principal != 0:
				data_list.append({'name':'Outstanding Principal ('+prod.name_en+')','amount':outstanding_principal,'color':color_lib['yellow'][i]})
			if overdue_principal != 0:
				data_list.append({'name':'Overdue Principal ('+prod.name_en+')','amount':overdue_principal,'color':color_lib['red'][i]})
			i += 1
			
		serialized_data_list = RepayPieSerializer(data_list, many=True)
		content = {'data': serialized_data_list.data}
		return Response(content)

class returnpie_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		prod_id = request.GET.get('prod_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if prod_id == 'all':
			inv_list = Investment.objects.filter(usr_id=usr.id)
		else:
			inv_list = Investment.objects.filter(usr_id=usr.id, prod_id=prod_id)
		
		# assume user applies not more than 3 loans
		color_lib = {'red':['#E08283','#E7505A','#D91E18'],'green':['#36D7B7','#4DB3A2','#26C281'],'yellow':['#F4D03F','#F7CA18','#F3C200']}
		data_list = []
		i = 0
		for inv in inv_list:
			loan_list = Loan.objects.filter(inv_id = inv.id)
			prod = Product.objects.get(id = inv.prod_id)
			
			returned_principal = sum([loan.initial_amount - loan.remain_principal for loan in loan_list])
			returning_principal = sum([loan.remain_principal for loan in loan_list])
			overdue_principal = sum([loan.overdue_principal for loan in loan_list])
			
			if returned_principal != 0:
				data_list.append({'name':'Returned Principal ('+prod.name_en+')','amount':returned_principal,'color':color_lib['green'][i]})
			if returning_principal != 0:
				data_list.append({'name':'Returning Principal ('+prod.name_en+')','amount':returning_principal,'color':color_lib['yellow'][i]})
			if overdue_principal != 0:
				data_list.append({'name':'Overdue Principal ('+prod.name_en+')','amount':overdue_principal,'color':color_lib['red'][i]})
			i += 1
			
		serialized_data_list = RepayPieSerializer(data_list, many=True)
		content = {'data': serialized_data_list.data}
		return Response(content)

class activeinv_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		prod_id = request.GET.get('prod_id')
		
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		if prod_id == 'all':
			prod_list = Product.objects.filter(status='ACTIVE')
		else:
			prod_list = Product.objects.filter(id=prod_id)
		rd_loan_list = []
		for prod in prod_list:
			try:
				inv = Investment.objects.get(prod_id=prod.id, usr_id= usr.id)
			except ObjectDoesNotExist:
				continue
			loan_list = Loan.objects.filter(inv_id=inv.id)
			loan_list = [loan for loan in loan_list if loan.status=='DISBURSED' or 'PAYBACK' in loan.status]
			
			for loan in loan_list:
				try:
					bor = BorrowRequest.objects.get(id = loan.bor_id)
				except:
					continue
					
				rd_loan = {
				'shadow_datetime': timezone.localtime(bor.draw_down_date),
				'date': datetime.strftime(timezone.localtime(loan.update_timestamp), '%Y/%m/%d'),
				'ref_num': bor.ref_num,
				'amount': FLOAT_DATA_FORMAT.format(loan.initial_amount),
				'interest': FLOAT_DATA_FORMAT.format(loan.total_repay_amount_lender - loan.initial_amount),
				'installment': FLOAT_DATA_FORMAT.format(loan.instalment_lender),
				'draw_down_date': datetime.strftime(timezone.localtime(bor.draw_down_date), '%Y/%m/%d'),
				'expected_end_date': datetime.strftime(timezone.localtime(bor.expected_end_date), '%Y/%m/%d'),
				'overdue_loan_receivable': FLOAT_DATA_FORMAT.format(loan.overdue_principal + loan.overdue_interest),
				'loan_id': loan.id,
				}
				rd_loan_list.append(rd_loan)
		#serialized_data_list = ActiveInvSerializer(rd_loan_list, many=True)
		content = {'data': rd_loan_list}
		return Response(content)

class allocatedinv_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		lang = sup_fn.get_lang(request)
		
		prod_id = request.GET.get('prod_id')
		if prod_id == 'all':
			inv_list = Investment.objects.filter(usr_id=usr.id)
		else:
			inv_list = Investment.objects.filter(usr_id=usr.id,prod_id=prod_id)
			
		acc = Account.objects.get(usr_id = usr.id)
		#color_lib = {'red':['#E08283','#E7505A','#D91E18'],'green':['#36D7B7','#4DB3A2','#26C281'],'yellow':['#F4D03F','#F7CA18','#F3C200'],'purple':['#BF55EC']}
		color_lib = ['#E08283','#36D7B7','#F4D03F','#BF55EC','#3598DC']
		data_list = []
		i = 0
		if prod_id == 'all':
			total_balance = acc.balance + sum([inv.on_hold_amount + inv.usable_amount for inv in inv_list])
			if lang == 'en':
				data_list.append({'name': 'Total Account Balance', 'amount': total_balance, 'color': color_lib[i]})
				i += 1
				data_list.append({'name': 'Available Amount', 'amount': acc.balance, 'color': color_lib[i]})
				i += 1
			elif lang == 'zh':
				#data_list.append({'name': '總賬戶結餘', 'amount': total_balance, 'color': color_lib[i]})
				#i += 1
				data_list.append({'name': '可用金額', 'amount': acc.balance, 'color': color_lib[i]})
				i += 1
		
			for inv in inv_list:
				prod = Product.objects.get(id=inv.prod_id)
				if lang == 'en':
					data_list.append({'name': 'Queuing Amount in %s' % (prod.name_en), 'amount': inv.usable_amount + inv.on_hold_amount, 'color': color_lib[i]})
				elif lang == 'zh':
					data_list.append({'name': '分配在' + (prod.name_zh.encode('utf8')), 'amount': inv.usable_amount + inv.on_hold_amount, 'color': color_lib[i]})
					
				i += 1
		else:
			if len(inv_list) == 0:
				prod = Product.objects.get(id=prod_id)
				if lang == 'en':
					data_list.append({'name': 'Total Queuing Amount %s' % (prod.name_en), 'amount': 0, 'color': color_lib[i]})
					i += 1
					data_list.append({'name': 'Queuing Amount %s' % (prod.name_en) + ' (not matched)', 'amount': 0, 'color': color_lib[i]})
					i += 1
					data_list.append({'name': 'Queuing Amount %s' % (prod.name_en) + ' (on hold)', 'amount': 0, 'color': color_lib[i]})
					i += 1
				elif lang == 'zh':
					#data_list.append({'name': '總分配在' + (prod.name_zh.encode('utf8')), 'amount': 0, 'color': color_lib[i]})
					#i += 1
					data_list.append({'name': '分配在' + (prod.name_zh.encode('utf8')) + ' (未匹配)', 'amount': 0, 'color': color_lib[i]})
					i += 1
					data_list.append({'name': '分配在' + (prod.name_zh.encode('utf8')) + ' (未提款)', 'amount': 0, 'color': color_lib[i]})
					i += 1
			else:
				for inv in inv_list:
					prod = Product.objects.get(id=inv.prod_id)
					if lang == 'en':
						data_list.append({'name': 'Total Queuing Amount %s' % (prod.name_en), 'amount': inv.usable_amount + inv.on_hold_amount, 'color': color_lib[i]})
						i += 1
						data_list.append({'name': 'Queuing Amount %s' % (prod.name_en) + ' (not matched)', 'amount': inv.usable_amount, 'color': color_lib[i]})
						i += 1
						data_list.append({'name': 'Queuing Amount %s' % (prod.name_en) + ' (on hold)', 'amount': inv.on_hold_amount, 'color': color_lib[i]})
						i += 1
					elif lang == 'zh':
						#data_list.append({'name': '總分配在' + (prod.name_zh.encode('utf8')), 'amount': inv.usable_amount + inv.on_hold_amount, 'color': color_lib[i]})
						#i += 1
						data_list.append({'name': '分配在' + (prod.name_zh.encode('utf8')) + ' (未匹配)', 'amount': inv.usable_amount, 'color': color_lib[i]})
						i += 1
						data_list.append({'name': '分配在' + (prod.name_zh.encode('utf8')) + ' (未提款)', 'amount': inv.on_hold_amount, 'color': color_lib[i]})
						i += 1
		for data in data_list:
			data['amount'] = round(data['amount'], 2)
			
		#serialized_data_list = RepayPieSerializer(data_list, many=True)
		content = {'data': data_list}
		return Response(content)

class investedinv_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		lang = sup_fn.get_lang(request)
		
		prod_id = request.GET.get('prod_id')
		if prod_id == 'all':
			inv_list = Investment.objects.filter(usr_id=usr.id)
		else:
			inv_list = Investment.objects.filter(usr_id=usr.id,prod_id=prod_id)
		
		#color_lib = {'red':['#E08283','#E7505A','#D91E18'],'green':['#36D7B7','#4DB3A2','#26C281'],'yellow':['#F4D03F','#F7CA18','#F3C200']}
		color_lib = ['#E08283','#36D7B7','#F4D03F','#BF55EC','#3598DC']
		i = 0
		data_list = []
		returning_principal = 0
		returning_interest = 0
		returned_principal = 0
		returned_interest = 0
		overdue = 0
		for inv in inv_list:
			prod = Product.objects.get(id=inv.prod_id)
			loan_list = Loan.objects.filter(inv_id=inv.id)
			loan_list = [loan for loan in loan_list if 'DISBURSED' in loan.status or 'PAYBACK' in loan.status]
			returning_principal += sum([loan.remain_principal for loan in loan_list])
			returning_interest += sum([loan.remain_interest_lender for loan in loan_list])
			returned_principal += sum([loan.initial_amount-loan.remain_principal for loan in loan_list])
			returned_interest += sum([loan.initial_amount for loan in loan_list]) * prod.APR_lender * 0.01 * (prod.repayment_period / 12) - sum([loan.remain_interest_lender for loan in loan_list])
			overdue += sum([loan.overdue_principal+loan.overdue_interest for loan in loan_list])
		
		if lang == 'en':
			if prod_id == 'all':
				name = 'All Products'
			else:
				name = Product.objects.get(id = prod_id).name_en
				
			data_list.append({'name': 'Returning Principal', 'amount': returning_principal, 'color': color_lib[0]})
			data_list.append({'name': 'Returning Interest', 'amount': returning_interest, 'color': color_lib[1]})
			data_list.append({'name': 'Returned Principal', 'amount': returned_principal, 'color': color_lib[2]})
			data_list.append({'name': 'Returned Interest', 'amount': returned_interest, 'color': color_lib[3]})
			data_list.append({'name': 'Overdue', 'amount': overdue,'color': color_lib[4]})
		elif lang == 'zh':
			if prod_id == 'all':
				name = '全部產品'
			else:
				name = Product.objects.get(id = prod_id).name_zh.encode('utf8')
				
			data_list.append({'name': '待收本金', 'amount': returning_principal, 'color': color_lib[0]})
			data_list.append({'name': '待收利息', 'amount': returning_interest, 'color': color_lib[1]})
			data_list.append({'name': '已收本金', 'amount': returned_principal, 'color': color_lib[2]})
			data_list.append({'name': '已收利息', 'amount': returned_interest, 'color': color_lib[3]})
			data_list.append({'name': '逾期還款', 'amount': overdue,'color': color_lib[4]})
		
		for data in data_list:
			data['amount'] = round(data['amount'], 2)
			
		#serialized_data_list = RepayPieSerializer(data_list, many=True)
		content = {'data': data_list}
		return Response(content)

class portfolio_pie_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		lang = sup_fn.get_lang(request)
		
		this_month = datetime.strptime(request.GET.get('date'), '%m/%Y')
		this_month = pytz.timezone('Asia/Hong_Kong').localize(this_month)
		
		if datetime.now().month == this_month.month and datetime.now().year == this_month.year:
			period = datetime.strftime(this_month, '%Y/%m/%d')+' - '+datetime.strftime(datetime.now(), '%Y/%m/%d')
		else:
			month = this_month.month
			year = this_month.year
			month += 1
			if month == 13:
				year += 1
				month = 1
			next_month = datetime.strptime(str(year)+'/'+str(month), '%Y/%m')
			period = datetime.strftime(this_month, '%Y/%m/%d')+' - '+datetime.strftime(next_month - dt.timedelta(days=1), '%Y/%m/%d')
		
		if datetime.now().month == this_month.month and datetime.now().year == this_month.year:
			res_details = sup_fn.generate_portfolio_summary(usr_id=usr.id, date=this_month)
		else:
			try:
				mps = MonthlyPortfolioSummary.objects.get(usr_id=usr.id, month=this_month.month, year=this_month.year)
			except ObjectDoesNotExist:
				content = {}
				# data 1
				content['account_summary'] = {
					'Account Amount': FLOAT_DATA_FORMAT.format(0),
					'Unallocated Amount': FLOAT_DATA_FORMAT.format(0),
					'Un-matched Amount': FLOAT_DATA_FORMAT.format(0),
					'Matched Amount': FLOAT_DATA_FORMAT.format(0)
				}
				
				# data 2 & 3
				data_list = []
				if lang == 'en':
					data_list.append({'name': 'Normal Repayment', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Normal Settlement', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Early Settlement', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
				elif lang == 'zh':
					data_list.append({'name': '正常供款', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '最後一期供款', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '提早還款', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
				
				#serialized_data_list = RepayPieSerializer(data_list, many=True)
				content['data_2'] = data_list
				content['title_2'] = 'HK$'+FLOAT_DATA_FORMAT.format(0)
				
				data_list = []
				if lang == 'en':
					data_list.append({'name': 'Overdue 0 day', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Overdue 1-29 days', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Overdue 30-59 days', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Overdue 60-89 days', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': 'Overdue 90-120 days', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
				elif lang == 'zh':
					data_list.append({'name': '逾期0日', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '逾期1-29日', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '逾期30-59日', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '逾期60-89日', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
					data_list.append({'name': '逾期90-120日', 'amount': FLOAT_DATA_FORMAT.format(0), 'color': ''})
				
				#serialized_data_list = RepayPieSerializer(data_list, many=True)
				content['data_3'] = data_list
				
				content['title_3'] = 'Repayment Status'
				
				content['basic_info'] = {
					'Accrued Interest': FLOAT_DATA_FORMAT.format(0),
					'Weighted Annual Interest Rate': FLOAT_DATA_FORMAT.format(0)+'%',
					'Active Account': 0,
					'New Account': FLOAT_DATA_FORMAT.format(0)+' (included '+FLOAT_DATA_FORMAT.format(0)+' borrowers)',
					'Period': period,
				}
				if lang == 'zh':
					content['basic_info']['New Account'] = FLOAT_DATA_FORMAT.format(0)+' (包含'+FLOAT_DATA_FORMAT.format(0)+'個借款人)'
					
				return Response(content)
			else:
				res_details = json.loads(mps.details)
				
		content = {}
		# data 1
		dict = res_details['Portfolio Summary ($)']
		content['account_summary'] = {
			'Account Amount': FLOAT_DATA_FORMAT.format(dict['Unallocated Amount']+dict['Unmatched Amount']+dict['Matched Amount']),
			'Unallocated Amount': FLOAT_DATA_FORMAT.format(dict['Unallocated Amount']),
			'Un-matched Amount': FLOAT_DATA_FORMAT.format(dict['Unmatched Amount']),
			'Matched Amount': FLOAT_DATA_FORMAT.format(dict['Matched Amount'])
		}
			
		# data 2 & 3
		dict = res_details['Portfolio Summary ($)']
		data_list = []
		if lang == 'en':
			data_list.append({'name': 'Normal Repayment', 'amount': FLOAT_DATA_FORMAT.format(dict['Normal Run-Down']), 'color': ''})
			data_list.append({'name': 'Normal Settlement', 'amount': FLOAT_DATA_FORMAT.format(dict['Normal Settlement']), 'color': ''})
			data_list.append({'name': 'Early Settlement', 'amount': FLOAT_DATA_FORMAT.format(dict['Early Settlement']), 'color': ''})
		elif lang == 'zh':
			data_list.append({'name': '正常供款', 'amount': FLOAT_DATA_FORMAT.format(dict['Normal Run-Down']), 'color': ''})
			data_list.append({'name': '最後一期供款', 'amount': FLOAT_DATA_FORMAT.format(dict['Normal Settlement']), 'color': ''})
			data_list.append({'name': '提早還款', 'amount': FLOAT_DATA_FORMAT.format(dict['Early Settlement']), 'color': ''})
		
		#serialized_data_list = RepayPieSerializer(data_list, many=True)
		#content['data_2'] = serialized_data_list.data
		content['data_2'] = data_list
		content['title_2'] = 'HK$'+FLOAT_DATA_FORMAT.format(dict['Normal Run-Down']+dict['Normal Settlement']+dict['Early Settlement'])
		
		dict = res_details['Net Flow and Delinquency ($)']
		data_list = []
		if lang == 'en':
			data_list.append({'name': 'Overdue 0 day', 'amount': FLOAT_DATA_FORMAT.format(dict['0 DPD (Current)']), 'color': ''})
			data_list.append({'name': 'Overdue 1-29 day', 'amount': FLOAT_DATA_FORMAT.format(dict['1-29 DPD (Cycle 1)']), 'color': ''})
			data_list.append({'name': 'Overdue 30-59 day', 'amount': FLOAT_DATA_FORMAT.format(dict['30-59 DPD (Cycle 2)']), 'color': ''})
			data_list.append({'name': 'Overdue 60-89 day', 'amount': FLOAT_DATA_FORMAT.format(dict['60-89 DPD (Cycle 3)']), 'color': ''})
			data_list.append({'name': 'Overdue 90-120 day', 'amount': FLOAT_DATA_FORMAT.format(dict['90-120 DPD (Cycle 4)']), 'color': ''})
			data_list.append({'name': 'Overdue 120+ day', 'amount': FLOAT_DATA_FORMAT.format(res_details['Portfolio Summary ($)']['Gross Charge Off']), 'color': ''})
		elif lang == 'zh':
			data_list.append({'name': '逾期0日', 'amount': FLOAT_DATA_FORMAT.format(dict['0 DPD (Current)']), 'color': ''})
			data_list.append({'name': '逾期1-29日', 'amount': FLOAT_DATA_FORMAT.format(dict['1-29 DPD (Cycle 1)']), 'color': ''})
			data_list.append({'name': '逾期30-59日', 'amount': FLOAT_DATA_FORMAT.format(dict['30-59 DPD (Cycle 2)']), 'color': ''})
			data_list.append({'name': '逾期60-89日', 'amount': FLOAT_DATA_FORMAT.format(dict['60-89 DPD (Cycle 3)']), 'color': ''})
			data_list.append({'name': '逾期90-120日', 'amount': FLOAT_DATA_FORMAT.format(dict['90-120 DPD (Cycle 4)']), 'color': ''})
			data_list.append({'name': '逾期120+日', 'amount': FLOAT_DATA_FORMAT.format(res_details['Portfolio Summary ($)']['Gross Charge Off']), 'color': ''})
		
		#serialized_data_list = RepayPieSerializer(data_list, many=True)
		#content['data_3'] = serialized_data_list.data
		content['data_3'] = data_list
		content['title_3'] = 'Repayment Status'
		
		content['basic_info'] = {
			'Accrued Interest': FLOAT_DATA_FORMAT.format(res_details['Portfolio Summary ($)']['Accrued Interest']),
			'Weighted Annual Interest Rate': FLOAT_DATA_FORMAT.format(res_details['Return']['Weighted Annual Interest Rate'])+'%',
			'Active Account': res_details['Portfolio Summary (#)']['Active Account'],
			'New Account': FLOAT_DATA_FORMAT.format(res_details['Portfolio Summary ($)']['New Account'])+' (included '+str(res_details['Portfolio Summary (#)']['New Account'])+' borrowers)',
			'Period': period,
		}
		if lang == 'zh':
			content['basic_info']['New Account'] = FLOAT_DATA_FORMAT.format(res_details['Portfolio Summary ($)']['New Account'])+' (包含'+str(res_details['Portfolio Summary (#)']['New Account'])+'個借款人)'
			
		return Response(content)

class portfolio_line_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	
	def get(self, request, format=None):
		usr = sup_fn.get_user(request)
		lang = sup_fn.get_lang(request)
		
		trend = request.GET.get('trend')
		year = int(request.GET.get('year'))
		"""
		if lang == 'en':
			num_to_month = {
				1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
				7: 'July', 8: 'Aug', 9: 'Sept', 10: 'Oct', 11: 'Nov', 12: 'Dec'
			}
		elif lang == 'zh':
			num_to_month = {
				1: '1月', 2: '2月', 3: '3月', 4: '4月', 5: '5月', 6: '6月',
				7: '7月', 8: '8月', 9: '9月', 10: '10月', 11: '11月', 12: '12月'
			}
		"""
		num_to_month = {
			1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
			7: 'July', 8: 'Aug', 9: 'Sept', 10: 'Oct', 11: 'Nov', 12: 'Dec'
		}
			
		mps_list = MonthlyPortfolioSummary.objects.filter(usr_id=usr.id, year=year)
		data_list = []
		content = {}
		if year == datetime.now().year:
			months = datetime.now().month - 1
		else:
			months = 12
		for i in range(months):
			filtered_mps_list = [mps for mps in mps_list if mps.month==(i+1)]
			if len(filtered_mps_list) != 0:
				mps = filtered_mps_list[0]
				details = json.loads(mps.details)
				if trend == 'Outstanding Balance':
					data_list.append({'x': num_to_month[mps.month].encode('utf8'), 'y': details['Portfolio Summary ($)']['Matched Amount']})
				elif trend == 'No. of Active Account':
					data_list.append({'x': num_to_month[mps.month].encode('utf8'), 'y': details['Portfolio Summary (#)']['Active Account']})
				elif trend == 'Accrued Interest':
					data_list.append({'x': num_to_month[mps.month].encode('utf8'), 'y': details['Portfolio Summary ($)']['Accrued Interest']})
				elif trend == 'New Account':
					data_list.append({'x': num_to_month[mps.month].encode('utf8'), 'y': details['Portfolio Summary ($)']['New Account']})
				elif trend == 'No. of New Account':
					data_list.append({'x': num_to_month[mps.month].encode('utf8'), 'y': details['Portfolio Summary (#)']['New Account']})
			else:
				data_list.append({'x': num_to_month[i+1].encode('utf8'), 'y': 0})
			
		content['data'] = data_list
		content['title'] = trend
		if trend == 'Outstanding Balance':
			content['formatter'] = 'HK${value}'
		elif trend == 'No. of Active Account':
			content['formatter'] = '{value}'
		elif trend == 'Accrued Interest':
			content['formatter'] = 'HK${value}'
		elif trend == 'New Account':
			content['formatter'] = 'HK${value}'
		elif trend == 'No. of New Account':
			content['formatter'] = '{value}'
		return Response(content)