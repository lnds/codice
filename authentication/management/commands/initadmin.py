from django.core.management import BaseCommand

from authentication.models import User
from codice import settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        if User.objects.count() == 0:
            password = settings.DEFAULT_ADMIN_PASSWORD
            email = settings.DEFAULT_ADMIN_EMAIL
            username = settings.DEFAULT_ADMIN_USER
            admin = User.objects.create_superuser(email=email, password=password, username=username)
            admin.is_active = True
            admin.is_admin = True
            admin.save()
        else:
            print('admin user only created if there is none')