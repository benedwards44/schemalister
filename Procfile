web: gunicorn schemalister.wsgi --workers $WEB_CONCURRENCY
worker: celery -A getschema.tasks worker --loglevel=INFO