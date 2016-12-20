#!/usr/bin/env python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_peerloan.settings")
django.setup()

from django.template.loader import render_to_string, get_template
from django.utils import timezone
from django.conf import settings

import peerloan.models as model
import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
import datetime as dt
import pytz
import json
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException

FLOAT_DATA_FORMAT = '{:,.2f}'
SEND_SMS = True

class BorrowerSMS:
	
	#def __init__(self, bor_usr=None):
	#	self.bor_usr = bor_usr
	#	
	def no_response_after_AIP_one_day(self, bor):
		details = json.loads(bor.detail_info)
		content = render_to_string('smsing_peerloan/borrower/no_response_after_AIP_one_day.txt')
		self.send_SMS(to_mobile=details['Mobile'], content=content)
	
	def fund_matching_SMS(self, bor):
		details = json.loads(bor.detail_info)
		content = render_to_string('smsing_peerloan/borrower/fund_matching_SMS.txt')
		self.send_SMS(to_mobile=details['Mobile'], content=content)
	
	def disbursed_final_confirmation_SMS(self, bor):
		details = json.loads(bor.detail_info)
		content = render_to_string('smsing_peerloan/borrower/disbursed_final_confirmation_SMS.txt')
		self.send_SMS(to_mobile=details['Mobile'], content=content)
	
	# general sub function
	def send_SMS(self, to_mobile, content):
		if SEND_SMS == False:
			return None
			
		ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
		AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
		client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)
		try:
			
			message = client.messages.create(
				body=content,  # Message body, if any
				to="+852" + str(to_mobile),
				from_="+13177080486",
			)
		except TwilioRestException as e:
			print e

class LenderSMS:
	
	#def __init__(self, bor_usr=None):
	#	self.bor_usr = bor_usr
	#	
	def approved(self, uor):
		details = json.loads(uor.details)
		content = render_to_string('smsing_peerloan/lender/approved.txt')
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def confirmed_deposit(self, uor):
		usr = model.User.objects.get(id=uor.usr_id)
		details = json.loads(usr.detail_info)
		content = render_to_string('smsing_peerloan/lender/confirmed_deposit.txt')
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def rejected_deposit(self, uor):
		usr = model.User.objects.get(id=uor.usr_id)
		details = json.loads(usr.detail_info)
		content = render_to_string('smsing_peerloan/lender/rejected_deposit.txt')
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def withdrawn_confirmed(self, uor):
		usr = model.User.objects.get(id=uor.usr_id)
		details = json.loads(usr.detail_info)
		uor_details = json.loads(uor.details)
		
		info = {
			'datetime': uor_details['confirm_date'],
		}
		
		content = render_to_string('smsing_peerloan/lender/withdrawn_confirmed.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def withdrawn_rejected(self, uor):
		usr = model.User.objects.get(id=uor.usr_id)
		details = json.loads(usr.detail_info)
		
		content = render_to_string('smsing_peerloan/lender/withdrawn_rejected.txt')
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def fund_matching_completed_every_loan(self, loan):
		inv = model.Investment.objects.get(id=loan.inv_id)
		bor = model.BorrowRequest.objects.get(id=loan.bor_id)
		usr = model.User.objects.get(id=inv.usr_id)
		details = json.loads(usr.detail_info)
		
		info = {
			'amount': FLOAT_DATA_FORMAT.format(loan.initial_amount),
			'bor_ref_num': bor.ref_num,
		}
		content = render_to_string('smsing_peerloan/lender/fund_matching_completed_every_loan.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def fund_matching_completed_every_day(self, usr):
		details = json.loads(usr.detail_info)
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		
		today = timezone.localtime(timezone.now()) - dt.timedelta(days=1)
		amount = 0
		num_of_loans = 0
		
		for inv in inv_list:
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				if bor.draw_down_date == None:
					continue
				if bor.draw_down_date.strftime('%Y/%m/%d') == today.strftime('%Y/%m/%d'):
					amount += loan.initial_amount
					num_of_loans += 1
		
		info = {
			'amount': FLOAT_DATA_FORMAT.format(amount),
			'num_of_loans': num_of_loans,
			'today_date': today.strftime('%Y/%m/%d')
		}
		content = render_to_string('smsing_peerloan/lender/fund_matching_completed_every_day.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def fund_matching_completed_every_week(self, usr):
		details = json.loads(usr.detail_info)
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		
		# use second day 00:00:00 to cut off
		today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
		today = pytz.timezone('Asia/Hong_Kong').localize(today)
		from_date = today - dt.timedelta(days=7)
		
		amount = 0
		num_of_loans = 0
		
		for inv in inv_list:
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				if bor.draw_down_date == None:
					continue
				try:
					bor.draw_down_date.tzinfo
				except AttributeError:
					continue
				if from_date <= bor.draw_down_date and bor.draw_down_date < today:
					amount += loan.initial_amount
					num_of_loans += 1
		
		info = {
			'amount':FLOAT_DATA_FORMAT.format(amount),
			'num_of_loans': num_of_loans,
			'from_date': from_date.strftime('%Y/%m/%d'),
			'to_date': (today-dt.timedelta(days=1)).strftime('%Y/%m/%d'),
		}
		content = render_to_string('smsing_peerloan/lender/fund_matching_completed_every_week.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def fund_matching_completed_every_month(self, usr):
		details = json.loads(usr.detail_info)
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		
		# use second day 00:00:00 to cut off
		today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
		today = pytz.timezone('Asia/Hong_Kong').localize(today)
		to_date = today - dt.timedelta(days=1)
		from_date = datetime.strptime('%s/%s/1'%(to_date.year, to_date.month), '%Y/%m/%d')
		
		amount = 0
		num_of_loans = 0
		
		for inv in inv_list:
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				if bor.draw_down_date == None:
					continue
				try:
					bor.draw_down_date.tzinfo
				except AttributeError:
					continue
				if from_date <= bor.draw_down_date and bor.draw_down_date < today:
					amount += loan.initial_amount
					num_of_loans += 1
		
		info = {
			'amount': FLOAT_DATA_FORMAT.format(amount),
			'num_of_loans': num_of_loans,
			'this_month': from_date.strftime('%B'),
		}
		content = render_to_string('smsing_peerloan/lender/fund_matching_completed_every_month.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	def fund_matching_completed_all_fund_matched(self, loan):
		inv = model.Investment.objects.get(id=loan.inv_id)
		usr = model.User.objects.get(id=inv.usr_id)
		details = json.loads(usr.detail_info)
		loan_list = model.Loan.objects.filter(inv_id=inv.id)
		
		info = {
			'num_of_loans': len(loan_list),
		}
		content = render_to_string('smsing_peerloan/lender/fund_matching_completed_all_fund_matched.txt', info)
		self.send_SMS(to_mobile=details['Individual']['Mobile'], content=content)
	
	# general sub function
	def send_SMS(self, to_mobile, content):
		if SEND_SMS == False:
			return None
			
		ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
		AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
		client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)
		try:
			
			message = client.messages.create(
				body=content,  # Message body, if any
				to="+852" + str(to_mobile),
				from_="+13177080486",
			)
		except TwilioRestException as e:
			print e

class GeneralSMS():
	
	def send_OTP(self, OTP, mobile):
		content = "Zwap: Your One-time Password is: " + OTP
		self.send_SMS(to_mobile=mobile, content=content)
	
	# general sub function
	def send_SMS(self, to_mobile, content):
		if SEND_SMS == False:
			return None
			
		ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
		AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
		client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)
		try:
			
			message = client.messages.create(
				body=content,  # Message body, if any
				to="+852" + str(to_mobile),
				from_="+13177080486",
			)
		except TwilioRestException as e:
			print e