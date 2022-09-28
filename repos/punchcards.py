"""functions for punchcard generation"""
from django.db.models import Count
from django.db.models.functions import ExtractWeekDay, ExtractHour

from commits.models import Commit

days = ['X', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', ]


def get_repos_week_punchcard(repos, branches):
    stats = Commit.objects.filter(repository__in=repos, branch__in=branches)\
        .annotate(wd=ExtractWeekDay('date'), h=ExtractHour('date'))\
        .values('wd', 'h').annotate(total=Count('id', distinct=True)).order_by('wd')
    result = dict()
    for s in stats:
        wd = int(s['wd'])
        day = days[wd]
        hwd = dict()
        for (h, t) in [(x['h'], x['total']) for x in stats if x['wd'] == wd]:
            if h in hwd:
                hwd[h] = hwd[h] + t
            else:
                hwd[h] = t

        result[day] = list()
        for h in range(24):
            if h in hwd:
                result[day].append(hwd[h])
            else:
                result[day].append(0)
    return result


def get_repos_hour_punchcard(repos):
    stats = Commit.objects.filter(repository__in=repos)\
        .annotate(wd=ExtractWeekDay('date'), h=ExtractHour('date'))\
        .values('wd', 'h').annotate(total=Count('id', distinct=True)).order_by('wd')
    result = dict()
    for s in stats:
        h = int(s['h'])
        hhd = dict()
        for (wd, t) in [(x['wd'], x['total']) for x in stats if x['h'] == h]:
            day = days[wd]
            if wd in hhd:
                hhd[day] = hhd[day] + t
            else:
                hhd[day] = t

        result[h] = list()
        for d in days:
            if d in hhd:
                result[h].append(hhd[d])
            else:
                result[h].append(0)
    return result


def get_dev_punchcard(dev, repos, branches):
    stats = Commit.objects.filter(repository__in=repos, branch__in=branches, author=dev)\
        .annotate(wd=ExtractWeekDay('date'), h=ExtractHour('date'))\
        .values('wd', 'h').annotate(total=Count('id', distinct=True), ).order_by('wd')
    result = dict()
    for s in stats:
        wd = int(s['wd'])
        day = days[wd]
        hwd = dict()
        for (h, t) in [(x['h'], x['total']) for x in stats if x['wd'] == wd]:
            if h in hwd:
                hwd[h] = hwd[h] + t
            else:
                hwd[h] = t

        result[day] = list()
        for h in range(24):
            if h in hwd:
                result[day].append(hwd[h])
            else:
                result[day].append(0)
    return result