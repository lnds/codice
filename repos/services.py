from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Sum, ExpressionWrapper, F, fields, Min, Max, Value
from django.utils.translation import gettext as _

from commits.models import Commit
from files.models import File
from repos.models import Repository


def check_repo_limit_reached(request):
    user = request.user
    if Repository.objects.filter(owner=user.customer).count() >= user.customer.repo_limit:
        messages.error(
            request, _('You have reached the limit of repos defined for you account. (Your current limit is: {})')
                       .format(user.customer.repo_limit))


def get_lang_participation_for_repo(repo, branch):
    return File.objects.filter(repository=repo, branch=branch, exists=True).values('language')\
        .annotate(files=Count('id', distinct=True),
                  code=Sum('code'),
                  comment=Sum('doc'),
                  blank=Sum('blanks')).filter(code__gt=0).order_by('-files')


def get_developers_contribution(repo, branch):
    duration = ExpressionWrapper(F('max_date') - F('min_date'), output_field=fields.DurationField())
    return Commit.objects.filter(repository=repo, branch=branch, author__blame__isnull=False,
                                 author__is_alias_of__isnull=True, author__enabled=True)\
        .values('author', 'author__name', 'author__email')\
        .annotate(added=Sum('insertions'),
                  deleted=Sum('deletions'),
                  net=Sum('net'),
                  commits=Count('id', distinct=True),
                  min_date=Min('date'),
                  max_date=Max('date'),
                  duration=duration).order_by('-commits')


def get_default_branches_for_repos(repos):
    result = []
    for repo in repos:
        r = None
        if repo.default_branch > '':
            try:
                r = repo.branch_set.get(name=repo.default_branch)
            except:
                r = None
        if r is None:
            r = repo.branch_set.first()
        result.append(r)
    return result


hotspot_threshold = settings.CODICE_HOT_SPOTS_THRESHOLD


def max_changes(repo, branch):
    qs = File.objects.filter(repository=repo, branch=branch, is_code=True).values('id')\
        .annotate(changes=Count('filechange__id', distinct=True))\
        .aggregate(max_change=Max('changes'))
    return (qs['max_change'] or 0.0) + 1.0


def get_hotspots(repo: Repository):
    branch = repo.get_default_branch()
    mc = max_changes(repo, branch)
    return File.objects.filter(repository=repo, branch=branch, is_code=True).values('id', 'filename') \
        .annotate(changes=Count('filechange__id', distinct=True),
                  percent=(F('changes')*Value(100.0))/Value(mc)).filter(percent__gt=hotspot_threshold).order_by('-changes')


def count_hotspots(repo):
    return get_hotspots(repo).count()


def top_committers_of(repo, branch):
    """calculates ownership of a project based on commits"""
    from developers.models import Blame
    stats = Blame.objects.filter(repository=repo, branch=branch,
                                 author__enabled=True, author__is_alias_of__isnull=True) \
        .values('author', 'author__email', 'author__name') \
        .annotate(loc=Sum('loc')).order_by('-loc')
    total_loc = 0
    for stat in stats:
        total_loc += stat['loc']

    committer_stats = list()
    for stat in stats:
        committer_stats.append({'author': '{} <{}>'.format(stat['author__name'], stat['author__email']),
                                'id': stat['author'],
                                'ownership': stat['loc'] / total_loc * 100.0 if total_loc > 0 else 0.0})
    return committer_stats


def get_bus_factor_of(repo):
    branch = repo.get_default_branch()
    committers = top_committers_of(repo, branch)
    acum = 0
    bus_factor = 0
    for c in committers:
        if acum <= 50:
            acum += c['ownership']
            bus_factor += 1
    return bus_factor