# Generated by Django 3.1.6 on 2021-02-16 23:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('developers', '0002_blame'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='developer',
            index=models.Index(fields=['email', 'owner'], name='codice_deve_email_4157e5_idx'),
        ),
    ]
