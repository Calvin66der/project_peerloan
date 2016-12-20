# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0027_borrowrequest_simplified_hkid'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='simplified_hkid',
            field=models.CharField(max_length=45, null=True),
        ),
    ]
