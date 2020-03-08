from django.utils.timezone import make_aware, is_aware

from authentication.models import User
from commits.models import Commit
from developers.models import Developer
from git_interface.gitobjects import GitRepository
from repos.models import Repository, Branch
import logging

_log_pygount = logging.getLogger('pygount')
_log_pygount.disabled = True
logger = logging.getLogger(__name__)


def process_repo_objects(repo: Repository):
    logger.info("processing repo: {}".format(repo))
    analyzer = RepoAnalyzer(repo)
    analyzer.process()


class RepoAnalyzer(object):

    def __init__(self, repo: Repository):
        self.repo : Repository = repo
        self.owner : User = repo.owner
        self.files_bag = dict()
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
        for branch in self.remote_branches_to_track:
            self.process_branch(branch)

            if self.repo.default_branch == '':
                self.repo.default_branch = branch
                self.repo.save()


    def process_branch(self, branch_name: str):
        logger.info("CHECKOUT BRANCH {}".format(branch_name))
        if not self.git_repo.checkout(branch_name):
            return None

        branch, created = Branch.objects.get_or_create(name=branch_name, repository=self.repo)
        logger.info('BRANCH %s CREATED: %s', branch_name, created)

        self.process_commits(branch)
        self.process_changes(branch)
        return branch

    def process_commits(self, branch: Branch):
        commit_history = self.git_repo.get_commits(branch=branch.name)

        logger.info('BEGIN COMMIT HISTORY')
        for commit in commit_history:
            logger.info("PROCESSING COMMIT HISTORY %s @ %s", commit.hexsha, commit.authored_datetime)
            author_email = commit.author.email
            author = self.__get_author(author_email, commit.author.name)
            self.__get_or_create_commit(commit, author, branch)

        logger.info("END COMMIT HISTORY")

    def __get_author(self, email, name):
        cache_key = (email, self.owner)
        if cache_key not in self.developer_cache:
            dev, created = Developer.objects.get_or_create(email=email, owner=self.owner, defaults={'name': name})
            self.developer_cache[cache_key] = dev
            dev.repos.add(self.repo)
            return dev
        return self.developer_cache[cache_key]

    def __get_or_create_commit(self, git_commit, author, branch):

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

        return self.commit_cache[cache_key]

    def process_changes(self, branch):
        pass

