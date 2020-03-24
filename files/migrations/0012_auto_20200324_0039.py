# Generated by Django 3.0.4 on 2020-03-24 00:39

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('developers', '0002_blame'),
        ('files', '0011_auto_20200323_2312'),
    ]

    operations = [
        migrations.AddField(
            model_name='filechange',
            name='author',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='developers.Developer'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='filechange',
            name='date',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
