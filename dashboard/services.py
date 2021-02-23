from datetime import timedelta

from django.db.models import Avg, Sum, Count, F, Max, Min, Value
from django.db.models.functions import Trunc

from codice import settings
from files.models import FileChange, File
from repos.models import Repository, Branch


# based on https://medium.com/the-andela-way/what-technical-debt-is-and-how-its-measured-ff41603005e3
def calc_tech_debt_ratio(repo: Repository, branch: Branch, hot_spots: int):
    commits = repo.commit_set.filter(branch=branch)
    changes = FileChange.objects.filter(commit__in=commits)

    qh = commits.annotate(dev=F('author'), day=Trunc('date', 'day')) \
        .values('day', 'dev').annotate(ma=Max('date'), mi=Min('date'), age=F('ma') - F('mi'))
    qh = qh.aggregate(days=Count('day', distinct=True), hours=Sum('age'))
    days = float(qh['days'] or 0.0) if qh else 0
    if 'hours' in qh and qh['hours']:
        period = qh['hours']
        hours = float(period.days * 24.0 + period.seconds / 3600.0)
    else:
        hours = 0
    fq = File.objects.filter(filechange__in=changes) \
        .aggregate(ic=Avg('indent_complexity'), cf=Avg('coupled_files'), loc=Sum('lines'),
                   files=Count('id', distinct=True))
    hours_per_day = hours / days if days > 0 else 0
    loc = fq['loc'] or 0
    files = fq['files'] or 0
    cpl = hours / loc if loc > 0 else 0.0
    cpf = hours / files if files > 0 else 0.0
    development_cost = loc * cpl
    k = hot_spots / files if files > 0 else 0
    factor = cpf * k
    cf = fq['cf'] or 0
    ic = fq['ic'] or 0
    k_ic = cf / ic if ic > 0 else 0
    complexity = ic * k_ic + cf  # linear composition
    remediation_cost = complexity * factor
    tech_debt_ratio = (remediation_cost / development_cost) * 100.0 if development_cost > 0.0 else 0.0
    print(
        "hours={}, days={}, hours_per_day={}, development_cost={}, remediation_cost={}, cpl={}, files={}, complexity={}, loc={}, factor={}, cf = {}, ic = {}".format(
            hours, days, hours_per_day, development_cost, remediation_cost, cpl, files, complexity, loc, factor, cf,
            ic))
    return development_cost, remediation_cost, tech_debt_ratio, cpl
