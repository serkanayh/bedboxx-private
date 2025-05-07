from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging
import datetime
from rest_framework.test import APIClient
from hotels.models import Hotel, Room, Market, MarketAlias
from .models import Email, AIModel, Prompt, EmailRow
from users.models import User
from emails.utils import ClaudeAnalyzer, check_for_attachment_references, body_mentions_attachment

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Email)
def auto_analyze_email(sender, instance, created, **kwargs):
    """
    Automatically analyze emails with AI when they are created or status updated to 'pending_analysis'.
    Also checks if the email body mentions attachments and processes them if needed.
    """
    # YENİ: Status değişikliği kontrolü - ya yeni oluşturulmuş ya da status pending_analysis olmalı
    if created or instance.status == 'pending_analysis':
        logger.info(f"Auto-analyzing email: {instance.id} - {instance.subject}")
        print(f"AUTO-ANALYZE: Starting analysis for email {instance.id} - {instance.subject}")

        try:
            # Eklerden bahsediliyor mu kontrol et
            has_attachment_references = check_for_attachment_references(instance.body_text)
            
            # Eğer e-posta hem eklere referans yapıyor hem de ekler varsa bunu logla
            # Bu durumda her halükarda ekleri işleyeceğiz
            if has_attachment_references:
                logger.info(f"EMAIL BODY MENTIONS ATTACHMENTS: Email {instance.id} body contains references to attachments.")
                print(f"AUTO-ANALYZE: Email {instance.id} body contains references to attachments ('ekte', 'attached', etc.)")

            # Öncelikle, attachments koleksiyonunu doğrudan kontrol edelim
            attachment_count = instance.attachments.count()

            # Ekler koleksiyonuyla has_attachments bayrağının tutarlı olduğundan emin ol
            if attachment_count > 0:
                attachment_list = list(instance.attachments.values_list('filename', flat=True))
                
                # DB'de ekler var ama email.has_attachments=False ise düzelt
                if not instance.has_attachments:
                    logger.warning(f"EMAIL FLAG MISMATCH: Email {instance.id} has has_attachments=False but {attachment_count} attachments in database. Fixing flag.")
                    instance.has_attachments = True
                    instance.save(update_fields=['has_attachments', 'updated_at'])
                    print(f"AUTO-ANALYZE: Fixed has_attachments flag for Email {instance.id}. Found {attachment_count} attachments: {', '.join(attachment_list)}")
                else:
                    logger.info(f"Email {instance.id} has {attachment_count} attachments: {', '.join(attachment_list)}")
            elif instance.has_attachments:
                # DB'de ekler yok ama email.has_attachments=True ise düzelt
                logger.warning(f"EMAIL FLAG MISMATCH: Email {instance.id} has has_attachments=True but no attachments in database. Fixing flag.")
                instance.has_attachments = False
                instance.save(update_fields=['has_attachments', 'updated_at'])
                print(f"AUTO-ANALYZE: Fixed has_attachments flag for Email {instance.id}. No attachments found.")
                
            # Devam eden işlemi kontrol et - işlenmiş veya işlenmekte olan e-postaları tekrar işleme
            if instance.status in ['processed', 'processing']:
                logger.info(f"Email {instance.id} already processed or being processed. Skipping auto-analysis.")
                return

            # Claude AI ile analiz etmeye başla
            logger.warning(f"AUTO-ANALYZE: Using model 'Claude' and prompt 'Claude_Promt'")
            analyzer = ClaudeAnalyzer()
            try:
                rows = analyzer.analyze_email(instance)
                if rows:
                    logger.info(f"Successfully auto-analyzed email {instance.id} using AI.")
                    print(f"AUTO-ANALYZE SUCCESS: Email {instance.id} analyzed successfully using AI")
                else:
                    logger.warning(f"AI analysis returned no results for email {instance.id}")
                    print(f"AUTO-ANALYZE WARNING: AI analysis returned no results for email {instance.id}")
            except Exception as e:
                logger.error(f"AI Analysis failed for email {instance.id}: {str(e)}", exc_info=True)
                print(f"AUTO-ANALYZE ERROR: AI analysis failed for email {instance.id}: {str(e)}")

            # ÖNEMLİ DEĞİŞİKLİK: Ek işlemleri için kontrol
            # Eğer instance.has_attachments true ise veya e-posta gövdesinde eklere atıf varsa, ekleri işle
            # Tüm durum ve bayraklar AI analizi yapıldıktan *sonra* tekrar kontrol edilir
            
            # E-postayı tekrar veritabanından al - bayraklar veya diğer alanlar değişmiş olabilir
            email_obj = Email.objects.get(pk=instance.id)
            
            # YENİ: Ekler varsa ya da e-posta metni ekleri belirtiyorsa, ekleri işle
            if email_obj.has_attachments or has_attachment_references:
                logger.info(f"ATTACHMENT PROCESSING TRIGGERED: Email {email_obj.id} has attachments={email_obj.has_attachments}, mentions attachments={has_attachment_references}")
                # Celery task'ı başlat
                from .tasks import process_email_attachments_task
                process_email_attachments_task.delay(email_obj.id)
                logger.info(f"ATTACHMENT PROCESSING STARTED: Scheduled attachment processing for email {email_obj.id}")
                print(f"AUTO-ANALYZE: Email {email_obj.id} has attachments or mentions them. Processing attachments.")
            else:
                logger.info(f"No attachments found for email {email_obj.id}. Continuing with body analysis only.")
                print(f"AUTO-ANALYZE: No attachments found for email {email_obj.id}. Continuing with body analysis only.")

            # Satırları eşleştirme işlemi
            if email_obj.rows.exists():
                # Batch eşleştirme işlemi başlat
                from .tasks import match_email_rows_batch_task
                logger.info(f"Scheduling BATCH matching task for email {email_obj.id} with {email_obj.rows.count()} rows.")
                print(f"AUTO-ANALYZE: Scheduling BATCH matching task for email {email_obj.id}.")
                match_email_rows_batch_task.delay(email_obj.id, list(email_obj.rows.values_list('id', flat=True)))
                logger.info(f"Matching task scheduled successfully for email {email_obj.id}.")
            
            # E-posta durumunu güncelle
            if email_obj.status == 'pending_analysis':  # Eğer status'u pending_analysis ise processing'e geçiş yap
                email_obj.status = 'processing'
                email_obj.save(update_fields=['status', 'updated_at'])
                logger.info(f"Email {email_obj.id} status set to 'processing'.")

        except Exception as e:
            logger.error(f"Error auto-analyzing email {instance.id}: {str(e)}", exc_info=True)
            print(f"AUTO-ANALYZE ERROR: Failed to auto-analyze email {instance.id}: {str(e)}")

# --- Removed matching logic from signal --- 
# This should be handled solely by the Celery task 
# @receiver(post_save, sender=EmailRow)
# def match_row_signal(sender, instance, created, **kwargs):
# ... (Removed the old matching logic that was here)
# --- End Removed matching logic --- 

# --- Signal to trigger matching task --- 
@receiver(post_save, sender=EmailRow)
def trigger_matching_task(sender, instance, created, **kwargs):
    if created and instance.status == 'matching': # Check if newly created and needs matching
        logger.info(f"[Signal] EmailRow {instance.id} created with status 'matching'. Triggering individual match task.")
        print(f"[Signal] EmailRow {instance.id} created with status 'matching'. Triggering task.")
        # You could potentially trigger an individual matching task here 
        # instead of relying only on the batch task from the email signal.
        # This might be useful if rows are created outside the main email processing flow.
        # from .tasks import match_single_email_row_task 
        # match_single_email_row_task.delay(instance.id)
        pass # For now, rely on the batch task triggered after all rows are created in the email signal