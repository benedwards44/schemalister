from django.core.management.base import BaseCommand
from getschema.models import Schema
import datetime

class Command(BaseCommand):

    def handle(self, **options):
        
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(minutes=60)
        schemas = Schema.objects.filter(finished_date__lt = one_hour_ago)
        schemas.delete()
