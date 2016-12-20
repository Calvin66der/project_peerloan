# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0021_auto_20160913_1545'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='mobile',
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='collection_fees',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='overdue_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='overdue_interest_paid_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='overdue_interest_remained',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='overdue_interest_unpay_paid',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='paid_interest',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='paid_interest_l',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='paid_overdue_interest',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='paid_principal',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='loanschedule',
            name='paid_principal_l',
            field=models.FloatField(default=0),
        ),
    ]
