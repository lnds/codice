# Generated by Django 3.0.4 on 2020-03-14 23:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commits', '0002_auto_20200308_1830'),
        ('files', '0002_fileblame'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='fileblame',
            unique_together={('file', 'commit')},
        ),
        migrations.AlterModelTable(
            name='fileblame',
            table='codice_fileblame',
        ),
    ]
