from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.views.generic import ListView, DetailView

from developers.models import Developer
from files.models import File
from repos.models import Repository, get_default_branches_for_repos
from tools.encoding import detect_encoding


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

    def get_queryset(self):
        self.owner = self.request.user
        if 'repo_id' in self.kwargs:
            self.repos = [Repository.objects.get(pk=self.kwargs['repo_id'])]
        else:
            self.repos = Repository.objects.filter(owner=self.owner)

        self.branches = get_default_branches_for_repos(self.repos)

        sort = self.request.GET['sort'] if 'sort' in self.request.GET else 'name'
        sorts = {'loc': 'code', '-loc': '-code',
                 'soc': 'soc', '-soc': '-soc',
                 'name': 'filename', '-name': '-filename',
                 'lang': 'language', '-lang': '-language',
                 'comments': 'doc', '-comments': '-doc',
                 'empty': 'blanks', '-empty': '-empty',
                 'ic': 'indent_complexity', '-ic': '-indent_complexity',
                 'cf': 'coupled_files', '-cf': '-coupled_files',
                 'changes': 'changes', '-changes': '-changes',
                 'authors': 'authors', '-authors': '-authors',
                 }
        sort = sorts[sort] if sort in sorts else 'filename'

        self.filter_lang = self.request.GET['filter'] if 'filter' in self.request.GET else None

        if self.filter_lang:
            query = File.objects.filter(language=self.filter_lang, is_code=True,
                                        repository__in=self.repos, branch__in=self.branches) \
                .annotate(authors=Count('filechange__commit__author', distinct=True)) \
                .annotate(changes=Count('filechange', distinct=True))
        else:
            query = File.objects.filter(repository__in=self.repos, branch__in=self.branches, is_code=True) \
                .annotate(authors=Count('filechange__commit__author', distinct=True))

        self.search_query = self.request.GET['q'] if 'q' in self.request.GET else None
        if self.search_query:
            return query.filter(filename__icontains=self.search_query).order_by(sort)
        else:
            return query.order_by(sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort = self.request.GET['sort'] if 'sort' in self.request.GET else None
        repo = Repository.objects.get(pk=self.kwargs['repo_id']) if 'repo_id' in self.kwargs else None
        context['repo'] = repo
        context['sort'] = sort
        filter_param = self.request.GET['filter'] if 'filter' in self.request.GET else None
        context['filter'] = filter_param
        languages = File.objects.filter(repository__in=self.repos, branch__in=self.branches, is_code=True) \
            .values('language').annotate(n=Count('language')).order_by('language')
        context['languages'] = languages
        context['filter_lang'] = self.filter_lang
        context['search_query'] = self.search_query
        return context


class FileView(FileMixin, DetailView):
    context_object_name = 'file'
    template_name = 'files/detail.html'

    def check_access(self):
        return self.owner is not None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        file = self.object
        if file.repository.owner != self.owner:
            raise PermissionDenied

        repo = file.repository
        path = Path(repo.base_directory) / Path(file.filename)
        context['path'] = Path(file.filename)
        try:
            encoding = detect_encoding(path)
            with open(path, 'r', newline='', encoding=encoding, errors='ignore') as source:
                context['content'] = source.read()
        except IOError:
            context['content'] = "ERROR"
        coupled_files = file.get_coupled_files(file.commits)
        context['count_coupled_files'] = len(coupled_files)
        context['coupled_files'] = coupled_files
        context['authors'] = file.get_authors
        context['creator'] = file.get_creator
        context['knowledge_owner'] = file.knowledge_owner

        if 'commits_by' in self.request.GET:
            author_id = int(self.request.GET['commits_by'])
            context['author'] = Developer.objects.get(pk=author_id)
            context['commits'] = file.get_commits_by(author_id)
        return context