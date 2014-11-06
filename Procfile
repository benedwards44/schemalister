web: gunicorn schemalister.wsgi --workers $WEB_CONCURRENCY
worker: celery worker --app=tasks.app