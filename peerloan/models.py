from django.db import models

# Create your models here.

class User(models.Model):
	email = models.CharField(max_length=45)
	password = models.CharField(max_length=45)
	receive_promotion = models.CharField(max_length=45)
	detail_info = models.CharField(max_length=3000)
	notification = models.CharField(max_length=3000, null=True)
	type = models.CharField(max_length=45)
	status = models.CharField(max_length=45)
	last_login = models.DateTimeField(null=True)
	this_login = models.DateTimeField(null=True)
	account_attempt = models.IntegerField(default=0)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class AdminUser(models.Model):
	email = models.CharField(max_length=45)
	password = models.CharField(max_length=45)
	type = models.CharField(max_length=45)
	status = models.CharField(max_length=45)
	last_login = models.DateTimeField(null=True)
	this_login = models.DateTimeField(null=True)
	account_attempt = models.IntegerField(default=0)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class Account(models.Model):
	usr_id = models.IntegerField()
	balance = models.FloatField()
	on_hold_amt = models.FloatField()

class UserInformation(models.Model):
	info_type = models.CharField(max_length=45)
	section = models.CharField(max_length=45)
	details = models.CharField(max_length=3000)

class UserTransaction(models.Model):
	usr_id = models.IntegerField()
	type = models.CharField(max_length=45)
	amount_in = models.FloatField()
	amount_out = models.FloatField()
	source_usr_id = models.IntegerField(null=True)
	destination_usr_id = models.IntegerField(null=True)
	internal_ref = models.CharField(max_length=45)
	cust_ref = models.CharField(max_length=45)
	href = models.CharField(max_length=100,null=True)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class UserOperationRequest(models.Model):
	usr_id = models.IntegerField()
	type = models.CharField(max_length=45)
	details = models.CharField(max_length=3000)
	simplified_hkid = models.CharField(max_length=45, null=True)
	status = models.CharField(max_length=45)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class UserOperationHistory(models.Model):
	usr_id = models.IntegerField()
	type = models.CharField(max_length=45)
	details = models.CharField(max_length=3000)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class MonthlyPortfolioSummary(models.Model):
	usr_id = models.IntegerField()
	month = models.IntegerField()
	year = models.IntegerField()
	details = models.CharField(max_length=5000)

class Product(models.Model):
	name_en = models.CharField(max_length=64)
	name_zh = models.CharField(max_length=64)
	repayment_period = models.IntegerField()
	min_amount_per_loan = models.FloatField()
	total_amount = models.FloatField()
	min_amount = models.FloatField()
	flat_rate_lender = models.FloatField()
	flat_rate_borrower = models.FloatField()
	APR_lender = models.FloatField()
	APR_borrower = models.FloatField()
	fake_APR_lender = models.FloatField(null=True)
	fake_APR_borrower = models.FloatField(null=True)
	fake_repayment_period = models.IntegerField(null=True)
	repayment_plan = models.CharField(max_length=45)
	detail_info = models.CharField(max_length=3000)
	required_docs = models.CharField(max_length=1000)
	status = models.CharField(max_length=45)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class BorrowRequest(models.Model):
	amount = models.FloatField()
	overpay_amount = models.FloatField(default=0)
	prod_id = models.IntegerField()
	usr_id = models.IntegerField()
	ref_num = models.CharField(max_length=45)
	repaid_month = models.IntegerField()
	instalment_lender = models.FloatField()
	instalment_borrower = models.FloatField()
	simplified_hkid = models.CharField(max_length=45, null=True)
	verify_identity = models.CharField(max_length=45, null=True)
	detail_info = models.CharField(max_length=3000)
	discount_rate = models.FloatField(default=0)
	status = models.CharField(max_length=45)
	draw_down_date = models.DateTimeField(null=True)
	expected_end_date = models.DateTimeField(null=True)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()
	
	def getBorAPR(self, prod_APR):
		return prod_APR * (1- self.discount_rate)
	
	def getMonthlyFlatRate(self, prod_tenor, prod_repayment_type):
		if prod_repayment_type == 'Balloon Payment':
			total_interest = float(prod_tenor) * self.instalment_borrower
		elif prod_repayment_type == 'Promotion Balloon Payment':
			total_interest = float(9) * self.instalment_borrower
		elif prod_repayment_type == 'Instalment':
			total_interest = float(prod_tenor) * self.instalment_borrower - self.amount
		
		monthly_flat_rate = (total_interest / self.amount) / int(prod_tenor)
		monthly_flat_rate = round(monthly_flat_rate * 100, 2)
		return monthly_flat_rate

class BorrowRequestDocument(models.Model):
	bor_id = models.IntegerField()
	name = models.CharField(max_length=45)
	type = models.CharField(max_length=45)
	detail = models.CharField(max_length=45)
	confirm = models.CharField(max_length=45, default="F")
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class Investment(models.Model):
	usr_id = models.IntegerField()
	prod_id = models.IntegerField()
	total_amount = models.FloatField()
	usable_amount = models.FloatField()
	used_amount = models.FloatField()
	on_hold_amount = models.FloatField()
	max_amount_per_loan = models.FloatField()
	option = models.CharField(max_length=45)
	ack = models.CharField(max_length=45)
	status = models.CharField(max_length=45)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class Loan(models.Model):
	inv_id = models.IntegerField()
	bor_id = models.IntegerField()
	ref_num = models.CharField(max_length=45)
	initial_amount = models.FloatField()
	total_repay_amount_lender = models.FloatField()
	total_repay_amount_borrower = models.FloatField()
	instalment_lender = models.FloatField()
	instalment_borrower = models.FloatField()
	remain_principal = models.FloatField()
	remain_principal_lender = models.FloatField()
	remain_interest_lender = models.FloatField()
	remain_interest_borrower = models.FloatField()
	overdue_principal = models.FloatField()
	overdue_interest = models.FloatField()
	paid_overdue_interest = models.FloatField()
	status = models.CharField(max_length=45)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class LoanSchedule(models.Model):
	bor_id = models.IntegerField()
	tenor = models.IntegerField()
	instalment = models.FloatField()
	principal = models.FloatField()
	interest = models.FloatField()
	instalment_l = models.FloatField()
	principal_l = models.FloatField()
	interest_l = models.FloatField()
	# underpay
	paid_principal = models.FloatField(default=0)
	paid_interest = models.FloatField(default=0)
	paid_overdue_interest = models.FloatField(default=0)
	paid_principal_l = models.FloatField(default=0)
	paid_interest_l = models.FloatField(default=0)
	# underpay end
	due_date = models.CharField(max_length=50)
	overdue_days = models.IntegerField(default=0)
	overdue_interest_remained = models.FloatField(default=0)
	overdue_interest_paid_days = models.IntegerField(default=0)
	overdue_interest_unpay_paid = models.FloatField(default=0)
	overdue_interest_accumulated = models.FloatField(default=0)
	late_charge = models.FloatField(default=0)
	paid_late_charge = models.FloatField(default=0)
	received_amount = models.FloatField(default=0)
	repayment_method = models.CharField(max_length=50)
	repayment_type = models.CharField(max_length=50,null=True)
	repayment_date = models.DateTimeField(null=True)
	status = models.CharField(max_length=50)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class AdminMemo(models.Model):
	model = models.CharField(max_length=50)
	identifier = models.CharField(max_length=50)
	no = models.IntegerField()
	content = models.CharField(max_length=200)
	updated_by = models.CharField(max_length=100)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class Ledger(models.Model):
	usr_id = models.IntegerField(null=True)
	bor_id = models.IntegerField(null=True)
	description = models.CharField(max_length=200)
	reference = models.CharField(max_length=50)
	debit = models.FloatField(null=True)
	credit = models.FloatField(null=True)
	balance = models.FloatField()
	status = models.CharField(max_length=50, null=True)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class AuditTrail(models.Model):
	usr_id = models.IntegerField()
	description = models.CharField(max_length=1000)
	ref_id = models.IntegerField()
	model = models.CharField(max_length=50)
	details = models.CharField(max_length=3000,null=True)
	by = models.CharField(max_length=50)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()

class PendingTaskNotification(models.Model):
	ref_id = models.IntegerField()
	model = models.CharField(max_length=50)
	type = models.CharField(max_length=50)
	description = models.CharField(max_length=100)
	status = models.CharField(max_length=50)
	create_timestamp = models.DateTimeField()
	update_timestamp = models.DateTimeField()
	
class OTPMessage(models.Model):
	usr_id = models.IntegerField()
	sequence = models.CharField(max_length=10)
	mobile_no = models.CharField(max_length=20)
	action = models.CharField(max_length=100)
	status = models.CharField(max_length=50)
	generated_timestamp = models.DateTimeField()
	expiring_timestamp = models.DateTimeField()