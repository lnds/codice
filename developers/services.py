import numpy
from django.db.models import Sum, Max, Value, Avg, F, Count, Min
from django.db.models.functions import TruncDate

from commits.models import CommitBlame, Commit, CommitStatistic
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
            update_blame_object(blame, commits, total_blame, total_insertions, total_deletions)

            # change for alias
            commits = blame.repository.commit_set.filter(branch=branch, author=alias).order_by('-date')
            total_blame, total_insertions, total_deletions = calc_total_blame(repo, branch)
            update_blame_object(blame, commits, total_blame, total_insertions, total_deletions)

    return dev


def calc_total_blame(repository, branch):
    """return the total blame for a repository"""
    blames = Blame.objects.filter(repository=repository, branch=branch)\
        .aggregate(total=Sum('loc'))
    commits = Commit.objects.filter(repository=repository, branch=branch)\
        .aggregate(insertions=Sum('insertions'), deletions=Sum('deletions'))
    return blames['total'], commits['insertions'], commits['deletions']


# see https://git-scm.com/docs/git-diff
# see https://github.com/rbanks54/GitStats/blob/master/GitStats.Console/ImpactAnalyser.cs
def update_blame_object(blame, commits, total_blame, total_insertions, total_deletions):
    """update a blame object, useful for statistics or when an alias is updated"""
    lines = 0
    insertions = 0
    deletions = 0
    net = 0
    num_commits = 0
    changes = 0
    add_self = 0
    add_others = 0
    del_self = 0
    del_others = 0
    total_files_changed = 0
    total_files_added = 0
    total_files_removed = 0
    total_interesting_lines = 0
    total_added = 0
    total_removed = 0
    total_edited = 0
    n = 0
    raw_factor = 0.4
    self_factor = 0.6
    for com in commits:
        num_commits += 1
        if com.is_merge:
            continue
        n += 1
        files_changed = 0
        files_added = 0
        files_removed = 0
        edited = 0
        added = 0
        removed = 0
        for fc in com.filechange_set.all():
            if fc.change_type == 'A' or fc.change_type == 'C':
                added = fc.insertions
                files_added += 1
            elif fc.change_type == 'M':
                edited += fc.insertions + fc.deletions
                files_changed += 1
            elif fc.change_type == 'D':
                removed = fc.deletions
                files_removed += 1
            else:
                removed = fc.deletions
                added = fc.insertions
            changes += 1

        total_edited += edited
        total_added += added
        total_removed += removed
        total_lines = edited + added + removed
        interesting_lines = edited + added
        old_code_weighting = edited / total_lines if total_lines else 0.0
        base_score = 10.0 * files_changed + 3.0 * files_added + files_removed + interesting_lines
        impact = base_score + base_score * old_code_weighting

        total_files_changed += files_changed
        total_files_removed += files_removed
        total_files_added += files_added
        total_interesting_lines += interesting_lines
        lines = lines + com.lines
        insertions = insertions + com.insertions
        deletions = deletions + com.deletions
        net = net + com.net
        commit_total_blame = com.commitblame_set.aggregate(total=Sum('loc'))['total'] or 0
        nc = com.filechange_set.count()
        b = None
        pb = None
        try:
            b = com.commitblame_set.get(author=com.author)
            pb = CommitBlame.objects.filter(date__lt=b.date, author=com.author).order_by('-date').first() if b else None
        except CommitBlame.DoesNotExist:
            pass
        bloc = b.loc if b else 0
        pbloc = pb.loc if pb else 0
        delta_loc = 0
        if pbloc > bloc:
            delta_loc = pbloc - bloc
        delta_ins = 0
        if com.insertions > bloc:
            delta_ins = com.insertions - bloc

        deno = com.insertions + pbloc
        raw_churn = (delta_loc + delta_ins) / deno if deno else 0
        log_impact = numpy.ma.sqrt(impact) if impact > 0.0 else 0.0
        ownership = bloc / commit_total_blame if commit_total_blame else 0.0
        raw_throughput = abs(com.net) / com.lines if com.lines else 1.0

        rcb = com.commitblame_set.aggregate(sum_add_self=Sum('add_self'), sum_add_others=Sum('add_others'),
                                            sum_del_self=Sum('del_self'), sum_del_others=Sum('del_others'))
        sum_add_self = rcb['sum_add_self']
        sum_del_self = rcb['sum_del_self']
        sum_add_others = rcb['sum_add_others']
        sum_del_others = rcb['sum_del_others']
        add_self += sum_add_self
        add_others += sum_add_others
        del_self += sum_del_self
        del_others += sum_del_others

        dsc = sum_add_self+sum_add_others+sum_del_others+sum_del_self
        nsc = sum_add_self+sum_add_others+sum_del_others
        self_throughput = nsc / dsc if dsc else 1.0
        self_churn = sum_del_self / dsc if dsc else 0.0

        work_self = (sum_add_self+sum_del_self) / dsc if dsc > 0 else 1.0
        work_others = 1.0 - work_self
        try:
            cs = CommitStatistic.objects.get(commit=com)
            cs.raw_throughput = raw_throughput
            cs.raw_churn = raw_churn
            cs.impact = impact
            cs.log_impact = log_impact
            cs.acum_lines = lines
            cs.acum_insertions = insertions
            cs.acum_deletions = deletions
            cs.blame_loc = bloc
            cs.net_result = net
            cs.add_self = sum_add_self
            cs.del_self = sum_del_self
            cs.add_others = sum_add_others
            cs.del_others = sum_del_others
            cs.self_churn = self_churn
            cs.self_throughput = self_throughput
            cs.work_self = work_self
            cs.work_others = work_others
            cs.churn = (0.3*cs.raw_churn + 0.7*cs.self_churn)
            cs.throughput = (0.3*cs.raw_throughput + 0.7*cs.self_throughput)

        except CommitStatistic.DoesNotExist:
            CommitStatistic.objects.create(commit=com, date=com.date, ownership=ownership, changes=nc,
                                           raw_throughput=raw_throughput, raw_churn=raw_churn, impact=impact,
                                           log_impact=log_impact, acum_lines=lines, acum_insertions=insertions,
                                           acum_deletions=deletions, blame_loc=bloc, net_result=net,
                                           add_self=sum_add_self, del_self=sum_del_self, add_others=sum_add_others,
                                           del_others=sum_del_others, self_churn=self_churn,
                                           self_throughput=self_throughput,
                                           churn=(raw_factor*raw_churn + self_factor*self_churn),
                                           throughput=(raw_factor*raw_throughput+self_factor*self_throughput),
                                           work_self=work_self,
                                           work_others=work_others)

    total_lines = total_insertions + total_deletions
    old_code_weighting = total_edited / total_lines if total_lines else 0.0
    base_score = 10.0 * total_files_changed + 3.0 * total_files_added + total_files_removed + total_interesting_lines
    impact = base_score + base_score * old_code_weighting
    blame.impact = impact
    blame.log_impact = numpy.ma.sqrt(impact)
    blame.ownership = blame.loc / total_blame if total_blame > 0.0 else 0.0
    blame.lines = lines
    blame.insertions = insertions
    blame.deletions = deletions
    blame.add_self = add_self
    blame.add_others = add_others
    blame.del_self = del_self
    blame.del_others = del_others
    blame.net = net
    dws = blame.add_self+blame.add_others+blame.del_self+blame.del_others
    blame.work_self = (blame.add_self+blame.del_self) / dws if dws > 0.0 else 1.0
    blame.work_others = 1.0 - blame.work_self
    dst = (blame.add_self+blame.add_others+blame.del_others)
    nst = (blame.add_self+blame.add_others+blame.del_others+blame.del_self)
    blame.self_throughput = dst / nst if nst > 0 else 1.0
    blame.self_churn = blame.del_self / nst if nst > 0 else 0.0

    blame.net_avg = int(net / n) if n > 0 else 0

    blame.raw_throughput = (blame.insertions+blame.deletions) / total_lines if total_lines > 0 else 0.0
    blame.raw_churn = blame.deletions / total_lines if total_lines > 0 else 0.0

    blame.churn = (blame.self_churn+numpy.ma.sqrt(blame.self_churn*blame.raw_churn)+blame.raw_churn)/3.0
    blame.throughput = (blame.self_throughput+numpy.ma.sqrt(blame.self_throughput*blame.raw_throughput)
                        + blame.raw_throughput)/3.0
    blame.commits = len(commits)
    blame.changes = changes
    blame.save()


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


avg_factor = 0.3
max_factor = 0.7


def get_developers_blame_summaries(repos, branches, sort_by, search_query, enabled_only=True):
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
        commits = dev.commit_set
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
    return FileChange.objects.filter(repository__in=commits).aggregate(changes=Count('id'))['changes']
