from math import log10

import numpy
from django.db.models import Sum
from commits.models import Commit
from developers.models import Blame, Developer
from repos.models import Repository, Branch


def calc_total_ins_and_dels(repository, branch):
    """return the total blame for a repository"""
    commits = Commit.objects.filter(repository=repository, branch=branch)\
        .aggregate(insertions=Sum('insertions'), deletions=Sum('deletions'))
    return commits['insertions'], commits['deletions']


# see https://git-scm.com/docs/git-diff
# see https://github.com/rbanks54/GitStats/blob/master/GitStats.Console/ImpactAnalyser.cs
def update_blame_object(blame: dict, dev: Developer, repo: Repository, branch: Branch, commits,
                        total_blame, total_insertions, total_deletions, for_bulk=False):
    """update a blame object, useful for statistics or when an alias is updated"""
    commits_by_dev = [c for c in commits if c.author.id == dev.id and not c.is_merge]
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
    for com in commits_by_dev:
        commits += 1
        n += 1
        files_changed = 0
        files_added = 0
        files_removed = 0
        edited = 0
        added = 0
        removed = 0
        for fc in com.filechange_set.all():
            if fc.change_type == 'A':
                added += fc.insertions
                files_added += 1
            elif fc.change_type == 'M' or fc.change_type == 'C':
                edited += fc.insertions + fc.deletions
                files_changed += 1
            elif fc.change_type == 'D':
                removed += fc.deletions
                files_removed += 1
            changes += 1

        total_edited += edited
        total_added += added
        total_removed += removed
        interesting_lines = edited + added

        total_files_changed += files_changed
        total_files_removed += files_removed
        total_files_added += files_added
        total_interesting_lines += interesting_lines
        lines = lines + com.lines
        insertions = insertions + com.insertions
        deletions = deletions + com.deletions
        net = net + com.net

        add_self += com.add_self
        add_others += com.add_others
        del_self += com.del_self
        del_others += com.del_others

    total_lines = total_insertions + total_deletions
    old_code_weighting = total_edited / total_lines if total_lines else 0.0
    base_score = 10.0 * total_files_changed + 3.0 * total_files_added + total_files_removed + total_interesting_lines
    impact = base_score + base_score * old_code_weighting

    blame["impact"] = impact
    blame["log_impact"] = log10(impact) if impact > 0.0  else 0.0
    blame["ownership"] = blame["loc"] / total_blame if total_blame > 0.0 else 0.0
    blame["lines"] = lines
    blame["insertions"] = insertions
    blame["deletions"] = deletions
    blame["add_self"] = add_self
    blame["add_others"] = add_others
    blame["del_self"] = del_self
    blame["del_others"] = del_others
    blame["net"] = net
    dws = add_self+add_others+del_self+del_others
    blame["work_self"] = (add_self+del_self) / dws if dws > 0.0 else 1.0
    blame["work_others"] = 1.0 - blame["work_self"]
    dst = (add_self+add_others+del_others)
    nst = (add_self+add_others+del_others+del_self)
    blame["raw_throughput"] = dst / nst if nst > 0 else 1.0

    if blame['loc'] < blame['net'] and blame['net'] > 0:
        blame['raw_churn'] = (blame['net'] - blame['loc']) / blame['net']
    else:
        blame["raw_churn"] = del_self / nst if nst > 0 else 0.0
    blame["self_churn"] = del_self / add_self if add_self > 0 and del_self <= add_self else 0.0
    blame["self_throughput"] = 1.0 - blame["raw_churn"]

    blame["net_avg"] = int(net / n) if n > 0 else 0

    blame["churn"] = (blame["self_churn"]+numpy.ma.sqrt(blame["self_churn"]*blame["raw_churn"])+blame["raw_churn"])/3.0
    blame["throughput"] = (blame["self_throughput"]
                           + numpy.ma.sqrt(blame["self_throughput"]*blame["raw_throughput"])
                           + blame["raw_throughput"])/3.0
    blame["commits"] = commits
    blame["changes"] = changes
    if for_bulk:
        blame = Blame(author=dev, repository=repo, branch=branch, **blame)
    else:
        blame, created = Blame.objects.update_or_create(defaults=blame, author=dev, repository=repo, branch=branch)
    return blame
