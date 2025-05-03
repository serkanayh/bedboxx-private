import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from emails.models import Email, EmailAttachment, EmailRow

# Count emails before deletion
email_count = Email.objects.count()
row_count = EmailRow.objects.count()
attachment_count = EmailAttachment.objects.count()

# Delete all email rows first (to avoid foreign key constraints)
EmailRow.objects.all().delete()
print(f"Deleted {row_count} email rows")

# Delete all email attachments
EmailAttachment.objects.all().delete()
print(f"Deleted {attachment_count} attachments")

# Delete all emails
Email.objects.all().delete()
print(f"Deleted {email_count} emails")

print("All emails have been successfully deleted from the database.")
print("You can now add new emails to the 'incoming mails' folder for processing.") 