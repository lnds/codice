# Generated by Django 3.1.6 on 2021-02-18 22:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0018_delete_fileblame'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='filechange',
            name='codice_file_commit__18f851_idx',
        ),
        migrations.RemoveIndex(
            model_name='filechange',
            name='codice_file_file_id_e244e6_idx',
        ),
    ]
