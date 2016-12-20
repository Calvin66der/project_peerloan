# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0028_user_simplified_hkid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='simplified_hkid',
        ),
        migrations.AddField(
            model_name='useroperationrequest',
            name='simplified_hkid',
            field=models.CharField(max_length=45, null=True),
        ),
    ]
