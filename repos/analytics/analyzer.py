import traceback
from pathlib import Path

import pygount
from django.utils.timezone import make_aware, is_aware
from pygount.analysis import SourceState
from authentication.models import User
from commits.models import Commit
from developers.models import Developer
from files.models import File, FilePath, FileChange, FileBlame
from git_interface.gitobjects import GitRepository
from repos.analytics.complexity import calculate_complexity_in
from repos.models import Repository, Branch
import logging

from tools.encoding import detect_encoding

_log_pygount = logging.getLogger('pygount')
_log_pygount.disabled = True
logger = logging.getLogger(__name__)

def language_is_code(lang):
    return lang not in ('__unknown__', '__binary__', '__error__', '__generated__', '__empty__')

def process_repo_objects(repo: Repository):
    logger.info("processing repo: {}".format(repo))
    analyzer = RepoAnalyzer(repo)
    analyzer.process()


class RepoAnalyzer(object):

    def __init__(self, repo: Repository):
        self.repo : Repository = repo
        self.owner : User = repo.owner
        self.files_bag = dict()
        self.file_cache = dict()
        self.filepath_cache = dict()
        self.git_repo = GitRepository(self.repo.base_directory)
        self.developer_cache = dict()
        self.commit_cache = dict()

        rbts = self.repo.branches_to_track.strip()
        if rbts == '':
            self.remote_branches_to_track = [self.repo.default_branch if self.repo.default_branch else 'master']
        else:
            self.remote_branches_to_track = rbts.replace(';', ',').replace(' ', ',').split(',')

        self.current_branch = self.repo.default_branch

    def process(self):
        self.repo.status = Repository.Status.ANALYZING
        self.repo.save()
        for branch in self.remote_branches_to_track:
            self.__process_branch(branch)

            if self.repo.default_branch == '':
                self.repo.default_branch = branch
                self.repo.save()

    def __process_branch(self, branch_name: str):
        logger.info("CHECKOUT BRANCH {}".format(branch_name))
        if not self.git_repo.checkout(branch_name):
            return None

        branch, created = Branch.objects.get_or_create(name=branch_name, repository=self.repo)
        logger.info('BRANCH %s CREATED: %s', branch_name, created)

        self.__process_commits(branch)
        return branch

    def __process_commits(self, branch: Branch):
        commit_history = self.git_repo.get_commits(branch=branch.name)

        logger.info('BEGIN COMMIT HISTORY')
        for commit in commit_history:
            logger.info("PROCESSING COMMIT HISTORY %s @ %s", commit.hexsha, commit.authored_datetime)
            author_email = commit.author.email
            author = self.__get_author(author_email, commit.author.name)
            self.__process_commit(commit, author, branch)

        logger.info("END COMMIT HISTORY")

    def __get_author(self, email, name):
        cache_key = (email, self.owner)
        if cache_key not in self.developer_cache:
            dev, created = Developer.objects.get_or_create(email=email, owner=self.owner, defaults={'name': name})
            self.developer_cache[cache_key] = dev
            dev.repos.add(self.repo)
            return dev
        return self.developer_cache[cache_key]

    def __process_commit(self, git_commit, author, branch):
        hexsha = str(git_commit.hexsha)
        date = git_commit.authored_datetime

        cache_key = (hexsha, date)
        if cache_key not in self.commit_cache:
            msg = git_commit.message
            is_merge = len(git_commit.parents) > 1
            stats = git_commit.stats.total
            ins = int(stats['insertions']) if not is_merge else 0
            dels = int(stats['deletions']) if not is_merge else 0
            lines = int(stats['lines']) if not is_merge else 0
            net = int(ins - dels) if not is_merge else 0
            real_author = author.get_principal()

            commit, created = Commit.objects.get_or_create(
                hexsha=hexsha,
                repository=self.repo,
                branch=branch,
                defaults=dict(
                    date=make_aware(date) if not is_aware(date) else date,
                    message=msg,
                    insertions=ins,
                    deletions=dels,
                    lines=lines,
                    net=net,
                    is_merge=is_merge,
                    author=real_author,
                    original_author=author
                )
            )

            self.commit_cache[cache_key] = commit

            self.__process_files(commit, branch, git_commit.stats.files, git_commit)

        return self.commit_cache[cache_key]

    def __process_files(self, commit, branch, files, git_commit):
        logger.info("FILES")
        for fn in files.keys():
            logger.info("file: {}".format(fn))
            file = self.__process_file(fn, branch)
            self.__process_file_change(commit, file, files[fn], git_commit)
            logger.info("data: {}".format(files[fn]))

            self.__process_file_blame(fn, commit, file)

    def __process_file_change(self, commit:Commit, file: File, fc, git_commit):
        ins = int(fc['insertions'])
        dels = int(fc['deletions'])
        change_type = self.__det_change_status(git_commit, git_commit.parents)
        print("change type = {}, for file: {}".format(change_type, file))
        return FileChange.objects.get_or_create(
            file=file,
            commit=commit,
            defaults=dict(
                repository=commit.repository,
                branch=commit.branch,
                insertions=ins,
                deletions=dels,
                change_type=change_type
            )
        )

    def __det_change_status(self, commit, parents):
        for parent in parents:
            for change in parent.diff(commit):
                return change.change_type
        return ""

    def __process_file(self, filename, branch):
        pkey = str(Path(self.repo.base_directory) / Path(filename))
        key = pkey + '@' + branch.name
        if key not in self.file_cache:
            p = Path(filename)
            parent = p.parent
            name = p.name
            if parent == name:
                parent = ''
            file_path = self.__get_filepath(branch, parent)
            try:
                path = Path(pkey)
                exists = path.is_file()
                if exists:
                    analysis = None
                    try:
                        analysis = pygount.source_analysis(pkey, self.repo.name)
                    except Exception as e:
                        logger.info('error on {}'.format(pkey))
                        tb = traceback.format_exc(e)
                        logger.info(tb)

                    empty = analysis.state == SourceState.empty.name
                    binary = analysis.state == SourceState.binary.name
                    indent_complexity = calculate_complexity_in(pkey) if not empty and not binary else 0
                    is_code = (not binary) and (not empty) and language_is_code(analysis.language)
                    lines = 0
                    if not binary:
                        encoding = detect_encoding(path)
                        with open(path, "r", newline='', encoding=encoding, errors='ignore') as fd:
                            lines = sum(1 for _ in fd)

                    file, created = File.objects.get_or_create(
                        filename=filename,
                        repository=self.repo,
                        branch=branch,
                        defaults=dict(
                            path=file_path,
                            name=name,
                            language=analysis.language,
                            code=analysis.code,
                            doc=analysis.documentation,
                            blanks=analysis.empty,
                            empty=empty,
                            strings=analysis.string,
                            binary=binary,
                            exists=True,
                            is_code=is_code,
                            indent_complexity=indent_complexity,
                            lines=lines
                        )
                    )
                    self.file_cache[key] = file
                else:
                    file, created = self.__get_or_create_file(filename, branch, file_path, name)
                    self.file_cache[key] = file
            except Exception as e:
                tb = traceback.format_exc(e)
                logger.info(tb)
                file, created = self.__get_or_create_file(filename, branch, file_path, name)
                self.file_cache[key] = file

        return self.file_cache[key]

    def __get_or_create_file(self, filename, branch, file_path, name):
        return File.objects.get_or_create(
            filename=filename,
            repository=self.repo,
            branch=branch,
            defaults=dict(
                path=file_path,
                name=name,
                language='',
                code=0,
                doc=0,
                blanks=0,
                lines=0,
                empty=True,
                strings=0,
                binary=False,
                exists=False,
                is_code=False,
                indent_complexity=0
            )
        )

    def __get_filepath(self, branch: Branch, path):
        pkey = str(Path(self.repo.base_directory) / Path(path))
        cache_key = pkey + '@' + branch.name

        if cache_key not in self.filepath_cache:
            path_obj = Path(path)

            if str(path) != '.' and str(path.parent) != '':
                parent = self.__get_filepath(branch, path_obj.parent)
            else:
                parent = None

            filepath, created = FilePath.objects.get_or_create(
                path=path,
                branch=branch,
                repository=self.repo,
                defaults=dict(
                    name=path_obj.name,
                    exists=Path(pkey).exists(),
                    parent=parent
                )
            )

            self.filepath_cache[cache_key] = filepath

        return self.filepath_cache[cache_key]

    def __process_file_blame(self, filename, commit: Commit, file: File):
        b = self.git_repo.blame(commit.hexsha, filename)
        print("b is = {}".format(b[0][1]))
        blame, created = FileBlame.objects.get_or_create(file=file, commit=commit, author=commit.author, loc=len(b[0][1]))
        return blame
