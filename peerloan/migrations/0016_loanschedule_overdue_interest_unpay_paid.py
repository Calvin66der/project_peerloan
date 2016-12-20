# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0015_auto_20160912_1344'),
    ]

    operations = [
        migrations.AddField(
            model_name='loanschedule',
            name='overdue_interest_unpay_paid',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
    ]
