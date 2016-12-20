# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0018_auto_20160912_1536'),
    ]

    operations = [
        migrations.AddField(
            model_name='loanschedule',
            name='paid_interest_l',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='loanschedule',
            name='paid_principal_l',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
    ]
