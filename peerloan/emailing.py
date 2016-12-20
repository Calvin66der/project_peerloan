#!/usr/bin/env python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_peerloan.settings")
django.setup()

from django.template.loader import render_to_string, get_template
from django.core.mail import EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

import peerloan.models as model
import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
import datetime as dt
import pytz
import json
import smtplib

FLOAT_DATA_FORMAT = '{:,.2f}'
SEND_EMAIL = True

class BorrowerEmail:
	subject = ''
	content = ''
	
	def __init__(self, bor):
		self.bor = bor
	
	def one_day_after_auto_approved(self):
		self.subject = 'Zwap: Congratulations! Your application is pre-approved!'
		
		bor = self.bor
		prod = model.Product.objects.get(id=bor.prod_id)
		
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_amount': bor.amount,
			'monthly_flat_rate': FLOAT_DATA_FORMAT.format(bor.getMonthlyFlatRate(prod.repayment_period, prod.repayment_plan))+'%',
			'annual_interest_rate': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower))+'%',
			'repayment_period': str(prod.repayment_period)+' months',
			'month_instalment': FLOAT_DATA_FORMAT.format(bor.instalment_borrower)
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/one_day_after_auto_approved.txt', info)
		self.send_email()
	
	def reject_loan_application(self):
		self.subject = 'Zwap: Your application result'
		
		bor = self.bor
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/reject_loan_application.txt', info)
		
		self.send_email()
	
	def cancel_loan_application(self):
		self.subject = 'Zwap: Application have been cancelled'
		
		bor = self.bor
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/cancel_loan_application.txt', info)
		
		self.send_email()
	
	def last_instalment(self):
		self.subject = 'Zwap: Loan instalment completed'
		
		bor = self.bor
		details = json.loads(bor.detail_info)
		prod = model.Product.objects.get(id=bor.prod_id)
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=prod.repayment_period)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_account': bor.ref_num,
			'due_date': los.due_date,
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/last_instalment.txt', info)
		
		self.send_email()
	
	def copy_of_loan_agreement(self):
		self.subject = 'Zwap: Copy of loan agreement'
		
		bor = self.bor
		prod = model.Product.objects.get(id=bor.prod_id)
		
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_amount': FLOAT_DATA_FORMAT.format(bor.amount),
			'monthly_flat_rate': FLOAT_DATA_FORMAT.format(bor.getMonthlyFlatRate(prod.repayment_period, prod.repayment_plan))+'%',
			'annual_interest_rate': FLOAT_DATA_FORMAT.format(bor.getBorAPR(prod.APR_borrower if prod.fake_APR_borrower == None else prod.fake_APR_borrower))+'%',
			'repayment_period': str(prod.repayment_period)+' months',
			'monthly_instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower)
		}
		
		if prod.repayment_plan == 'Promotion Balloon Payment':
			info['repayment_period'] = '9 months'
		
		self.content = render_to_string('emailing_peerloan/borrower/copy_of_loan_agreement.txt', info)
		
		attachments = []
		
		# attach lender agreement
		fpath = sup_fn.generate_docx(id=bor.id, model='BorrowRequest', doc_type='Loan Agreement')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		attachments.append({
			'fname': 'loan_agreement.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
		})
		
		# attach repayment_schedule
		fpath = sup_fn.generate_xlsx(id=bor.id, model='BorrowRequest', doc_type='Repayment Schedule')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		attachments.append({
			'fname': 'Schedule 1 - Repayment Schedule.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
		})
		
		# attach MLO & PDPO
		for fname in ['MLO.pdf', 'PDPO.pdf']:
			fpath = '/home/ubuntu/project_peerloan/document_peerloan/' + fname
			with open(fpath, 'rb') as f:
				fcontent = f.read()
			attachments.append({
				'fname': fname,
				'fcontent': fcontent,
				'ftype': 'application/pdf',
			})
		
		self.send_email(attachments=attachments)
	
	def loan_memorandum(self):
		self.subject = 'Zwap: Loan Memorandum'
		
		bor = self.bor
		
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/loan_memorandum.txt', info)
		
		self.send_email()
	
	def autopay_authorization_required(self):
		self.subject = 'Zwap: Confirmation of Disbursement'
		
		bor = self.bor
		
		details = json.loads(bor.detail_info)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/autopay_authorization_required.txt', info)
		
		attachments = []
		
		# attach memorandum agreement
		fpath = sup_fn.generate_docx(id=bor.id, model='BorrowRequest', doc_type='Memorandum Agreement')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		attachments.append({
			'fname': 'memorandum_agreement.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
		})
		
		# attach DDA
		fpath = sup_fn.generate_docx(id=bor.id, model='BorrowRequest', doc_type='DDA')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		attachments.append({
			'fname': 'direct_debit_authorisation.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
		})
		
		# attach repayment_schedule
		fpath = sup_fn.generate_xlsx(id=bor.id, model='BorrowRequest', doc_type='Repayment Schedule')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		attachments.append({
			'fname': 'Schedule 1 - Repayment Schedule.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
		})
		
		
		self.send_email(attachments=attachments)
		
	def last_instalment(self):
		bor = self.bor
		details = json.loads(bor.detail_info)
		self.subject = 'Zwap: Finishing Loan Repayment'
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
		
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_account': bor.ref_num,
			'due_date': los.due_date,
			
		}
		self.content = render_to_string('emailing_peerloan/borrower/last_instalment.txt', info)
		self.send_email()
	
	
	def repayment_reminder(self):
		bor = self.bor
		details = json.loads(bor.detail_info)
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
		self.subject = 'Zwap: %s Repayment Reminder'%(los.due_date)
		
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'instalment_amount': FLOAT_DATA_FORMAT.format(bor.instalment_borrower),
			'due_date': los.due_date,
			'hang_seng_bank_account': '239498348883',
			
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/repayment_reminder.txt', info)
		self.send_email()
		
	def overdue_repayment_reminder(self):
		bor = self.bor
		details = json.loads(bor.detail_info)
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
		self.subject = 'Zwap: Overdue Repayment Reminder'
		
		remain_instalment = (los.instalment-los.paid_principal-los.paid_interest)
		remain_overdue_interest = (los.overdue_interest_remained+los.overdue_interest_unpay_paid)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_account_number': bor.ref_num,
			'due_date': los.due_date,
			'instalment': FLOAT_DATA_FORMAT.format(remain_instalment),
			'overdue_interest': FLOAT_DATA_FORMAT.format(remain_overdue_interest),
			'total_amount': FLOAT_DATA_FORMAT.format(remain_instalment + remain_overdue_interest),
			'tenor': '%s%s'%(bor.repaid_month+1, sup_fn.date_postfix(bor.repaid_month+1))
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/overdue_repayment_reminder.txt', info)
		self.send_email()
	
	def final_overdue_repayment_reminder(self):
		bor = self.bor
		details = json.loads(bor.detail_info)
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
		self.subject = 'Zwap: Final Overdue Repayment Reminder'
		
		remain_instalment = (los.instalment-los.paid_principal-los.paid_interest)
		remain_overdue_interest = (los.overdue_interest_remained+los.overdue_interest_unpay_paid)
		info = {
			'usr_name': details['Surname'] + ' ' + details['Given Name'],
			'loan_account_number': bor.ref_num,
			#'due_date': los.due_date,
			'instalment': FLOAT_DATA_FORMAT.format(remain_instalment),
			'overdue_interest': FLOAT_DATA_FORMAT.format(remain_overdue_interest),
			'total_amount': FLOAT_DATA_FORMAT.format(remain_instalment + remain_overdue_interest),
			#'tenor': '%s%s'%(bor.repaid_month+1, sup_fn.date_postfix)
		}
		
		self.content = render_to_string('emailing_peerloan/borrower/final_overdue_repayment_reminder.txt', info)
		self.send_email()
	
	# general sub function
	def send_email(self, attachments=None):
		if SEND_EMAIL == False:
			return None
			
		usr = model.User.objects.get(id=self.bor.usr_id)
		msg = EmailMessage(self.subject, self.content, to=[usr.email])
		
		if attachments != None:
			for item in attachments:
				msg.attach(item['fname'], item['fcontent'], item['ftype'])
		try:
			msg.send()
		except smtplib.SMTPRecipientsRefused:
			''
		
	def send_html_email(self):
		if SEND_EMAIL == False:
			return None
			
		usr = model.User.objects.get(id=self.bor.usr_id)
		msg = EmailMultiAlternatives(self.subject, '', to=[usr.email])
		msg.attach_alternative(self.content, "text/html")
		try:
			msg.send()
		except smtplib.SMTPRecipientsRefused:
			''

class LenderEmail:
	subject = ''
	content = ''
	
	def __init__(self, uor=None, loan=None, inv_usr=None):
		self.uor = uor
		self.loan = loan
		self.inv_usr = inv_usr
	
	def lender_application(self):
		self.subject = 'Zwap: Submitted lender application'
		
		uor = self.uor
		details = json.loads(uor.details)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/lender/lender_application.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	def approved_lender_application(self):
		self.subject = 'Zwap: Application approved!'
		
		uor = self.uor
		details = json.loads(uor.details)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/lender/approved_lender_application.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	
	def reject_lender_application(self):
		self.subject = 'Zwap: Your application result'
		
		uor = self.uor
		details = json.loads(uor.details)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/lender/reject_lender_application.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	def cancel_lender_application(self):
		self.subject = 'Zwap: Application has been cancelled'
		
		uor = self.uor
		details = json.loads(uor.details)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/lender/cancel_lender_application.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	def lender_agreement(self):
		self.subject = 'Zwap: Lender Agreement'
		
		uor = self.uor
		details = json.loads(uor.details)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
		}
		
		self.content = render_to_string('emailing_peerloan/lender/lender_agreement.txt', info)
		
		attachments = []
		# attach lender agreement
		fpath = sup_fn.generate_docx(id=uor.id, model='UserOperationRequest', doc_type='Lender Agreement')
		with open(fpath, 'rb') as f:
			fcontent = f.read()
		
		attachments.append({
			'fname': 'lender_agreement.pdf',
			'fcontent': fcontent,
			'ftype': 'application/pdf',
			
		})
		
		self.send_email(to_usr_id=uor.usr_id, attachments=attachments)
	
	def deposit_amount_confirmed(self):
		self.subject = 'Zwap: Deposit amount confirmed'
		
		uor = self.uor
		details = json.loads(uor.details)
		usr = model.User.objects.get(id=uor.usr_id)
		usr_details = json.loads(usr.detail_info)
		info = {
			'usr_name': usr_details['Individual']['Surname'] + ' ' + usr_details['Individual']['Given Name'],
			'deposit_amount': details['transferred_amount']
		}
		
		self.content = render_to_string('emailing_peerloan/lender/deposit_amount_confirmed.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	def withdraw_amount_confirmed(self):
		self.subject = 'Zwap: Confirmed withdrawn instruction'
		
		uor = self.uor
		details = json.loads(uor.details)
		usr = model.User.objects.get(id=uor.usr_id)
		usr_details = json.loads(usr.detail_info)
		info = {
			'usr_name': usr_details['Individual']['Surname'] + ' ' + usr_details['Individual']['Given Name'],
			'withdraw_amount': FLOAT_DATA_FORMAT.format(details['withdraw_amt']),
			'confirm_datetime': details['confirm_date']
		}
		
		self.content = render_to_string('emailing_peerloan/lender/withdraw_amount_confirmed.txt', info)
		self.send_email(to_usr_id=uor.usr_id)
	
	def fund_matching_notification_every_loan(self):
		self.subject = 'Zwap: Fund Matching Notification (every loan)'
		
		loan = self.loan
		bor = model.BorrowRequest.objects.get(id=loan.bor_id)
		inv = model.Investment.objects.get(id=loan.inv_id)
		usr = model.User.objects.get(id=inv.usr_id)
		details = json.loads(usr.detail_info)
		
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'loan_amount': FLOAT_DATA_FORMAT.format(loan.initial_amount),
			'bor_ref_num': bor.ref_num,
		}
		
		self.content = render_to_string('emailing_peerloan/lender/fund_matching_notification_every_loan.txt', info)
		self.send_email(to_usr_id=usr.id)
	
	def fund_matching_notification_daily_result(self):
		self.subject = 'Zwap: Fund Matching Notification (daily result)'
		
		today = timezone.localtime(timezone.now()) - dt.timedelta(days=1)
		usr = self.inv_usr
		deposited_amount = 0
		matched_amount = 0
		queueing_amount = 0
		num_of_borrowers = 0
		
		# update deposited_amount
		uor_list = model.UserOperationRequest.objects.filter(usr_id=usr.id, type='Deposit Money', status='CONFIRMED')
		for uor in uor_list:
			if uor.updated_timestamp.strftime('%Y/%m/%d') == today.strftime('%Y/%m/%d'):
				details = json.loads(uor.details)
				amount = float(details['transferred_amount'])
				deposited_amount += amount
		
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		for inv in inv_list:
			# update matched amount
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				if bor.draw_down_date == None:
					continue
				if bor.draw_down_date.strftime('%Y/%m/%d') == today.strftime('%Y/%m/%d'):
					matched_amount += loan.initial_amount
					num_of_borrowers += 1
			# update queueing amount
			queueing_amount += inv.usable_amount + inv.on_hold_amount
		
		details = json.loads(usr.detail_info)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'today_date': today.strftime('%Y/%m/%d'),
			'deposited_amount': FLOAT_DATA_FORMAT.format(deposited_amount),
			'matched_amount': FLOAT_DATA_FORMAT.format(matched_amount),
			'queueing_amount': FLOAT_DATA_FORMAT.format(queueing_amount),
			'num_of_borrowers': (num_of_borrowers),
		}
		
		self.content = render_to_string('emailing_peerloan/lender/fund_matching_notification_daily_result.txt', info)
		self.send_email(to_usr_id=usr.id)
	
	def fund_matching_notification_weekly_result(self):
		self.subject = 'Zwap: Fund Matching Notification (weekly result)'
		
		# use second day 00:00:00 to cut off
		today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
		today = pytz.timezone('Asia/Hong_Kong').localize(today)
		from_date = today - dt.timedelta(days=7)
		usr = self.inv_usr
		deposited_amount = 0
		matched_amount = 0
		queueing_amount = 0
		num_of_borrowers = 0
		
		# update deposited_amount
		uor_list = model.UserOperationRequest.objects.filter(usr_id=usr.id, type='Deposit Money', status='CONFIRMED')
		for uor in uor_list:
			if from_date <= uor.updated_timestamp and uor.updated_timestamp < today:
				details = json.loads(uor.details)
				amount = float(details['transferred_amount'])
				deposited_amount += amount
		
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		for inv in inv_list:
			# update matched amount
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				try:
					bor.draw_down_date.tzinfo
				except AttributeError:
					continue
					
				if bor.draw_down_date == None:
					continue
				if from_date <= bor.draw_down_date and bor.draw_down_date < today:
					matched_amount += loan.initial_amount
					num_of_borrowers += 1
			# update queueing amount
			queueing_amount += inv.usable_amount + inv.on_hold_amount
		
		details = json.loads(usr.detail_info)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'from_date': from_date.strftime('%Y/%m/%d'),
			'to_date': (today-dt.timedelta(days=1)).strftime('%Y/%m/%d'),
			'deposited_amount': FLOAT_DATA_FORMAT.format(deposited_amount),
			'matched_amount': FLOAT_DATA_FORMAT.format(matched_amount),
			'queueing_amount': FLOAT_DATA_FORMAT.format(queueing_amount),
			'num_of_borrowers': (num_of_borrowers),
		}
		
		self.content = render_to_string('emailing_peerloan/lender/fund_matching_notification_weekly_result.txt', info)
		self.send_email(to_usr_id=usr.id)
	
	def fund_matching_notification_monthly_result(self):
		self.subject = 'Zwap: Fund Matching Notification (monthly result)'
		
		# use second day 00:00:00 to cut off
		today = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
		today = pytz.timezone('Asia/Hong_Kong').localize(today)
		to_date = today - dt.timedelta(days=1)
		from_date = datetime.strptime('%s/%s/1'%(to_date.year, to_date.month), '%Y/%m/%d')
		from_date = pytz.timezone('Asia/Hong_Kong').localize(from_date)
		usr = self.inv_usr
		deposited_amount = 0
		matched_amount = 0
		queueing_amount = 0
		num_of_borrowers = 0
		
		# update deposited_amount
		uor_list = model.UserOperationRequest.objects.filter(usr_id=usr.id, type='Deposit Money', status='CONFIRMED')
		for uor in uor_list:
			if from_date <= uor.updated_timestamp and uor.updated_timestamp < today:
				details = json.loads(uor.details)
				amount = float(details['transferred_amount'])
				deposited_amount += amount
		
		inv_list = model.Investment.objects.filter(usr_id=usr.id)
		for inv in inv_list:
			# update matched amount
			loan_list = model.Loan.objects.filter(inv_id=inv.id)
			for loan in loan_list:
				bor = model.BorrowRequest.objects.get(id=loan.bor_id)
				try:
					bor.draw_down_date.tzinfo
				except AttributeError:
					continue
					
				if bor.draw_down_date == None:
					continue
				if from_date <= bor.draw_down_date and bor.draw_down_date < today:
					matched_amount += loan.initial_amount
					num_of_borrowers += 1
			# update queueing amount
			queueing_amount += inv.usable_amount + inv.on_hold_amount
		
		details = json.loads(usr.detail_info)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'this_month': from_date.strftime('%B'),
			'deposited_amount': FLOAT_DATA_FORMAT.format(deposited_amount),
			'matched_amount': FLOAT_DATA_FORMAT.format(matched_amount),
			'queueing_amount': FLOAT_DATA_FORMAT.format(queueing_amount),
			'num_of_borrowers': (num_of_borrowers),
		}
		
		self.content = render_to_string('emailing_peerloan/lender/fund_matching_notification_monthly_result.txt', info)
		self.send_email(to_usr_id=usr.id)
	
	def fund_matching_notification_all_fund_matched(self):
		self.subject = 'Zwap: Fund Matching Notification (all fund matched)'
		loan = self.loan
		inv = model.Investment.objects.get(id=loan.inv_id)
		loan_list = model.Loan.objects.filter(inv_id=inv.id)
		usr = model.User.objects.get(id=inv.usr_id)
		
		details = json.loads(usr.detail_info)
		info = {
			'usr_name': details['Individual']['Surname'] + ' ' + details['Individual']['Given Name'],
			'num_of_borrowers': len(loan_list),
		}
		
		self.content = render_to_string('emailing_peerloan/lender/fund_matching_notification_all_fund_matched.txt', info)
		self.send_email(to_usr_id=usr.id)
	
	
	# general sub function
	def send_email(self, attachments=None, to_usr_id=None):
		if SEND_EMAIL == False:
			return None
			
		usr = model.User.objects.get(id=to_usr_id)
		msg = EmailMessage(self.subject, self.content, to=[usr.email])
		
		if attachments != None:
			for item in attachments:
				msg.attach(item['fname'], item['fcontent'], item['ftype'])
		try:
			msg.send()
		except smtplib.SMTPRecipientsRefused:
			''
		
	def send_html_email(self):
		if SEND_EMAIL == False:
			return None
			
		usr = model.User.objects.get(id=self.bor.usr_id)
		msg = EmailMultiAlternatives(self.subject, '', to=[usr.email])
		msg.attach_alternative(self.content, "text/html")
		try:
			msg.send()
		except smtplib.SMTPRecipientsRefused:
			''

class GeneralEmail:
	subject = ''
	content = ''
	
	def __init__(self, email_addr):
		self.email_addr = email_addr
	
	def account_activate(self, token):
		self.subject = 'Zwap: Account Activation'
		
		info = {
			'token': token,
		}
		
		self.content = render_to_string('emailing_peerloan/general/account_activate.txt', info)
		self.send_email()
	
	def reset_password(self, token):
		self.subject = 'Zwap: Account Password Reset'
		
		info = {
			'token': token,
		}
		
		self.content = render_to_string('emailing_peerloan/general/reset_password.txt', info)
		self.send_email()
		
	def unlock_account(self, token):
		self.subject = 'Zwap: Unlock Account'
		
		info = {
			'token': token,
		}
		
		self.content = render_to_string('emailing_peerloan/general/unlock_account.txt', info)
		self.send_email()
	
	def OTP_email(self, OTP_code, subject, type):
		self.subject = subject
		
		info = {
			'OTP_code': OTP_code,
			'type': type,
		}
		self.content = render_to_string('emailing_peerloan/general/OTP_email.txt', info)
		self.send_email()
	"""
	def OTP_for_change_mobile(self, OTP_code):
		self.subject = 'Zwap: OTP Code for Changing Mobile'
		
		info = {
			'OTP_code': OTP_code,
		}
		self.content = render_to_string('emailing_peerloan/general/OTP_for_change_mobile.txt', info)
		self.send_email()
	
	def OTP_for_lender_agreement(self, OTP_code):
		self.subject = 'Zwap: OTP Code for Lender Agreement'
		
		info = {
			'OTP_code': OTP_code,
		}
		self.content = render_to_string('emailing_peerloan/general/OTP_for_lender_agreement.txt', info)
		self.send_email()
	"""
	
	# general sub function
	def send_email(self, attachments=None, to_usr_id=None):
		if SEND_EMAIL == False:
			return None
			
		msg = EmailMessage(self.subject, self.content, to=[self.email_addr])
		
		if attachments != None:
			for item in attachments:
				msg.attach(item['fname'], item['fcontent'], item['ftype'])
		try:
			msg.send()
		except smtplib.SMTPRecipientsRefused:
			''