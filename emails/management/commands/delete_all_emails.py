from django.core.management.base import BaseCommand
from emails.models import Email
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Deletes all Email objects from the database.'

    def handle(self, *args, **options):
        email_count = Email.objects.count()
        if email_count == 0:
            self.stdout.write(self.style.SUCCESS('No emails found in the database.'))
            return

        confirm = input(f'Are you sure you want to delete all {email_count} emails? This cannot be undone. (yes/no): ')
        if confirm.lower() == 'yes':
            try:
                deleted_count, _ = Email.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} emails.'))
            except Exception as e:
                logger.error(f"Error deleting emails: {str(e)}", exc_info=True)
                self.stderr.write(self.style.ERROR(f'An error occurred while deleting emails: {str(e)}'))
        else:
            self.stdout.write(self.style.WARNING('Email deletion cancelled.')) 