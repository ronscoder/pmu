# Generated by Django 2.2.6 on 2019-12-07 14:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0059_resolutionlink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resolutionlink',
            name='resolution',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='work.Resolution'),
        ),
    ]
