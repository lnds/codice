import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Min, Max, Sum
from django.views.generic import TemplateView

from commits.models import Commit
from developers.models import Developer
from files.models import File
from repos.models import Repository


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['repo_count'] = Repository.objects.filter(Q(owner= self.request.user) | Q(public=True)).count()

        repos = Repository.objects

        context['file_count'] = File.objects.filter(repository__in=repos.all(), is_code=True).count()

        context['dev_count'] = Developer.objects.annotate(count_blame=Count('blame')) \
            .filter(owner=self.request.user, enabled=True, is_alias_of=None, count_blame__gt=0).count()

        r = Commit.objects.filter(repository__in=repos.all()) \
            .aggregate(min_date=Min('date'), max_date=Max('date'), count=Count('id', distinct=True))
        context['min_date'] = r['min_date']
        context['max_date'] = r['max_date']
        context['commit_count'] = r['count']

        date = datetime.datetime.now()
        delta = datetime.timedelta(days=7)
        time_ago = date - delta
        count = Commit.objects.filter(date__gte=time_ago).count()
        context['commits_in_last_week'] = "+{:,}".format(count) if count else '0'

        query = Commit.objects.filter(date__gte=time_ago).aggregate(net=Sum('net'))
        count = query['net'] or 0
        if count < 0:
            context['net_lines_in_last_week'] = "{:,}".format(count)
        elif count > 0:
            context['net_lines_in_last_week'] = "+{:,}".format(count)
        else:
            context['net_lines_in_last_week'] = '0'

        return context