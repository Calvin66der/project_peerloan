# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0023_loanschedule_overdue_interest_accumulated'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audittrail',
            name='description',
            field=models.CharField(max_length=1000),
        ),
    ]
