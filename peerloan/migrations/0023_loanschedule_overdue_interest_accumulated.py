# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0022_auto_20160920_1127'),
    ]

    operations = [
        migrations.AddField(
            model_name='loanschedule',
            name='overdue_interest_accumulated',
            field=models.FloatField(default=0),
        ),
    ]
