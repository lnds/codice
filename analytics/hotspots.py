from django.db.models import Count, Max, F, Value

from codice import settings
from files.models import File
from repos.models import Branch, Repository

hotspot_threshold = settings.CODICE_HOT_SPOTS_THRESHOLD


def max_changes(repo: Repository, branch: Branch):
    qs = File.objects.filter(repository=repo, branch=branch, is_code=True).values('id')\
        .aggregate(max_change=Max('changes'))
    return (qs['max_change'] or 0.0) + 1.0


def get_hotspots(repo: Repository, branch: Branch):
    mc = max_changes(repo, branch)
    return File.objects.filter(repository=repo, branch=branch, is_code=True).values('id', 'filename') \
        .annotate(percent=(F('changes')*Value(100.0))/Value(mc))\
        .filter(percent__gt=hotspot_threshold).order_by('-changes')


def count_hotspots(repo: Repository, branch: Branch):
    return get_hotspots(repo, branch).count()
