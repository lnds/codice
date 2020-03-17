# Generated by Django 3.0.4 on 2020-03-08 23:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repos', '0003_auto_20200308_1829'),
    ]

    operations = [
        migrations.AlterField(
            model_name='repository',
            name='status',
            field=models.IntegerField(choices=[(0, 'CREATED'), (1, 'ERROR'), (2, 'CLONING'), (3, 'CLONED'), (4, 'ANALYZING'), (5, 'OK')]),
        ),
    ]
