# Generated by Django 2.2.6 on 2019-11-06 18:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0027_dprhh_dprinfra'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dprinfra',
            name='site',
        ),
        migrations.DeleteModel(
            name='DprHH',
        ),
        migrations.DeleteModel(
            name='DprInfra',
        ),
    ]
