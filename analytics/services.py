from django.db.models import Sum, Count
from developers.models import Blame
from files.models import File


def top_committers_of(repo, branch):
    """calculates ownership of a project based on commits"""
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


def get_lang_participation_for_repo(repo, branch):
    return File.objects.filter(repository=repo, branch=branch, exists=True).values('language')\
        .annotate(files=Count('id', distinct=True),
                  code=Sum('code'),
                  comment=Sum('doc'),
                  blank=Sum('blanks')).filter(code__gt=0).order_by('-files')