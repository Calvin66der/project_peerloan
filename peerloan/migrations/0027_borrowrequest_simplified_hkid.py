# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0026_auto_20161007_1558'),
    ]

    operations = [
        migrations.AddField(
            model_name='borrowrequest',
            name='simplified_hkid',
            field=models.CharField(max_length=45, null=True),
        ),
    ]
