# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0019_auto_20160912_1754'),
    ]

    operations = [
        migrations.AddField(
            model_name='loanschedule',
            name='repayment_type',
            field=models.CharField(default='Instalment', max_length=50),
            preserve_default=False,
        ),
    ]
