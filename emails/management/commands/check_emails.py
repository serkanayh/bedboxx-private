import os
import email
import imaplib
import datetime
import logging
import mimetypes
import uuid
import hashlib
from email.header import decode_header
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from core.models import EmailConfiguration
from emails.models import Email, EmailRow, EmailAttachment

# --- Import for text extraction ---
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    # Logger might not be configured yet, print instead for initial warning
    print("WARNING: pypdf library not found. PDF text extraction will be disabled. Run 'pip install pypdf'")
    # logger.warning("pypdf library not found. PDF text extraction will be disabled. Run 'pip install pypdf'")
# --- End Import ---

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check for new emails via IMAP or from a local folder'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force checking even if not active in configuration',
        )
    
    def handle(self, *args, **options):
        # Get configuration
        try:
            config = EmailConfiguration.objects.first()
            if not config:
                self.stdout.write(self.style.ERROR('No email configuration found'))
                return
            
            if not config.is_active and not options['force']:
                self.stdout.write(self.style.WARNING('Email checking is not active in configuration'))
                return
            
            # Update last check time
            config.last_check = timezone.now()
            config.save()
            
            # Check emails based on configuration
            if config.use_local_folder:
                self.check_local_folder(config)
            else:
                self.check_imap(config)
            
            self.stdout.write(self.style.SUCCESS('Email check completed successfully'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking emails: {str(e)}'))
            logger.exception("Error in check_emails command")
    
    def check_imap(self, config):
        """Check emails from IMAP server"""
        try:
            # Connect to IMAP server
            self.stdout.write(f"Connecting to IMAP server {config.imap_host}:{config.imap_port}")
            
            if config.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
            else:
                mail = imaplib.IMAP4(config.imap_host, config.imap_port)
            
            # Login
            mail.login(config.imap_username, config.imap_password)
            
            # Check if we're connecting to Gmail
            is_gmail = 'gmail' in config.imap_host.lower()
            
            # List available mailboxes/labels for reference and find label match
            self.stdout.write("Available mailboxes/labels:")
            status, mailboxes = mail.list()
            
            # Variables to store info about available labels
            available_mailboxes = []
            found_label_mailbox = None
            
            # Safely get imap_label - handle case where it might not exist in older configs
            imap_label = getattr(config, 'imap_label', None)
            
            if status == 'OK':
                for mailbox in mailboxes:
                    mailbox_str = mailbox.decode()
                    self.stdout.write(f"  {mailbox_str}")
                    available_mailboxes.append(mailbox_str)
                    
                    # Check if this mailbox matches our label
                    if imap_label and imap_label.lower() in mailbox_str.lower():
                        # Extract the actual mailbox name from the response
                        # Format is typically: (flags) "/" "mailbox_name"
                        # We want the mailbox_name part
                        parts = mailbox_str.split('"')
                        if len(parts) >= 2:
                            found_label_mailbox = parts[-2]  # Get the mailbox name
                            self.stdout.write(self.style.SUCCESS(f"Found matching mailbox for label '{imap_label}': {found_label_mailbox}"))
            
            # Decide which mailbox to select based on configuration and available mailboxes
            selected_mailbox = config.imap_folder  # Default
            
            if imap_label and found_label_mailbox:
                selected_mailbox = found_label_mailbox
                self.stdout.write(f"Using mailbox that matches label: {selected_mailbox}")
            
            # Select the appropriate mailbox
            self.stdout.write(f"Selecting mailbox: {selected_mailbox}")
            status, _ = mail.select(selected_mailbox)
            
            if status != 'OK':
                self.stdout.write(self.style.ERROR(f"Could not select mailbox: {selected_mailbox}"))
                # Fall back to the default
                self.stdout.write(f"Falling back to default mailbox: {config.imap_folder}")
                mail.select(config.imap_folder)
            
            # Search for unseen emails in the selected mailbox
            self.stdout.write(f"Searching for unseen emails in mailbox: {selected_mailbox}")
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != 'OK':
                self.stdout.write(self.style.ERROR(f"Error searching for emails: {status}"))
                return
            
            # Process emails
            message_ids = messages[0].split()
            self.stdout.write(f"Found {len(message_ids)} new email(s)")
            
            for msg_id in message_ids:
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                
                if status != 'OK':
                    self.stdout.write(self.style.WARNING(f"Error fetching email {msg_id}: {status}"))
                    continue
                
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Process the email
                self.process_email(email_message)
            
            # Logout
            mail.close()
            mail.logout()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"IMAP error: {str(e)}"))
            logger.exception("Error in IMAP connection")
    
    def check_local_folder(self, config):
        """Check emails from local folder"""
        if not config.local_email_folder or not os.path.exists(config.local_email_folder):
            self.stdout.write(self.style.ERROR(f"Local folder does not exist: {config.local_email_folder}"))
            return
        
        self.stdout.write(f"Checking local folder: {config.local_email_folder}")
        
        processed_files = []
        
        # Process files in main folder
        for filename in os.listdir(config.local_email_folder):
            if filename.endswith('.eml'):
                file_path = os.path.join(config.local_email_folder, filename)
                self.process_eml_file(file_path)
                processed_files.append(file_path)
        
        # Process files in subdirectories if configured
        if config.process_subdirectories:
            for root, dirs, files in os.walk(config.local_email_folder):
                if root == config.local_email_folder:
                    continue  # Skip main directory, already processed
                
                for filename in files:
                    if filename.endswith('.eml'):
                        file_path = os.path.join(root, filename)
                        self.process_eml_file(file_path)
                        processed_files.append(file_path)
        
        self.stdout.write(f"Processed {len(processed_files)} .eml file(s)")
        
        # Handle processed files
        if processed_files:
            if config.delete_after_processing:
                for file_path in processed_files:
                    try:
                        os.remove(file_path)
                        self.stdout.write(f"Deleted: {file_path}")
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Error deleting {file_path}: {str(e)}"))
            
            elif config.move_to_folder and os.path.exists(config.move_to_folder):
                for file_path in processed_files:
                    try:
                        filename = os.path.basename(file_path)
                        destination = os.path.join(config.move_to_folder, filename)
                        os.rename(file_path, destination)
                        self.stdout.write(f"Moved: {file_path} -> {destination}")
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Error moving {file_path}: {str(e)}"))
    
    def process_eml_file(self, file_path):
        """Process a single .eml file"""
        try:
            with open(file_path, 'rb') as file:
                email_message = email.message_from_binary_file(file)
                self.process_email(email_message)
                self.stdout.write(f"Processed: {file_path}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing {file_path}: {str(e)}"))
    
    def process_email(self, email_message):
        """Process an email message and save to database"""
        message_id = email_message.get('Message-ID', '').strip()
        if not message_id:
            # Generate a fallback unique identifier if message_id is missing
            message_id = f"generated-{uuid.uuid4()}"
            logger.warning(f"[WARNING] Email missing Message-ID. Generated fallback ID: {message_id}")

        try:
            # Extract headers
            subject = self.decode_email_header(email_message['Subject'])
            sender = self.decode_email_header(email_message['From'])
            recipient = self.decode_email_header(email_message['To'])

            # Extract date
            date_str = email_message['Date']
            if date_str:
                try:
                    # Parse the date
                    received_date = email.utils.parsedate_to_datetime(date_str)
                except Exception:
                    received_date = timezone.now()
            else:
                received_date = timezone.now()
                
            # Extract body first to use for content hash
            body_text, body_html = self.get_email_body(email_message)
            
            # Create a content hash from subject and body to detect similar emails
            content_to_hash = f"{subject}{body_text}"
            content_hash = hashlib.md5(content_to_hash.encode('utf-8')).hexdigest()

            # Check if email already exists by message_id (primary check)
            if Email.objects.filter(message_id=message_id).exists():
                self.stdout.write(f"[SKIP] Duplicate email detected by Message-ID: {subject} (Message-ID: {message_id})")
                logger.info(f"[SKIP] Duplicate email detected by Message-ID: {subject} (Message-ID: {message_id})")
                return False  # Indicate that the email was not processed
            
            # Secondary check by subject, sender and date (within a 10-minute window)
            # This catches forwarded emails or emails with regenerated Message-IDs
            ten_minutes = timezone.timedelta(minutes=10)
            date_min = received_date - ten_minutes
            date_max = received_date + ten_minutes
            
            # Check for very similar emails
            similar_emails = Email.objects.filter(
                subject=subject,
                sender=sender,
                received_date__gte=date_min,
                received_date__lte=date_max
            )
            
            if similar_emails.exists():
                # Log more details for the admin
                similar_count = similar_emails.count()
                similar_list = ", ".join([f"ID: {e.id}, Date: {e.received_date}" for e in similar_emails[:3]])
                
                self.stdout.write(f"[SKIP] Similar email(s) detected: {subject} - Found {similar_count} similar email(s): {similar_list}")
                logger.info(f"[SKIP] Similar email(s) detected: {subject} - Found {similar_count} similar email(s): {similar_list}")
                return False  # Indicate that the email was not processed
                
            # Third check: Examine recently processed emails for similar content
            # This can catch emails that were forwarded from different senders/dates
            # but contain the same essential content
            one_day_ago = timezone.now() - timezone.timedelta(days=1)
            
            # Check if there's a similar email with the same content in the last day
            # We only check recent emails to avoid performance issues with larger databases
            recent_emails = Email.objects.filter(created_at__gte=one_day_ago)
            
            for recent_email in recent_emails:
                recent_content = f"{recent_email.subject}{recent_email.body_text}"
                recent_hash = hashlib.md5(recent_content.encode('utf-8')).hexdigest()
                
                # If content is very similar (we can adjust the comparison as needed)
                if content_hash == recent_hash:
                    self.stdout.write(f"[SKIP] Email with identical content detected: {subject} matches ID: {recent_email.id}")
                    logger.info(f"[SKIP] Email with identical content detected: {subject} matches ID: {recent_email.id}")
                    return False  # Indicate that the email was not processed

            # Create email object
            email_obj = Email.objects.create(
                subject=subject,
                sender=sender,
                recipient=recipient,
                received_date=received_date,
                message_id=message_id,
                body_text=body_text,
                body_html=body_html,
                status='pending',
                has_attachments=False  # Will be updated if attachments are found
            )

            try:
                # Process attachments
                has_attachments = False
                attachment_count = 0
                
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        # Process only attachments
                        if "attachment" not in content_disposition:
                            continue
                            
                        # Extract attachment filename
                        filename = part.get_filename()
                        if not filename:
                            # Generate a filename if none is provided
                            ext = mimetypes.guess_extension(part.get_content_type())
                            if not ext:
                                ext = '.bin'  # Default extension
                            filename = f'attachment-{uuid.uuid4().hex}{ext}'
                        
                        # Clean up the filename
                        filename = os.path.basename(filename)
                        
                        # Get attachment content
                        payload = part.get_payload(decode=True)
                        if not payload:
                            logger.warning(f"Empty attachment payload for {filename} in email: {message_id}")
                            continue
                        
                        try:
                            # Extract Content-ID if present
                            content_id = part.get('Content-ID', '')
                            if content_id:
                                # Remove angle brackets if present
                                content_id = content_id.strip('<>')
                            
                            # Create attachment object
                            attachment = EmailAttachment(
                                email=email_obj,
                                filename=filename,
                                content_type=part.get_content_type(),
                                size=len(payload) if payload else 0,
                                content_id=content_id  # Store the Content-ID
                            )
                            
                            # Save attachment file
                            content_file = ContentFile(payload)
                            attachment.file.save(filename, content_file, save=True)
                            
                            # Log success
                            logger.info(f"Saved attachment: {filename} for email: {message_id}")
                            attachment_count += 1
                            has_attachments = True
                            
                        except Exception as attach_err:
                            logger.error(f"Error saving attachment {filename}: {str(attach_err)}", exc_info=True)
                
                # Update email has_attachments flag if attachments were found
                if has_attachments:
                    email_obj.has_attachments = True
                    email_obj.save(update_fields=['has_attachments'])
                    self.stdout.write(f"Saved {attachment_count} attachment(s) for email: {subject}")
                
            except Exception as e:
                logger.error(f"An error occurred: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"Error during email processing: {str(e)}"))
            finally:
                logger.info("Processing logic completed.")
                
            return email_obj
            
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error during email processing: {str(e)}"))
    
    def decode_email_header(self, header):
        """Decode email header"""
        if not header:
            return ""
        
        decoded_header = ""
        try:
            decoded_chunks = email.header.decode_header(header)
            for chunk, encoding in decoded_chunks:
                if isinstance(chunk, bytes):
                    if encoding:
                        decoded_chunk = chunk.decode(encoding)
                    else:
                        decoded_chunk = chunk.decode('utf-8', errors='replace')
                else:
                    decoded_chunk = str(chunk)
                decoded_header += decoded_chunk
            return decoded_header
        except Exception as e:
            logger.warning(f"Error decoding header: {str(e)}")
            return str(header)
    
    def get_email_body(self, email_message):
        """Extract body text and HTML from email message"""
        body_text = ""
        body_html = None
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get the payload
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                
                # Decode payload
                charset = part.get_content_charset()
                if charset:
                    try:
                        payload = payload.decode(charset)
                    except:
                        payload = payload.decode('utf-8', errors='replace')
                else:
                    payload = payload.decode('utf-8', errors='replace')
                
                # Capture text and html parts
                if content_type == "text/plain":
                    body_text += payload
                elif content_type == "text/html":
                    body_html = payload
        else:
            # Not multipart - get the content
            payload = email_message.get_payload(decode=True)
            if payload:
                charset = email_message.get_content_charset()
                if charset:
                    try:
                        payload = payload.decode(charset)
                    except:
                        payload = payload.decode('utf-8', errors='replace')
                else:
                    payload = payload.decode('utf-8', errors='replace')
                
                if email_message.get_content_type() == "text/html":
                    body_html = payload
                else:
                    body_text = payload
        
        return body_text, body_html