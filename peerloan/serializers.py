from rest_framework import serializers

class LaasSerializer(serializers.Serializer):
	updated_date = serializers.CharField(max_length=10)
	prod_name = serializers.CharField(max_length=30)
	ref_num = serializers.CharField(max_length=30)
	amount = serializers.FloatField()
	APR = serializers.FloatField()
	apply_date = serializers.CharField(max_length=10)
	status = serializers.CharField(max_length=30)
	bor_id = serializers.CharField(max_length=10)
	
class LoanLenderSerializer(serializers.Serializer):
	updated_date = serializers.CharField(max_length=10)
	prod_name = serializers.CharField(max_length=30)
	ref_num = serializers.CharField(max_length=30)
	amount = serializers.FloatField()
	APR = serializers.FloatField()
	draw_down_date = serializers.CharField(max_length=10)
	status = serializers.CharField(max_length=30)
	
class KeyValueSerializer(serializers.Serializer):
	key = serializers.CharField(max_length=50)
	value = serializers.CharField(max_length=50)

class XYSerializer(serializers.Serializer):
	x = serializers.FloatField()
	y = serializers.FloatField()
	
class RepayTableSerializer(serializers.Serializer):
	date = serializers.CharField(max_length=10)
	os_principal = serializers.FloatField()
	os_interest = serializers.FloatField()
	os_balance = serializers.FloatField()
	paid_principal = serializers.FloatField()
	paid_interest = serializers.FloatField()
	ref_num = serializers.CharField(max_length=20)
	prod_name = serializers.CharField(max_length=20)
	installment = serializers.FloatField()
	status = serializers.CharField(max_length=10)
	
class RepayPieSerializer(serializers.Serializer):
	name = serializers.CharField(max_length=30)
	amount = serializers.FloatField()
	color = serializers.CharField(max_length=10)

class ActiveInvSerializer(serializers.Serializer):
	date = serializers.CharField(max_length=10)
	ref_num = serializers.CharField(max_length=10)
	amount = serializers.FloatField()
	installment = serializers.FloatField()
	interest = serializers.FloatField()
	draw_down_date = serializers.CharField(max_length=10)
	expected_end_date = serializers.CharField(max_length=10)
	overdue_loan_receivable = serializers.FloatField()
	loan_id = serializers.IntegerField()

class DepositSerializer(serializers.Serializer):
	acc_no = serializers.CharField(max_length=30)
	date = serializers.CharField(max_length=10)
	amount = serializers.FloatField()
	bank_in_slip = serializers.CharField(max_length=30)
	bank_in_date = serializers.CharField(max_length=10)
	bank_in_time = serializers.CharField(max_length=10)
	bank_in_slip = serializers.CharField(max_length=10)
	ref_num = serializers.CharField(max_length=30)
	uor_id = serializers.IntegerField()

class WithdrawSerializer(serializers.Serializer):
	acc_no = serializers.CharField(max_length=30)
	date = serializers.CharField(max_length=10)
	acc_balance = serializers.FloatField()
	amount = serializers.FloatField()
	bank = serializers.CharField(max_length=30)
	bank_acc_no = serializers.CharField(max_length=30)
	payment_chq_no = serializers.CharField(max_length=30)
	bank_in_date = serializers.CharField(max_length=10)
	bank_in_time = serializers.CharField(max_length=10)
	bank_in_slip = serializers.CharField(max_length=10)
	ref_num = serializers.CharField(max_length=30)
	confirm_time = serializers.CharField(max_length=30)
	uor_id = serializers.IntegerField()

class AdminApplicationSerializer(serializers.Serializer):
	application_no = serializers.CharField(max_length=30)
	name = serializers.CharField(max_length=30)
	application_time = serializers.CharField(max_length=30)
	amount = serializers.CharField(max_length=30)
	prod_type = serializers.CharField(max_length=30)
	follow_by = serializers.CharField(max_length=30)
	last_updated_time = serializers.CharField(max_length=30)
	last_updated_by = serializers.CharField(max_length=30)
	state = serializers.CharField(max_length=30)

class AdminRepaymentSerializer(serializers.Serializer):
	loan_no = serializers.CharField(max_length=30)
	name = serializers.CharField(max_length=30)
	loan_amount = serializers.CharField(max_length=30)
	outstanding_principal = serializers.CharField(max_length=30)
	product = serializers.CharField(max_length=30)
	last_updated_time = serializers.CharField(max_length=30)
	last_updated_by = serializers.CharField(max_length=30)
	state = serializers.CharField(max_length=30)

class ApplyInvestorSerializer(serializers.Serializer):
	account_no = serializers.CharField(max_length=30)
	name = serializers.CharField(max_length=30)
	last_updated_time = serializers.CharField(max_length=30)
	last_updated_by = serializers.CharField(max_length=30)
	state = serializers.CharField(max_length=30)
	source = serializers.CharField(max_length=30)
	uor_id = serializers.CharField(max_length=30)

class FundMatchBorSerializer(serializers.Serializer):
	loan_no = serializers.CharField(max_length=30)
	amount_to_collect = serializers.CharField(max_length=30)
	matched_percentage = serializers.CharField(max_length=30)
	prod_name = serializers.CharField(max_length=30)
	application_date = serializers.CharField(max_length=30)
	agreement_date = serializers.CharField(max_length=30)
	no_of_investors = serializers.CharField(max_length=30)

class FundMatchInvSerializer(serializers.Serializer):
	account_no = serializers.CharField(max_length=30)
	investment_amount = serializers.CharField(max_length=30)
	matched_percentage = serializers.CharField(max_length=30)
	investment_start_date = serializers.CharField(max_length=30)
	max_investment_amount = serializers.CharField(max_length=30)
	no_of_borrowers = serializers.CharField(max_length=30)