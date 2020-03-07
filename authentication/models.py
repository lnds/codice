from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pass

    def can_add_repo(self):
        return self.has_perm('repos.add_repository')

    def can_del_repo(self):
        return self.has_perm('repos.del_repository')