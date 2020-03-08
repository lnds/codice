import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codice.settings')

app = Celery('codice', backend='rpc://', broker=os.getenv("CELERY_BROKER_URL", 'pyamqp://guest@localhost//'))
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
