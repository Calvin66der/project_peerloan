#!/usr/bin/env python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_peerloan.settings")
django.setup()

from django.db.models import Q
from django.utils import timezone

import peerloan.models as model
import peerloan.emailing as emailing
import peerloan.smsing as smsing
import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
import datetime as dt
import pytz
import json

def send_bor_email_notification():
	now = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
	now = pytz.timezone('Asia/Hong_Kong').localize(now)
	
	# AIP - 1 day after auto approved
	bor_list = model.BorrowRequest.objects.filter(status='AUTO APPROVED')
	for bor in bor_list:
		if (now - bor.create_timestamp).days == 1:
			bor_emailing = emailing.BorrowEmail(bor=bor)
			bor_emailing.one_day_after_auto_approved()
	
	# repayment reminder
	bor_list = model.BorrowRequest.objects.filter(~Q(draw_down_date = None))
	for bor in bor_list:
		los = model.LoanSchedule.objects.get(bor_id=bor.id, tenor=bor.repaid_month+1)
		due_date = datetime.strptime(los.due_date, '%Y/%m/%d')
		due_date = pytz.timezone('Asia/Hong_Kong').localize(due_date)
		if (due_date - now).days == 3:
			prod = model.Product.objects.get(id=bor.prod_id)
			bor_emailing = emailing.BorrowEmail(bor=bor)
			# check last instalment or not
			if bor.repaid_month + 1 == prod.repayment_period:
				bor_emailing.last_instalment()
			else:
				bor_emailing.repayment_reminder()
	
	# overdue repayment reminder
	los_list = model.LoanSchedule.objects.filter(status='OVERDUE')
	for los in los_list:
		bor = model.BorrowRequest.objects.get(id=los.bor_id)
		bor_emailing = emailing.BorrowerEmail(bor=bor)
		
		if los.overdue_days == 7 or los.overdue_days == 14:
			bor_emailing.overdue_repayment_reminder()
		elif los.overdue_days == 21:
			bor_emailing.final_overdue_repayment_reminder()
			

def send_ldr_email_notification():
	usr_list = model.User.objects.filter(type='L')
	for usr in usr_list:
		if usr.notification == None:
			continue
		notification = json.loads(usr.notification)
		ldr_emailing = emailing.LenderEmail(inv_usr=usr)
		if notification['Fund Matching Completed (Email)'] == 'Every Day':
			ldr_emailing.fund_matching_notification_daily_result()
		elif notification['Fund Matching Completed (Email)'] == 'Every Week' and timezone.localtime(timezone.now()).strftime('%A') == 'Monday':
			ldr_emailing.fund_matching_notification_weekly_result()
		elif notification['Fund Matching Completed (Email)'] == 'Every Month' and timezone.localtime(timezone.now()).day == 1:
			ldr_emailing.fund_matching_notification_monthly_result()
			

def send_bor_SMS_notification():
	now = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
	now = pytz.timezone('Asia/Hong_Kong').localize(now)
	
	# AIP - 1 day after auto approved
	bor_list = model.BorrowRequest.objects.filter(status='AUTO APPROVED')
	for bor in bor_list:
		if (now - bor.create_timestamp).days == 1:
			bor_smsing = smsing.BorrowerSMS()
			bor_smsing.no_response_after_AIP_one_day(bor=bor)

def send_ldr_SMS_notification():
	usr_list = model.User.objects.filter(type='L')
	for usr in usr_list:
		if usr.notification == None:
			continue
		notification = json.loads(usr.notification)
		ldr_smsing = smsing.LenderSMS()
		
		if notification['Fund Matching Completed (SMS)'] == 'Every Day':
			ldr_smsing.fund_matching_completed_every_day(usr=usr)
		elif notification['Fund Matching Completed (SMS)'] == 'Every Week' and timezone.localtime(timezone.now()).strftime('%A') == 'Monday':
			ldr_smsing.fund_matching_completed_every_week(usr=usr)
		elif notification['Fund Matching Completed (SMS)'] == 'Every Month' and timezone.localtime(timezone.now()).day == 1:
			ldr_smsing.fund_matching_completed_every_month(usr=usr)
	

if __name__ == "__main__":
	# send email notification
	send_bor_email_notification()
	send_ldr_email_notification()
	
	# send SMS notification
	send_bor_SMS_notification()
	send_ldr_SMS_notification()