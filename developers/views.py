from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum, Avg, Count, F, Max
from django.db.models.functions import TruncDate
from django.views.generic import ListView, DetailView

from commits.models import Commit
from developers.charts import get_dev_activity_chart, get_devs_blame_data, get_devs_owner_pie_chart, \
    get_devs_churn_production_chart, get_devs_quadrant_chart
from developers.models import Developer, Blame
from developers.services import get_developers_blame_summaries, get_developer_commits, get_developer_blame_summary
from developers.templatetags.committer_stats import get_badge_data
from files.models import FileKnowledge, FileChange, File
from repos.models import get_default_branches_for_repos, Repository
from repos.punchcard import get_dev_punchcard


class DeveloperMixin(LoginRequiredMixin):
    model = Developer
    variable = 'commit'
    label = 'Commits'
    throughput_lower_threshold = 0.5
    throughput_higher_threshold = 0.5
    churn_lower_threshold = 0.5
    churn_higher_threshold = 0.5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['throughput_lower_threshold'] = self.throughput_lower_threshold
        context['throughput_higher_threshold'] = self.throughput_higher_threshold
        context['churn_lower_threshold'] = self.churn_lower_threshold
        context['churn_higher_threshold'] = self.churn_higher_threshold
        return context


class DeveloperList(DeveloperMixin, ListView):
    paginate_by = 10
    context_object_name = 'developer_list'
    template_name = 'developers/developer_list.html'

    def get_queryset(self):
        self.owner = self.request.user
        if 'repo_id' in self.kwargs:
            self.repos = Repository.objects.filter(id=self.kwargs['repo_id'])
            self.branches = get_default_branches_for_repos(self.repos)
            self.devs = Developer.objects.filter(commit__repository__in=self.repos, commit__branch__in=self.branches,
                                                 is_alias_of__isnull=True, enabled=True).distinct()
        else:
            self.repos = Repository.objects.filter(owner=self.owner)
            self.branches = get_default_branches_for_repos(self.repos)
            self.devs = Developer.objects.filter(commit__repository__in=self.repos, commit__branch__in=self.branches,
                                                 is_alias_of__isnull=True, enabled=True).distinct()

        blame_aggregate = Blame.objects.filter(
            author__in=self.devs.all(),
            repository__in=self.repos,
            branch__in=self.branches
        ).aggregate(
            loc=Sum('loc'),
            max_churn=Max('churn')
        )

        self.total_blame = blame_aggregate['loc']
        self.max_churn = blame_aggregate['max_churn']

        blame_aggregate = Blame.objects.filter(repository__in=self.repos) \
            .values('author') \
            .annotate(total_impact=Sum('log_impact')).all()

        self.total_impact = 0

        self.min_impact = None
        self.max_impact = 0
        n = 0
        for b in blame_aggregate:
            n += 1
            self.total_impact += (b['total_impact'] or 0)
            if not self.min_impact:
                self.min_impact = b['total_impact']
            if b['total_impact'] < self.min_impact:
                self.min_impact = b['total_impact']
            if b['total_impact'] > self.max_impact:
                self.max_impact = b['total_impact']
        if n > 0:
            self.min_impact = self.total_impact / n

        self.sort_by = '-commits'
        if 'sort' in self.request.GET:
            self.sort = self.request.GET['sort']
            sorts = {'commits': 'commits', '-commits': '-commits',
                     'lines': 'lines', '-lines': '-lines',
                     'ins': 'insertions', '-ins': '-insertions',
                     'del': 'deletions', '-del': '-deletions',
                     'net': 'net', '-net': '-net',
                     'avg': 'net_avg', '-avg': '-net_avg',
                     'blame': 'loc', '-blame': '-loc',
                     'churn': 'raw_churn', '-churn': '-raw_churn',
                     'throughput': 'throughput', '-throughput': '-throughput',
                     'impact': 'impact', '-impact': '-impact',
                     'owns': 'owns', '-owns': '-owns',
                     'factor': 'factor', '-factor': '-factor',
                     'self_churn': 'self_churn', '-self_churn': '-self_churn',
                     'work_others': 'work_others', '-work_others': '-work_others',
                     'changes': 'changes', '-changes': '-changes'}
            if self.sort in sorts:
                self.sort_by = sorts[self.sort]

        self.search_query = self.request.GET['q'] if 'q' in self.request.GET else None
        self.blames = get_developers_blame_summaries(self.repos, self.branches, self.sort_by, self.search_query)
        return self.blames

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        if 'repo_id' in self.kwargs:
            context['repo'] = Repository.objects.get(pk=self.kwargs['repo_id'])
        self.branches = get_default_branches_for_repos(self.repos)
        context['devs'] = self.devs if self.devs else None
        context['variable'] = self.variable
        context['label'] = self.label
        context['repos'] = self.repos
        if 'sort' in self.request.GET:
            self.sort = self.request.GET['sort']
        else:
            self.sort = '-commits'
        context['total_blame'] = self.total_blame
        context['total_impact'] = self.total_impact
        context['sort'] = self.sort
        context['min_impact'] = self.min_impact
        context['max_impact'] = self.max_impact
        context['max_churn'] = self.max_churn
        page_obj = context['page_obj']
        context['search_query'] = self.search_query
        return context


class DeveloperProfile(DeveloperMixin, DetailView):
    context_object_name = 'developer'
    template_name = 'developers/profile.html'
    commits_limit = 12

    def get_context_data(self, **kwargs):
        self.owner = self.request.user
        if self.object.owner != self.owner:
            raise PermissionDenied

        context = super().get_context_data(**kwargs)
        if 'repo_id' in self.kwargs:
            repo_id = self.kwargs['repo_id']
            context['repo'] = Repository.objects.get(pk=repo_id)
            repos_id = [repo_id]
        else:
            repos_id = Commit.objects.filter(author=self.object).values('repository_id').distinct()

        self.repos = Repository.objects.filter(id__in=repos_id)
        self.branches = get_default_branches_for_repos(self.repos)

        blame_aggregate = Blame.objects.filter(
            repository__in=self.repos,
            branch__in=self.branches
        ).aggregate(
            loc=Sum('loc'),
            total_impact=Sum('impact'),
            min_impact=Avg('impact'),
            max_impact=Max('log_impact'),
            max_churn=Max('churn')
        )
        self.total_blame = blame_aggregate['loc']
        self.total_impact = blame_aggregate['total_impact']
        self.min_impact = blame_aggregate['min_impact']
        self.max_impact = blame_aggregate['max_impact']
        self.max_churn = blame_aggregate['max_churn']

        commit_set = get_developer_commits(self.object, self.repos, self.branches)
        blame_stats = get_developer_blame_summary(self.object, self.repos, self.branches, self.total_blame)
        if not blame_stats:
            return context

        self_churn = blame_stats['self_churn']
        context['self_churn'] = self_churn
        work_others = blame_stats['work_others']
        context['changes'] = blame_stats['changes']
        context['commits_limit'] = self.commits_limit

        commit_count = blame_stats['commits_count'] or 0
        context['commits_count'] = commit_count

        repo_data = []
        files_created = 0
        files_deleted = 0
        for repo in self.repos:
            branch = repo.get_default_branch()
            fc = FileChange.objects.filter(repository=repo, branch=branch, commit__author = self.object,
                                           change_type__in=["A", "C"]).distinct().count()
            files_created += fc
            fd = FileChange.objects.filter(repository=repo, branch=branch, commit__author = self.object,
                                           change_type__in=["D"]).distinct().count()
            files_deleted += fd
            co = Commit.objects.filter(repository=repo, author=self.object, branch=branch).count()
            cod = Blame.objects.filter(repository=repo, author=self.object, branch=branch)\
                .aggregate(commits=Sum('commits'), changes=Sum('changes'),

                           insertions=Sum('insertions'), deletions=Sum('deletions'), net=Sum('net'))

            ch = FileChange.objects.filter(repository=repo, commit__author=self.object, branch=branch).count()
            repo_data.append({'repo': repo, 'files_created': fc, 'files_deleted': fd, 'commits': co, 'changes': ch,
                              'insertions': cod['insertions'] or 'lost',
                              'deletions': cod['deletions'] or 'lost',
                              'net': cod['net'] or 'lost'})

        context['files_created'] = files_created
        context['files_deleted'] = files_deleted
        active_days = blame_stats['days']
        context['active_days'] = active_days

        context['commits_per_day'] = commit_count/ active_days if active_days > 0 else 0

        context['total_days'] = Commit.objects.filter(repository__in=self.repos, branch__in=self.branches)\
            .annotate(only_date=TruncDate('date'))\
            .aggregate(days=Count('only_date', distinct=True))['days']


        owned_files = File.objects.filter(repository__in=self.repos, branch__in=self.branches, knowledge_owner=self.object).count()
        total_files = File.objects.filter(repository__in=self.repos, branch__in=self.branches).count()

        context['owned_files'] = owned_files
        context['total_files'] = total_files

        file_ownership = owned_files / total_files if total_files > 0 else 0.0
        context['file_ownership'] = file_ownership

        fc1 = FileKnowledge.objects.filter(file__repository__in=self.repos, file__branch__in=self.branches,
                                           author=self.object)\
            .aggregate(a=Sum('added'), d=Sum('deleted'), k=Avg('knowledge'))

        a = fc1['a']
        d = fc1['d']

        context['knowledge'] = fc1['k']

        fc2 = FileKnowledge.objects.filter(file__repository__in=self.repos, file__branch__in=self.branches) \
            .aggregate(a=Sum('added'), d=Sum('deleted'))

        at = fc2['a']
        dt = fc2['d']

        file_knowledge = (a+d) / (at+dt) if a and d and (at+dt) > 0 else 0.0

        context['file_knowledge'] = file_knowledge

        context['active_since'] = blame_stats['since']
        context['last_commit'] = blame_stats['last_commit']
        context['punchcard'] = get_dev_punchcard(self.object, self.repos, self.branches)

        activity_chart = get_dev_activity_chart(self.object, self.repos)
        context['charttype_activity'] = 'lineChart'
        context['chartdata_activity'] = activity_chart['data1']
        context['chartcontainer_activity'] = 'chartcontainer_activity'
        context['extra_activity'] = activity_chart['extra2']

        context['charttype_activity_acum'] = 'stackedAreaChart'
        context['chartdata_activity_acum'] = activity_chart['data3']
        context['chartcontainer_activity_acum'] = 'chartcontainer_activity_acum'
        context['extra_activity_acum'] = activity_chart['extra3']

        context['charttype_commit'] = 'lineChart'
        context['chartdata_commit'] = activity_chart['data2']
        context['chartcontainer_commit'] = 'chartcontainer_commit'
        context['extra_commit'] = activity_chart['extra2']

        context['charttype_commit_acum'] = 'stackedAreaChart'
        context['chartdata_commit_acum'] = activity_chart['data4']
        context['chartcontainer_commit_acum'] = 'chartcontainer_commit_acum'
        context['extra_commit_acum'] = activity_chart['extra4']

        context['total_blame'] = self.total_blame
        context['ownership'] = blame_stats['blame'] / self.total_blame if self.total_blame else 0
        context['blame'] = blame_stats['blame']
        context['commits'] = commit_set.distinct().order_by('-date')[0:self.commits_limit]
        context['work_others'] = work_others

        churn = blame_stats['churn']
        context['churn'] = churn

        impact = blame_stats['log_impact']
        throughput = blame_stats['throughput']
        context['throughput'] = throughput
        context['deletions'] = blame_stats['deletions']
        context['lines'] = blame_stats['lines']
        context['insertions'] = blame_stats['insertions']
        context['net'] = blame_stats['net']

        context['loc_per_day'] = context['lines'] / active_days if active_days > 0 else 0

        print("call get_badge_data for {}: {}, {}, {}, {}, {}, {}, {}".format(self.object, impact, churn, self_churn, throughput, work_others, self.max_churn, self.max_impact ))
        print(get_badge_data(impact, churn, self_churn, throughput, work_others, self.max_churn, self.max_impact))
        context.update(get_badge_data(impact, churn, self_churn, throughput, work_others, self.max_churn, self.max_impact))

        context['impact'] = impact
        return context


class DeveloperDashboard(DeveloperMixin, ListView):
    context_object_name = 'developer_list'
    template_name = 'developers/dashboard.html'
    paginate_by = 20

    def get_queryset(self):
        self.owner = self.request.user
        if 'repo_id' in self.kwargs:
            self.repo = Repository.objects.get(pk=self.kwargs['repo_id'])
            self.repos = [self.repo]
            self.branches = get_default_branches_for_repos(self.repos)
            self.devs = Developer.objects.filter(commit__repository__in=self.repos, commit__branch__in=self.branches,
                                                 is_alias_of__isnull=True, enabled=True).distinct()
        else:
            self.repo = None
            self.repos = Repository.objects.filter(owner=self.owner)
            self.branches = get_default_branches_for_repos(self.repos)
            self.devs = Developer.objects.filter(commit__repository__in=self.repos, commit__branch__in=self.branches,
                                                 is_alias_of__isnull=True, enabled=True).distinct()


        blame_aggregate = Blame.objects.filter(author__in=self.devs.all(), repository__in=self.repos,
                                               branch__in=self.branches).aggregate(loc=Sum('loc'))

        self.total_blame = blame_aggregate['loc']

        self.sort_by = '-impact'
        self.search_query = None
        self.blames = get_developers_blame_summaries(self.repos, self.branches, self.sort_by, self.search_query)

        return self.blames

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.branches = get_default_branches_for_repos(self.repos)
        context['repo'] = self.repo
        context['devs'] = self.devs
        context['repos'] = self.repos
        blames = Paginator(self.blames, self.paginate_by)

        page = self.request.GET.get('page') or 1

        total_devs = blames.count
        context['total_devs'] = total_devs

        devs = []
        commits_dev = 0
        locs_dev = 0
        for blame in blames.page(page).object_list:
            dev = Developer.objects.get(pk=blame['author'])
            devs.append(dev)
            commits_dev += blame['commits']
            locs_dev += blame['loc']
        context['commits_dev'] = commits_dev / len(devs) if devs and len(devs) > 0 else 0
        context['locs_dev'] = locs_dev / len(devs) if devs and len(devs) > 0 else 0
        context['dev_count'] = len(devs)

        blames = get_devs_blame_data(devs, self.repos, self.branches, self.total_blame)
        pie = get_devs_owner_pie_chart(blames)
        context['charttype_pie'] = "pieChart"
        context['chartdata_pie'] = pie['data']
        context['chartcontainer_pie'] = "piechart_container"
        context['extra_pie'] = pie['extra']

        mbh_chart = get_devs_churn_production_chart(blames)
        context['charttype_mbh'] = "multiBarHorizontalChart"
        context['chartdata_mbh'] = mbh_chart['data']
        context['extra_mbh'] = mbh_chart['extra']
        context['chartcontainer_mbh'] = "mbhchart_container"

        knowledge = FileKnowledge.objects.filter(file__repository__in=self.repos,
                                                 file__branch__in=self.branches, author__in=devs).\
            select_related('author__name').filter(author__enabled=True).\
            values('author__name').annotate(knowledge=Sum(F('added') + F('deleted')))
        context['knowledge'] = knowledge

        quadrant = get_devs_quadrant_chart(blames)
        context['quadrant_data'] = quadrant['data']

        return context