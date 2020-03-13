import sys

from celery import shared_task
from celery.utils.log import get_task_logger
from git import GitCommandError

from authentication.models import User
from git_interface.giturls import build_repo_url
from repos.analytics.analyzer import process_repo_objects
from repos.models import Repository
import git_interface.gitcmds as git

logger = get_task_logger(__name__)


@shared_task
def clone_remote_repository(owner_id: int, repo_id: int):
    try:
        owner: User = User.objects.get(pk=owner_id)
        repo: Repository = Repository.objects.get(pk=repo_id)
        repo.status = Repository.Status.CLONING
        repo.save()
        logger.info("repo.url={}".format(repo.url))
        repo_url = build_repo_url(repo.url, repo.username, repo.password)
        logger.info("repo_url: {}".format(repo_url))

        path = git.clone_repository(owner.id, repo.name, repo_url)

        logger.info("repo cloned in {}".format(path))
        repo.base_directory = path
        repo.status = Repository.Status.CLONED
        repo.save()

        process_repo_objects(repo)
        repo.status = Repository.Status.OK
        repo.save()

        return "Repository {} cloned successfully".format(repo)
    except User.DoesNotExist:
        return "error cloning repository, user_id {} not found".format(owner_id)
    except Repository.DoesNotExist:
        return "error cloning repository, repository_id {} not found".format(repo_id)
    except GitCommandError as cmd_err:
        repo = Repository.objects.get(pk=repo_id)
        repo.status = Repository.ERROR
        repo.save()
        return "git error: {}".format(cmd_err)


@shared_task
def remove_local_repository(owner_id, repo_name):
    try:
        logger.info('remove local repository')
        git.remove_local_repository(owner_id, repo_name)
        return "Repository {} removed".format(repo_name)
    except:
        return "error removing local repository: {}".format(sys.exc_info()[0])