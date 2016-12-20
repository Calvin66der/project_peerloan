# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0013_auto_20160912_1330'),
    ]

    operations = [
        migrations.RenameField(
            model_name='loanschedule',
            old_name='overdue_day',
            new_name='overdue_days',
        ),
        migrations.RenameField(
            model_name='loanschedule',
            old_name='overdue_interest_dict',
            new_name='overdue_interest_paid_day',
        ),
        migrations.RenameField(
            model_name='loanschedule',
            old_name='overdue_interest',
            new_name='overdue_interest_remained',
        ),
    ]
