# Generated by Django 2.2.6 on 2019-11-30 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0049_resolution_deadline'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resolution',
            name='deadline',
            field=models.DateField(blank=True, null=True),
        ),
    ]
