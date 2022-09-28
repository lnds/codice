from django.conf import settings
from django.db.models import Count, Max, F, Value
from files.models import File
from repos.services import get_default_branches_for_repos

hotspot_threshold = settings.CODICE_HOT_SPOTS_THRESHOLD

def max_changes(repos, branches):
    qs = File.objects.filter(repository__in=repos, branch__in=branches, is_code=True).values('id')\
        .annotate(changes=Count('filechange__id', distinct=True))\
        .aggregate(max_change=Max('changes'))
    return (qs['max_change'] or 0.0) + 1.0

def get_hotspots(repos):
    branches = get_default_branches_for_repos(repos)
    mc = max_changes(repos, branches)
    return File.objects.filter(repository__in=repos, branch__in=branches, is_code=True).values('id', 'filename') \
        .annotate(changes=Count('filechange__id', distinct=True),
                  percent=(F('changes')*Value(100.0))/Value(mc)).filter(percent__gt=hotspot_threshold).order_by('-changes')
