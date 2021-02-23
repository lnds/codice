from datetime import timedelta, datetime

from django.db.models import Count, Max, F, Value

from codice import settings
from files.models import File
from repos.models import Branch, Repository

hotspot_threshold = settings.CODICE_HOT_SPOTS_THRESHOLD
hotspot_time_range = settings.CODICE_HOT_SPOTS_TIME_RANGE
hotspot_time_limit = datetime.now() - timedelta(days=hotspot_time_range)


def file_filter(repo: Repository, branch: Branch):
    return File.objects.filter(repository=repo, branch=branch, is_code=True, last_update__gte=hotspot_time_limit)


def max_changes(repo: Repository, branch: Branch):
    qs = file_filter(repo, branch).values('id').aggregate(max_change=Max('changes'))
    return (qs['max_change'] or 0.0) + 1.0


def get_hotspots(repo: Repository, branch: Branch):
    mc = max_changes(repo, branch)
    return file_filter(repo,branch).values('id', 'filename').annotate(percent=(F('changes')*Value(100.0))/Value(mc))\
        .filter(percent__gte=hotspot_threshold).order_by('-changes')


def count_hotspots(repo: Repository, branch: Branch):
    return get_hotspots(repo, branch).count()
