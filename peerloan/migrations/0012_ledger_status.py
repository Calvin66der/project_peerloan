# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0011_auto_20160909_1052'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledger',
            name='status',
            field=models.CharField(max_length=50, null=True),
        ),
    ]
