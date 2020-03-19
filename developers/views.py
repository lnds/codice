from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, F
from django.views.generic import ListView

from developers.charts import get_devs_blame_data, get_devs_owner_pie_chart, get_devs_churn_production_chart, \
    get_devs_quadrant_chart
from developers.models import Developer, Blame
from developers.services import get_developers_blame_summaries
from files.models import FileKnowledge
from repos.models import get_default_branches_for_repos, Repository


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

        blame_aggregate = Blame.objects.filter(author__in=self.devs.all(), repository__in=self.repos,
                                               branch__in=self.branches).aggregate(loc=Sum('loc'))

        self.total_blame = blame_aggregate['loc']

        blame_aggregate = Blame.objects.filter(repository__in=self.repos) \
            .values('author') \
            .annotate(total_impact=Sum('log_impact')).all()

        self.total_impact = 0
        self.min_impact = None
        n = 0
        for b in blame_aggregate:
            n += 1
            self.total_impact += b['total_impact']
            if not self.min_impact:
                self.min_impact = b['total_impact']
            if b['total_impact'] < self.min_impact:
                self.min_impact = b['total_impact']
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
        context['sort'] = self.sort
        context['min_impact'] = self.min_impact
        page_obj = context['page_obj']
        context['search_query'] = self.search_query
        return context