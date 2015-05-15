from django.core.management.base import NoArgsCommand, CommandError, BaseCommand
from getschema.models import Schema
import datetime

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        
        """
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(minutes=60)
        schemas = Schema.objects.filter(finished_date__lt = one_hour_ago)
        schemas.delete()
        """

        one_day_ago = datetime.datetime.now() - datetime.timedelta(hours=24)
        schemas = Schema.objects.filter(created_date__lt = one_day_ago)
        schemas.delete()


