#!/usr/bin/env python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_peerloan.settings")
django.setup()

from peerloan.models import Account
from peerloan.models import Product
from peerloan.models import Investment
from peerloan.models import BorrowRequest
from peerloan.models import Ledger
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import User
from peerloan.models import UserTransaction

from django.db.models import Q
from django.db import transaction

from datetime import datetime
import datetime as dt
import pytz
from django.utils import timezone

import peerloan.emailing as emailing
import peerloan.peerloan_src.supporting_function as sup_fn

import json

@transaction.atomic
def update_pay_los_loan(inputs):
	"""
	inputs:
	los
	repayment_method
	payment_status: '(Pending confirm)' or ''
	"""
	los = inputs['los']
	repayment_method = inputs['repayment_method']
	payment_status = inputs['payment_status']
	
	los.status = 'PAID'
	los.received_amount = los.instalment
	los.paid_interest = los.interest
	los.paid_principal = los.principal
	los.paid_interest_l = los.interest_l
	los.paid_principal_l = los.principal_l
	los.repayment_method = repayment_method
	los.repayment_type = 'Instalment'
	los.repayment_date = timezone.localtime(timezone.now())
	los.save()
	
	# update bor
	bor = BorrowRequest.objects.get(id=los.bor_id)
	prev_status = bor.status
	prod = Product.objects.get(id = bor.prod_id)
	bor.repaid_month += 1
	if bor.repaid_month == prod.repayment_period:
		bor.status = 'PAYBACK COMPLETED'
	else:
		bor.status = 'PAYBACK ' + str(bor.repaid_month)
	#print bor.status
	bor.save()
	
	# update aut
	inputs = {
		'usr_id': bor.usr_id,
		'description': 'State "%s changed to "%s"'%(prev_status, bor.status),
		'ref_id': bor.id,
		'model': 'BorrowRequest',
		'by': 'System',
		'datetime': timezone.localtime(timezone.now()),
		
	}
	sup_fn.update_aut(inputs)
	
	# update ledger
	inputs = {
		'bor_id': bor.id,
		'description': payment_status+' Pay auto-pay %s%s repayment by Borrower: Amount $%.2f' %(bor.repaid_month,sup_fn.date_postfix(bor.repaid_month),los.instalment),
		'reference': bor.ref_num,
		'status': 'Pending Confirm' if payment_status == '(Pending confirm)'  else None,
		'debit': round(los.instalment, 2),
		'credit': 0,
		'datetime': timezone.localtime(timezone.now())
	}
	sup_fn.update_ledger(inputs)
	
	# update loan list
	
	rate_per_month_b = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
	#rate_per_month_l = prod.APR_lender * 0.01 / 12
	
	loan_list = Loan.objects.filter(bor_id = bor.id)
	for loan in loan_list:
		return_interest_b = loan.remain_principal * rate_per_month_b
		#return_interest_l = loan.remain_principal_lender * rate_per_month_l
		
		ratio = (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
		return_interest_l = return_interest_b * ratio
		return_principal_b = loan.instalment_borrower - return_interest_b
		#return_principal_l = loan.instalment_lender - return_interest_l
		return_principal_l = return_principal_b
		
		if (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month != prod.repayment_period:
			return_principal_b = 0
			return_principal_l = 0
		elif (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month == prod.repayment_period:
			return_principal_b = loan.remain_principal
			return_principal_l = loan.remain_principal_lender
		
		if prod.repayment_plan == 'Promotion Ballon Payment' and bor.repaid_month < 4:
			return_interest_b = 0
			#return_interest_l = 0
		
		loan.remain_principal -= return_principal_b
		loan.remain_principal_lender -= return_principal_l
		loan.remain_interest_borrower -= return_interest_b
		loan.remain_interest_lender -= return_interest_l
		loan.status = 'PAYBACK ' + str(bor.repaid_month)
		loan.save()
		#print return_principal_b,loan.remain_principal
		
		# update ledger
		inv = Investment.objects.get(id=loan.inv_id)
		inv_usr = User.objects.get(id=inv.usr_id)
		lender_no = sup_fn.try_KeyError(json.loads(inv_usr.detail_info), 'Lender No')
		inputs = {
			'usr_id': inv.usr_id,
			'description': payment_status+' Receive auto-pay %s%s repayment by Lender <a href="/pl_admin/account/ledger/?usr_id=%s" target="_blank">%s</a>: Amount $%.2f'%(str(bor.repaid_month),sup_fn.date_postfix(bor.repaid_month),inv_usr.id,lender_no,return_principal_l + return_interest_l),
			'reference': bor.ref_num,
			'status': 'Pending Confirm' if payment_status == '(Pending confirm)'  else None,
			'debit': 0,
			#'credit': round(loan.instalment_lender,2),
			'credit': round(return_principal_l + return_interest_l,2),
			'datetime': timezone.localtime(timezone.now())
		}
		
		sup_fn.update_ledger(inputs)
		
	# update pl ledger
	pl_interest = los.interest - los.interest_l
	inputs = {
		'usr_id': 0,
		'description': payment_status+' Receive auto-pay %s%s repayment by P L Account: Amount $%.2f'%(str(bor.repaid_month),sup_fn.date_postfix(bor.repaid_month),pl_interest),
		'reference': bor.ref_num,
		'status': 'Pending Confirm' if payment_status == '(Pending confirm)'  else None,
		'debit': 0,
		#'credit': round(bor.instalment_borrower - bor.instalment_lender,2),
		'credit': round(pl_interest,2),
		'datetime': timezone.localtime(timezone.now())
	}
	sup_fn.update_ledger(inputs)

@transaction.atomic
def update_overdue_loanschedule():
	# update overdue_day and overdue_interest
	los_list = LoanSchedule.objects.filter(status='OVERDUE')
	
	for los in los_list:
		due_date = pytz.timezone('Asia/Hong_Kong').localize(datetime.strptime(los.due_date, '%Y/%m/%d'))
		overdue_days = (timezone.localtime(timezone.now()) - due_date).days
		bor = BorrowRequest.objects.get(id=los.bor_id)
		
		loan_list = Loan.objects.filter(bor_id=bor.id)
		prod = Product.objects.get(id=bor.prod_id)
		
		rate_per_day = bor.getBorAPR(prod.APR_borrower) * 0.01 / 360
		overdue_interest_remained = (los.instalment) * rate_per_day * (overdue_days - los.overdue_interest_paid_days)
		
		los.overdue_days = overdue_days
		los.overdue_interest_remained = overdue_interest_remained
		los.overdue_interest_accumulated = los.overdue_interest_remained + los.overdue_interest_unpay_paid + los.paid_overdue_interest
		
		if due_date.day == timezone.localtime(timezone.now()).day:
			# next month same date
			los.late_charge += 200
		los.save()

@transaction.atomic
def update_overpay2pay_loan():
	# update los
	los_list = LoanSchedule.objects.filter(status='OPEN')
	
	for los in los_list:
		try:
			due_date = datetime.strptime(los.due_date, '%Y/%m/%d')
		except ValueError:
			continue
		due_date = pytz.timezone('Asia/Hong_Kong').localize(due_date)
		
		if due_date <= timezone.localtime(timezone.now()):
			bor = BorrowRequest.objects.get(id=los.bor_id)
			if 'OVERDUE' in bor.status:
				continue
			if bor.overpay_amount >= los.instalment:
				inputs = {
					'los': los,
					'repayment_method': 'Deduct From Overpay',
					'payment_status': ''
				}
				update_pay_los_loan(inputs)
				bor = BorrowRequest.objects.get(id=los.bor_id)
				bor.overpay_amount -= los.instalment
				bor.save()
				
				# update borrower trx record
				new_trx = UserTransaction(
				usr_id = bor.usr_id,
				type = 'Repayment',
				amount_in = 0,
				amount_out = los.instalment,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				# return money to lender
				loan_list = Loan.objects.filter(bor_id=bor.id)
				
				# update P L interest
				new_trx = UserTransaction(
				usr_id = 0,
				type = 'P L interest',
				amount_in = los.instalment - los.instalment_l,
				amount_out = 0,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()
				
				prod = Product.objects.get(id=bor.prod_id)
				rate_per_month_b = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
				
				for loan in loan_list:
					#amount_l = loan.instalment_lender
					return_interest_b = loan.remain_principal * rate_per_month_b
					#return_interest_l = loan.remain_principal_lender * rate_per_month_l
					ratio = (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
					return_interest_l = return_interest_b * ratio
					
					return_interest_l = return_interest_b * ratio
					return_principal_b = loan.instalment_borrower - return_interest_b
					#return_principal_l = loan.instalment_lender - return_interest_l
					return_principal_l = return_principal_b
					
					if (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month != prod.repayment_period:
						return_principal_b = 0
						return_principal_l = 0
					elif (prod.repayment_plan == 'Balloon Payment' or prod.repayment_plan == 'Promotion Balloon Payment') and bor.repaid_month == prod.repayment_period:
						return_principal_b = loan.remain_principal
						return_principal_l = loan.remain_principal_lender
					
					if prod.repayment_plan == 'Promotion Ballon Payment' and bor.repaid_month < 4:
						return_interest_b = 0
					
					amount_l = return_interest_l + return_principal_l
					
					# reduce remain principal, interest
					loan.remain_principal -= return_principal_b
					loan.remain_principal_lender -= return_principal_l
					loan.remain_interest_borrower -= return_interest_b
					loan.remain_interest_lender -= return_interest_l
					loan.status = 'PAYBACK ' + str(bor.repaid_month)
					loan.save()
					
					inv = Investment.objects.get(id=loan.inv_id)
					if inv.option == 'Reinvest':
						inv.total_amount += amount_l
						inv.usable_amount += amount_l
						inv.save()
					elif inv.option == 'Not Reinvest':
						acc = Account.objects.get(usr_id=inv.usr_id)
						acc.balance += amount_l
						acc.save()
					
					# update lender trx record
					new_trx = UserTransaction(
					usr_id = inv.usr_id,
					type = 'Loan Return',
					amount_in = amount_l,
					amount_out = 0,
					internal_ref = bor.ref_num,
					cust_ref = '--',
					href = '/loan_repay_schedule/?loan_id=' + str(loan.id),
					create_timestamp = timezone.localtime(timezone.now()),
					update_timestamp = timezone.localtime(timezone.now())
					)
					new_trx.save()

@transaction.atomic
def update_autopay_loan():
	# update los
	los_list = LoanSchedule.objects.filter(status='OPEN')
	
	for los in los_list:
		try:
			bor = BorrowRequest.objects.get(id=los.bor_id)
		except:
			continue
			
		if 'OVERDUE' in bor.status or 'PAYBACK COMPLETED' in bor.status:
			continue
		
		try:
			due_date = datetime.strptime(los.due_date, '%Y/%m/%d')
		except ValueError:
			continue
		due_date = pytz.timezone('Asia/Hong_Kong').localize(due_date)

		if due_date <= timezone.localtime(timezone.now()):
			# autopay start
			# update aut
			bor = BorrowRequest.objects.get(id=los.bor_id)
			inputs = {
				'usr_id': bor.usr_id,
				'description': 'Autopay %s instalment $%s'%(str(bor.repaid_month)+sup_fn.date_postfix(bor.repaid_month), bor.instalment_borrower),
				'ref_id': bor.id,
				'model': 'BorrowRequest',
				'by': 'System',
				'datetime': timezone.localtime(timezone.now()),
				
			}
			sup_fn.update_aut(inputs)
			
			inputs = {
				'los': los,
				'repayment_method': 'Auto Pay',
				'payment_status': '(Pending confirm)'
			}
			update_pay_los_loan(inputs)
		
		
@transaction.atomic
def update_confirmed_autopay_loan():
	led_list = Ledger.objects.filter(status='Pending Confirm')
	public_holidays = sup_fn.import_public_holiday()
	
	for led in led_list:
		now = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
		create_date = datetime.strptime(led.create_timestamp.strftime('%Y/%m/%d'), '%Y/%m/%d')
		days = (now - create_date).days
		#days = (timezone.localtime(timezone.now()) - led.create_timestamp).days
		business_days = 0
		
		for i in range(days):
			date = led.create_timestamp + dt.timedelta(days=i)
			if date.strftime('%a') not in ['Sat', 'Sun'] and date.strftime('%d/%m/%Y') not in public_holidays:
				business_days += 1
			
		if business_days >= 3:
			led.description = led.description.replace('(Pending confirm)', '')
			led.status = None
			led.update_timestamp = timezone.localtime(timezone.now())
			led.save()
			
			# update borrower trx record
			bor = BorrowRequest.objects.get(ref_num=led.reference)
			new_trx = UserTransaction(
			usr_id = bor.usr_id,
			type = 'Repayment',
			amount_in = 0,
			amount_out = led.debit,
			internal_ref = bor.ref_num,
			cust_ref = '--',
			href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_trx.save()
			
			# return money to lender
			
			loan_list = Loan.objects.filter(bor_id=bor.id)
			
			# update P L interest
			new_trx = UserTransaction(
			usr_id = 0,
			type = 'P L interest',
			amount_in = led.debit - sum([loan.instalment_lender for loan in loan_list]),
			amount_out = 0,
			internal_ref = bor.ref_num,
			cust_ref = '--',
			href = '/loan_repay_schedule/?bor_id=' + str(bor.id),
			create_timestamp = timezone.localtime(timezone.now()),
			update_timestamp = timezone.localtime(timezone.now())
			)
			new_trx.save()
			
			for loan in loan_list:
				amount_l = loan.instalment_lender
				inv = Investment.objects.get(id=loan.inv_id)
				if inv.option == 'Reinvest':
					inv.total_amount += amount_l
					inv.usable_amount += amount_l
					inv.save()
				elif inv.option == 'Not Reinvest':
					acc = Account.objects.get(usr_id=inv.usr_id)
					acc.balance += amount_l
					acc.save()
				
				# update lender trx record
				inv = Investment.objects.get(id=loan.inv_id)
				new_trx = UserTransaction(
				usr_id = inv.usr_id,
				type = 'Loan Return',
				amount_in = amount_l,
				amount_out = 0,
				internal_ref = bor.ref_num,
				cust_ref = '--',
				href = '/loan_repay_schedule/?loan_id=' + str(loan.id),
				create_timestamp = timezone.localtime(timezone.now()),
				update_timestamp = timezone.localtime(timezone.now())
				)
				new_trx.save()

@transaction.atomic
def update_release_loan():
	def check_expire(bor, now, expire_days):
		update_date = datetime.strptime(bor.update_timestamp.strftime('%Y/%m/%d'), '%Y/%m/%d')
		if (now - update_date).days >= expire_days:
			# cancel bor
			bor.status = 'CANCELLED'
			bor.save()
			# release loan
			loan_list = Loan.objects.filter(bor_id=bor.id)
			for loan in loan_list:
				inv = Investment.objects.get(id = loan.inv_id)
				inv.total_amount += loan.initial_amount
				inv.on_hold_amount -= loan.initial_amount
				inv.save()
				
				loan.status = 'RELEASED'
				loan.save()
				
	now = datetime.strptime(timezone.localtime(timezone.now()).strftime('%Y/%m/%d'), '%Y/%m/%d')
	bor_list = BorrowRequest.objects.filter(status='FUND MATCHING')
	for bor in bor_list:
		check_expire(bor=bor, now=now, expire_days=7)
		
	bor_list = BorrowRequest.objects.filter(status='FUND MATCHING COMPLETED')
	for bor in bor_list:
		check_expire(bor=bor, now=now, expire_days=7)

if __name__ == "__main__":
	
	# check overdue
	update_overdue_loanschedule()
	
	# check overpay whether can pay instalment
	update_overpay2pay_loan()
	
	# check autopay
	update_autopay_loan()
	
	# update autopay that not returned
	update_confirmed_autopay_loan()
	
	update_release_loan()