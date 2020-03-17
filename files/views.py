from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from files.models import File
from repos.models import Repository, get_default_branches_for_repos


class FileMixin(LoginRequiredMixin):
    model = File

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.owner = self.request.user
        self.repos = Repository.objects.filter(owner=self.owner)
        context['repos'] = self.repos
        self.branches = get_default_branches_for_repos(self.repos)
        context['branches'] = self.branches
        return context


class FileList(FileMixin, ListView):
    context_object_name = 'file_list'
    paginate_by = 10