# Generated by Django 3.0.4 on 2020-03-08 18:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repos', '0002_auto_20200308_1220'),
    ]

    operations = [
        migrations.AlterField(
            model_name='repository',
            name='default_branch',
            field=models.CharField(blank=True, default='master', max_length=40),
        ),
    ]