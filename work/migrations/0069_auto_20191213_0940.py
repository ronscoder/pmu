# Generated by Django 2.2.6 on 2019-12-13 09:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0068_auto_20191211_0642'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dprqty',
            old_name='dtr100_no',
            new_name='dtr_100',
        ),
        migrations.RenameField(
            model_name='dprqty',
            old_name='dtr25_no',
            new_name='dtr_25',
        ),
        migrations.RenameField(
            model_name='dprqty',
            old_name='dtr63_no',
            new_name='dtr_63',
        ),
        migrations.RenameField(
            model_name='dprqty',
            old_name='ht_length',
            new_name='ht',
        ),
        migrations.RenameField(
            model_name='dprqty',
            old_name='lt1_length',
            new_name='lt_1p',
        ),
        migrations.RenameField(
            model_name='dprqty',
            old_name='lt3_length',
            new_name='lt_3p',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='dtr100_no',
            new_name='dtr_100',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='dtr25_no',
            new_name='dtr_25',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='dtr63_no',
            new_name='dtr_63',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='ht_length',
            new_name='ht',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='lt1_length',
            new_name='lt_1p',
        ),
        migrations.RenameField(
            model_name='historicaldprqty',
            old_name='lt3_length',
            new_name='lt_3p',
        ),
        migrations.AddField(
            model_name='dprqty',
            name='pole_9m',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dprqty',
            name='pole_ht_8m',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dprqty',
            name='pole_lt_8m',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaldprqty',
            name='pole_9m',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaldprqty',
            name='pole_ht_8m',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicaldprqty',
            name='pole_lt_8m',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
