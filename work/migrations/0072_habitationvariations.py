# Generated by Django 2.2.6 on 2019-12-17 18:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0071_variations'),
    ]

    operations = [
        migrations.CreateModel(
            name='HabitationVariations',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('habitation', models.CharField(max_length=50)),
                ('site', models.ManyToManyField(to='work.Site')),
            ],
        ),
    ]
