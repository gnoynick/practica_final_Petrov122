from __future__ import absolute_import
import os
import gevent
from gevent import monkey
monkey.patch_all()

from celery import Celery
from django.conf import settings
from celery.result import AsyncResult

# Установите переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filemanager.settings')

app = Celery('filemanager')

# Настройки для Windows
if os.name == 'nt':
    # Решение для проблемы с Eventlet на Windows
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42

# Используйте строку настроек для автоматической загрузки конфигурации
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоподгрузка задач
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Настройки для работы с Eventlet
app.conf.update(
    worker_pool='eventlet',
    worker_concurrency=100,
    task_always_eager=False,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=100,
    worker_cancel_long_running_tasks_on_connection_loss=True
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')