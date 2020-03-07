from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, DeleteView
from django.utils.translation import gettext as _

from repos.models import Repository
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


'''Add a new repo'''
class RepositoryCreate(RepositoryMixin, CanAdminReposMixin, CreateView):
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
        # clone_remote_repository.delay(self.object.owner.id, self.project.id, self.object.id)
        return super(RepositoryCreate, self).form_valid(form)


class RepositoryDetail(RepositoryMixin, CanSeeRepoMixin, DetailView):
    template_name = 'repository/detail.html'


class RepositoryDelete(RepositoryMixin, CanAdminReposMixin, DeleteView):
    success_message = _('Repository was deleted successfully')
    success_url = '/repos/'
