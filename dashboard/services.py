# based on https://medium.com/the-andela-way/what-technical-debt-is-and-how-its-measured-ff41603005e3
from django.db.models import Avg, Sum, Count, F, Max, Min
from django.db.models.functions import Trunc

from files.models import FileChange, File
from repos.models import Repository, Branch


def calc_tech_debt_ratio(repo: Repository, branch: Branch):
    commits = repo.commit_set.filter(branch=branch)
    changes = FileChange.objects.filter(commit__in=commits)

    qh = changes.annotate(day=Trunc('date', 'day')).values('day').annotate(ma=Max('date'), mi=Min('date'), age=F('ma')-F('mi'))
    days = float(qh.aggregate(days=Count('day', distinct=True))['days'] or 0.0)
    hours_per_day = float(qh.aggregate(hours=Avg('age'))['hours'].seconds or 0.0) / 3600.0 if qh else 0

    fq = File.objects.filter(filechange__in=changes)\
        .aggregate(complexity=Avg('indent_complexity'), loc=Sum('code'), files=Count('id', distinct=True))
    hours = days * hours_per_day
    loc = fq['loc'] or 0
    files = fq['files'] or 0
    cpl = hours / loc  if loc > 0 else 0.0
    cpf = hours / files if files > 0 else 0.0
    development_cost = loc * cpl
    factor = cpf * files * 0.1
    complexity = fq['complexity'] or 0
    remediation_cost = complexity * factor
    tech_debt_ratio = (remediation_cost / development_cost) * 100.0 if development_cost > 0.0 else 0.0
    print("hours={}, days={}, hours_per_day={}, development_cost={}, remediation_cost={}, cpl={}, files={}, complexity={}, loc={}, factor={}".format(
        hours, days, hours_per_day, development_cost, remediation_cost, cpl, files, complexity, loc, factor))
    return development_cost, remediation_cost, tech_debt_ratio, cpl