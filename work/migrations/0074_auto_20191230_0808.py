# Generated by Django 2.2.6 on 2019-12-30 08:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0073_auto_20191230_0804'),
    ]

    operations = [
        migrations.AddField(
            model_name='dprqty',
            name='is_dpr_scope',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicaldprqty',
            name='is_dpr_scope',
            field=models.BooleanField(default=False),
        ),
    ]
