web: gunicorn schemalister.wsgi --workers $WEB_CONCURRENCY
worker: celery -A schemalister worker -l info