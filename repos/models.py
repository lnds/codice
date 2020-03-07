from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext as _

from codice import settings


class Repository(models.Model):

    git_url_validator = RegexValidator(r'((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?',
                                       _("Invalid git url"))

    class Status(models.IntegerChoices):
        CREATED = 0
        ERROR = 1
        CLONING = 2
        ANALYZING = 3
        OK = 4

    name = models.SlugField(max_length=40)
    url = models.CharField(max_length=200, validators=[git_url_validator])
    branches_to_track = models.CharField(max_length=200, blank=True)
    default_branch = models.CharField(max_length=40, blank=True)
    username = models.CharField(max_length=80, blank=True)
    password = models.CharField(max_length=200, blank=True)
    public = models.BooleanField(default=False)
    base_directory = models.CharField(max_length=300, null=True)

    status = models.IntegerField(choices=Status.choices)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_repository'
        unique_together = (('name', 'owner'), ('url', 'owner'),)

    def __str__(self):
        return self.name

    def ready(self):
        return self.status == self.Status.OK or self.status == self.Status.ERROR

    def status_icon(self):
        result = ['fas fa-spinner', 'fas fa-times', 'fas fa-clone', 'far fa-analytics', 'fas fa-check-circle']
        return result[self.status]

    def branches_count(self):
        return self.branch_set.count()

class Branch(models.Model):
    name = models.CharField(max_length=200)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_branch'
        unique_together = (('name', 'repository'),)