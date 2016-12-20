# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0004_audittrail_ref_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingTaskNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ref_id', models.IntegerField()),
                ('model', models.CharField(max_length=50)),
                ('status', models.CharField(max_length=50)),
                ('create_timestamp', models.DateTimeField()),
                ('update_timestamp', models.DateTimeField()),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='last_login',
            field=models.DateTimeField(null=True),
        ),
    ]
