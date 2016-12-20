#!/usr/bin/env python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_peerloan.settings")
django.setup()

from peerloan.models import Product
from peerloan.models import Investment
from peerloan.models import BorrowRequest
from peerloan.models import Loan
#from peerloan.models import LoanWorkflowHistory

import peerloan.emailing as emailing
import peerloan.smsing as smsing
import peerloan.peerloan_src.supporting_function as sup_fn

from django.db.models import Q
from django.db import transaction
from datetime import datetime
import datetime as dt
from django.utils import timezone

if __name__ == "__main__":
	# Step 1: get all active products
	prod_list = Product.objects.filter(status = 'ACTIVE')
	
	# Step 2: get all investments and borrow requests for each product
	invs_dict = {}
	bors_dict = {}
	for prod in prod_list:
		inv_list = Investment.objects.filter(Q(prod_id = prod.id), Q(status = 'ACTIVE'))
		
		if prod.repayment_plan == 'Promotion Balloon Payment':
			inv_list = Investment.objects.filter(Q(prod_id = 2), Q(status = 'ACTIVE'))
		
		invs_dict[prod.id] = inv_list
		bor_list = BorrowRequest.objects.filter(Q(prod_id = prod.id), (Q(status = 'FUND MATCHING') | Q(status = 'VALIDATED')))
		bors_dict[prod.id] = bor_list
	#print invs_dict, bors_dict
	
	# Step 3: in each product, do: for each borrow request, assign appropriate loans to it.
	for prod in prod_list:
		for bor in bors_dict[prod.id]:
			total_amount = bor.amount
			loan_list = Loan.objects.filter(bor_id = bor.id)
			cur_amount = sum([loan.initial_amount for loan in loan_list])
			amount2collect = total_amount - cur_amount
			print 'Now processing bor id %s, amount to collect is %s' % (bor.id, amount2collect)
			with transaction.atomic():
				for inv in invs_dict[prod.id]:
					loan_list = Loan.objects.filter(Q(inv_id = inv.id), Q(bor_id = bor.id))
					if len(loan_list) != 0: # this investment already has allocated fund to the borrow request
						print 'inv id %s has already invested in bor id %s' % (inv.id, bor.id)
						continue
					else:
						min_per_loan = prod.min_amount_per_loan
						max_per_loan = inv.max_amount_per_loan
						if max_per_loan == 0:
							# put investment but assign $0 for each loan?
							continue
							
						if amount2collect <= max_per_loan and max_per_loan <= inv.usable_amount:
						    allocated_amount  = amount2collect
						elif amount2collect > max_per_loan and max_per_loan <= inv.usable_amount:
						    allocated_amount = max_per_loan
						else:
						    if inv.usable_amount < min_per_loan:
						        continue
						    else:
						        allocated_amount = min(amount2collect, int(inv.usable_amount/min_per_loan) * min_per_loan)
						if allocated_amount == 0:
							continue
						
						amount2collect -= allocated_amount
						inv.usable_amount -= allocated_amount
						#inv.used_amount += allocated_amount
						inv.on_hold_amount += allocated_amount
						inv.save()
						
						# calculate instalment
						amount = allocated_amount
						if prod.repayment_plan == 'Instalment':
							rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
							instalment_borrower = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
							rate_per_month = prod.APR_lender * 0.01 / 12
							instalment_lender = amount * (rate_per_month / (1- (1 + rate_per_month)**(-12*(prod.repayment_period/12))))
							total_repay_amount_borrower = prod.repayment_period * instalment_borrower
							
							total_repay_interest_borrower = total_repay_amount_borrower - amount
							total_repay_interest_lender = total_repay_interest_borrower * (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
							total_repay_amount_lender = amount + total_repay_interest_lender
							#total_repay_amount_lender = prod.repayment_period * instalment_lender
						elif prod.repayment_plan == 'Balloon Payment':
							rate_per_month = bor.getBorAPR(prod.APR_borrower) * 0.01 / 12
							instalment_borrower = amount * rate_per_month
							rate_per_month = prod.APR_lender * 0.01 / 12
							instalment_lender = amount * rate_per_month
							total_repay_amount_borrower = amount + prod.repayment_period * instalment_borrower
							total_repay_amount_lender = amount + prod.repayment_period * instalment_lender
							
							total_repay_interest_borrower = prod.repayment_period * instalment_borrower
							total_repay_interest_lender = total_repay_interest_borrower * (prod.APR_lender / bor.getBorAPR(prod.APR_borrower))
						elif prod.repayment_plan == 'Promotion Balloon Payment':
							# pass to balloon payment to generate instalment
							bp_prod = Product.objects.get(repayment_plan='Balloon Payment')
							
							rate_per_month = bor.getBorAPR(bp_prod.APR_borrower) * 0.01 / 12
							instalment_borrower = amount * rate_per_month
							rate_per_month = bp_prod.APR_lender * 0.01 / 12
							instalment_lender = amount * rate_per_month
							
							total_repay_amount_borrower = amount + prod.repayment_period * instalment_borrower
							total_repay_amount_lender = amount + bp_prod.repayment_period * instalment_lender
							
							total_repay_interest_borrower = prod.repayment_period * instalment_borrower
							total_repay_interest_lender = bp_prod.repayment_period * instalment_lender
						
						new_loan = Loan(
						inv_id = inv.id,
						bor_id = bor.id,
						initial_amount = allocated_amount,
						total_repay_amount_borrower = total_repay_amount_borrower,
						total_repay_amount_lender = total_repay_amount_lender,
						instalment_borrower = instalment_borrower,
						instalment_lender = instalment_lender,
						remain_principal = allocated_amount,
						remain_principal_lender = allocated_amount,
						remain_interest_lender = total_repay_interest_lender,
						remain_interest_borrower = total_repay_interest_borrower,
						overdue_principal = 0,
						overdue_interest = 0,
						paid_overdue_interest = 0,
						status = 'MATCHED',
						create_timestamp = timezone.localtime(timezone.now()),
						update_timestamp = timezone.localtime(timezone.now())
						)
						new_loan.save()
						new_loan.ref_num = 'L' + str(new_loan.id)
						new_loan.save()
						
						# generate lwh
						"""
						new_lwh = LoanWorkflowHistory(
						loan_id = new_loan.id,
						event = 'Matched by Peerloan',
						remark = '--',
						create_timestamp = timezone.localtime(timezone.now()),
						update_timestamp = timezone.localtime(timezone.now())
						)
						new_lwh.save()
						"""
						
						print 'Generated loan reference number: %s' % new_loan.ref_num
						print 'Amount remaining: %s' % amount2collect
						# if matching is finished, move to the next borrow request
						if amount2collect == 0:
							bor.status = 'FUND MATCHING COMPLETED'
							bor.update_timestamp = timezone.localtime(timezone.now())
							bor.save()
							
							# update aut
							inputs = {
								'usr_id': bor.usr_id,
								'description': 'State "%s" changed to "%s"'%("FUND MATCHING", bor.status),
								'ref_id': bor.id,
								'model': 'BorrowRequest',
								'by': 'Program Machine',
								'datetime': timezone.localtime(timezone.now()),
								
								'action': 'modify',
								'type': 'Disburse',
								'status': 'UNREAD',
							}
							sup_fn.update_aut(inputs)
							sup_fn.update_ptn(inputs)
							
							# send email notification
							bor_emailing = emailing.BorrowerEmail(bor=bor)
							bor_emailing.loan_memorandum()
							
							# send SMS notification
							bor_smsing = smsing.BorrowerSMS()
							bor_smsing.fund_matching_SMS(bor=bor)
							break
						else:
							# update aut
							if bor.status != 'FUND MATCHING':
								inputs = {
									'usr_id': bor.usr_id,
									'description': 'State "%s" changed to "%s"'%(bor.status, 'FUND MATCHING'),
									'ref_id': bor.id,
									'model': 'BorrowRequest',
									'by': 'Program Machine',
									'datetime': timezone.localtime(timezone.now()),
								}
								sup_fn.update_aut(inputs)
								
							bor.status = 'FUND MATCHING'
				bor.save()