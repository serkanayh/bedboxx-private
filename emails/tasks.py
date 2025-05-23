from celery import shared_task
from django.core.management import call_command
import logging
import os
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Email, EmailRow, EmailAttachment, AIModel, Prompt, RoomTypeMatch, RoomTypeReject
from hotels.models import Hotel, Room, Market, JuniperContractMarket, RoomTypeGroup, RoomTypeVariant
from difflib import SequenceMatcher
from thefuzz import fuzz
from core.ai_analyzer import ClaudeAnalyzer
from django.db import transaction
import unicodedata

logger = logging.getLogger(__name__)

def parse_date_range(date_range):
    """
    Parse a date range string in format 'YYYY-MM-DD - YYYY-MM-DD'
    Returns tuple of (start_date, end_date) as datetime.date objects
    """
    try:
        if ' - ' in date_range:
            parts = date_range.split(' - ')
            start_date = datetime.strptime(parts[0], '%Y-%m-%d').date()
            end_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            return start_date, end_date
    except:
        pass
    
    # Default dates if parsing fails
    today = timezone.now().date()
    return today, today + timedelta(days=7)

def similar(a, b):
    """Calculate string similarity ratio between 0-1"""
    if not a or not b:
        return 0
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

def word_overlap_score(email_name, juniper_name):
    """Calculate score based on how many words from email_name appear in juniper_name"""
    if not email_name or not juniper_name:
        return 0
    
    email_words = [w.lower() for w in str(email_name).split() if len(w) > 2]
    juniper_name_lower = str(juniper_name).lower()
    
    if not email_words:
        return 0
    
    exact_matches = sum(1 for word in email_words if word in juniper_name_lower.split())
    substring_matches = sum(1 for word in email_words if word in juniper_name_lower)
    
    match_ratio = exact_matches / len(email_words)
    
    if exact_matches == 0 and substring_matches > 0:
        match_ratio = 0.3 * (substring_matches / len(email_words))
        
    if exact_matches == len(email_words):
        return 0.95
    
    if email_name.lower() in juniper_name_lower:
        return 0.9
        
    return match_ratio

@shared_task(name="emails.tasks.check_emails_task")
def check_emails_task():
    """Celery task to run the check_emails management command."""
    try:
        logger.info("Running check_emails management command via Celery task.")
        call_command('check_emails')
        logger.info("check_emails command finished successfully.")
    except Exception as e:
        logger.error(f"Error running check_emails command via Celery: {str(e)}", exc_info=True)
        # You might want to raise the exception again depending on your error handling strategy
        # raise 

@shared_task(name="emails.tasks.process_email_attachments_task")
def process_email_attachments_task(email_id):
    """
    Celery task to process all attachments of an email using the unified ClaudeAnalyzer.
    Arg:
        email_id: The primary key of the Email to process attachments for.
    """
    logger.info(f"Starting attachment processing task for Email ID: {email_id}")
    try:
        # Fetch the Email object
        email = Email.objects.get(pk=email_id)
        
        # Check if email has attachments
        if not email.has_attachments:
            logger.warning(f"Email {email_id} has no attachments marked. Checking for actual attachments...")
            attachment_count = email.attachments.count()
            if attachment_count == 0:
                logger.warning(f"Email {email_id} has no attachments to process. Marking as processed_nodata.")
                email.status = 'processed_nodata'
                email.save(update_fields=['status', 'updated_at'])
                return False
            else:
                # Found attachments but has_attachments flag was False - update it
                email.has_attachments = True
                email.save(update_fields=['has_attachments'])
                logger.info(f"Updated has_attachments flag for Email {email_id} - found {attachment_count} attachments")

        # --- YENİ: E-posta gövdesinden zaten veri çıkarılmış mı kontrol et ---
        existing_rows = EmailRow.objects.filter(email=email, extracted_from_attachment=False, ai_extracted=True).exists()
        if existing_rows:
            logger.info(f"E-posta {email_id} için gövdeden başarılı veri çıkarılmış. Ek analizi iptal ediliyor.")
            return True
        # --- YENİ SON ---

        # --- Fetch Active AI Model --- 
        active_model = AIModel.objects.filter(active=True).first()
        if not active_model or not active_model.api_key:
             logger.error(f"No active AI model with API key found. Cannot perform AI attachment analysis for email {email_id}.")
             email.status = 'error' 
             email.save(update_fields=['status', 'updated_at'])
             return False
             
        # --- Initialize the UNIFIED Analyzer --- 
        analyzer = ClaudeAnalyzer(api_key=active_model.api_key)
        if not analyzer.claude_client: # Check if client initialized
             logger.error(f"Failed to initialize ClaudeAnalyzer for email {email_id}. Aborting attachment task.")
             email.status = 'error'
             email.save(update_fields=['status', 'updated_at'])
             return False
        # --- End Initialize --- 
        
        created_row_ids = []
        analysis_results_store = email.attachment_analysis_results or {} # Load existing results
        
        # Get all attachments for this email
        attachments = email.attachments.all()
        if not attachments:
            logger.warning(f"No attachments found for Email {email_id} even though has_attachments is True.")
            email.status = 'processed_nodata'
            email.save(update_fields=['status', 'updated_at'])
            return False
            
        # Process each attachment
        for attachment in attachments:
            logger.info(f"Processing attachment: {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email_id})")
            
            # Check if attachment should be processed based on filename
            # SADECE PDF ve Word dosyalarını işle, diğerlerini atla
            allowed_extensions = ['.pdf', '.doc', '.docx']
            
            # Use the model's file_extension property which handles MIME encoding correctly
            attachment_ext = attachment.file_extension
            logger.debug(f"Attachment extension detected: '{attachment_ext}' for {attachment.filename}")
            
            if attachment_ext not in allowed_extensions:
                logger.info(f"Skipping non-PDF/Word attachment: {attachment.filename} (extension: {attachment_ext})")
                analysis_results_store[str(attachment.id)] = {'skipped': f'Non-PDF/Word file skipped (extension: {attachment_ext})'}
                continue
                
            # Skip if filename indicates it's a stop sale chart summary (not individual stop sales)
            if is_stop_sale_chart_file(attachment.filename):
                logger.info(f"Skipping stop sale chart file: {attachment.filename}")
                analysis_results_store[str(attachment.id)] = {'skipped': 'Stop sale chart file identified'}
                continue
            
            # 1. Extract Text using the method from ClaudeAnalyzer
            if not attachment.file or not os.path.exists(attachment.file.path):
                error_msg = f"Attachment file not found or path is invalid for Attachment ID {attachment.id}"
                logger.error(error_msg)
                analysis_results_store[str(attachment.id)] = {'error': error_msg}
                continue

            extracted_text, error_msg = analyzer.extract_text_from_attachment(attachment.file.path)
                
            # --- SAVE extracted text to the attachment model --- 
            if extracted_text and not error_msg:
                try:
                    attachment.extracted_text = extracted_text
                    attachment.save(update_fields=['extracted_text']) # Only update this field
                    logger.info(f"Saved extracted text ({len(extracted_text)} chars) to Attachment ID {attachment.id}")
                except Exception as save_error:
                     logger.error(f"Error saving extracted text to attachment {attachment.id}: {save_error}", exc_info=True)
            # --- END SAVE --- 
            
            if error_msg:
                logger.error(f"Failed to extract text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email_id}): {error_msg}")
                analysis_results_store[str(attachment.id)] = {'error': error_msg}
                continue
            
            if not extracted_text:
                logger.warning(f"No text extracted from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email_id}). Skipping analysis.")
                analysis_results_store[str(attachment.id)] = {'error': 'No text content extracted'}
                continue
            
            # 2. Analyze Extracted Text with AI
            logger.info(f"Analyzing extracted text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email_id})")
            analysis_result = analyzer.analyze_content(extracted_text)
            analysis_results_store[str(attachment.id)] = analysis_result # Store raw result
            
            if analysis_result.get('error'):
                logger.error(f"AI analysis failed for extracted text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email_id}): {analysis_result['error']}")
                continue
            
            # 3. Process Rows from Successful Analysis
            rows_data = analysis_result.get('rows', [])
            if not rows_data:
                logger.warning(f"AI analysis for {attachment.filename} (Attachment ID: {attachment.id}) successful but returned no rows after processing.")
                continue
                
            logger.info(f"AI analysis for {attachment.filename} yielded {len(rows_data)} rows.")
            initial_row_count = len(created_row_ids) # Store count before loop
            
            # --- YENİ: E-posta tarihini al ---
            mail_date = email.received_date.date()
            # --- YENİ SON ---
            
            for row_data in rows_data:
                start_date_str = row_data.get('start_date')
                end_date_str = row_data.get('end_date')
                
                if not (isinstance(start_date_str, str) and isinstance(end_date_str, str)):
                     logger.error(f"Invalid date format received after post-processing for row {row_data} from attachment {attachment.id}. Skipping row.")
                     continue
                
                # --- YENİ: Tarih analizi ve aynı gün kontrolü ---
                try:
                    # Farklı formattaki tarihleri dene
                    try:
                        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
                        except ValueError:
                            start_date = None
                            
                    try:
                        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
                        except ValueError:
                            end_date = None
                            
                    # E-posta tarihi ile aynı tarihleri kontrol et ve atla
                    # if (start_date == mail_date and end_date == mail_date) or (start_date == mail_date and end_date is None):
                    #     logger.warning(f"Skipping row with same date as email: {mail_date}. Start: {start_date}, End: {end_date}")
                    #     continue
                except Exception as date_err:
                    logger.error(f"Error checking dates: {date_err}. Using original dates.")
                # --- YENİ SON ---
                     
                try:
                    email_row = EmailRow.objects.create(
                        email=email,
                        hotel_name=row_data.get('hotel_name', 'Unknown'),
                        room_type=row_data.get('room_type', 'Unknown'),
                        start_date=start_date_str,
                        end_date=end_date_str,
                        sale_type=row_data.get('sale_type', 'stop'),
                        status='matching', 
                        ai_extracted=False,
                        extracted_from_attachment=True,
                        source_attachment=attachment
                    )
                    created_row_ids.append(email_row.id)
                    logger.info(f"Created EmailRow {email_row.id} from attachment {attachment.filename} (ID: {attachment.id}) for email {email_id}")

                    market_names_from_ai = row_data.get('markets', [])
                    market_objects = []
                    if market_names_from_ai:
                        for market_name in market_names_from_ai:
                            market_name_clean = market_name.strip()
                            try:
                                market_obj = Market.objects.get(name__iexact=market_name_clean)
                                market_objects.append(market_obj)
                            except Market.DoesNotExist:
                                logger.warning(f"Market name '{market_name_clean}' from AI analysis (Attachment {attachment.id}) not found in DB. Skipping for row {email_row.id}.")
                        
                        if market_objects:
                            email_row.markets.set(market_objects)
                            logger.debug(f"Set markets {market_objects} for EmailRow {email_row.id}")
                    else:
                         logger.warning(f"No market names provided by AI for row {email_row.id} (Attachment {attachment.id}). Leaving markets empty.")

                except Exception as e:
                    logger.error(f"Error creating EmailRow or setting markets from attachment AI data {row_data} (Attachment ID: {attachment.id}, Email ID: {email_id}): {e}", exc_info=True)

        # If any rows were created, update the email object and delete any body-extracted rows
        if created_row_ids:
            logger.info(f"Created {len(created_row_ids)} rows from all attachments for email {email_id}")
            try:
                with transaction.atomic():
                    deleted_count, deleted_details = EmailRow.objects.filter(
                        email=email,
                        extracted_from_attachment=False
                    ).delete()
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} rows previously extracted from the email body: {deleted_details}")
                else:
                    logger.info(f"No body-extracted rows found to delete for email {email_id}.")
            except Exception as delete_error:
                 logger.error(f"Error deleting body-extracted rows for email {email_id}: {delete_error}", exc_info=True)
                
        # Save attachment analysis results to the email object
        if analysis_results_store:
             email.attachment_analysis_results = analysis_results_store
             logger.debug(f"Stored/Updated attachment analysis results for email {email_id}")
             email.save(update_fields=['attachment_analysis_results', 'updated_at'])

        # If any rows were created, schedule matching task
        if created_row_ids:
            logger.info(f"Attachment analysis for email {email_id} finished. Scheduling BATCH matching for {len(created_row_ids)} newly created rows.")
            try:
                match_email_rows_batch_task.delay(email.id, created_row_ids)
                if email.status not in ['processing', 'processed', 'error']:
                    email.status = 'processing'
                    email.save(update_fields=['status', 'updated_at'])
            except Exception as task_error:
                 logger.error(f"CRITICAL: Error scheduling matching task for email {email_id}: {task_error}", exc_info=True)
                 email.status = 'error'
                 email.save(update_fields=['status', 'updated_at'])
            logger.info(f"Attachment processing task finished successfully for Email ID: {email_id}. {len(created_row_ids)} rows created and matching scheduled.")
            return True
        else:
            logger.info(f"Attachment processing task finished for Email ID: {email_id}. No new rows created.")
            email.status = 'processed_nodata'
            email.save(update_fields=['status', 'updated_at'])
            return False

    except Email.DoesNotExist:
        logger.error(f"Attachment processing task failed: Email ID {email_id} not found.")
        return False
    except Exception as e:
        logger.error(f"Attachment processing task failed unexpectedly for Email ID: {email_id}. Error: {str(e)}", exc_info=True)
        try:
            email = Email.objects.get(pk=email_id)
            email.status = 'error'
            email.save(update_fields=['status', 'updated_at'])
            logger.info(f"Marked email {email_id} as error due to attachment task failure.")
        except Email.DoesNotExist:
            logger.warning(f"Could not mark email as error: Email {email_id} not found during error handling.")
        except Exception as save_error:
            logger.error(f"Failed to mark email as error after attachment task failure (Email ID: {email_id}): {save_error}", exc_info=True)
        return False

def is_stop_sale_chart_file(filename):
    """
    Check if a filename indicates it's a file that should not be processed for individual stop sale entries.
    This includes:
    - Stop sale chart/summary files
    - Reports and statistics files
    - Pattern or graph visualizations
    - Other non-individual entry files
    """
    filename_lower = filename.lower()
    
    # File extension check - certain Excel files are more likely to be reports/summaries
    if filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
        return True
    
    # Patterns indicating summary/chart/report files that shouldn't be analyzed
    patterns = [
        # Stop sale charts/reports
        'stop sale chart', 'stopsale chart', 'stop-sale-chart', 'chart of stop', 'report of stop',
        'stopreport', 'stop report', 'stop_report', 'chart', 'summary', 'overview',
        
        # Pattern indicators
        'pattern', 'graph', 'visual', 'tableau', 'dashboard',
        
        # General report indicators
        'report', 'stats', 'statistics', 'analysis', 'weekly', 'monthly', 'daily',
        'overview', 'summary', 'recap', 'özet', 'rapor',
        
        # Files with specific hotel codes in filename (likely standardized reports)
        '_swn_', '_kemer_', '_alb_', '_antalya_',
        
        # Files containing dates in standard formats (YYYYMMDD, DDMMYYYY) are often reports
        '_20', '-20', '/20'  # Year prefix for date formats
    ]
    
    for pattern in patterns:
        if pattern in filename_lower:
            return True
            
    return False

HOTEL_FUZZY_MATCH_THRESHOLD = 75  # 85'den 75'e düşürüldü
ROOM_FUZZY_MATCH_THRESHOLD = 80   # 90'dan 80'e düşürüldü

@shared_task(name="emails.tasks.match_email_rows_batch_task")
def match_email_rows_batch_task(email_id, row_ids):
    """Celery task to match hotels and rooms for a batch of EmailRows."""
    logger.info(f"Starting matching task for Email ID: {email_id}, Row IDs: {row_ids}")
    
    processed_count = 0
    not_found_count = 0
    skipped_count = 0
    
    try:
        email = Email.objects.get(pk=email_id)
        rows_to_process = EmailRow.objects.filter(id__in=row_ids, email=email)
        all_hotels = list(Hotel.objects.all())
        all_rooms_by_hotel = {h.id: list(Room.objects.filter(hotel=h)) for h in all_hotels}
        
        # --- Email received date validation ---
        email_received_date = email.received_date.date() if email.received_date else None
        
        # --- First pass: Filter out rows with problematic dates ---
        if email_received_date:
            rows_to_skip = []
            for row in rows_to_process:
                # Skip rules where BOTH start AND end date match email received date
                if row.start_date == email_received_date and row.end_date == email_received_date:
                    logger.warning(f"Row {row.id}: BOTH start and end dates ({row.start_date}/{row.end_date}) match email received date. Skipping rule.")
                    rows_to_skip.append(row.id)
                    skipped_count += 1
                    
                # Check for date source if available in extra_data
                if hasattr(row, 'extra_data') and row.extra_data:
                    try:
                        extra_data = row.extra_data
                        if isinstance(extra_data, str):
                            import json
                            extra_data = json.loads(extra_data)
                            
                        date_source = extra_data.get('date_source', {})
                        
                        # Skip if date is from subject only
                        if (isinstance(date_source, dict) and 
                            date_source.get('from_subject', False) and 
                            not date_source.get('from_body', False)):
                            logger.warning(f"Row {row.id}: Date is from subject line only. Skipping rule.")
                            if row.id not in rows_to_skip:
                                rows_to_skip.append(row.id)
                                skipped_count += 1
                                
                        # Skip if date_source is explicitly marked as 'subject_only'
                        elif date_source == 'subject_only':
                            logger.warning(f"Row {row.id}: Date is marked as subject_only. Skipping rule.")
                            if row.id not in rows_to_skip:
                                rows_to_skip.append(row.id)
                                skipped_count += 1
                    except Exception as e:
                        logger.error(f"Error checking date source for row {row.id}: {e}")
            
            # Filter out the rows to skip
            if rows_to_skip:
                rows_to_process = rows_to_process.exclude(id__in=rows_to_skip)
                logger.info(f"Skipped {skipped_count} rows due to date validation issues")
        
        # --- Learned email-to-hotel mapping check ---
        learned_hotel = None
        sender_email = email.sender
        
        # Extract email address from sender field
        if '<' in sender_email and '>' in sender_email:
            # Format: "Name Surname <email@domain.com>"
            sender_email = sender_email.split('<')[1].split('>')[0].strip()
        elif '@' in sender_email:
            # Format: email@domain.com
            sender_email = sender_email.strip()
            
        # Check for learned mappings with a lower threshold
        from .models import EmailHotelMatch
        try:
            # Find mapping with highest confidence score
            learned_match = EmailHotelMatch.objects.filter(
                sender_email=sender_email
            ).order_by('-confidence_score', '-match_count').first()
            
            # Lower threshold from 80 to 60 for better utilization
            if learned_match and learned_match.confidence_score >= 60:
                learned_hotel = learned_match.hotel
                logger.info(f"Found learned mapping: Sender {sender_email} -> Hotel {learned_hotel.juniper_hotel_name} (Confidence: {learned_match.confidence_score})")
        except Exception as e:
            logger.error(f"Error checking learned mappings: {str(e)}")
        # --- End of learned mapping check ---
        
        for row in rows_to_process:
            logger.info(f"Matching row {row.id}: Hotel='{row.hotel_name}', Room='{row.room_type}'")
            
            hotel_name = row.hotel_name
            room_type_input = row.room_type
            
            # --- Apply learned hotel mapping if available ---
            if learned_hotel:
                # Store original hotel name for comparison
                original_hotel_name = hotel_name
                
                # Calculate similarity between actual hotel name and learned mapping hotel
                similarity_score = fuzz.token_set_ratio(str(original_hotel_name).lower(), 
                                                      str(learned_hotel.juniper_hotel_name).lower())
                
                # Öncelikle diğer tüm otellerle benzerlik hesapla ve daha yüksek benzerlik skoru olan otel var mı kontrol et
                best_direct_hotel = None
                best_direct_score = 0
                
                for hotel in all_hotels:
                    juniper_hotel_lower = str(hotel.juniper_hotel_name).lower()
                    current_score = fuzz.token_set_ratio(str(original_hotel_name).lower(), juniper_hotel_lower)
                    
                    # Give full score for exact match
                    if str(original_hotel_name).lower() == juniper_hotel_lower:
                        current_score = 100
                    
                    if current_score > best_direct_score:
                        best_direct_score = current_score
                        best_direct_hotel = hotel
                
                # Eğer doğrudan eşleşme puanı çok yüksekse (90+) veya learned hotel puanından belirgin şekilde yüksekse, 
                # learned mapping yerine doğrudan eşleşmeyi kullan
                if best_direct_score >= 90 or (best_direct_score > similarity_score + 20):
                    logger.info(f"  [Hotel Match] Row {row.id}: Overriding learned mapping: '{original_hotel_name}' -> '{best_direct_hotel.juniper_hotel_name}' (Direct match: {best_direct_score}% > Learned: {similarity_score}%)")
                    row.juniper_hotel = best_direct_hotel
                    row.hotel_match_score = best_direct_score
                    best_hotel_match = best_direct_hotel
                    best_hotel_score = best_direct_score
                else:
                    # Learned mapping kullan
                    row.juniper_hotel = learned_hotel
                    row.hotel_match_score = max(similarity_score, 85)  # Minimum 85% confidence for learned mappings
                    logger.info(f"  [Hotel Match] Row {row.id}: '{original_hotel_name}' -> '{learned_hotel.juniper_hotel_name}' (Learned Mapping, Similarity: {similarity_score}%)")
                    best_hotel_match = learned_hotel
                    best_hotel_score = row.hotel_match_score
            else:
                # If no learned mapping exists, use normal matching process
                best_hotel_match = None
                best_hotel_score = 0

                # Skip normalization, use direct string matching
                input_hotel_lower = str(hotel_name).lower()
                
                if not input_hotel_lower:
                     logger.warning(f"Row {row.id}: Empty hotel name received. Skipping hotel match.")
                     row.status = 'hotel_not_found'
                     row.save(update_fields=['status'])
                     not_found_count += 1
                     continue

                for hotel in all_hotels:
                    juniper_hotel_lower = str(hotel.juniper_hotel_name).lower()
                    
                    # Direct similarity score (fuzz)
                    current_score = fuzz.token_set_ratio(input_hotel_lower, juniper_hotel_lower)
                    
                    # Give full score for exact match
                    if input_hotel_lower == juniper_hotel_lower:
                        current_score = 100
                    
                    if current_score > best_hotel_score:
                        best_hotel_score = current_score
                        best_hotel_match = hotel
            
            # Auto-match hotel if good enough
            # Use a lower threshold for task (HOTEL_FUZZY_MATCH_THRESHOLD) compared to web UI
            if best_hotel_match and best_hotel_score >= HOTEL_FUZZY_MATCH_THRESHOLD:
                logger.info(f"  [Hotel Match] Row {row.id}: Matched '{hotel_name}' -> '{best_hotel_match.juniper_hotel_name}' (Score: {best_hotel_score}%)")
                row.juniper_hotel = best_hotel_match
                row.hotel_match_score = best_hotel_score
                
                # Otel otomatik eşleşti, şimdi oda eşleştirme kısmına geçelim
                # Oda tipini işle ve odaları eşleştir
                # "All Room" veya "All Rooms" durumunda özel işlem
                all_room_keywords = ['all room', 'all rooms', 'all room types', 'tüm odalar']
                input_room_type = str(room_type_input).strip()
                
                if not input_room_type:
                    logger.warning(f"  [Room Match] Row {row.id}: Empty room type, using ALL ROOM.")
                    input_room_type = "ALL ROOM"
                
                if input_room_type.lower() in all_room_keywords:
                    # Özel "All Room" durumu - odaları eşleştirmeye gerek yok
                    logger.info(f"  [Room Match] Row {row.id}: ALL ROOM type detected. Skipping room matching.")
                    row.status = 'pending'
                    row.save(update_fields=['juniper_hotel', 'hotel_match_score', 'status']) 
                    processed_count += 1
                    continue
                
                # Diğer oda tipleri için normal eşleşme:
                
                # 1. İlk olarak RoomTypeGroup eşleşmesini deneyelim
                # (a) Tam eşleşme
                room_type_group = RoomTypeGroup.objects.filter(
                    hotel=best_hotel_match,
                    name__iexact=input_room_type
                ).first()
                
                # (b) Eğer tam eşleşme bulunamazsa, kapsama eşleşmesi deneyelim
                if not room_type_group:
                    room_type_group = RoomTypeGroup.objects.filter(
                        hotel=best_hotel_match,
                        name__icontains=input_room_type
                    ).first()
                
                # (c) Hala bulunamazsa, oda tipi bir grup adını içeriyor mu kontrol et
                if not room_type_group:
                    all_groups = RoomTypeGroup.objects.filter(hotel=best_hotel_match)
                    for group in all_groups:
                        if group.name.upper() in input_room_type.upper():
                            room_type_group = group
                            break
                
                # Oda tipi grubu bulduk mu?
                if room_type_group:
                    logger.info(f"  [Room Match] Row {row.id}: Found room type GROUP match: '{input_room_type}' -> Group: '{room_type_group.name}'")
                    # Grup bulundu, şimdi bu gruba ait tüm varyantları eşleştirelim
                    
                    # Gruptaki tüm varyantları al
                    variants = room_type_group.variants.all()
                    if not variants.exists():
                        logger.warning(f"  [Room Match] Row {row.id}: Room type group '{room_type_group.name}' has no variants.")
                        
                        # Grup varyantı yoksa doğrudan fuzzy match deneyelim
                        best_room_match = None
                        best_room_score = 0
                        for room in all_rooms_by_hotel.get(best_hotel_match.id, []):
                            # Direct similarity score (token_set_ratio is more flexible than ratio)
                            current_score = fuzz.token_set_ratio(input_room_type.lower(), room.juniper_room_type.lower())
                            
                            # Give full score for exact match 
                            if input_room_type.lower() == room.juniper_room_type.lower():
                                current_score = 100
                                
                            if current_score > best_room_score:
                                best_room_score = current_score
                                best_room_match = room
                                
                        if best_room_match and best_room_score >= ROOM_FUZZY_MATCH_THRESHOLD:
                            logger.info(f"  [Room Match] Row {row.id}: Fallback to direct match. Matched '{input_room_type}' -> '{best_room_match.juniper_room_type}' (Score: {best_room_score}%)")
                            row.juniper_rooms.add(best_room_match)
                            row.room_match_score = best_room_score
                            row.status = 'pending'
                        else:
                            logger.warning(f"  [Room Match] Row {row.id}: Could not find matching room for '{input_room_type}' in hotel '{best_hotel_match.juniper_hotel_name}'")
                            row.status = 'room_not_found'
                    else:
                        # Varyantlardan oda eşleşmelerini bul
                        matched_rooms = []
                        for variant in variants:
                            # Varyant adını içeren odaları bul
                            variant_rooms = Room.objects.filter(
                                hotel=best_hotel_match,
                                juniper_room_type__icontains=variant.variant_room_name
                            )
                            # Bulunan odaları listeye ekle
                            if variant_rooms.exists():
                                matched_rooms.extend(variant_rooms)
                                
                        if matched_rooms:
                            # Tekrarlanan odaları kaldır
                            unique_matched_rooms = list(set(matched_rooms))
                            
                            # Tüm eşleşen odaları ekle
                            row.juniper_rooms.set(unique_matched_rooms)
                            row.room_match_score = 100  # Grup eşleşmesi olduğu için yüksek skor ver
                            row.status = 'pending'
                            logger.info(f"  [Room Match] Row {row.id}: Matched {len(unique_matched_rooms)} rooms from group '{room_type_group.name}'")
                            
                            # RoomTypeMatch kayıtlarını oluştur (öğrenen sistem için)
                            for room in unique_matched_rooms:
                                RoomTypeMatch.objects.get_or_create(
                                    email_room_type=input_room_type, 
                                    juniper_room=room
                                )
                        else:
                            # Grup varyantları var ama eşleşen oda yok
                            logger.warning(f"  [Room Match] Row {row.id}: No matching rooms found for variants in group '{room_type_group.name}'")
                            row.status = 'room_not_found'
                else:
                    # Grup eşleşmedi, doğrudan fuzzy match deneyelim
                    best_room_match = None
                    best_room_score = 0
                    for room in all_rooms_by_hotel.get(best_hotel_match.id, []):
                        # Direct similarity score (token_set_ratio is more flexible than ratio)
                        current_score = fuzz.token_set_ratio(input_room_type.lower(), room.juniper_room_type.lower())
                        
                        # Give full score for exact match 
                        if input_room_type.lower() == room.juniper_room_type.lower():
                            current_score = 100
                            
                        if current_score > best_room_score:
                            best_room_score = current_score
                            best_room_match = room
                            
                    if best_room_match and best_room_score >= ROOM_FUZZY_MATCH_THRESHOLD:
                        # Get related room suggestions to capture variants
                        from emails.views import get_room_suggestions
                        _, room_suggestions, _ = get_room_suggestions(input_room_type, best_hotel_match)
                        
                        # If we got multiple suggestions from room group variants, use all of them
                        if len(room_suggestions) > 1:
                            logger.info(f"  [Room Match] Row {row.id}: Found multiple room suggestions - likely group variants. Matching all {len(room_suggestions)} rooms")
                            row.juniper_rooms.set(room_suggestions)
                            row.room_match_score = best_room_score
                            row.status = 'pending'
                            
                            # Create RoomTypeMatch records for all matched rooms
                            for room in room_suggestions:
                                RoomTypeMatch.objects.get_or_create(
                                    email_room_type=input_room_type, 
                                    juniper_room=room
                                )
                        else:
                            # Just match the single best room
                            logger.info(f"  [Room Match] Row {row.id}: Matched '{input_room_type}' -> '{best_room_match.juniper_room_type}' (Score: {best_room_score}%)")
                            row.juniper_rooms.add(best_room_match)
                            row.room_match_score = best_room_score
                            row.status = 'pending'
                            
                            # RoomTypeMatch kaydı oluştur (öğrenen sistem için)
                            RoomTypeMatch.objects.get_or_create(
                                email_room_type=input_room_type, 
                                juniper_room=best_room_match
                            )
                    else:
                        logger.warning(f"  [Room Match] Row {row.id}: Could not find matching room for '{input_room_type}' in hotel '{best_hotel_match.juniper_hotel_name}'")
                        row.status = 'room_not_found'
                
                row.save()
                processed_count += 1
            else:
                # Not a good enough hotel match 
                logger.warning(f"  [Hotel Match] Row {row.id}: No hotel match found for '{hotel_name}' (Best score: {best_hotel_score if best_hotel_match else 0})")
                row.status = 'hotel_not_found'
                row.save(update_fields=['status'])
                not_found_count += 1
        
        # Update email status based on how many rows were successfully processed
        if rows_to_process:
            total_rows = len(rows_to_process)
            email.status = 'processed'
            # Update pending rows to needs_review if needed
            email.save(update_fields=['status', 'updated_at'])
            
            logger.info(f"Finished matching for Email ID: {email_id}. Processed {processed_count}/{total_rows} rows successfully, {not_found_count} not found.")
            return True
        else:
            logger.warning(f"No rows found to process for Email ID: {email_id}")
            email.status = 'error' 
            email.save(update_fields=['status', 'updated_at'])
            return False
            
    except Email.DoesNotExist:
        logger.error(f"Match task failed: Email ID {email_id} not found")
        return False
    except Exception as e:
        logger.error(f"Match task failed for Email ID: {email_id}. Error: {str(e)}", exc_info=True)
        try:
            email = Email.objects.get(pk=email_id)
            email.status = 'error'
            email.save(update_fields=['status', 'updated_at'])
        except:
            pass
        return False

@shared_task(name="emails.tasks.update_room_groups_task")
def update_room_groups_task():
    """
    Oda grubu eşleştirmelerini güncelleyen düzenli celery task.
    Bu task, RoomTypeGroup ile eşleşen tüm oda tiplerini bulur ve
    grupta bulunan tüm varyantların doğru şekilde eşleştirilmesini sağlar.
    """
    from difflib import SequenceMatcher
    from emails.models import EmailRow
    from hotels.models import Hotel, Room, RoomTypeGroup, RoomTypeVariant
    from emails.models import RoomTypeMatch
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Oda Grupları Güncelleme Görevi başlatıldı.")
    
    def find_best_group_match(room_type, groups):
        """Verilen oda tipi için en iyi grup eşleşmesini bulan yardımcı fonksiyon"""
        best_match = None
        best_score = 0
        
        clean_room_type = room_type.strip().upper()
        
        for group in groups:
            # Tam eşleşme kontrolü
            if group.name.upper() == clean_room_type:
                return group, 1.0  # Tam eşleşme, skor 1.0
            
            # Bulanık eşleşme
            score = SequenceMatcher(None, clean_room_type, group.name.upper()).ratio()
            
            # Kelime içerme kontrolü (ilave puan)
            if clean_room_type in group.name.upper() or group.name.upper() in clean_room_type:
                score += 0.2
                
            if score > best_score:
                best_score = score
                best_match = group
        
        return best_match, best_score
    
    try:
        # Juniper otelle eşleşmiş ve henüz onaylanmamış bütün satırları bul
        all_rows = EmailRow.objects.filter(
            juniper_hotel__isnull=False, 
            status__in=['pending', 'matching']
        ).order_by('-id')
        
        logger.info(f"Toplam {all_rows.count()} işlenecek satır bulundu.")
        
        fixed_count = 0
        skipped_count = 0
        
        for row in all_rows:
            logger.debug(f"İşleniyor: Row ID: {row.id}, Hotel: {row.hotel_name}, Room Type: {row.room_type}")
            
            if not row.room_type or row.room_type.strip() == '':
                logger.debug(f"  Bu satırda oda tipi yok, atlanıyor.")
                skipped_count += 1
                continue
                
            # ALL ROOM tiplerini atla
            if row.room_type.strip().upper() in ["ALL ROOM", "ALL ROOMS", "ALL ROOM TYPES", "TÜM ODALAR"]:
                logger.debug(f"  Bu satır 'ALL ROOM' tipi içeriyor, atlanıyor.")
                skipped_count += 1
                continue
                
            hotel = row.juniper_hotel
            
            # Oda tipini temizle
            clean_room_type = row.room_type.strip().upper()
            
            # 1. Otele ait tüm oda gruplarını al
            hotel_groups = RoomTypeGroup.objects.filter(hotel=hotel)
            if not hotel_groups.exists():
                logger.debug(f"  Bu otel için hiç oda grubu tanımlanmamış, atlanıyor.")
                skipped_count += 1
                continue
            
            # 2. En iyi grup eşleşmesini bul
            best_group, group_score = find_best_group_match(clean_room_type, hotel_groups)
            
            # Eğer iyi bir grup eşleşmesi yoksa atla
            if not best_group or group_score < 0.6:  # 0.6 eşik değeri
                logger.debug(f"  Bu oda tipi için uygun grup bulunamadı (En yüksek skor: {group_score:.2f})")
                skipped_count += 1
                continue
                
            # 3. Gruptaki varyantları al
            variants = best_group.variants.all()
            if not variants.exists():
                logger.debug(f"  Bu grupta hiç varyant tanımlanmamış, atlanıyor.")
                skipped_count += 1
                continue
            
            # 4. Bu varyantlara sahip odaları bul
            all_variant_rooms = []
            for variant in variants:
                variant_rooms = Room.objects.filter(
                    hotel=hotel, 
                    juniper_room_type__icontains=variant.variant_room_name
                )
                if variant_rooms.exists():
                    all_variant_rooms.extend(variant_rooms)
            
            # 5. Eğer hiç oda bulunamadıysa atla
            if not all_variant_rooms:
                logger.debug(f"  Bu grup için hiç oda bulunamadı, atlanıyor.")
                skipped_count += 1
                continue
            
            # 6. Tekrarlanan odaları kaldır
            unique_rooms = list(set(all_variant_rooms))
            
            # 7. Önceki oda sayısını kontrol et
            previous_rooms = row.juniper_rooms.all()
            
            # 8. Eğer zaten birden fazla oda eşleşmişse ve sayı aynıysa atla
            if previous_rooms.count() >= len(unique_rooms):
                logger.debug(f"  Bu satır için zaten {previous_rooms.count()} oda eşleşmiş, güncellemeye gerek yok.")
                skipped_count += 1
                continue
            
            # 9. Yeni odaları ekle
            row.juniper_rooms.set(unique_rooms)
            
            # RoomTypeMatch kayıtlarını oluştur (öğrenen sistem için)
            for room in unique_rooms:
                RoomTypeMatch.objects.get_or_create(
                    email_room_type=row.room_type, 
                    juniper_room=room
                )
            
            fixed_count += 1
            logger.info(f"Satır {row.id} güncellendi: '{row.room_type}' için {len(unique_rooms)} oda eşleştirildi.")
        
        logger.info(f"Oda Grupları Güncelleme Görevi tamamlandı. {fixed_count} satır güncellendi, {skipped_count} satır atlandı.")
        return {"fixed": fixed_count, "skipped": skipped_count}
        
    except Exception as e:
        logger.error(f"Oda Grupları Güncelleme Görevi hata ile sonlandı: {str(e)}")
        return {"error": str(e)}

@shared_task(name="emails.tasks.check_room_variants_task")
def check_room_variants_task(row_id):
    """
    Tek bir EmailRow satırının oda tipini kontrol edip, eğer bir oda grubu ile eşleşiyorsa
    o grubun tüm varyantlarını ekler.
    
    Args:
        row_id (int): İşlenecek EmailRow'un ID'si
    
    Returns:
        dict: İşlem sonucu
    """
    from difflib import SequenceMatcher
    from emails.models import EmailRow
    from hotels.models import Hotel, Room, RoomTypeGroup, RoomTypeVariant
    from emails.models import RoomTypeMatch
    import logging
    logger = logging.getLogger(__name__)
    
    logger.debug(f"Oda varyant kontrolü başlatıldı: Row ID: {row_id}")
    
    try:
        # EmailRow'u bul
        row = EmailRow.objects.get(id=row_id)
        
        # Eğer otel veya oda tipi yoksa işleme
        if not row.juniper_hotel or not row.room_type:
            return {"status": "skipped", "reason": "no_hotel_or_room_type"}
        
        # ALL ROOM tiplerini atla
        if row.room_type.strip().upper() in ["ALL ROOM", "ALL ROOMS", "ALL ROOM TYPES", "TÜM ODALAR"]:
            return {"status": "skipped", "reason": "all_room_type"}
        
        # Sadece bekleyen veya eşleştirme durumundaki satırları kontrol et
        if row.status not in ['pending', 'matching']:
            return {"status": "skipped", "reason": "status_not_matching"}
        
        hotel = row.juniper_hotel
        clean_room_type = row.room_type.strip().upper()
        
        # Tam eşleşen bir grup var mı kontrol et
        room_type_group = RoomTypeGroup.objects.filter(
            hotel=hotel,
            name__iexact=clean_room_type
        ).first()
        
        # Eğer tam eşleşme yoksa, içerik eşleşmesi dene
        if not room_type_group:
            room_type_group = RoomTypeGroup.objects.filter(
                hotel=hotel,
                name__icontains=clean_room_type
            ).first()
        
        # Eğer içerik eşleşmesi de yoksa, daha yüksek bir bulanık eşleşme eşiği ile başka grupları dene
        if not room_type_group:
            best_group = None
            best_score = 0
            
            for group in RoomTypeGroup.objects.filter(hotel=hotel):
                score = SequenceMatcher(None, clean_room_type, group.name.upper()).ratio()
                
                # Kelime içerme kontrolü (ilave puan)
                if clean_room_type in group.name.upper() or group.name.upper() in clean_room_type:
                    score += 0.2
                    
                if score > best_score and score >= 0.6:  # 0.6 eşik değeri
                    best_score = score
                    best_group = group
            
            room_type_group = best_group
        
        # Eğer uygun grup bulunamadıysa işlemi sonlandır
        if not room_type_group:
            return {"status": "skipped", "reason": "no_matching_group"}
        
        # Gruptaki varyantları al
        variants = room_type_group.variants.all()
        if not variants.exists():
            return {"status": "skipped", "reason": "no_variants_in_group"}
        
        # Varyantlara ait odaları bul
        all_variant_rooms = []
        for variant in variants:
            variant_rooms = Room.objects.filter(
                hotel=hotel, 
                juniper_room_type__icontains=variant.variant_room_name
            )
            if variant_rooms.exists():
                all_variant_rooms.extend(variant_rooms)
        
        # Eğer hiç oda bulunamadıysa işlemi sonlandır
        if not all_variant_rooms:
            return {"status": "skipped", "reason": "no_rooms_for_variants"}
        
        # Tekrarlanan odaları kaldır
        unique_rooms = list(set(all_variant_rooms))
        
        # Önceki oda sayısını kontrol et
        previous_rooms = row.juniper_rooms.all()
        
        # Eğer zaten birden fazla oda eşleşmişse ve sayı aynıysa atla
        if previous_rooms.count() >= len(unique_rooms):
            return {"status": "skipped", "reason": "already_has_same_or_more_rooms"}
        
        # Özyinelemeyi önlemek için flag ekle
        row._room_variants_checked = True
        
        # Yeni odaları ekle
        row.juniper_rooms.set(unique_rooms)
        
        # RoomTypeMatch kayıtlarını oluştur (öğrenen sistem için)
        for room in unique_rooms:
            RoomTypeMatch.objects.get_or_create(
                email_room_type=row.room_type, 
                juniper_room=room
            )
        
        logger.info(f"Oda varyantları güncellendi: Row {row_id} için {len(unique_rooms)} oda eklendi - Grup: {room_type_group.name}")
        return {
            "status": "updated", 
            "row_id": row_id,
            "group": room_type_group.name,
            "variants_count": variants.count(),
            "rooms_count": len(unique_rooms)
        }
        
    except EmailRow.DoesNotExist:
        logger.warning(f"Row ID {row_id} bulunamadı.")
        return {"status": "error", "reason": "row_not_found"}
    except Exception as e:
        logger.error(f"Oda varyant kontrolü hatası (Row ID: {row_id}): {str(e)}")
        return {"status": "error", "reason": str(e)}