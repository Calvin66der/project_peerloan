# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0010_ledger_bor_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ledger',
            name='usr_id',
            field=models.IntegerField(null=True),
        ),
    ]
