from django.conf.urls import url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import TemplateView

from .peerloan_src import login
from .peerloan_src import header
from .peerloan_src import portfolio
from .peerloan_src import investment
from .peerloan_src import my_account
from .peerloan_src import trans_records
from .peerloan_src import settings
from .peerloan_src import product
from .peerloan_src import ack
from .peerloan_src import ack_admin
from .peerloan_src import admin
from .peerloan_src import list_json
from .peerloan_src import admin_list_json
from . import views

urlpatterns = [
    # login
    url(r'^login/$', login.login, name='login'),
    url(r'^login/pl_admin/$', login.login, name='login'),
    url(r'^auth/$', login.auth, name='auth'),
    url(r'^sign_up/$', login.sign_up, name='sign_up'),
    url(r'^email_request/$', login.email_request, name='email_request'),
    url(r'^email_request/activate_account/$', login.email_request, name='email_request'),

    url(r'^logout/$', login.logout, name='logout'),
    url(r'^forget_password/$', login.forget_password, name='forget_password'),
    url(r'^password_reset/$', login.password_reset, name='password_reset'),

    # header, footer
    url(r'^header/', header.header, name='header'),
    url(r'^footer/$', header.footer, name='footer'),
    url(r'^invest_now/', header.invest_now, name='invest_now'),
    url(r'^borrow_now/$', header.borrow_now, name='borrow_now'),
    url(r'^switch_role/$', header.switch_role, name='switch_role'),
    url(r'^change_lang/$', header.change_lang, name='change_lang'),
    url(r'^apply_to_be_investor/$', header.apply_to_be_investor, name='apply_to_be_investor'),
    url(r'^lender_agreement/$', header.lender_agreement),
    url(r'^loan_agreement/$', header.loan_agreement),

    # portfolio
    url(r'^portfolio/$', portfolio.portfolio),
    url(r'^portfolio/portfolio_summary/$', portfolio.portfolio),
    url(r'^portfolio/portfolio_summary/estimated_returning_schedule/$', portfolio.portfolio),
    url(r'^portfolio/active_investment/$', portfolio.portfolio),

    # investment
    url(r'^investment/$', investment.investment),
    url(r'^investment/invest_now/$', investment.investment),
    url(r'^investment/invest_now/product_details/$', investment.investment),
    url(r'^investment/reallocate_fund/$', investment.investment),
    url(r'^investment/transfer_fund/$', investment.investment),

    # my account
    url(r'^my_account/$', my_account.my_account, name='my_account'),
    url(r'^my_account/all_application_listing/$', my_account.my_account, name='my_account'),
    url(r'^my_account/all_application_listing/detail/$', my_account.my_account, name='my_account'),
    url(r'^my_account/repayment_and_settlement/$', my_account.my_account, name='my_account'),
    url(r'^my_account/change_acc_info/$', my_account.my_account, name='my_account'),

    url(r'^my_account/deposit_money/$', my_account.my_account, name='my_account'),
    url(r'^my_account/withdraw_money/$', my_account.my_account, name='my_account'),
    url(r'^my_account/transaction_records/$', my_account.my_account, name='my_account'),

    # trans record
    url(r'^trans_records/$', trans_records.trans_records),

    # product
    url(r'^product/$', product.product, name='product'),
    url(r'^product/apply/$', product.product, name='product'),
    url(r'^product/upload_docs/$', product.product, name='product'),
    url(r'^product/confirm_agreement/$', product.product, name='product'),
    url(r'^product/confirm_memorandum/$', product.product, name='product'),
    url(r'^product/invest/$', product.product, name='product'),
    url(r'^product/transfer/$', product.product, name='product'),

    # settings
    url(r'^settings/$', settings.settings),
    url(r'^settings/sms_email_notification/$', settings.settings),

    # ack
    url(r'^ack/$', ack.ack_handler, name='ack'),
    url(r'^ack_admin/$', ack_admin.ack_handler),
    url(r'^ack_page/$', ack.ack_page, name='ack'),

    # admin side
    url(r'^pl_admin/application/$', admin.application),
    url(r'^pl_admin/application/detail/$', admin.application),
    url(r'^pl_admin/application/all_application/$', admin.application),
    url(r'^pl_admin/disbursement/$', admin.disbursement),
    url(r'^pl_admin/repayment/$', admin.repayment),
    url(r'^pl_admin/repayment/detail/$', admin.repayment),
    url(r'^pl_admin/repayment/detail/repayment_history/$', admin.repayment),
    url(r'^pl_admin/collection/$', admin.collection),
    url(r'^pl_admin/account/$', admin.account),
    url(r'^pl_admin/account/ledger/$', admin.account),
    url(r'^pl_admin/fund_matching/$', admin.fund_matching),
    url(r'^pl_admin/fund_matching/list_detail/$', admin.fund_matching),
    url(r'^pl_admin/deposit/$', admin.deposit),
    url(r'^pl_admin/cash_out/$', admin.cash_out),
    url(r'^pl_admin/KYC_and_AML/$', admin.KYC_and_AML),
    url(r'^pl_admin/report/$', admin.report),
    url(r'^pl_admin/audit_trail/$', admin.audit_trail),
    url(r'^pl_admin/pl_account/$', admin.pl_account),
    url(r'^pl_admin/promotion_handling/$', admin.promotion_handling),

    # admin side json data
    url(r'^uor_list_json/$', admin_list_json.uor_list_json.as_view(), name='uor_list_json'),
    url(r'^admin_bor_list_json/$', admin_list_json.bor_list_json.as_view()),
    url(r'^admin_inv_list_json/$', admin_list_json.inv_list_json.as_view()),
    url(r'^admin_repay_list_json/$', admin_list_json.repay_list_json.as_view()),
    url(r'^admin_account_list_json/$', admin_list_json.account_list_json.as_view()),
    url(r'^admin_ledger_list_json/$', admin_list_json.ledger_list_json.as_view()),
    url(r'^admin_aut_list_json/$', admin_list_json.aut_list_json.as_view()),
    url(r'^admin_ph_list_json/$', admin_list_json.ph_list_json.as_view()),

    # json data url
    url(r'^loan_list_json/$', list_json.loan_list_json.as_view(), name='loan_list_json'),
    url(r'^repayboard_list_json/$', list_json.repayboard_list_json.as_view(), name='repayboard_list_json'),
    url(r'^returnboard_list_json/$', list_json.returnboard_list_json.as_view(), name='returnboard_list_json'),
    url(r'^repaytable_list_json/$', list_json.repaytable_list_json.as_view(), name='repaytable_list_json'),
    url(r'^returntable_list_json/$', list_json.returntable_list_json.as_view(), name='returntable_list_json'),
    url(r'^repaypie_list_json/$', list_json.repaypie_list_json.as_view(), name='repaypie_list_json'),
    url(r'^returnpie_list_json/$', list_json.returnpie_list_json.as_view(), name='returnpie_list_json'),
    url(r'^trans_list_json/$', list_json.trans_list_json.as_view(), name='trans_list_json'),
    url(r'^activeinv_list_json/$', list_json.activeinv_list_json.as_view(), name='activeinv_list_json'),
    url(r'^allocatedinv_list_json/$', list_json.allocatedinv_list_json.as_view(), name='allocatedinv_list_json'),
    url(r'^investedinv_list_json/$', list_json.investedinv_list_json.as_view(), name='investedinv_list_json'),

    url(r'^portfolio_pie_list_json/$', list_json.portfolio_pie_list_json.as_view()),
    url(r'^portfolio_line_list_json/$', list_json.portfolio_line_list_json.as_view()),

    # pop window schedule
    url(r'^loan_repay_schedule/$', views.loan_repay_schedule, name='loan_repay_schedule'),
    url(r'^generate_pdf_file/$', views.generate_pdf_file),

    url(r'^tmp/$', views.tmp, name='tmp'),

    # view
    url(r'^upload_file/$', views.upload_file),
    url(r'^tnc/$', TemplateView.as_view(template_name="peerloan/tnc.html")),
    url(r'^MLO/$', TemplateView.as_view(template_name="peerloan/MLO.html")),
    url(r'^important_notice/$', TemplateView.as_view(template_name="peerloan/important_notice.html")),
    url(r'^personal_data_privacy_policy/$',
        TemplateView.as_view(template_name="peerloan/personal_data_privacy_policy.html")),
    url(r'^refresh-captcha/$', views.refresh_captcha, name='refresh-captcha'),
    url(r'^file/', views.file, name='file'),
    url(r'^document/$', views.document),
    url(r'^uor_handler/$', views.uor_handler),
    url(r'^bor_handler/$', views.bor_handler),
    url(r'^ptn_handler/$', views.ptn_handler),
    url(r'^late_charge_handler/$', views.late_charge_handler),
    url(r'^ledger_table_handler/$', views.ledger_table_handler),
    url(r'^generate_OTP/$', views.generate_OTP),
    url(r'^change_acc_info_handler/$', views.change_acc_info_handler),
    url(r'^calculate_repayment_amount/$', views.calculate_repayment_amount),

]
urlpatterns += staticfiles_urlpatterns()
