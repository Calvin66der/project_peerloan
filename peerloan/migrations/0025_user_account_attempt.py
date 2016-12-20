# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0024_auto_20160923_1326'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='account_attempt',
            field=models.IntegerField(default=0),
        ),
    ]
