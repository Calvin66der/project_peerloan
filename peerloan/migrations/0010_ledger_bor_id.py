# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0009_auto_20160908_1706'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledger',
            name='bor_id',
            field=models.IntegerField(null=True),
        ),
    ]
