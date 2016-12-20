# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0002_account_adminmemo_audittrail_borrowrequest_borrowrequestdocument_investment_ledger_loan_loanschedule'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='audittrail',
            name='ref_id',
        ),
    ]
