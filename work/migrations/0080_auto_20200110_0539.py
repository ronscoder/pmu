# Generated by Django 2.2.6 on 2020-01-10 05:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0079_auto_20200104_1242'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalprogressqty',
            name='has_infra',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicalprogressqtyextra',
            name='has_infra',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='progressqty',
            name='has_infra',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='progressqtyextra',
            name='has_infra',
            field=models.BooleanField(default=False),
        ),
    ]
