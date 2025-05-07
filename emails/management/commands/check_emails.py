import os
import email
import imaplib
import datetime
import logging
import mimetypes
import uuid
from email.header import decode_header
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from core.models import EmailConfiguration
from emails.models import Email, EmailRow, EmailAttachment
import time

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
        message_id = email_message.get('Message-ID', '').strip()
        if not message_id:
            # Generate a fallback unique identifier if message_id is missing
            message_id = f"generated-{uuid.uuid4()}"
            logger.warning(f"[WARNING] Email missing Message-ID. Generated fallback ID: {message_id}")

        # İlk olarak, bu message_id'ye sahip bir e-posta olup olmadığını kontrol et
        if Email.objects.filter(message_id=message_id).exists():
            self.stdout.write(f"[SKIP] Duplicate email detected: {message_id}")
            logger.info(f"[SKIP] Duplicate email detected: {message_id}")
            return False  # Indicate that the email was not processed

        try:
            # Temel e-posta bilgilerini hazırla
            subject = self.decode_email_header(email_message['Subject'])
            sender = self.decode_email_header(email_message['From'])
            recipient = self.decode_email_header(email_message['To'])

            # Tarihi ayarla
            date_str = email_message['Date']
            if date_str:
                try:
                    received_date = email.utils.parsedate_to_datetime(date_str)
                except Exception:
                    received_date = timezone.now()
            else:
                received_date = timezone.now()

            # E-posta gövdesini çıkar
            body_text, body_html = self.get_email_body(email_message)

            # Ekleri İŞLEME - Önce ekleri hazırlayıp sonra e-postayı oluşturacağız
            attachment_data = []  # attachment verilerini depolayacak liste
            has_attachments = False
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # Sadece ekleri işle
                    if "attachment" not in content_disposition:
                        continue
                        
                    # Dosya adını çıkar
                    filename = part.get_filename()
                    if not filename:
                        # Dosya adı yoksa, üret
                        ext = mimetypes.guess_extension(part.get_content_type())
                        if not ext:
                            ext = '.bin'  # Varsayılan uzantı
                        filename = f'attachment-{uuid.uuid4().hex}{ext}'
                    
                    # Dosya adını temizle
                    filename = os.path.basename(filename)
                    
                    # İçeriği al
                    payload = part.get_payload(decode=True)
                    if not payload:
                        logger.warning(f"Empty attachment payload for {filename} in email: {message_id}")
                        continue
                    
                    # Ek verilerini listeye ekle
                    attachment_data.append({
                        'filename': filename,
                        'content_type': part.get_content_type(),
                        'size': len(payload) if payload else 0,
                        'payload': payload
                    })
                    
                    has_attachments = True
            
            # ÖNEMLİ DEĞİŞİKLİK: İşlem sırasını değiştirdik - önce email objesi oluştur, sonra attachments, sonra da güncelle
            # E-posta nesnesini oluştur ama sinyaller tetiklenmemesi için has_attachments=False ile başlat
            email_obj = Email.objects.create(
                subject=subject,
                sender=sender,
                recipient=recipient,
                received_date=received_date,
                message_id=message_id,
                body_text=body_text,
                body_html=body_html,
                status='pending',
                has_attachments=False  # Başlangıçta FALSE olarak ayarla, böylece auto_analyze_email sinyali tetiklenmez
            )
            
            # Ekleri oluştur ve kaydet
            attachment_count = 0
            with transaction.atomic():
                for attach_data in attachment_data:
                    try:
                        # Ek nesnesini oluştur
                        attachment = EmailAttachment(
                            email=email_obj,
                            filename=attach_data['filename'],
                            content_type=attach_data['content_type'],
                            size=attach_data['size']
                        )
                        
                        # Dosyayı kaydet
                        content_file = ContentFile(attach_data['payload'])
                        attachment.file.save(attach_data['filename'], content_file, save=True)
                        
                        # Başarıyı logla
                        logger.info(f"Saved attachment: {attach_data['filename']} for email: {message_id}")
                        attachment_count += 1
                        
                    except Exception as attach_err:
                        logger.error(f"Error saving attachment {attach_data['filename']}: {str(attach_err)}", exc_info=True)
            
            # Tüm ekler kaydedildikten sonra email.has_attachments'i güncelle
            if attachment_count > 0:
                email_obj.has_attachments = True
                email_obj.save(update_fields=['has_attachments', 'updated_at'])
                self.stdout.write(f"Saved {attachment_count} attachment(s) for email: {subject}")
                
                # Veritabanına değişikliklerin yazılması için commit'i zorla
                transaction.commit()
                
                # Kısa bir bekleme ekle (opsiyonel)
                time.sleep(0.5)

            # Son olarak, AI analizi tetiklemek için status'u güncelleyerek auto_analyze_email sinyalini zorlayalım
            # Bu noktada has_attachments değeri doğru ve ekler tam kaydedilmiş durumda
            email_obj.refresh_from_db()  # Güncel verileri al
            logger.info(f"FINAL EMAIL STATE: Email {email_obj.id} has has_attachments={email_obj.has_attachments}, real attachment count={email_obj.attachments.count()}")
            
            # AI analizi için bir sinyal tetikle
            # (has_attachments doğru olduğunda, auto_analyze_email ekleri doğru işleyecek)
            if email_obj.status == 'pending':  # Sadece ilk kez için
                email_obj.status = 'pending_analysis'  # Farklı bir durum belirterek güncelleme yapalım
                email_obj.save(update_fields=['status', 'updated_at'])
                logger.info(f"Triggered AI analysis for email {email_obj.id} with has_attachments={email_obj.has_attachments}")
            
            # E-posta nesnesini döndür
            logger.info("Email processing logic completed successfully.")
            return email_obj
            
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error during email processing: {str(e)}"))
            return None
    
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