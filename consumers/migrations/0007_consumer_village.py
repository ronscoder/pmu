# Generated by Django 2.2.6 on 2019-12-07 06:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consumers', '0006_consumer_remark'),
    ]

    operations = [
        migrations.AddField(
            model_name='consumer',
            name='village',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
