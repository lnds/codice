import os
import shutil
from pathlib import Path
from git import Repo

if 'CODICE_DATA' in os.environ:
    home = os.environ['CODICE_DATA']
else:
    home = Path.home()


codice_home = home / Path('.codice')
users_home = codice_home / Path('users')


def clone_repository(owner_id, repository_name, repository_url):
    """clone a remote repository"""
    base_path = users_home / Path(str(owner_id))
    print(base_path)
    if not base_path.exists():
        base_path.mkdir(parents=True)
    repository_path = base_path / Path('repos') / Path(repository_name)
    print("repository_path = {}".format(repository_path))
    print("repository_url = {}".format(repository_url))
    if not repository_path.exists():
        Repo.clone_from(repository_url, str(repository_path), env={'GIT_SSL_NO_VERIFY': '1'})
    return str(repository_path)


def remove_local_repository(owner_id, repository_name):
    """remove a local repository"""
    base_path = users_home / Path(str(owner_id))
    repository_path = base_path / Path('repos') / Path(repository_name)
    if repository_path.exists():
        shutil.rmtree(str(repository_path), ignore_errors=False)
    return str(repository_path)