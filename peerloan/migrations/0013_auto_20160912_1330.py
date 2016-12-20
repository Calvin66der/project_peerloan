# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0012_ledger_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='loanschedule',
            name='overdue_interest_dict',
            field=models.CharField(default='{}', max_length=5000),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='paid_interest',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='paid_overdue_interest',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='paid_principal',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
    ]
