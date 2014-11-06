from celery import Celery
import iron_celery

app = Celery('tasks', broker='ironmq://', backend='ironcache://')

@app.task
def add(x, y):
	print 'XXXXXXXXX HELLO'
	return x + y