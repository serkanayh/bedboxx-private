# stopsale_automation/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
app = Celery('stopsale_automation')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Diğer görevler...
    'match_email_rows_batch': {
        'task': 'emails.tasks.match_email_rows_batch_task',
        'schedule': 30.0,
    },
    # 15 dakikada bir çalışan oda gruplarını güncelleme görevi
    'update_room_groups': {
        'task': 'emails.tasks.update_room_groups_task',
        'schedule': 60 * 15,  # 15 dakika
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
