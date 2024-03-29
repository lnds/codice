from django.db import models
from django.db.models import Count, F
from django.utils.functional import cached_property

from commits.models import Commit
from developers.models import Developer
from repos.models import Repository, Branch


class FilePath(models.Model):
    name = models.TextField(blank=True, null=True)
    path = models.TextField(blank=True)
    exists = models.BooleanField(default=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name='children')

    class Meta:
        db_table = 'codice_filepath'
        unique_together = (('path', 'repository', 'branch'),)
        indexes = [
            models.Index(fields=['parent', 'exists']),
        ]

    def __str__(self):
        return "{}".format(self.path)


class File(models.Model):
    filename = models.TextField()
    name = models.TextField(null=True, blank=True)
    language = models.CharField(max_length=40, null=True)
    indent_complexity = models.FloatField(default=0)
    is_code = models.BooleanField(default=False)
    code = models.IntegerField(default=0)
    doc = models.IntegerField(default=0)
    blanks = models.IntegerField(default=0)
    strings = models.IntegerField(default=0)
    binary = models.BooleanField(default=False)
    empty = models.BooleanField(default=False)
    exists = models.BooleanField(default=True)
    lines = models.IntegerField(default=0)
    coupled_files = models.IntegerField(default=0)
    soc = models.IntegerField(default=0)
    changes = models.IntegerField(default=0)
    hotspot_weight = models.FloatField(default=0.0)

    path = models.ForeignKey(FilePath, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_file'

    @cached_property
    def commits(self):
        return Commit.objects.filter(filechange__file=self).all()

    @property
    def get_authors(self):
        return self.commits.values(
            'author',
            'author__email',
            'author__name'
        ).annotate(
            count=Count('id', distinct=True)
        ).order_by(
            '-count'
        )

    @property
    def get_creator(self):
        fc = self.filechange_set.order_by('commit__date').first()
        return fc.commit.author

    def get_commits_by(self, author_id):
        commits = Commit.objects.filter(filechange__in=self.filechange_set.all(), author_id=author_id) \
            .order_by('-date').all()
        return commits

    def calc_temporal_coupling(self, commits):
        return self.get_coupled_files(commits).count()

    def get_coupled_files(self, commits):
        return File.objects.filter(
            filechange__commit__in=commits
        ).exclude(
            pk=self.pk
        ).annotate(
            num_commits=Count(F('filechange__commit') / len(commits)),
        ).order_by(
            '-num_commits'
        )

    # sum of temporal coupling, as defined by Tornhill, chapter 8, page 78
    def calc_soc(self, commits):
        return File.objects.filter(filechange__commit__in=commits).exclude(pk=self.pk).count()

    def get_last_change(self):
        return self.filechange_set.last()

    def get_css(self):
        if not self.exists:
            return "fa fa-ban text-danger"

        if self.empty:
            return "fa fa-ban text-danger"

        if self.binary:
            return "fa fa-file-image-o text-warning"

        return "fa fa-file text-success"

    def get_indent_complexity_css(self):
        if self.indent_complexity <= 3.0:
            return 'text-success'
        elif self.indent_complexity <= 10.0:
            return 'text-warning'
        return 'text-danger'

    def __str__(self):
        return "{}-{}".format(self.id, self.filename)


class FileChange(models.Model):
    insertions = models.IntegerField()
    deletions = models.IntegerField()
    change_type = models.TextField(max_length=1, blank=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)

    def __str__(self):
        return "'{}' {} {} => {} {}".format(self.change_type, self.file.filename, self.file.id,
                                            self.insertions, self.deletions)

    class Meta:
        db_table = 'codice_filechange'
        unique_together = (('file', 'commit'),)


class FileBlame(models.Model):
    loc = models.IntegerField()
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_fileblame'
        unique_together = (('file', 'commit'),)


class FileKnowledge(models.Model):

    class Meta:
        db_table = 'codice_fileknowledge'

    added = models.IntegerField()
    deleted = models.IntegerField()
    knowledge = models.FloatField()
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)
