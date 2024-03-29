# Generated by Django 3.0.4 on 2020-03-14 20:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('repos', '0004_auto_20200308_2345'),
        ('commits', '0002_auto_20200308_1830'),
    ]

    operations = [
        migrations.CreateModel(
            name='File',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.TextField()),
                ('name', models.TextField(blank=True, null=True)),
                ('language', models.CharField(max_length=40, null=True)),
                ('indent_complexity', models.FloatField(default=0)),
                ('is_code', models.BooleanField(default=False)),
                ('code', models.IntegerField(default=0)),
                ('doc', models.IntegerField(default=0)),
                ('blanks', models.IntegerField(default=0)),
                ('strings', models.IntegerField(default=0)),
                ('binary', models.BooleanField(default=False)),
                ('empty', models.BooleanField(default=False)),
                ('exists', models.BooleanField(default=True)),
                ('lines', models.IntegerField(default=0)),
                ('coupled_files', models.IntegerField(default=0)),
                ('soc', models.IntegerField(default=0)),
                ('changes', models.IntegerField(default=0)),
                ('hotspot_weight', models.FloatField(default=0.0)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Branch')),
            ],
        ),
        migrations.CreateModel(
            name='FilePath',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(blank=True, null=True)),
                ('path', models.TextField(blank=True)),
                ('exists', models.BooleanField(default=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Branch')),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='files.FilePath')),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Repository')),
            ],
            options={
                'db_table': 'codice_filepath',
            },
        ),
        migrations.CreateModel(
            name='FileChange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('insertions', models.IntegerField()),
                ('deletions', models.IntegerField()),
                ('change_type', models.TextField(blank=True, max_length=1)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Branch')),
                ('commit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='commits.Commit')),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='files.File')),
                ('repository', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Repository')),
            ],
            options={
                'db_table': 'codice_filechange',
            },
        ),
        migrations.AddField(
            model_name='file',
            name='path',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='files.FilePath'),
        ),
        migrations.AddField(
            model_name='file',
            name='repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='repos.Repository'),
        ),
        migrations.AddIndex(
            model_name='filepath',
            index=models.Index(fields=['parent', 'exists'], name='codice_file_parent__04396c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='filepath',
            unique_together={('path', 'repository', 'branch')},
        ),
        migrations.AlterUniqueTogether(
            name='filechange',
            unique_together={('file', 'commit')},
        ),
    ]
