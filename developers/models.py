from django.db import models

from codice import settings
from repos.models import Repository


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