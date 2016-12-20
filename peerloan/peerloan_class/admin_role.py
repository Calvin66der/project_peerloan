class AdminRole:
	def __init__(self):
		self.perm_list = []
		self.allowed_loan_state_list = []
		self.allowed_lender_app_state_list = []
	
	def has_perm(self, action):
		if action in self.perm_list:
			return True
		else:
			return False
	
	def get_allowed_loan_state_list(self):
		return self.allowed_loan_state_list
	
	def get_allowed_lender_app_state_list(self):
		return self.allowed_lender_app_state_list

class SuperAdmin(AdminRole):
	def __init__(self):
		self.allowed_loan_state_list = ['PENDING DOC/IV', 'DOC UPLOADED', 'VALIDATED', 'REJECTED', 'CANCELLED']
		self.allowed_lender_app_state_list = ['APPROVED', 'PENDING DOC/IV', 'REJECTED', 'CANCELLED']
		
	def has_perm(self, action):
		return True

class Approver(AdminRole):
	def __init__(self):
		self.perm_list = ['change loan state', 'change lender app state', 'un-tick checklist', 'request resign loan agreement']
		self.allowed_loan_state_list = ['PENDING DOC/IV', 'DOC UPLOADED', 'VALIDATED', 'REJECTED', 'CANCELLED']
		self.allowed_lender_app_state_list = ['APPROVED', 'PENDING DOC/IV', 'REJECTED', 'CANCELLED']

class Officer(AdminRole):
	def __init__(self):
		self.perm_list = ['change loan state', 'change lender app state', 'tick checklist', 'un-tick checklist', 'request resign loan agreement']
		self.allowed_loan_state_list = ['PENDING DOC/IV', 'DOC UPLOADED', 'VALIDATED', 'REJECTED', 'CANCELLED']
		self.allowed_lender_app_state_list = ['APPROVED', 'PENDING DOC/IV', 'REJECTED', 'CANCELLED']

class Accountant(AdminRole):
	def __init__(self):
		AdminRole.__init__(self)
		self.perm_list = ['confirm deposit', 'confirm withdrawal', 'confirm repayment', 'confirm disbursement']

class Viewer(AdminRole):
	def __init__(self):
		self.perm_list = []
		self.allowed_loan_state_list = []
		self.allowed_lender_app_state_list = []
	def has_perm(self, action):
		return False