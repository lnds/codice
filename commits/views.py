from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView

from commits.models import Commit
from files.models import File
from repos.models import Repository


class CommitMixin(LoginRequiredMixin):
    model = Commit


class CanSeeCommitMixin(PermissionRequiredMixin):
    def has_permission(self):
        self.owner = self.request.user
        self.file = File.objects.get(pk=self.kwargs['file_id']) if 'file_id' in self.kwargs else None
        if self.file:
            return self.file.repository.owner == self.owner
        return True


class CommitList(CommitMixin, CanSeeCommitMixin, ListView):
    context_object_name = 'commit_list'
    template_name = 'commit/list.html'
    paginate_by = 10

    def get_queryset(self):
        if self.file:
            return Commit.objects.filter(filechange__file=self.file).order_by('-date')
        repos = Repository.objects.filter(owner=self.owner)
        if self.search_query:
            return Commit.objects.filter(repository__in=repos, message__icontains=self.search_query).order_by('-date')
        return Commit.objects.filter(repository__in=repos).order_by('-date')

    def get_context_data(self,  **kwargs):
        context = super().get_context_data(**kwargs)
        context['file'] = self.file
        self.search_query = self.request.GET['q'] if 'q' in self.request.GET else None

        context['search_query'] = self.search_query
        return context


class CommitDetail(CommitMixin, DetailView):
    template_name = 'commit/detail.html'