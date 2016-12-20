# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0016_loanschedule_overdue_interest_unpay_paid'),
    ]

    operations = [
        migrations.AddField(
            model_name='borrowrequest',
            name='overpay_amount',
            field=models.FloatField(default=0),
        ),
    ]
