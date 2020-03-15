from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Count, ExpressionWrapper, fields, Sum, Min, Max, F
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from codice import settings


class Repository(models.Model):

    git_url_validator = RegexValidator(r'((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?',
                                       _("Invalid git url"))

    class Status(models.IntegerChoices):
        CREATED = 0, _('CREATED')
        ERROR = 1, _('ERROR')
        CLONING = 2, _('CLONING')
        CLONED = 3, _('CLONED')
        ANALYZING = 4, _('ANALYZING')
        OK = 5, _('OK')

    name = models.SlugField(max_length=40)
    url = models.CharField(max_length=200, validators=[git_url_validator], blank=False)
    branches_to_track = models.CharField(max_length=200, blank=True)
    default_branch = models.CharField(max_length=40, blank=True, default="master")
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

    def get_absolute_url(self):
        return reverse('repository-detail', kwargs={'pk': self.pk})

    def ready(self):
        return self.status == self.Status.OK or self.status == self.Status.ERROR

    def status_icon(self):
        result = ['fas fa-spinner', 'fas fa-times', 'fas fa-clock', 'fas fa-clone', 'far fa-analytics',
                  'fas fa-check-circle']
        return result[self.status]

    def commits_count(self):
        return self.commit_set.filter(branch=self.get_default_branch()).count()

    def devs_count(self):
        result = self.commit_set.filter(branch=self.get_default_branch()) \
            .aggregate(devs=Count('author__id', distinct=True))
        return result['devs']

    def devs_count_of_branch(self, branch):
        result = self.commit_set.filter(branch=branch) \
            .aggregate(devs=Count('author__id', distinct=True))
        return result['devs']

    def branches_count(self):
        return self.branch_set.count()

    def get_default_branch(self):
        if self.status != Repository.Status.OK:
            return None
        if self.default_branch > '':
            try:
                return self.branch_set.get(name=self.default_branch)
            except Branch.DoesNotExist:
                return None
        else:
            return self.branch_set.first()

    def find_branch(self, branch_name):
        if not branch_name:
            return self.get_default_branch()
        try:
            return self.branch_set.get(name=branch_name)
        except Branch.DoesNotExist:
            return self.get_default_branch()

    def get_developers_contribution(self, branch):
        """Get developers contribution stats for this repo in given branch"""
        from commits.models import Commit
        duration = ExpressionWrapper(F('max_date') - F('min_date'), output_field=fields.DurationField())
        return Commit.objects.filter(repository=self, branch=branch,
                                     author__is_alias_of__isnull=True, author__enabled=True) \
            .values('author', 'author__name', 'author__email') \
            .annotate(added=Sum('insertions'),
                      deleted=Sum('deletions'),
                      net=Sum('net'),
                      commits=Count('id', distinct=True),
                      min_date=Min('date'),
                      max_date=Max('date'),
                      duration=duration).order_by('-commits')


class Branch(models.Model):
    name = models.CharField(max_length=200)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)

    class Meta:
        db_table = 'codice_branch'
        unique_together = (('name', 'repository'),)

