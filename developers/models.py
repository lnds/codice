from django.db import models

from codice import settings
from repos.models import Repository, Branch


class Developer(models.Model):
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    repos = models.ManyToManyField(Repository)
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=80, default="committer", blank=True)
    is_alias_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_developer'
        unique_together = (('email', 'owner'),)

    def __str__(self):
        return "{} <{}>".format(self.name, self.email)

    def get_principal(self):
        if self.is_alias_of is not None:
            return self.is_alias_of.get_principal()
        return self


class Blame(models.Model):
    lines = models.IntegerField(default=0)
    insertions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    net = models.IntegerField(default=0)
    net_avg = models.IntegerField(default=0)
    loc = models.IntegerField(default=0)
    commits = models.IntegerField(default=0)
    changes = models.IntegerField(default=0)
    impact = models.FloatField(default=0.0)
    log_impact = models.FloatField(default=0.0)
    ownership = models.FloatField(default=0.0)
    add_self = models.IntegerField(default=0)
    del_self = models.IntegerField(default=0)
    add_others = models.IntegerField(default=0)
    del_others = models.IntegerField(default=0)
    raw_churn = models.FloatField(default=0.0)
    self_churn = models.FloatField(default=0.0)
    churn = models.FloatField(default=0.0)
    raw_throughput = models.FloatField(default=0.0)
    self_throughput = models.FloatField(default=0.0)
    throughput = models.FloatField(default=0.0)
    work_self = models.FloatField(default=0.0)
    work_others = models.FloatField(default=0.0)
    author = models.ForeignKey(Developer, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_blame'
        unique_together = (('author', 'repository', 'branch'),)