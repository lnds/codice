# Generated by Django 3.0.4 on 2020-03-14 21:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('developers', '0001_initial'),
        ('commits', '0002_auto_20200308_1830'),
        ('files', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileBlame',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('loc', models.IntegerField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='developers.Developer')),
                ('commit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='commits.Commit')),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='files.File')),
            ],
        ),
    ]
