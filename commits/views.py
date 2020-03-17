from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView

from commits.models import Commit
from files.models import File


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
    paginate_by = 10
