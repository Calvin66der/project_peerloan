# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0030_borrowrequest_discount_rate'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.CharField(max_length=45)),
                ('password', models.CharField(max_length=45)),
                ('type', models.CharField(max_length=45)),
                ('status', models.CharField(max_length=45)),
                ('last_login', models.DateTimeField(null=True)),
                ('this_login', models.DateTimeField(null=True)),
                ('account_attempt', models.IntegerField(default=0)),
                ('create_timestamp', models.DateTimeField()),
                ('update_timestamp', models.DateTimeField()),
            ],
        ),
    ]
