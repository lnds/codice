import numpy
from django.db.models import Sum, Max, Value, Avg, F, Count, Min
from django.db.models.functions import TruncDate
from django.forms import model_to_dict

from analytics.blames import update_blame_object
from commits.models import Commit
from developers.models import Blame
from files.models import FileChange


def change_alias_of(dev, alias):
    """change the is_alias_of for a dev"""
    if alias:
        Commit.objects.filter(author=dev).update(original_author=dev, author=alias)
    else:
        Commit.objects.filter(original_author=dev).update(author=dev)

    dev.is_alias_of = alias
    dev.save()

    if alias:
        blames = alias.blame_set.all()
        for blame in blames:
            repo = blame.repository
            branch = blame.branch

            # change for original
            commits = blame.repository.commit_set.filter(branch=branch, author=dev).order_by('-date')
            total_blame, total_insertions, total_deletions = calc_total_blame(repo, branch)
            update_blame_object(model_to_dict(blame, exclude=['author','repository','branch']), blame.author,
                                repo, branch,
                                commits, total_blame, total_insertions, total_deletions)

            # change for alias
            commits = blame.repository.commit_set.filter(branch=branch, author=alias).order_by('-date')
            total_blame, total_insertions, total_deletions = calc_total_blame(repo, branch)
            update_blame_object(model_to_dict(blame, exclude=['author','repository','branch']), blame.author,
                                repo, branch,
                                commits, total_blame, total_insertions, total_deletions)

    return dev


def calc_total_blame(repository, branch):
    """return the total blame for a repository"""
    blames = Blame.objects.filter(repository=repository, branch=branch)\
        .aggregate(total=Sum('loc'))
    commits = Commit.objects.filter(repository=repository, branch=branch)\
        .aggregate(insertions=Sum('insertions'), deletions=Sum('deletions'))
    return blames['total'], commits['insertions'], commits['deletions']

def top_committers(repos, branches):
    """calculates ownership of a project based on commits"""
    stats = Blame.objects.filter(repository__in=repos, branch__in=branches,
                                 author__enabled=True, author__is_alias_of__isnull=True) \
        .values('author', 'author__email', 'author__name') \
        .annotate(loc=Sum('loc')).order_by('-loc')
    total_loc = 0
    for stat in stats:
        total_loc += stat['loc']

    committer_stats = list()
    for stat in stats:
        committer_stats.append({'author': '{} <{}>'.format(stat['author__name'], stat['author__email']),
                                'email': stat['author__email'],
                                'id': stat['author'],
                                'ownership': stat['loc']/total_loc*100.0 if total_loc > 0 else 0.0})
    return committer_stats


avg_factor = 0.5
max_factor = 0.5


def get_developers_blame_summaries(repos, branches, sort_by, search_query, enabled_only=True, limit=100):
    query = Blame.objects.filter(repository__in=repos, branch__in=branches,
                                  author__enabled=enabled_only, author__is_alias_of__isnull=True)
    if search_query:
        query = query.filter(author__name__icontains=search_query)
    result = query.values('author', 'author__email', 'author__name') \
        .annotate(lines=Sum('lines'), insertions=Sum('insertions'),
                  owns=Sum('loc'),
                  loc=Sum('loc'),
                  deletions=Sum('deletions'),
                  net=Sum('net'),
                  max_churn=Max('churn'), avg_churn=Avg('churn'),
                  churn=F('max_churn') * Value(max_factor) + F('avg_churn') * Value(avg_factor),
                  max_throughput=Max('throughput'), avg_throughput=Avg('throughput'),
                  throughput=F('max_throughput') * Value(max_factor) + F('avg_throughput') * Value(avg_factor),
                  raw_churn=Avg('raw_churn'),
                  raw_throughput=Avg('raw_throughput'),
                  factor=Sum('impact'),
                  impact=Sum('impact'),
                  log_impact=Sum('log_impact'),
                  net_avg=Avg('net_avg'),
                  ownership=Avg('ownership'),
                  work_self=Max('work_self'),
                  max_work_others=Max('work_others'), avg_work_others=Avg('work_others'),
                  work_others=F('max_work_others') * Value(max_factor) + F('avg_work_others') * Value(avg_factor),
                  max_self_churn=Max('self_churn'), avg_self_churn=Avg('self_churn'),
                  self_churn=F('max_self_churn') * Value(max_factor) + F('avg_self_churn') * Value(avg_factor),
                  changes=Sum('changes'),
                  commits=Sum('commits'))
    return result.order_by(sort_by)


def get_developer_blame_summary(dev, repos, branches, total_blame, enabled_only=True):
    qs = Blame.objects.filter(repository__in=repos, branch__in=branches, author=dev,
                              author__enabled=enabled_only, author__is_alias_of__isnull=True)\
        .values('author') \
        .annotate(max_churn=Max('churn'), avg_churn=Avg('churn'),
                  churn=F('max_churn') * Value(max_factor) + F('avg_churn') * Value(avg_factor),
                  lines=Sum('lines'), insertions=Sum('insertions'), deletions=Sum('deletions'), net=Sum('net'),
                  max_throughput=Max('throughput'), avg_throughput=Avg('throughput'),
                  raw_throughput=Avg('raw_throughput'),
                  raw_churn=Avg('raw_churn'),
                  throughput=F('max_throughput') * Value(max_factor) + F('avg_throughput') * Value(avg_factor),
                  max_work_others=Max('work_others'), avg_work_others=Avg('work_others'),
                  max_work_self=Max('work_self'), avg_work_self=Avg('work_self'),
                  max_self_churn=Max('self_churn'), avg_self_churn=Avg('self_churn'),
                  self_churn=F('max_self_churn')*Value(max_factor)+F('avg_self_churn')*Value(avg_factor),
                  work_others=F('max_work_others') * Value(max_factor) + F('avg_work_others') * Value(avg_factor),
                  work_self=Max('work_self'), changes=Sum('changes'), commits=Sum('commits'), impact=Sum('impact'),
                  log_impact=Sum('log_impact'),
                  blame=Sum('loc')).order_by('churn')
    result = qs.last()

    if result:
        if 'blame' in result:
            blame = int(result['blame'])
        else:
            blame = 0
        commits = dev.commit_set.filter(is_merge=False, repository__in=repos)
        result['dev'] = dev
        result['last_commit'] = commits.order_by('date').last()
        result['commits_count'] = commits.count()
        commits = commits.annotate(only_date=TruncDate('date'))
        r = commits.filter(repository__in=repos).aggregate(days=Count('only_date', distinct=True),
                                                           since=Min('only_date'))
        result['days'] = r['days']
        result['since'] = r['since']
        result['ownership'] = blame / total_blame if blame and total_blame else 0.0
    return result


def get_developer_commits(dev, repos, branches):
    commits = Commit.objects.filter(repository__in=repos, author=dev, branch__in=branches)
    return commits


def get_developer_total_changes(dev, repos):
    commits = get_developer_commits(dev, repos)
    return FileChange.objects.filter(commit__repository__in=commits).aggregate(changes=Count('id'))['changes']
