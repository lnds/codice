# Generated by Django 3.0.12 on 2021-02-18 20:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commits', '0007_delete_commitstatistic'),
    ]

    operations = [
        migrations.AddField(
            model_name='commit',
            name='add_others',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='commit',
            name='add_self',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='commit',
            name='del_others',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='commit',
            name='del_self',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='commit',
            name='loc',
            field=models.IntegerField(default=0),
        ),
        migrations.DeleteModel(
            name='CommitBlame',
        ),
    ]
