import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Ari.settings')

app = Celery('Ari')

# Django sozlamalaridan yuklash
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tasklarni avtomatik yuklash
app.autodiscover_tasks()
