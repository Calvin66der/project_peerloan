# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0014_auto_20160912_1344'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='loanschedule',
            name='overdue_interest_paid_day',
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='overdue_interest_paid_days',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]
