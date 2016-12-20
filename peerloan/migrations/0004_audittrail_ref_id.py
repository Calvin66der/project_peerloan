# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peerloan', '0003_remove_audittrail_ref_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='audittrail',
            name='ref_id',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
