from datetime import timedelta

from django.db.models import Avg, Sum, Count, F, Max, Min, Value
from django.db.models.functions import Trunc

from analytics.hotspots import get_hotspots
from codice import settings
from files.models import FileChange, File
from repos.models import Repository, Branch
import math

# based on https://medium.com/the-andela-way/what-technical-debt-is-and-how-its-measured-ff41603005e3
def calc_tech_debt_ratio(repo: Repository, branch: Branch):
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

    hot_spots = get_hotspots(repo, branch).aggregate(loc=Sum('lines'))
    if 'loc' in hot_spots and hot_spots['loc']:
        hot_spot_cost = hot_spots['loc'] * cpl
    else:
        hot_spot_cost = 0

    cf = fq['cf'] or 0
    ic = fq['ic'] or 0

    k1 = math.log10(cf) if cf > 0 else 1
    k2 = math.log10(ic) if ic > 0 else 1
    if k1 > k2:
        k_ic = math.pow(10.0, k1 - k2)
    else:
        k_ic = math.pow(10.0, k2 - k1)
    k_ic = k1 / k2 if k2 > 0 else (k2 / k1 if k1 > 0 else 1) 
    print("cf = {} k1 = {}  ic = {} k2 = {}, k_ic = {}".format(cf, k1, ic, k2, k_ic))

    k = settings.TECH_DEBT_FACTOR_ADJUST
    complexity = (ic * k_ic + cf) * k * cpf

    remediation_cost = complexity + hot_spot_cost
    tech_debt_ratio = (remediation_cost / development_cost) * 100.0 if development_cost > 0.0 else 0.0
    print(
        "hours={}, days={}, hours_per_day={}, development_cost={}, remediation_cost={}, cpl={}, files={}, complexity={}, loc={}, cf = {}, ic = {}, k = {}, hot_spot_cost = {}".format(
            hours, days, hours_per_day, development_cost, remediation_cost, cpl, files, complexity, loc,  cf,
            ic, k, hot_spot_cost))
    return development_cost, remediation_cost, tech_debt_ratio, cpl
