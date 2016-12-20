# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0017_borrowrequest_overpay_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loanschedule',
            name='received_amount',
            field=models.FloatField(default=0),
        ),
    ]
