from celery import Celery
import iron_celery

app = Celery('tasks', broker='ironmq://', backend='ironcache://')

@app.task
def add(x, y):
	schema = Schema()
	schema.org_id = 'abc'
	schema.org_name = 'abc'
	schema.save()
	return x + y