# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0025_user_account_attempt'),
    ]

    operations = [
        migrations.RenameField(
            model_name='loanschedule',
            old_name='collection_fees',
            new_name='late_charge',
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='paid_late_charge',
            field=models.FloatField(default=0),
        ),
    ]
