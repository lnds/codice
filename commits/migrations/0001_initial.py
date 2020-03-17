# Generated by Django 3.0.4 on 2020-03-08 18:30

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Commit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hexsha', models.CharField(max_length=40)),
                ('date', models.DateTimeField()),
                ('message', models.TextField(blank=True, null=True)),
                ('lines', models.IntegerField()),
                ('insertions', models.IntegerField()),
                ('deletions', models.IntegerField()),
                ('net', models.IntegerField()),
                ('is_merge', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'codice_commit',
            },
        ),
    ]