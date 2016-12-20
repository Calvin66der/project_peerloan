# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0031_adminuser'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='fake_APR_borrower',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='fake_APR_lender',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='fake_repayment_period',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='name_en',
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name='product',
            name='name_zh',
            field=models.CharField(max_length=64),
        ),
    ]
