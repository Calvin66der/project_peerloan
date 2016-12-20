# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0007_pendingtasknotification_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingtasknotification',
            name='type',
            field=models.CharField(default='Apply To Be Investor', max_length=50),
            preserve_default=False,
        ),
    ]
