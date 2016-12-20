# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0029_auto_20161012_1820'),
    ]

    operations = [
        migrations.AddField(
            model_name='borrowrequest',
            name='discount_rate',
            field=models.FloatField(default=0),
        ),
    ]
