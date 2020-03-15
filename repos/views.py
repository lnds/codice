from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.db.transaction import on_commit
from django.views.generic import ListView, CreateView, DetailView, DeleteView
from django.utils.translation import gettext as _

from analytics.hotspots import count_hotspots
from files.models import File, FileChange
from analytics.services import get_bus_factor_of
from repos.models import Repository
from repos.tasks import clone_remote_repository, remove_local_repository
import logging

logger = logging.getLogger(__name__)


class RepositoryMixin(LoginRequiredMixin, SuccessMessageMixin):
    model = Repository


class CanSeeRepoMixin(PermissionRequiredMixin):
    def has_permission(self):
        self.owner = self.request.user
        if 'pk' in self.kwargs:
            self.repo = Repository.objects.get(pk=self.kwargs['pk'])
            return self.repo.owner == self.owner or self.repo.public
        return False


class CanAdminReposMixin(CanSeeRepoMixin):
    def has_permission(self):
        result = self.request.user.can_add_repo() and self.request.user.can_del_repo()
        return result


class RepositoryList(RepositoryMixin, ListView):
    context_object_name = 'repo_list'
    template_name = 'repository/list.html'
    paginate_by = 10
    owner = None

    def get_queryset(self):
        self.owner = self.request.user
        return Repository.objects.filter(Q(owner=self.owner) | Q(public=True))


class RepositoryCreate(RepositoryMixin, CanAdminReposMixin, CreateView):
    """Add a new repo"""
    success_message = _('Repository was added successfully')
    template_name = 'repository/add.html'
    fields = ['name', 'url', 'username', 'password', 'branches_to_track', 'default_branch', 'public']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.owner = self.request.user
        return form

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.status = Repository.Status.CREATED
        self.object = form.save()
        on_commit(lambda: clone_remote_repository.delay(self.object.owner.id, self.object.id))
        return super(RepositoryCreate, self).form_valid(form)


class RepositoryDetail(RepositoryMixin, CanSeeRepoMixin, DetailView):
    template_name = 'repository/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.branch = self.object.find_branch(self.request.GET['filter'] if 'filter' in self.request.GET else None)
        print("branch = {}".format(self.branch))
        commit_set = self.repo.commit_set.filter(branch=self.branch)

        context['file_changes_count'] = FileChange.objects.filter(commit__in=commit_set.all()).count()

        qs = File.objects.filter(repository=self.repo, branch=self.branch, is_code=True, exists=True) \
            .aggregate(count=Count('id', distinct=True), loc=Sum('code'), avg=Avg('indent_complexity'))

        context['file_count'] = qs['count'] or 0
        context['loc'] = qs['loc'] or 0
        context['commit_count'] = commit_set.count()

        context['bus_factor'] = get_bus_factor_of(self.repo)

        context['filter'] = self.branch.name if self.branch else None
        context['branches_count'] = self.repo.branches_count()

        devs= Paginator(self.repo.get_developers_contribution(self.branch), 10)
        page = self.request.GET.get('page')
        context['devs'] = devs.get_page(page)
        context['devs_count'] = devs.count

        context['hotspots_count'] = count_hotspots(self.repo, self.branch)
        return context


class RepositoryDelete(RepositoryMixin, CanAdminReposMixin, DeleteView):
    success_message = _('Repository was deleted successfully')
    success_url = '/repos/'

    def delete(self, request, *args, **kwargs):
        self.owner = request.user
        result = super(RepositoryDelete, self).delete(request, *args, **kwargs)

        remove_local_repository.delay(self.object.owner.id, self.object.name)
        messages.success(self.request, self.success_message)
        return result
