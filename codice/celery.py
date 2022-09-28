import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codice.settings')

app = Celery('codice')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

task = app.task
