# based on https://medium.com/the-andela-way/what-technical-debt-is-and-how-its-measured-ff41603005e3
from django.db.models import Avg, Sum, Count, F, Max, Min
from django.db.models.functions import Trunc

from files.models import FileChange, File
from repos.models import Repository, Branch

def calc_tech_debt_ratio(repo: Repository, branch: Branch):
    commits = repo.commit_set.filter(branch=branch)
    changes = FileChange.objects.filter(commit__in=commits)

    hours = changes.annotate(day=Trunc('date', 'day')).values('day').annotate(ma=Max('date'), mi=Min('date'), age=F('ma')-F('mi'))
    days = float(hours.aggregate(days=Count('day', distinct=True))['days'] or 0.0)
    hours_per_day = float(hours.aggregate(hours=Avg('age'))['hours'].seconds) / 3600.0
    files = File.objects.filter(filechange__in=changes)\
        .aggregate(complexity=Sum('indent_complexity'), loc=Sum('code'), files=Count('id', distinct=True))
    hours = days * hours_per_day
    development_cost = hours
    remediation_cost = files['complexity'] / files['files'] if files['files'] > 0 else 0.0
    cpl = files['loc'] / hours if hours > 0.0 else 0.0
    tech_debt_ratio = (remediation_cost / development_cost) * 100.0 if development_cost > 0.0 else 0.0
    return development_cost, remediation_cost, tech_debt_ratio, cpl