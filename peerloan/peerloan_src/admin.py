# This Python file uses the following encoding: utf-8
from django.shortcuts import render, redirect, render_to_response
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from peerloan.models import Account
from peerloan.models import AdminMemo
from peerloan.models import BorrowRequest
from peerloan.models import BorrowRequestDocument
from peerloan.models import Investment
from peerloan.models import Loan
from peerloan.models import LoanSchedule
from peerloan.models import Product
from peerloan.models import User
from peerloan.models import UserInformation
from peerloan.models import UserOperationRequest

from peerloan.decorators import require_login

import peerloan.classes as classes
import peerloan.peerloan_src.supporting_function as sup_fn

from datetime import datetime
from django.utils import timezone
import pytz
from collections import OrderedDict
import csv
import json


@require_login
def application(request):
    if request.session['handling_side'] == 'B':

        # view details
        if 'detail' in request.META.get('PATH_INFO').split('/'):
            bor_ref_num = request.GET.get('bor_ref_num')
            try:
                bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
            except:
                HttpResponse('Loan application doesn\'t exist.')
            usr = User.objects.get(id=bor.usr_id)
            bor_detail = json.loads(bor.detail_info)

            borrower_name = bor_detail['Surname'] + ' ' + bor_detail['Given Name']
            date_of_birth = pytz.timezone('Asia/Hong_Kong').localize(
                datetime.strptime(bor_detail['Date of Birth'], '%Y-%m-%d'))
            borrower_age = int((timezone.localtime(timezone.now()) - date_of_birth).days / float(365))

            prod = Product.objects.get(id=bor.prod_id)

            # check re-sign agreement required or not
            re_sign_agreement_required = False
            if bor.status == 'AGREEMENT CONFIRMED' or bor.status == 'PENDING DOC/IV':
                details = json.loads(bor.detail_info)
                agreement_info = details['Agreement Info']
                for k, v in agreement_info.iteritems():
                    if k == 'Amount':
                        if v != bor.amount:
                            re_sign_agreement_required = True
                    else:
                        if v != details[k]:
                            re_sign_agreement_required = True

            preface = {
                'application_amount': sup_fn.try_KeyError(bor_detail, 'Applied Amount'),
                'application_tenor': prod.repayment_period,
                'application_product': prod.name_en,
                'approve_loan_amount': bor.amount,
                'annual_interest_rate': prod.APR_borrower * (1 - bor.discount_rate),
                'name': borrower_name,
                'age': borrower_age,
                'loan_purpose': sup_fn.try_KeyError(bor_detail, 'Loan Purpose'),
                'loan_purpose_list': ['Tuition', 'Investment', 'Travel', 'Debt payment', 'Others'],
                'subject': sup_fn.try_KeyError(bor_detail, 'Subject'),
                'school': sup_fn.try_KeyError(bor_detail, 'Studying University'),
                'application_state': bor.status,
                'approval_records': sup_fn.try_KeyError(bor_detail, 'Approval Records'),
                'addit_condit_decla': sup_fn.try_KeyError(bor_detail, 'Additional Condition Declaration'),
            }

            memos = AdminMemo.objects.filter(model="BorrowRequest", identifier=bor_ref_num)

            summary = {
                'disbursement': sup_fn.try_KeyError(bor_detail, 'Disbursement Method'),
                'identity_verification': bor.verify_identity,
                'identity_verification_list': ['Upload Photo', 'Face To Face'],
                'confirmed_identity': sup_fn.try_KeyError(bor_detail, 'Confirmed Identity'),
                'confirmed_identity_list': ['N', 'Y'],
                'disbursement_method': sup_fn.try_KeyError(bor_detail, 'Disbursement Method'),
                'disbursement_method_list': ['Cheque', 'Transfer'],
                'bank_code': sup_fn.try_KeyError(bor_detail, 'Bank Code').zfill(3),
                'bank_account_no': sup_fn.try_KeyError(bor_detail, 'Account Number'),
                'memos': memos,
            }

            information = {
                'surname': sup_fn.try_KeyError(bor_detail, 'Surname'),
                'given_name': sup_fn.try_KeyError(bor_detail, 'Given Name'),
                # 'name': borrower_name,
                'date_of_birth': sup_fn.try_KeyError(bor_detail, 'Date of Birth'),
                'email': usr.email,
                'HKID': sup_fn.try_KeyError(bor_detail, 'HKID'),
                'gender': sup_fn.try_KeyError(bor_detail, 'Gender'),
                'gender_list': ['Male', 'Female'],
                'mobile': sup_fn.try_KeyError(bor_detail, 'Mobile'),
                'home_tel': sup_fn.try_KeyError(bor_detail, 'Home Phone No.'),
                'home_address': sup_fn.try_KeyError(bor_detail, 'Residential Address'),
                'home_status': sup_fn.try_KeyError(bor_detail, 'Living Status'),
                'home_status_list': ['Public Housing', 'Owned by Family', 'Rent', 'Quarter',
                                     'Student Hall of Residence'],
                'living_with': sup_fn.try_KeyError(bor_detail, 'Living with'),
                'living_with_list': ['Parents', 'Relatives', 'Friends or Classmates', 'Others'],
                'school': sup_fn.try_KeyError(bor_detail, 'Studying University'),
                'subject': sup_fn.try_KeyError(bor_detail, 'Subject'),
                'subject_list': ['Medical/Health', 'Law', 'Accounting', 'Construction and Environment', 'Engineering',
                                 'Design',
                                 'Business/Finance/Economic', 'Education and Language',
                                 'Information Technology/Computing',
                                 'Social Sciences', 'Hotel and Tourism', 'Others'],
                'GPA': sup_fn.try_KeyError(bor_detail, 'Overall GPA'),
                'year_of_study': sup_fn.try_KeyError(bor_detail, 'Currently Studying'),
                'year_of_study_list': ['Year 1', 'Year 2', 'Year 3', 'Year 4'],
                'facebook': '--',
                'website': '--',

            }

            # bor.usr_id = 'emilian.siemsia@gmail.com'
            fs = classes.FriendlyScore()
            fs.getToken()
            code, main_score_detail = fs.get(endpoint='users/partner-id/' + str(bor.usr_id) + '/show')
            code, network_score_detail = fs.get(
                endpoint='users/partner-id/' + str(bor.usr_id) + '/show/social-network-data')
            code, ip_address_detail = fs.get(endpoint='users/partner-id/' + str(bor.usr_id) + '/show/ip-address-data')
            social_score = {
                'main_score_detail': main_score_detail,
                'network_score_detail': network_score_detail,
                'ip_address_detail': ip_address_detail,
                'friendlyscore_href': 'https://friendlyscore.com/company/user/application/user/show/' + sup_fn.try_KeyError(
                    main_score_detail, 'id')
            }

            bod_list = BorrowRequestDocument.objects.filter(bor_id=bor.id)

            check_list = OrderedDict()

            if len(bod_list) != 0:
                check_list[1] = {
                    'fields': {
                        'Surname': sup_fn.try_KeyError(bor_detail, 'Surname'),
                        'Given Name': sup_fn.try_KeyError(bor_detail, 'Given Name'),
                        'HKID': sup_fn.try_KeyError(bor_detail, 'HKID'),
                        'Date of Birth': sup_fn.try_KeyError(bor_detail, 'Date of Birth'),
                    },
                    'rowspan': 4,
                    'doc': 'HKID',
                    'fname': BorrowRequestDocument.objects.get(bor_id=bor.id, type='HKID').detail,
                    'confirm': BorrowRequestDocument.objects.get(bor_id=bor.id, type='HKID').confirm,
                }
                check_list[2] = {
                    'fields': {
                        'Studying University': sup_fn.try_KeyError(bor_detail, 'Studying University'),
                        'Subject': sup_fn.try_KeyError(bor_detail, 'Subject'),
                    },
                    'rowspan': 2,
                    'doc': 'Student Card',
                    'fname': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Student Card').detail,
                    'confirm': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Student Card').confirm,
                }
                check_list[3] = {
                    'fields': {
                        'Overall GPA': sup_fn.try_KeyError(bor_detail, 'Overall GPA'),
                    },
                    'rowspan': 1,
                    'doc': 'GPA',
                    'fname': BorrowRequestDocument.objects.get(bor_id=bor.id, type='GPA').detail,
                    'confirm': BorrowRequestDocument.objects.get(bor_id=bor.id, type='GPA').confirm,
                }
                check_list[4] = {
                    'fields': {
                        'Residential Address': sup_fn.try_KeyError(bor_detail, 'Residential Address'),
                        'Living Status': sup_fn.try_KeyError(bor_detail, 'Living Status'),
                    },
                    'rowspan': 2,
                    'doc': 'Address Proof',
                    'fname': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Address Proof').detail,
                    'confirm': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Address Proof').confirm,
                }
                check_list[5] = {
                    'fields': {
                        'Account Number': sup_fn.try_KeyError(bor_detail, 'Account Number'),
                        'Bank Code': sup_fn.try_KeyError(bor_detail, 'Bank Code'),
                    },
                    'rowspan': 2,
                    'doc': 'Bank Account Proof',
                    'fname': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Bank Account Proof').detail,
                    'confirm': BorrowRequestDocument.objects.get(bor_id=bor.id, type='Bank Account Proof').confirm,
                }

            status_list = ['PENDING DOC/IV', 'VALIDATED', 'REJECTED', 'CANCELLED']

            # print acknowledgement href link
            reject_print_status_list = ['AUTO APPROVED', 'DOC UPLOADED', 'CANCELLED']
            if bor.status not in reject_print_status_list:
                print_loan_agreement = '/generate_pdf_file/?bor_id=%s&doc_type=Loan Agreement' % (bor.id)
            else:
                print_loan_agreement = 'about:blank'

            content = {
                'cate': 'application',
                'title': 'Application Information - ' + bor_ref_num,
                'usr_id': usr.id,
                'bor_ref_num': bor_ref_num,
                'bor_id': bor.id,
                'model': 'BorrowRequest',
                'preface': preface,
                'status_list': status_list,
                'summary': summary,
                'information': information,
                'social_score': social_score,
                'bod_list': bod_list,
                'check_list': check_list,
                're_sign_agreement_required': re_sign_agreement_required,
                'require_tick_all_checklist': request.GET.get('require_tick_all_checklist'),

                'print_loan_agreement': print_loan_agreement,
            }
            return render(request, 'peerloan/admin/borrower/loan_application_detail.html', content)
        # view table
        prod_list = Product.objects.all()
        status_list = ['AUTO APPROVED', 'DOC UPLOADED', 'AGREEMENT CONFIRMED', 'PENDING DOC/IV',
                       'VALIDATED', 'CANCELLED', 'REJECTED']

        content = {
            'cate': 'application',
            'sub_cate': '',
            'title': 'Borrower Loan Application',
            'prod_list': prod_list,
            'status_list': status_list,
        }
        if 'all_application' in request.META.get('PATH_INFO').split('/'):
            content['sub_cate'] = 'all_application'
            content['title'] = 'All Application'
            status_list = ['AUTO APPROVED', 'DOC UPLOADED', 'AGREEMENT CONFIRMED', 'PENDING DOC/IV',
                           'VALIDATED', 'CANCELLED', 'REJECTED', 'FUND MATCHING', 'FUND MATCHING COMPLETED',
                           'DISBURSED',
                           'PAYBACK', 'PAYBACK OVERDUE', 'PAYBACK COMPLETED']
            content['status_list'] = status_list
            return render(request, 'peerloan/admin/borrower/all_application.html', content)
        return render(request, 'peerloan/admin/borrower/application.html', content)
    if request.session['handling_side'] == 'L':
        # view details
        if 'detail' in request.META.get('PATH_INFO').split('/'):

            uor_id = request.GET.get('uor_id')
            uor = UserOperationRequest.objects.get(id=uor_id)
            usr = User.objects.get(id=uor.usr_id)
            uor_details = json.loads(uor.details)
            try:
                uor_details['Corporate']
            except KeyError:
                uor_details['Corporate'] = {}
                # is individual
                account_type = 'Individual'
                name = uor_details['Individual']['Surname'] + ' ' + uor_details['Individual']['Given Name']
                age = int((timezone.localtime(timezone.now()) - pytz.timezone('Asia/Hong_Kong').localize(
                    datetime.strptime(uor_details['Individual']['Date of Birth'], '%Y-%m-%d'))).days / float(365))
                occupation = uor_details['Individual']['Occupation']
            else:
                # is corporate
                account_type = 'Corporate'
                name = uor_details['Corporate']['Company Name']
                age = int((timezone.localtime(timezone.now()) - pytz.timezone('Asia/Hong_Kong').localize(
                    datetime.strptime(uor_details['Corporate']['Established at'], '%Y-%m-%d'))).days / float(365))
                occupation = uor_details['Corporate']['Industry']
            preface = {
                'source_of_fund': uor_details['Individual']['Source of Fund'],
                'source_of_fund_list': ['Salary', 'Business', 'Investment', 'Others'],
                'other_source_of_fund': sup_fn.try_KeyError(uor_details['Individual'], 'Other Source of Fund'),

                'account_type': account_type,
                'account_type_list': ['Individual', 'Corporate'],
                'name': name,
                'age': age,
                'occupation': occupation,
                'customer_declaration': uor_details['Individual']['Customer Declaration'],
                'customer_declaration_list': ['1', '2', '3', '4'],
                'application_state': uor.status,
            }

            summary = {
            }

            nationality_list = []
            f = open('/home/ubuntu/project_peerloan/peerloan/peerloan_src/nationality.csv', 'r')
            for row in csv.DictReader(f):
                nationality_list.append(row['Nationality'])
            f.close()

            country_list = []
            f = open('/home/ubuntu/project_peerloan/peerloan/peerloan_src/countries_of_the_world.csv', 'r')
            for row in csv.DictReader(f):
                country_list.append(row['Country'])
            f.close()
            information = {
                'company_name': sup_fn.try_KeyError(uor_details['Corporate'], 'Company Name'),
                'established_at': sup_fn.try_KeyError(uor_details['Corporate'], 'Established at'),
                'CR_no': sup_fn.try_KeyError(uor_details['Corporate'], 'CR NO.'),
                'country': sup_fn.try_KeyError(uor_details['Corporate'], 'Country'),
                'country_list': country_list,
                'office_address': sup_fn.try_KeyError(uor_details['Corporate'], 'Office Address'),
                'office_tel': sup_fn.try_KeyError(uor_details['Corporate'], 'Office Tel'),

                'surname': sup_fn.try_KeyError(uor_details['Individual'], 'Surname'),
                'given_name': sup_fn.try_KeyError(uor_details['Individual'], 'Given Name'),
                'date_of_birth': sup_fn.try_KeyError(uor_details['Individual'], 'Date of Birth'),
                'email': usr.email,
                'id_passport': sup_fn.try_KeyError(uor_details['Individual'], 'HKID'),
                'gender': sup_fn.try_KeyError(uor_details['Individual'], 'Gender'),
                'gender_list': ['Male', 'Female'],
                'occupation': sup_fn.try_KeyError(uor_details['Individual'], 'Occupation'),
                'nationality': sup_fn.try_KeyError(uor_details['Individual'], 'Nationality'),
                'nationality_list': nationality_list,
                'mobile': sup_fn.try_KeyError(uor_details['Individual'], 'Mobile'),
                'home_tel': sup_fn.try_KeyError(uor_details['Individual'], 'Home Phone No.'),
                'home_address': sup_fn.try_KeyError(uor_details['Individual'], 'Residential Address'),
                'education_level': sup_fn.try_KeyError(uor_details['Individual'], 'Education Level'),
                'annual_income': sup_fn.try_KeyError(uor_details['Individual'], 'Annual Income'),
                'type_of_employment': sup_fn.try_KeyError(uor_details['Individual'], 'Type of Employment'),
                'type_of_employment_list': ['Full Time Employed', 'Part Time Employed', 'Self-Employed', 'Unemployed',
                                            'Housewife', 'Retired'],
                'company_name': sup_fn.try_KeyError(uor_details['Individual'], 'Company Name'),
                'office_address': sup_fn.try_KeyError(uor_details['Individual'], 'Office Address'),
                'office_tel': sup_fn.try_KeyError(uor_details['Individual'], 'Office Tel'),
                'source_of_fund': sup_fn.try_KeyError(uor_details['Individual'], 'Source of Fund'),
                'other_source_of_fund': sup_fn.try_KeyError(uor_details['Individual'], 'Other Source of Fund'),

                'memos': AdminMemo.objects.filter(model="UserOperationRequest", identifier=uor.id)
            }

            try:
                lender_usr = User.objects.get(email=usr.email, type='L')
            except ObjectDoesNotExist:
                setting = {}
            else:
                setting = {}
                uri_list = UserInformation.objects.filter(info_type='Settings')
                notification = json.loads(lender_usr.notification)
                for uri in uri_list:
                    uri.details = json.loads(uri.details, object_pairs_hook=OrderedDict)
                    setting[uri.section] = OrderedDict()
                    for k, v in uri.details.iteritems():
                        setting[uri.section][k] = notification[k]

            check_list = OrderedDict()

            if len(uor_details['File Uploaded']) != 0:
                file_details = uor_details['File Uploaded']
                try:
                    confirm_file_details = uor_details['Confirm File Uploaded']
                except:
                    confirm_file_details = {}
                check_list[1] = {
                    'fields': {
                        'Surname': sup_fn.try_KeyError(uor_details['Individual'], 'Surname'),
                        'Given Name': sup_fn.try_KeyError(uor_details['Individual'], 'Given Name'),
                        'HKID': sup_fn.try_KeyError(uor_details['Individual'], 'HKID'),
                        'Date of Birth': sup_fn.try_KeyError(uor_details['Individual'], 'Date of Birth'),
                    },
                    'rowspan': 4,
                    'doc': 'HKID Proof',
                    'fname': file_details['HKID Proof'],
                    'confirm': sup_fn.try_KeyError(confirm_file_details, 'HKID Proof'),
                }
                check_list[2] = {
                    'fields': {
                        'Residential Address': sup_fn.try_KeyError(uor_details['Individual'], 'Residential Address'),
                    },
                    'rowspan': 1,
                    'doc': 'Address Proof',
                    'fname': file_details['Address Proof'],
                    'confirm': sup_fn.try_KeyError(confirm_file_details, 'Address Proof'),
                }
                if account_type == 'Corporate':
                    check_list[3] = {
                        'fields': {
                            'Company Name': sup_fn.try_KeyError(uor_details['Corporate'], 'Company Name'),
                            'Established at': sup_fn.try_KeyError(uor_details['Corporate'], 'Established at'),
                            'CR NO.': sup_fn.try_KeyError(uor_details['Corporate'], 'CR NO.'),
                            'Office Address': sup_fn.try_KeyError(uor_details['Corporate'], 'Office Address'),
                            'Company Size': sup_fn.try_KeyError(uor_details['Corporate'], 'Company Size'),
                            'Office Tel': sup_fn.try_KeyError(uor_details['Corporate'], 'Office Tel'),
                            'Industry': sup_fn.try_KeyError(uor_details['Corporate'], 'Industry'),
                        },
                        'rowspan': 7,
                        'doc': 'BR/CR',
                        'fname': file_details['BR/CR'],
                        'confirm': sup_fn.try_KeyError(confirm_file_details, 'BR/CR'),
                    }

            status_list = ['PENDING DOC/IV', 'APPROVED', 'REJECTED', 'CANCELLED']

            # print acknowledgement href link
            reject_print_status_list = ['DOC UPLOADED', 'PENDING DOC/IV', 'APPROVED', 'REJECTED', 'CANCELLED']
            if uor.status not in reject_print_status_list:
                print_lender_agreement = '/generate_pdf_file/?uor_id=%s&doc_type=Lender Agreement' % (uor.id)
            else:
                print_lender_agreement = 'about:blank'

            content = {
                'cate': 'application',
                'sub_cate': '',
                'title': 'Investor Application Information',
                'usr_id': usr.id,
                'ref_id': uor.id,
                'model': 'UserOperationRequest',
                'status_list': status_list,
                'preface': preface,
                'information': information,
                'document': uor_details['File Uploaded'],
                'setting': setting,
                'check_list': check_list,
                'print_lender_agreement': print_lender_agreement,

                'require_tick_all_checklist': request.GET.get('require_tick_all_checklist'),
            }
            return render(request, 'peerloan/admin/lender/investor_application_detail.html', content)
        # view table
        status_list = [
            'DOC UPLOADED', 'PENDING DOC/IV', 'APPROVED', 'AGREEMENT CONFIRMED',
            'REJECTED', 'CANCELLED',
        ]
        content = {
            'cate': 'application',
            'sub_cate': '',
            'title': 'Application',
            'status_list': status_list,
        }
        return render(request, 'peerloan/admin/lender/application.html', content)


@require_login
def disbursement(request):
    prod_list = Product.objects.all()
    content = {
        'cate': 'disbursement',
        'sub_cate': '',
        'title': 'Disbursement',
        'prod_list': prod_list,
    }
    return render(request, 'peerloan/admin/borrower/disbursement.html', content)


@require_login
def repayment(request):
    # view details
    if 'detail' in request.META.get('PATH_INFO').split('/'):
        # if view repayment history
        if 'repayment_history' in request.META.get('PATH_INFO').split('/'):
            bor_ref_num = request.GET.get('bor_ref_num')
            bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
            loan_list = Loan.objects.filter(bor_id=bor.id)
            prod = Product.objects.get(id=bor.prod_id)

            # create repayment table
            los_list = LoanSchedule.objects.filter(bor_id=bor.id)
            repayment_table = []
            repayment_history = []
            remain_balance = bor.amount
            for i in range(prod.repayment_period):
                los = los_list[i]
                remain_balance -= los.principal
                row = {
                    'tenor': str(i + 1),
                    'due_date': los.due_date,
                    'instalment_amount': '%.2f' % (los.instalment),
                    'interest': '%.2f' % (los.interest),
                    'principal': '%.2f' % (los.principal),
                    'outstanding_principal': '%.2f' % (remain_balance),
                }
                repayment_table.append(row)

                if 'PAID' in los.status or 'PAYBACK COMPLETED' in los.status:
                    row = {
                        'due_date': los.due_date,
                        'repayment_date': timezone.localtime(los.repayment_date).strftime('%Y/%m/%d'),
                        'overdue_day': los.overdue_days,
                        'overdue_interest': '%.2f' % (los.overdue_interest_remained + los.overdue_interest_unpay_paid),
                        'payment_amount': '%.2f' % (los.received_amount),
                        'repayment_method': los.repayment_method,
                        'repayment_type': los.repayment_type,
                    }
                    repayment_history.append(row)

            content = {
                'caption': 'Estimated Repayment Schedule - ' + bor_ref_num,
                'caption2': 'Repayment History - ' + bor_ref_num,
                'repayment_table': repayment_table,
                'repayment_history': repayment_history
            }
            return render(request, 'peerloan/admin/borrower/repayment_history.html', content)

        # detail page
        bor_ref_num = request.GET.get('bor_ref_num')
        bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
        detail = json.loads(bor.detail_info)
        try:
            name = detail['Surname'] + ' ' + detail['Given Name']
        except KeyError:
            name = '--'

        prod = Product.objects.get(id=bor.prod_id)
        loan_list = Loan.objects.filter(bor_id=bor.id)

        def date_postfix(n):
            if n % 10 == 1:
                return 'st'
            elif n % 10 == 2:
                return 'nd'
            elif n % 10 == 3:
                return 'rd'
            else:
                return 'th'

        due_day = bor.draw_down_date.day
        los_list = LoanSchedule.objects.filter(bor_id=bor.id, status='OVERDUE')
        preface = {
            'loan_no': bor_ref_num,
            'due_date': str(due_day) + date_postfix(due_day) + ' day of each calendar',
            'loan_amount': sum([loan.initial_amount for loan in loan_list]),
            'tenor': prod.repayment_period,
            'name': name,
            'autopay_return_reason': '--',
            # 'outstanding_amount': round(bor.instalment_borrower * (prod.repayment_period - bor.repaid_month), 2),
            'outstanding_amount': '%.2f' % (sum([loan.remain_principal for loan in loan_list])),
            'overdue_interest': round(sum([los.overdue_interest_accumulated for los in los_list]), 2),
            'interest_rate': '%.2f' % (bor.getBorAPR(prod.APR_borrower)),
        }
        overdue_record_list = []
        los_list = LoanSchedule.objects.filter(bor_id=bor.id, status='OVERDUE')
        for los in los_list:
            row = {
                'tenor': los.tenor,
                'instalment': round(los.instalment, 2),
                'principal': str(round(los.principal, 2)) + '<br>(paid:' + str(round(los.paid_principal, 2)) + ')',
                'interest': str(round(los.interest, 2)) + '<br>(paid:' + str(round(los.paid_interest, 2)) + ')',
                'due_date': los.due_date,
                'overdue_day': los.overdue_days,
                'overdue_interest': str(round(los.overdue_interest_accumulated, 2)) + '<br>(paid:' + str(
                    round(los.paid_overdue_interest, 2)) + ')',
                'late_charge': str(round(los.late_charge, 2)) + '<br>(paid:' + str(
                    round(los.paid_late_charge, 2)) + ')',
                'total': str(round(los.instalment + los.overdue_interest_accumulated + los.late_charge, 2))
                         + '<br>(paid:' + str(
                    round(los.paid_principal + los.paid_interest + los.paid_late_charge + los.paid_overdue_interest,
                          2)) + ')',
            }
            overdue_record_list.append(row)

        # calculate early settlement
        inputs = {
            'bor_id': bor.id,
            'type': 'early_settlement',
        }
        outputs = sup_fn.calculate_repay_amount(inputs)
        early_settlement_amount = outputs['early_settlement_amount'] + outputs['late_charge'] - outputs[
            'overpay_amount']

        # get borrower repayment submission
        """
        uor_list = UserOperationRequest.objects.filter(usr_id=bor.usr_id, type='Repayment')
        uor_list = [uor for uor in uor_list if int(json.loads(uor.details)['bor_id']) == bor.id]
        if len(uor_list) != 0:
            uor = uor_list[-1]
            details = json.loads(uor.details)
            repay_info = {
                'type': details['Repayment Type'],
                'amount': details['Deposit Amount'],
                'uploaded_document': '<a href="/file/'+str(details['fname'])+'" target="_blank">View</a>',
                'date': details['Deposit Date'],
                'status': uor.status,
            }
        else:
            repay_info = {
                'type': '--',
                'amount': '--',
                'uploaded_document': '--',
                'date': '--',
                'status': '--',
            }
        """
        content = {
            'cate': 'repayment',
            'sub_cate': '',
            'title': 'Repayment Information - ' + bor_ref_num,
            'bor_ref_num': bor_ref_num,
            'preface': preface,
            'overdue_record_list': overdue_record_list,
            'early_settlement_amount': '%.2f' % (early_settlement_amount),
            'overpay_amount': '%.2f' % (bor.overpay_amount),
            # 'repay_info': repay_info,
        }
        return render(request, 'peerloan/admin/borrower/repayment_detail.html', content)

    # view table
    prod_list = Product.objects.all()
    status_list = ['DISBURSED', 'PAYBACK', 'PAYBACK OVERDUE', 'PAYBACK COMPLETED']
    content = {
        'cate': 'repayment',
        'sub_cate': '',
        'title': 'Repayment',
        'prod_list': prod_list,
        'status_list': status_list,
    }
    return render(request, 'peerloan/admin/borrower/repayment.html', content)


@require_login
def collection(request):
    return redirect(request.META.get('HTTP_REFERER'))


@require_login
def account(request):
    if request.session['handling_side'] == 'B':
        if 'ledger' in request.META.get('PATH_INFO').split('/'):
            bor_ref_num = request.GET.get('bor_ref_num')
            bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
            prod = Product.objects.get(id=bor.prod_id)
            details = json.loads(bor.detail_info)

            total_interest = '--'
            if prod.repayment_plan == 'Instalment':
                total_interest = bor.instalment_borrower * prod.repayment_period - bor.amount
            elif prod.repayment_plan == 'Balloon Payment':
                total_interest = bor.instalment_borrower * prod.repayment_period
            elif prod.repayment_plan == 'Promotion Balloon Payment':
                total_interest = bor.instalment_borrower * 9

            infos = {
                'name_of_borrower': details['Surname'] + ' ' + details['Given Name'],
                'interest_rate': str(prod.APR_borrower * (1 - bor.discount_rate)) + '%',
                'loan_no': bor.ref_num,
                'interest_start_date': bor.draw_down_date.strftime('%Y/%m/%d'),
                'loan_amount': bor.amount,
                'total_interest': '%.2f' % (total_interest),
                'total_tenor': prod.repayment_period,
            }
            content = {
                'cate': 'account',
                'sub_cate': '',
                'title': 'Account - Ledger',
                'bor_id': bor.id,
                'bor_ref_num': bor.ref_num,
                'infos': infos
            }
            return render(request, 'peerloan/admin/borrower/ledger.html', content)

        prod_list = Product.objects.all()
        status_list = ['DISBURSED', 'PAYBACK', 'PAYBACK OVERDUE', 'PAYBACK COMPLETED']
        content = {
            'cate': 'account',
            'sub_cate': '',
            'title': 'Account',
            'prod_list': prod_list,
            'status_list': status_list,
        }
        return render(request, 'peerloan/admin/borrower/account.html', content)
    if request.session['handling_side'] == 'L':
        if 'ledger' in request.META.get('PATH_INFO').split('/'):
            usr_id = request.GET.get('usr_id')
            acc = Account.objects.get(usr_id=usr_id)
            usr = User.objects.get(id=usr_id)
            details = json.loads(usr.detail_info)

            try:
                name = details['Individual']['Surname'] + ' ' + details['Individual']['Given Name']
            except KeyError:
                name = '--'

            inv_list = Investment.objects.filter(usr_id=usr_id)
            loan_list = []
            for inv in inv_list:
                loans = Loan.objects.filter(inv_id=inv.id)
                loans = [loan for loan in loans if
                         'MATCHED' not in loan.status and 'COMPLETED' not in loan.status and 'RELEASE' not in loan.status]
                for loan in loans:
                    loan_list.append(loan)

            total_amount = sum([loan.remain_principal_lender for loan in loan_list])
            try:
                write_off_percentage = sum(
                    [loan.remain_principal_lender for loan in loan_list if 'WRITE OFF' in loan.status]) / sum(
                    [loan.remain_principal_lender for loan in loan_list])
            except ZeroDivisionError:
                write_off_percentage = 0

            weighted_interest_rate = 0
            for inv in inv_list:
                prod = Product.objects.get(id=inv.prod_id)
                loans = Loan.objects.filter(inv_id=inv.id)
                loans = [loan for loan in loans if
                         'MATCHED' not in loan.status and 'COMPLETED' not in loan.status and 'RELEASE' not in loan.status]
                try:
                    ratio = sum([loan.remain_principal_lender for loan in loans]) / total_amount
                except ZeroDivisionError:
                    ratio = 0
                weighted_interest_rate += prod.APR_lender * 0.01 * ratio

            infos = {
                'name_of_investor': name,
                'account_no': usr.id,
                'account_balance': acc.balance + acc.on_hold_amt,
                'write_off_percentage': str(round(write_off_percentage * 100, 2)) + '%',
                'adjusted_return_percentage': str(
                    round((weighted_interest_rate - write_off_percentage) * 100, 2)) + '%',
            }
            content = {
                'cate': 'account',
                'sub_cate': '',
                'title': 'Account - Ledger',
                'usr_id': usr_id,
                'infos': infos
            }
            return render(request, 'peerloan/admin/lender/ledger.html', content)

        prod_list = Product.objects.all()
        content = {
            'cate': 'account',
            'sub_cate': '',
            'title': 'Account',
            'prod_list': prod_list
        }
        return render(request, 'peerloan/admin/lender/account.html', content)


@require_login
def fund_matching(request):
    if 'list_detail' in request.META.get('PATH_INFO').split('/'):
        bor_ref_num = request.GET.get('bor_ref_num')
        inv_id = request.GET.get('inv_id')

        if bor_ref_num != None:
            bor = BorrowRequest.objects.get(ref_num=bor_ref_num)
            loan_list = Loan.objects.filter(bor_id=bor.id)
            table = {}
            header = ['Investor', 'Initial Investment Amount', 'Matched Date']
            rows = []
            for loan in loan_list:
                inv = Investment.objects.get(id=loan.inv_id)
                usr = User.objects.get(id=inv.usr_id)
                acc = Account.objects.get(usr_id=inv.usr_id)
                row = [usr.email, loan.initial_amount, loan.create_timestamp.strftime('%Y/%m/%d')]
                rows.append(row)
            table = {
                'header': header,
                'rows': rows,
            }
            caption = 'Loan - ' + bor_ref_num
        if inv_id != None:
            inv = Investment.objects.get(id=inv_id)
            inv_usr = User.objects.get(id=inv.usr_id)
            table = {}
            header = ['Borrower', 'Initial Investment Amount', 'Matched Date']
            rows = []

            loan_list = Loan.objects.filter(inv_id=inv.id, status='MATCHED')
            for loan in loan_list:
                bor = BorrowRequest.objects.get(id=loan.bor_id)
                bor_usr = User.objects.get(id=bor.usr_id)
                row = [bor_usr.email, loan.initial_amount, loan.create_timestamp.strftime('%Y/%m/%d')]
                rows.append(row)
            table = {
                'header': header,
                'rows': rows,
            }
            caption = 'Investor - ' + inv_usr.email
        content = {
            'caption': caption,
            'table': table,
        }
        return render(request, 'peerloan/admin/lender/matching_list.html', content)

    content = {
        'cate': 'fund_matching',
        'title': 'Fund Matching',
        'prod_list': Product.objects.filter(status='ACTIVE'),
    }
    return render(request, 'peerloan/admin/lender/fund_matching.html', content)


@require_login
def deposit(request):
    content = {
        'cate': 'deposit',
        'sub_cate': '',
    }
    return render(request, 'peerloan/admin/lender/deposit.html', content)


@require_login
def cash_out(request):
    content = {
        'cate': 'cash_out',
        'sub_cate': '',
    }
    return render(request, 'peerloan/admin/lender/cash_out.html', content)


@require_login
def KYC_and_AML(request):
    return redirect(request.META.get('HTTP_REFERER'))


@require_login
def report(request):
    return redirect(request.META.get('HTTP_REFERER'))


@require_login
def audit_trail(request):
    if request.session['handling_side'] == 'L':
        content = {
            'cate': 'audit_trail',
            'sub_cate': '',
            'title': 'Audit Trail',
        }
        return render(request, 'peerloan/admin/lender/audit_trail.html', content)
    if request.session['handling_side'] == 'B':
        if 'active_account' in request.META.get('PATH_INFO').split('/'):
            content = {
                'cate': 'audit_trail',
                'sub_cate': 'active_account',
                'title': 'Audit Trail of Active Account',
            }
            return render(request, 'peerloan/admin/borrower/active_borrower_account.html', content)
        content = {
            'cate': 'audit_trail',
            'sub_cate': '',
            'title': 'Audit Trail',
        }
        return render(request, 'peerloan/admin/borrower/audit_trail.html', content)


@require_login
def pl_account(request):
    content = {
        'cate': 'pl_account',
        'sub_cate': '',
        'title': 'P L Account',
    }
    return render(request, 'peerloan/admin/lender/pl_account.html', content)


@require_login
def promotion_handling(request):
    content = {
        'cate': 'promotion_handling',
        'sub_cate': '',
        'title': 'Promotion Handling',
    }
    return render(request, 'peerloan/admin/lender/promotion_handling.html', content)
    # return HttpResponse("hello promotion handling!!")
