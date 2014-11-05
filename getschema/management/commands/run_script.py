from django.core.management.base import NoArgsCommand, CommandError, BaseCommand
from django.db import connection, transaction

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        
        cursor = connection.cursor()
        cursor.execute('DROP TABLE Field')


