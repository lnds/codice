import numpy
from django.db.models import Sum, Count
from commits.models import Commit, CommitStatistic
from developers.models import Blame, Developer
from repos.models import Repository, Branch


def calc_total_ins_and_dels(repository, branch):
    """return the total blame for a repository"""
    commits = Commit.objects.filter(repository=repository, branch=branch)\
        .aggregate(insertions=Sum('insertions'), deletions=Sum('deletions'))
    return commits['insertions'], commits['deletions']


# see https://git-scm.com/docs/git-diff
# see https://github.com/rbanks54/GitStats/blob/master/GitStats.Console/ImpactAnalyser.cs
def update_blame_object(blame: dict, dev:Developer, repo:Repository, branch:Branch, commits,
                        total_blame, total_insertions, total_deletions):
    """update a blame object, useful for statistics or when an alias is updated"""
    commits_by_dev = [c for c in commits if c.author.id == dev.id]
    commits_by_dev.sort(key=lambda x: x.date, reverse=False)
    lines = 0
    insertions = 0
    deletions = 0
    net = 0
    commits = 0
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
    for com in commits_by_dev:
        commits += 1
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
        commit_total_blame = com.fileblame_set.aggregate(total=Sum('loc'))['total'] or 0
        nc = com.filechange_set.count()
        bloc = com.fileblame_set.filter(author=com.author).aggregate(loc=Count('loc'))['loc'] or 0
        delta_loc = 0
        delta_ins = 0
        if com.insertions > bloc:
            delta_ins = com.insertions - bloc

        deno = com.insertions + bloc
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

    blame["impact"] = impact
    blame["log_impact"] = numpy.ma.sqrt(impact)
    blame["ownership"]= blame["loc"] / total_blame if total_blame > 0.0 else 0.0
    blame["lines"] = lines
    blame["insertions"] = insertions
    blame["deletions"] = deletions
    blame["add_self"] = add_self
    blame["add_others"] = add_others
    blame["del_self"] = del_self
    blame["del_others"] = del_others
    blame["net"]= net
    dws = add_self+add_others+del_self+del_others
    blame["work_self"] = (add_self+del_self) / dws if dws > 0.0 else 1.0
    blame["work_others"] = 1.0 - blame["work_self"]
    dst = (add_self+add_others+del_others)
    nst = (add_self+add_others+del_others+del_self)
    blame["self_throughput"] = dst / nst if nst > 0 else 1.0
    blame["self_churn"] = del_self / nst if nst > 0 else 0.0

    blame["net_avg"] = int(net / n) if n > 0 else 0

    blame["raw_throughput"] = (insertions+deletions) / total_lines if total_lines > 0 else 0.0
    blame["raw_churn"] = deletions / total_lines if total_lines > 0 else 0.0

    blame["churn"] = (blame["self_churn"]+numpy.ma.sqrt(blame["self_churn"]*blame["raw_churn"])+blame["raw_churn"])/3.0
    blame["throughput"] = (blame["self_throughput"]
                           +numpy.ma.sqrt(blame["self_throughput"]*blame["raw_throughput"])
                           + blame["raw_throughput"])/3.0
    blame["commits"] = commits
    blame["changes"] = changes
    blame, created = Blame.objects.update_or_create(defaults=blame, author=dev, repository=repo, branch=branch)
    return blame
