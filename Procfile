web: gunicorn schemalister.wsgi --workers $WEB_CONCURRENCY
worker: celery -A tasks worker --loglevel=info