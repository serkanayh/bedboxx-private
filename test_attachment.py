#!/usr/bin/env python
"""
Test script to check attachment analysis
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

# Import models after Django setup
from emails.models import Email, EmailAttachment, EmailRow
from emails.views import process_email_attachments
from users.models import User
import logging

logger = logging.getLogger(__name__)

def test_attachment_analysis(email_id):
    """
    Test attachment analysis for the specified email
    """
    try:
        # Get the email
        email = Email.objects.get(id=email_id)
        print(f"Email ID: {email.id}, Subject: {email.subject}, Status: {email.status}")
        
        # Get attachments
        attachments = email.attachments.all()
        print(f"Attachment count: {attachments.count()}")
        
        for attachment in attachments:
            # Check if file exists
            file_exists = attachment.file and attachment.file.path and os.path.exists(attachment.file.path)
            
            print(f"Attachment {attachment.id}: {attachment.filename}")
            print(f"  Decoded filename: {attachment.decoded_filename}")
            print(f"  File extension: {attachment.file_extension}")
            print(f"  Content type: {attachment.content_type}")
            print(f"  Is PDF: {attachment.is_pdf}")
            print(f"  File exists: {file_exists}")
            
            # Check if extension is allowed
            allowed_extensions = ('.pdf', '.docx', '.xlsx', '.xls', '.doc')
            is_allowed = attachment.file_extension in allowed_extensions
            print(f"  Extension allowed: {is_allowed}")
        
        # Process attachments
        user = User.objects.first()
        if not user:
            print("No user found. Creating a test user.")
            user = User.objects.create(username="test_user", email="test@example.com")
        
        print(f"\nProcessing attachments for email {email_id} with user {user.username}...")
        
        # Reset email status
        old_status = email.status
        email.status = 'pending'
        email.save()
        
        # Process attachments
        success = process_email_attachments(email, user)
        
        print(f"Processing result: {'Success' if success else 'Failed'}")
        print(f"Email status after processing: {email.status}")
        
        # Check if any rows were created
        rows_after = EmailRow.objects.filter(email=email, extracted_from_attachment=True).count()
        print(f"Rows created from attachments: {rows_after}")
        
        return success
    
    except Email.DoesNotExist:
        print(f"Email ID {email_id} not found")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        email_id = int(sys.argv[1])
        test_attachment_analysis(email_id)
    else:
        print("Usage: python test_attachment.py <email_id>")
        # Default to email ID 2323 for testing
        print("Using default email ID 2323 for testing...")
        test_attachment_analysis(2323) 