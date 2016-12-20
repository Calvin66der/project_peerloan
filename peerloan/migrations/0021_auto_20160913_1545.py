# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0020_loanschedule_repayment_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loanschedule',
            name='repayment_type',
            field=models.CharField(max_length=50, null=True),
        ),
    ]
