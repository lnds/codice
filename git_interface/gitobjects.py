from git import Repo, GitCommandError, CheckoutError
import logging


logger = logging.getLogger(__name__)


class GitRepository(object):

    """The local repository"""
    def __init__(self, base_dir: str):
        self.git_repo = Repo(base_dir)

    def checkout(self, branch_name):
        try:
            self.git_repo.git.checkout(branch_name)
            return True
        except GitCommandError:
            return False
        except CheckoutError:
            return False

    def get_commits(self, branch):
        return self.git_repo.iter_commits(branch)

    def blame(self, rev, filename):
        try:
            return self.git_repo.blame(rev, filename, incremental=False)
        except GitCommandError:
            return None
        except KeyError:
            return None