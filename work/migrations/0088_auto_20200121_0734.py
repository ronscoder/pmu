# Generated by Django 2.2.6 on 2020-01-21 07:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0087_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalsite',
            name='project',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='work.Project'),
        ),
        migrations.AddField(
            model_name='historicalsiteextra',
            name='project',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='work.Project'),
        ),
        migrations.AddField(
            model_name='site',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='work.Project'),
        ),
        migrations.AddField(
            model_name='siteextra',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='work.Project'),
        ),
    ]
