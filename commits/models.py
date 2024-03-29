from django.db import models

from developers.models import Developer
from repos.models import Branch, Repository


class Commit(models.Model):
    hexsha = models.CharField(max_length=40)
    date = models.DateTimeField()
    message = models.TextField(null=True, blank=True)
    lines = models.IntegerField()
    insertions = models.IntegerField()
    deletions = models.IntegerField()
    net = models.IntegerField()
    is_merge = models.BooleanField(default=False)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    original_author = models.ForeignKey(Developer, related_name='original_author',
                                        related_query_name='original_authors',
                                        on_delete=models.SET_NULL,
                                        default=None,
                                        null=True)

    class Meta:
        db_table = 'codice_commit'

    def __str__(self):
        return "{} @ {}: {}".format(self.hexsha[-6:], self.date,  self.message[:20])


class CommitStatistic(models.Model):
    date = models.DateTimeField()
    commit = models.OneToOneField(Commit, on_delete=models.CASCADE, primary_key=True)
    blame_loc = models.IntegerField()
    impact = models.FloatField(default=0.0)
    log_impact = models.FloatField(default=0.0)
    raw_churn = models.FloatField(default=0.0)
    self_churn = models.FloatField(default=0.0)
    churn = models.FloatField(default=0.0)
    raw_throughput = models.FloatField(default=0.0)
    self_throughput = models.FloatField(default=0.0)
    throughput = models.FloatField(default=0.0)
    ownership = models.FloatField(default=0.0)
    acum_lines = models.IntegerField()
    acum_insertions = models.IntegerField()
    acum_deletions = models.IntegerField()
    net_result = models.IntegerField()
    changes = models.IntegerField()
    add_self = models.IntegerField(default=0)
    del_self = models.IntegerField(default=0)
    add_others = models.IntegerField(default=0)
    del_others = models.IntegerField(default=0)
    work_self = models.FloatField(default=0.0)
    work_others = models.FloatField(default=0.0)

    class Meta:
        db_table = 'codice_commitstatistic'

    def author(self):
        return self.commit.author


class CommitBlame(models.Model):
    loc = models.IntegerField()
    add_self = models.IntegerField(default=0)
    add_others = models.IntegerField(default=0)
    del_self = models.IntegerField(default=0)
    del_others = models.IntegerField(default=0)
    date = models.DateTimeField()
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)
    commit = models.ForeignKey(Commit, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_commitblame'
