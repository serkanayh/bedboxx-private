import os
import email
import imaplib
import datetime
import logging
from email.header import decode_header
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from core.models import EmailConfiguration
from emails.models import Email, EmailRow, EmailAttachment
from django.core.files.base import ContentFile

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
            
            # Select mailbox
            mail.select(config.imap_folder)
            
            # Search for unseen emails
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
        message_id = email_message['Message-ID'] or '' # Ensure message_id is defined early
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
            
            # Check if email already exists
            if Email.objects.filter(message_id=message_id).exists():
                self.stdout.write(f"Email already exists: {subject}")
                return
            
            # Extract body
            body_text, body_html = self.get_email_body(email_message)
            
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
            
            # Process attachments
            attachments = []
            for part in email_message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                
                if part.get('Content-Disposition') is None:
                    continue
                
                filename = part.get_filename()
                if not filename:
                    continue
                
                # Decode filename if needed
                filename = self.decode_email_header(filename)
                
                # Save attachment to database
                content_type = part.get_content_type() or 'application/octet-stream'
                content = part.get_payload(decode=True)
                
                if content:
                    attachment = EmailAttachment(
                        email=email_obj,
                        filename=filename,
                        content_type=content_type,
                        size=len(content),
                        extracted_text=None # Initialize extracted_text
                    )
                    
                    # Save the actual file using ContentFile
                    try:
                        content_file = ContentFile(content, name=filename)
                        attachment.file.save(filename, content_file, save=False)
                        attachment.save()

                        # --- Trigger attachment processing task (on commit) ---
                        try:
                            from emails.tasks import process_email_attachments_task
                            # Wrap the task scheduling in transaction.on_commit
                            transaction.on_commit(lambda: (
                                process_email_attachments_task.delay(attachment.id),
                                logger.info(f"Scheduled attachment processing task for attachment ID: {attachment.id}"),
                                self.stdout.write(f"Scheduled processing for attachment: {filename}")
                            ))
                        except ImportError:
                            # Log import error immediately, it won't run on commit
                            logger.error("Could not import process_email_attachments_task. Task not scheduled.")
                            self.stdout.write(self.style.ERROR("Could not import attachment processing task."))
                        except Exception as task_error:
                            # Log scheduling error immediately
                            logger.error(f"Error preparing attachment task scheduling for ID {attachment.id}: {task_error}", exc_info=True)
                            self.stdout.write(self.style.ERROR(f"Error preparing task scheduling for attachment: {filename}"))
                        # --- End Trigger ---

                        attachments.append(attachment)
                        email_obj.has_attachments = True # Mark email as having attachments
                    except Exception as file_save_error:
                        logger.error(f"Error saving attachment file {filename} for email {email_obj.id}: {file_save_error}", exc_info=True)
                        self.stdout.write(self.style.ERROR(f"Error saving attachment file: {filename}"))
            
            # Update has_attachments flag if any were saved
            if email_obj.has_attachments:
                email_obj.save(update_fields=['has_attachments'])

            self.stdout.write(f"Saved email: {subject} with {len(attachments)} attachment(s)")
            
            # AI processing is handled by signal. 
            # The signal should now find the extracted_text in attachments if it needs it.
            
            # --- Check if Attachment Analysis is Needed (After Signal) --- 
            try:
                # Re-fetch the object to get the latest status potentially updated by the signal
                email_obj.refresh_from_db() 
                
                # --- Check for statuses indicating attachment check is needed --- 
                if email_obj.status in ['needs_attachment_check', 'needs_review_check_attachments'] and email_obj.has_attachments:
                    self.stdout.write(self.style.WARNING(f"Email {email_obj.id} (Status: {email_obj.status}) needs attachment check. Processing attachments..."))
                    logger.info(f"Email {email_obj.id} (Status: {email_obj.status}) needs attachment check. Processing attachments in command.")
                    
                    # Import here or at the top of the file
                    from emails.views import process_email_attachments 
                    from users.models import User # Import User model
                    
                    # Find a user to associate the log with (e.g., first superuser)
                    log_user = User.objects.filter(is_superuser=True).first()
                    
                    attachment_success = process_email_attachments(email_obj, log_user)
                    
                    if attachment_success:
                        self.stdout.write(self.style.SUCCESS(f"Attachment analysis succeeded for email {email_obj.id}."))
                        # Status should be updated within the function to 'processed'
                        # If status was 'needs_review_check_attachments', it should now be 'processed'
                        # (Assuming process_email_attachments sets status to 'processed' on success)
                    else:
                        self.stdout.write(self.style.WARNING(f"Attachment analysis failed or found no data for email {email_obj.id}."))
                        # If initial status was 'needs_review_check_attachments', keep it as 'needs_review' (user needs to review fallback + failed attach)
                        # If initial status was 'needs_attachment_check', mark as 'error'
                        if email_obj.status == 'needs_attachment_check':
                             email_obj.status = 'error'
                             email_obj.save(update_fields=['status', 'updated_at'])
                             logger.info(f"Attachment analysis failed for email {email_obj.id}. Status set to error.")
                        else: # Was 'needs_review_check_attachments'
                             # Keep status as needs_review - already set by signal
                             logger.info(f"Attachment analysis failed for email {email_obj.id}. Status remains needs_review.")
                        
            except Email.DoesNotExist:
                 logger.error(f"Email {email_obj.id} not found after saving, cannot check for attachment processing.")
            except ImportError:
                 logger.error("Could not import process_email_attachments or User model in check_emails command.")
            except Exception as attach_check_error:
                logger.error(f"Error checking/processing attachments for email {email_obj.id} in command: {attach_check_error}", exc_info=True)
                # Optionally mark as error if this check fails
                try:
                    email_obj.status = 'error'
                    email_obj.save(update_fields=['status', 'updated_at'])
                except: pass # Ignore errors during error marking
            # --- End Attachment Check --- 
            
        except Exception as process_error:
            self.stdout.write(self.style.ERROR(f"Error processing email: {str(process_error)}"))
            logger.exception(f"[check_emails] Error processing email {message_id}") # Added message_id
    
    def get_email_body(self, email_message):
        """Extract text and HTML body from an email message"""
        body_text = ""
        body_html = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True)
                        if body:
                            charset = part.get_content_charset()
                            if charset is None:
                                charset = 'utf-8'
                            
                            body = body.decode(charset, errors='replace')
                            
                            if content_type == "text/plain":
                                body_text += body
                            elif content_type == "text/html":
                                body_html += body
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Error extracting body: {str(e)}"))
        else:
            # Not multipart - get the payload directly
            try:
                body = email_message.get_payload(decode=True)
                if body:
                    charset = email_message.get_content_charset()
                    if charset is None:
                        charset = 'utf-8'
                    
                    body = body.decode(charset, errors='replace')
                    
                    if email_message.get_content_type() == "text/plain":
                        body_text = body
                    elif email_message.get_content_type() == "text/html":
                        body_html = body
                    else:
                        # Default to text
                        body_text = body
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error extracting body: {str(e)}"))
        
        return body_text, body_html
    
    def decode_email_header(self, header):
        """Decode email header"""
        if not header:
            return ""
            
        try:
            decoded_header = decode_header(header)
            result = ""
            
            for content, encoding in decoded_header:
                if isinstance(content, bytes):
                    if encoding:
                        result += content.decode(encoding, errors='replace')
                    else:
                        result += content.decode('utf-8', errors='replace')
                else:
                    result += str(content)
            
            return result
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error decoding header: {str(e)}"))
            return str(header)

    def extract_attachment_text(self, file_path, filename):
        """Extracts text from supported attachment types."""
        logger.debug(f"[extract_attachment_text] Called for: {filename} at path: {file_path}")
        extracted_text = ""
        _, file_extension = os.path.splitext(filename)
        file_extension = file_extension.lower()

        if file_extension == '.pdf':
            logger.debug(f"[extract_attachment_text] Processing PDF: {filename}")
            if not PYPDF_AVAILABLE:
                logger.error("[extract_attachment_text] Cannot extract text from PDF: pypdf library not installed.")
                return None
            try:
                with open(file_path, 'rb') as f:
                    reader = PdfReader(f)
                    logger.debug(f"[extract_attachment_text] PDF {filename} opened. Pages: {len(reader.pages)}")
                    for i, page in enumerate(reader.pages):
                        try:
                           page_text = page.extract_text()
                           if page_text:
                               extracted_text += page_text + "\n"
                           # logger.debug(f"[extract_attachment_text] Extracted text from page {i+1} of {filename}") # Too verbose potentially
                        except Exception as page_extract_error:
                             logger.warning(f"[extract_attachment_text] Error extracting text from page {i+1} in PDF {filename}: {page_extract_error}")
                final_text = extracted_text.strip()
                logger.info(f"[extract_attachment_text] Finished PDF processing for {filename}. Extracted length: {len(final_text)}")
                return final_text if final_text else None
            except Exception as pdf_error:
                logger.error(f"[extract_attachment_text] Error reading PDF file {filename}: {pdf_error}", exc_info=True)
                return None
        
        elif file_extension in ['.txt', '.csv', '.html', '.xml']: 
             logger.debug(f"[extract_attachment_text] Processing text file: {filename}")
             try:
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: 
                     content = f.read()
                     logger.info(f"[extract_attachment_text] Finished text file processing for {filename}. Extracted length: {len(content)}")
                     return content
             except Exception as txt_error:
                 logger.error(f"[extract_attachment_text] Error reading text file {filename}: {txt_error}", exc_info=True)
                 return None

        # TODO: Add support for other formats like DOCX using python-docx
        
        else:
            logger.info(f"[extract_attachment_text] Text extraction not supported for file type: {file_extension} ({filename})")
            return None 