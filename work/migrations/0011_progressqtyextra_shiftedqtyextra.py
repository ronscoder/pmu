# Generated by Django 2.2.6 on 2019-11-05 09:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0010_auto_20191105_0553'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgressQtyExtra',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hab_id', models.CharField(max_length=200, unique=True)),
                ('ht', models.FloatField(blank=True, null=True)),
                ('pole_ht_8m', models.IntegerField(blank=True, null=True)),
                ('lt_3p', models.FloatField(blank=True, null=True)),
                ('lt_1p', models.FloatField(blank=True, null=True)),
                ('pole_lt_8m', models.IntegerField(blank=True, null=True)),
                ('dtr_100', models.IntegerField(blank=True, null=True)),
                ('dtr_63', models.IntegerField(blank=True, null=True)),
                ('dtr_25', models.IntegerField(blank=True, null=True)),
                ('remark', models.CharField(blank=True, max_length=200, null=True)),
                ('status', models.CharField(blank=True, max_length=200, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ShiftedQtyExtra',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hab_id', models.CharField(max_length=200, unique=True)),
                ('acsr', models.FloatField(blank=True, null=True)),
                ('cable_3p', models.FloatField(blank=True, null=True)),
                ('cable_1p', models.FloatField(blank=True, null=True)),
                ('pole_8m', models.IntegerField(blank=True, null=True)),
                ('pole_9m', models.IntegerField(blank=True, null=True)),
                ('dtr_100', models.IntegerField(blank=True, null=True)),
                ('dtr_63', models.IntegerField(blank=True, null=True)),
                ('dtr_25', models.IntegerField(blank=True, null=True)),
                ('remark', models.CharField(blank=True, max_length=200, null=True)),
                ('site', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='work.Site')),
            ],
        ),
    ]
