from django_datatables_view.base_datatable_view import BaseDatatableView
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework.response import Response

from peerloan.models import Account
from peerloan.models import AuditTrail
from peerloan.models import BorrowRequest
from peerloan.models import Investment
from peerloan.models import Product
from peerloan.models import PendingTaskNotification
from peerloan.models import Loan
from peerloan.models import Ledger
from peerloan.models import User
from peerloan.models import UserOperationRequest

from peerloan.serializers import AdminApplicationSerializer
from peerloan.serializers import AdminRepaymentSerializer
from peerloan.serializers import DepositSerializer
from peerloan.serializers import WithdrawSerializer
from peerloan.serializers import ApplyInvestorSerializer
from peerloan.serializers import FundMatchBorSerializer
from peerloan.serializers import FundMatchInvSerializer

import peerloan.peerloan_src.supporting_function as sup_fn

import json
from datetime import datetime
import pytz
from django.utils import timezone

FLOAT_DATA_FORMAT = '{:,.2f}'

class uor_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		data_src = request.GET.get('data_src')
		def try_KeyError(dict, key):
			try:
				return dict[key]
			except KeyError:
				return ''
		if data_src == 'deposit_money':
			uor_list = UserOperationRequest.objects.filter(type="Deposit Money")
			data_list = []
			for item in uor_list:
				details = json.loads(item.details)
				
				# check is pending task or not
				try:
					ptn = PendingTaskNotification.objects.get(ref_id=item.id, model='UserOperationRequest')
				except ObjectDoesNotExist:
					ptn_status = 'READ'
				else:
					ptn_status = ptn.status
				
				usr = User.objects.get(id=item.usr_id)
				usr_detail = json.loads(usr.detail_info)
				data_list.append({
				'acc_no': usr_detail['Lender No'],
				'date': datetime.strftime(timezone.localtime(item.create_timestamp), "%d/%m/%Y"),
				'amount': details['transferred_amount'],
				'bank_in_slip': details['file'],
				'bank_in_date': try_KeyError(details,'bank_in_date'),
				'bank_in_time': try_KeyError(details,'bank_in_time'),
				'ref_num': details['ref_num'],
				'uor_id': item.id,
				'status': item.status,
				'ptn_status': ptn_status,
				})
			#serialized_data_list = DepositSerializer(data_list, many=True)
			serialized_data_list = data_list
		if data_src == 'withdraw_money':
			uor_list = UserOperationRequest.objects.filter(type="Withdraw Money")
			data_list = []
			for item in uor_list:
				acc = Account.objects.get(usr_id=item.usr_id)
				details = json.loads(item.details)
				
				# check is pending task or not
				try:
					ptn = PendingTaskNotification.objects.get(ref_id=item.id, model='UserOperationRequest')
				except ObjectDoesNotExist:
					ptn_status = 'READ'
				else:
					ptn_status = ptn.status
				
				usr = User.objects.get(id=item.usr_id)
				usr_detail = json.loads(usr.detail_info)
				data_list.append({
				'acc_no': usr_detail['Lender No'],
				'date': datetime.strftime(timezone.localtime(item.create_timestamp), "%d/%m/%Y"),
				'amount': details['withdraw_amt'],
				'acc_balance': round(acc.balance+acc.on_hold_amt,2),
				'bank': try_KeyError(details,'bank_acc_proof'),
				'bank_acc_no': try_KeyError(details,'bank_acc_no'),
				'chq_no': try_KeyError(details,'chq_no'),
				'bank_in_date': try_KeyError(details,'bank_in_date'),
				'bank_in_time': try_KeyError(details,'bank_in_time'),
				'ref_num': details['ref_num'],
				'bank_in_slip': '/upload_file/?uor_id='+str(item.id),
				'confirm_date': try_KeyError(details,'confirm_date'),
				'uor_id': item.id,
				'status': item.status,
				'ptn_status': ptn_status,
				})
			#serialized_data_list = WithdrawSerializer(data_list, many=True)
			serialized_data_list = data_list
		if data_src == 'apply_to_be_investor':
			status = request.GET.get('status')
			uor_list = UserOperationRequest.objects.filter(type="Apply To Be Investor")
			
			if status != 'all':
				uor_list = [uor for uor in uor_list if status in uor.status]
			data_list = []
			for uor in uor_list:
				details = json.loads(uor.details)
				try:
					name = details['Corporate']['Company Name']
				except KeyError:
					name = details['Individual']['Surname'] + ' ' + details['Individual']['Given Name']
				
				# check is pending task or not
				try:
					ptn = PendingTaskNotification.objects.get(ref_id=uor.id, model='UserOperationRequest')
				except ObjectDoesNotExist:
					ptn_status = 'READ'
				else:
					ptn_status = ptn.status
				
				data_list.append({
				'application_no': sup_fn.try_KeyError(details['Individual'], 'Application No'),
				'name': name,
				'last_updated_time': datetime.strftime(timezone.localtime(uor.create_timestamp), '%Y/%m/%d %H:%M'),
				'last_updated_by': '--',
				'state': uor.status,
				'source': details['Individual']['Source of Fund'],
				'uor_id': uor.id,
				'hkid': details['Individual']['HKID'],
				'mobile_no': details['Individual']['Mobile'],
				'ptn_status': ptn_status,
				})
			#serialized_data_list = ApplyInvestorSerializer(data_list, many=True)
			serialized_data_list = data_list
		if data_src == 'repayment':
			bor_ref_num = request.GET.get('bor_ref_num')
			bor = BorrowRequest.objects.get(ref_num = bor_ref_num)
			uor_list = UserOperationRequest.objects.filter(type='Repayment', usr_id=bor.usr_id)
			data_list = []
			for uor in uor_list:
				details = json.loads(uor.details)
				
				if int(details['bor_id']) != bor.id:
					continue
				row = {
					'method': details['Deposit Method'],
					'type': details['Repayment Type'],
					'deposit_date': details['Deposit Date'],
					'amount': details['Deposit Amount'],
					'uploaded_doc': details['fname'],
					'submit_date': uor.create_timestamp.strftime('%Y/%m/%d'),
					'status': uor.status,
					'uor_id': uor.id
				}
				data_list.append(row)
			serialized_data_list = data_list
			
		content = {'data': serialized_data_list}
		return Response(content)

class bor_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		data_src = request.GET.get('data_src')
		prod_id = request.GET.get('prod_id')
		status = request.GET.get('status')
		cate = request.GET.get('cate')
		
		bor_list = BorrowRequest.objects.all()
		
		if data_src == 'fund_matching_bor':
			bor_list = [bor for bor in bor_list if bor.status in ['VALIDATED', 'FUND MATCHING', 'FUND MATCHING COMPLETED']]
			if prod_id != 'all':
				bor_list = [bor for bor in bor_list if int(bor.prod_id) == int(prod_id)]
			data_list = []
			for bor in bor_list:
				details = json.loads(bor.detail_info)
				prod = Product.objects.get(id=bor.prod_id)
				loan_list = Loan.objects.filter(bor_id=bor.id)
				matched_percentage = float(sum([loan.initial_amount for loan in loan_list])) / float(bor.amount)
				data_list.append({
				'loan_no': bor.ref_num,
				'amount_to_collect': bor.amount,
				'matched_percentage': str(round(matched_percentage * 100, 2)) + '%',
				'prod_name': prod.name_en,
				'application_date': datetime.strftime(timezone.localtime(bor.create_timestamp), '%Y/%m/%d %H:%M'),
				'agreement_date': details['Confirm Loan Agreement Date'],
				'no_of_investors': len(loan_list),
				})
			serialized_data_list = FundMatchBorSerializer(data_list, many=True)
			content = {'data': serialized_data_list.data}
			return Response(content)
		if cate == 'application':
			apply_state_list = ['AUTO APPROVED', 'DOC UPLOADED', 'AGREEMENT CONFIRMED', 'PENDING DOC/IV', 'VALIDATED', 'CANCELLED', 'REJECTED']
			bor_list = [bor for bor in bor_list if bor.status in apply_state_list]
		elif cate == 'disbursement':
			disburse_state_list = ['FUND MATCHING', 'FUND MATCHING COMPLETED', 'MEMORANDUM CONFIRMED']
			bor_list = [bor for bor in bor_list if bor.status in disburse_state_list]
			
		if prod_id != 'all':
			bor_list = [bor for bor in bor_list if int(bor.prod_id) == int(prod_id)]
		if status != 'all':
			bor_list = [bor for bor in bor_list if status in bor.status]
			
		data_list = []
		for bor in bor_list:
			details = json.loads(bor.detail_info)
			name = details['Surname'] + ' ' + details['Given Name']
			
			# check is pending task or not
			try:
				ptn = PendingTaskNotification.objects.get(ref_id=bor.id, model='BorrowRequest')
			except ObjectDoesNotExist:
				ptn_status = 'READ'
			else:
				ptn_status = ptn.status
			
			data_list.append({
			'application_no': bor.ref_num,
			'name': name,
			'application_time': datetime.strftime(timezone.localtime(bor.create_timestamp), '%Y/%m/%d %H:%M'),
			'amount': bor.amount,
			'prod_type': Product.objects.get(id=bor.prod_id).name_en,
			'follow_by': '--',
			'confirmed_identity': 'Y' if sup_fn.try_KeyError(details,'Confirmed Identity') == 'Y' else 'N',
			'last_updated_time': datetime.strftime(timezone.localtime(bor.update_timestamp), '%Y/%m/%d %H:%M'),
			'last_updated_by': '--',
			'disbursement_method': sup_fn.try_KeyError(details, 'Disbursement Method'),
			'state': bor.status,
			'bor_id': bor.id,
			'hkid': details['HKID'],
			'mobile_no': details['Mobile'],
			'ptn_status': ptn_status
			})
		#serialized_data_list = AdminApplicationSerializer(data_list, many=True)
		content = {'data': data_list}
		return Response(content)

class inv_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		data_src = request.GET.get('data_src')
		prod_id = request.GET.get('prod_id')
		
		inv_list = Investment.objects.filter(status="ACTIVE")
		
		if data_src == 'fund_matching_inv':
			if prod_id != 'all':
				inv_list = [inv for inv in inv_list if int(inv.prod_id) == int(prod_id)]
			data_list = []
			for inv in inv_list:
				prod = Product.objects.get(id=inv.prod_id)
				loan_list = Loan.objects.filter(inv_id=inv.id, status='MATCHED')
				if inv.total_amount != 0:
					matched_percentage = round(inv.on_hold_amount / inv.total_amount * 100, 2)
				else:
					matched_percentage = 0
				
				usr = User.objects.get(id=inv.usr_id)
				usr_detail = json.loads(usr.detail_info)
				data_list.append({
				'account_no': usr_detail['Lender No'],
				'investment_amount': inv.total_amount,
				'matched_percentage': str(matched_percentage) + '%',
				'investment_start_date': datetime.strftime(timezone.localtime(inv.create_timestamp), '%Y/%m/%d %H:%M'),
				'max_investment_amount': inv.max_amount_per_loan,
				'reinvest': inv.option,
				'no_of_borrowers': len(loan_list),
				'inv_id': inv.id,
				'prod_name': prod.name_en,
				})
			#serialized_data_list = FundMatchInvSerializer(data_list, many=True)
			content = {'data': data_list}
			return Response(content)

class repay_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		prod_id = request.GET.get('prod_id')
		status = request.GET.get('status')
		due_on = request.GET.get('due_on')
		
		bor_list = BorrowRequest.objects.all()
		bor_list = [bor for bor in bor_list if 'DISBURSED' in bor.status or 'PAYBACK' in bor.status]
		
		if prod_id != 'all':
			bor_list = [bor for bor in bor_list if int(bor.prod_id) == int(prod_id)]
		if status != 'all':
			bor_list = [bor for bor in bor_list if status in bor.status]
		if due_on != 'All':
			due_on = datetime.strptime(due_on, '%m/%d/%Y')
			bor_list = [bor for bor in bor_list if datetime.strptime(timezone.localtime(bor.create_timestamp).strftime('%m/%d/%Y'), '%m/%d/%Y')>= due_on]
			
		data_list = []
		for bor in bor_list:
			detail = json.loads(bor.detail_info)
			try:
				borrower_name = detail['Surname'] + ' ' + detail['Given Name']
			except KeyError:
				borrower_name = '--'
			prod = Product.objects.get(id = bor.prod_id)
			loan_list = Loan.objects.filter(bor_id = bor.id)
			loan_amount = sum([loan.initial_amount for loan in loan_list])
			outstanding_principal = sum([loan.remain_principal for loan in loan_list])
			# check is pending task or not
			
			try:
				ptn = PendingTaskNotification.objects.get(ref_id=bor.id, model='BorrowRequest')
			except ObjectDoesNotExist:
				ptn_status = 'READ'
			else:
				ptn_status = ptn.status
				
			data_list.append({
			'loan_no': bor.ref_num,
			'name': borrower_name,
			'initial_amount': loan_amount,
			'loan_amount': loan_amount,
			'outstanding_principal': outstanding_principal,
			'instalment_tenor': prod.repayment_period,
			'overpay_amount': FLOAT_DATA_FORMAT.format(bor.overpay_amount),
			'product': prod.name_en,
			'last_updated_time': bor.update_timestamp.strftime('%d/%m/%Y'),
			'last_updated_by': '--',
			'state': bor.status,
			'bor_id': bor.id,
			'ptn_status': ptn_status
			})
		#serialized_data_list = AdminRepaymentSerializer(data_list, many=True)
		content = {'data': data_list}
		return Response(content)

class account_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		prod_id = request.GET.get('prod_id')
		usr_list = User.objects.filter(type = 'L', status = 'ACTIVE')
		data_list = []
		for usr in usr_list:
			acc = Account.objects.get(usr_id = usr.id)
			inv_list = Investment.objects.filter(usr_id = usr.id)
			if prod_id != 'all':
				inv_list = [inv for inv in inv_list if inv.prod_id == int(prod_id)]
			loan_list = []
			for inv in inv_list:
				loans = Loan.objects.filter(inv_id = inv.id)
				loans = [loan for loan in loan_list if 'DISBURSED' in loan.status or 'PAYBACK' in loan.status]
				for loan in loans:
					loan_list.append(loan)
			details = json.loads(usr.detail_info)
			try:
				name = details['Individual']['Surname']+' '+details['Individual']['Given Name']
			except KeyError:
				name = '--'
			allocated_amount = sum([inv.usable_amount + inv.on_hold_amount for inv in inv_list]) + sum([loan.remain_principal for loan in loan_list])
			
			try:
				fund_matching_percentage = round((sum([inv.on_hold_amount for inv in inv_list])+sum([loan.remain_principal for loan in loan_list]))/allocated_amount, 2)
			except ZeroDivisionError:
				fund_matching_percentage = 0
			try:
				delinquent_percentage = round(sum([loan.remain_principal for loan in loan_list if 'OVERDUE' in loan.status])/sum([loan.remain_principal for loan in loan_list]), 2)
			except ZeroDivisionError:
				delinquent_percentage = 0
			data_list.append({
			'account_no': sup_fn.try_KeyError(details, 'Lender No'),
			'usr_id': usr.id,
			'name': name,
			'allocated_amount': round(allocated_amount, 2),
			'account_balance': round(acc.balance + acc.on_hold_amt, 2),
			'fund_matching_percentage': str(fund_matching_percentage)+'%',
			'delinquent_percentage': str(delinquent_percentage)+'%',
			'ledger': '--',
			})
		content = { 'data': data_list }
		return Response(content)

class ledger_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
		
		usr_id = request.GET.get('usr_id')
		bor_id = request.GET.get('bor_id')
		bor_ref_num = request.GET.get('bor_ref_num')
		from_ = request.GET.get('from')
		to = request.GET.get('to')
		
		if usr_id != None:
			if int(usr_id) != 0:
				usr = User.objects.get(id=usr_id)
			led_list = Ledger.objects.filter(usr_id=usr_id).order_by('id')
		if bor_id != None:
			led_list = Ledger.objects.filter(bor_id=bor_id).order_by('id')
		if bor_ref_num != None:
			led_list = Ledger.objects.filter(reference=bor_ref_num).order_by('id')
			led_list = [led for led in led_list if led.description not in ['Begin Balance', 'Loan Disbursement']]
		
		
		if from_ == '' or to == '':
			from_ = 'all'
			to = 'all'
		if from_ != 'all' and to != 'all':
			from_ = datetime.strptime(from_, '%Y-%m-%d')
			from_ = pytz.timezone('Asia/Hong_Kong').localize(from_)
			to = datetime.strptime(to, '%Y-%m-%d')
			to = pytz.timezone('Asia/Hong_Kong').localize(to)
			led_list = [led for led in led_list if led.create_timestamp >= from_ and led.create_timestamp <= to]
		
		data_list = []
		for led in led_list:
			data_list.append({
				'date': datetime.strftime(led.create_timestamp, '%Y/%m/%d %H:%M'),
				'description': led.description,
				'reference': led.reference,
				'debit': led.debit,
				'credit': led.credit,
				'balance': led.balance
			})
			
		content = { 'data': data_list }
		return Response(content)

class aut_list_json(APIView):
	renderer_classes = (JSONRenderer, )
	def get(self, request, format=None):
		# check XSS
		if sup_fn.checkHTMLtags([v for k, v in request.GET.iteritems()]):
			return HttpResponse('Invalid input.')
			
		usr_id = request.GET.get('usr_id')
		ref_id = request.GET.get('ref_id')
		model = request.GET.get('model')
		range = request.GET.get('range')
		
		data_list = []
		
		if range == 'bor_only':
			aut_list = AuditTrail.objects.all()
			aut_list = [aut for aut in aut_list if User.objects.get(id=aut.usr_id).type == request.session['handling_side']]
			for aut in aut_list:
				if aut.model == 'UserOperationRequest':
					try:
						uor = UserOperationRequest.objects.get(id=aut.ref_id)
					except:
						continue
					if uor.type == 'Apply To Be Investor':
						continue
						
				res = sup_fn.find_ref_num(id=aut.ref_id, model=aut.model)
				data_list.append({
					'date': datetime.strftime(aut.create_timestamp, '%Y/%m/%d %H:%M'),
					'description': aut.description,
					'reference': res['ref_num'],
					'by': aut.by
				})
		elif range == 'ldr_only':
			aut_list = AuditTrail.objects.all()
			#aut_list = [aut for aut in aut_list if User.objects.get(id=aut.usr_id).type == request.session['handling_side']]
			for aut in aut_list:
				aut_usr = User.objects.get(id = aut.usr_id)
				if aut_usr == 'B' and aut.model != 'UserOperationRequest':
					# not Apply To Be Investor case
					continue
				if aut_usr == 'B' and aut.model == 'UserOperationRequest':
					try:
						uor = UserOperationRequest.objects.get(id=aut.ref_id)
					except:
						# Apply To Be Investor request deleted
						continue
					if uor.type != 'Apply To Be Investor':
						continue
						
				res = sup_fn.find_ref_num(id=aut.ref_id, model=aut.model)
				data_list.append({
					'date': datetime.strftime(aut.create_timestamp, '%Y/%m/%d %H:%M'),
					'description': aut.description,
					'reference': res['ref_num'],
					'by': aut.by
				})
		else:
			aut_list = AuditTrail.objects.filter(usr_id=usr_id, ref_id=int(ref_id), model=model)
			for aut in aut_list:
				res = sup_fn.find_ref_num(id=aut.ref_id, model=aut.model)
				if res['type'] != request.GET.get('type'):
					continue
				data_list.append({
					'date': datetime.strftime(aut.create_timestamp, '%Y/%m/%d %H:%M'),
					'description': aut.description,
					'by': aut.by
				})
		content = { 'data': data_list }
		return Response(content)