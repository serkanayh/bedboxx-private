from celery import shared_task
from django.core.management import call_command
import logging
import os
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Email, EmailRow, EmailAttachment, AIModel, Prompt, RoomTypeMatch, RoomTypeReject
from hotels.models import Hotel, Room, Market, JuniperContractMarket
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
def process_email_attachments_task(attachment_id):
    """
    Celery task to process a specific email attachment using the unified ClaudeAnalyzer.
    Arg:
        attachment_id: The primary key of the EmailAttachment to process.
    """
    logger.info(f"Starting attachment processing task for Attachment ID: {attachment_id}")
    try:
        # Correctly fetch the EmailAttachment object
        attachment = EmailAttachment.objects.get(pk=attachment_id)
        email = attachment.email # Access the related Email object

        logger.info(f"Processing attachment '{attachment.filename}' for Email ID: {email.id}")

        # --- YENİ: E-posta gövdesinden zaten veri çıkarılmış mı kontrol et ---
        existing_rows = EmailRow.objects.filter(email=email, extracted_from_attachment=False, ai_extracted=True).exists()
        if existing_rows:
            logger.info(f"E-posta {email.id} için gövdeden başarılı veri çıkarılmış. Ek analizi iptal ediliyor.")
            return True
        # --- YENİ SON ---

        # --- Fetch Active AI Model --- 
        active_model = AIModel.objects.filter(active=True).first()
        if not active_model or not active_model.api_key:
             logger.error(f"No active AI model with API key found. Cannot perform AI attachment analysis for attachment {attachment_id} (Email {email.id}).")
             # Update EMAIL status, not attachment
             email.status = 'error' 
             email.save(update_fields=['status', 'updated_at'])
             return False
             
        # --- Initialize the UNIFIED Analyzer --- 
        analyzer = ClaudeAnalyzer(api_key=active_model.api_key)
        if not analyzer.claude_client: # Check if client initialized
             logger.error(f"Failed to initialize ClaudeAnalyzer for attachment {attachment_id} (Email {email.id}). Aborting attachment task.")
             email.status = 'error'
             email.save(update_fields=['status', 'updated_at'])
             return False
        # --- End Initialize --- 
        
        created_row_ids = []
        analysis_results_store = email.attachment_analysis_results or {} # Load existing results
        
        # Process the single attachment passed to the task
        logger.info(f"Extracting text from attachment: {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email.id})")
        # 1. Extract Text using the method from ClaudeAnalyzer
        if not attachment.file or not os.path.exists(attachment.file.path):
            error_msg = f"Attachment file not found or path is invalid for Attachment ID {attachment.id}"
            logger.error(error_msg)
            analysis_results_store[str(attachment.id)] = {'error': error_msg}
            # Update results on email and return False
            email.attachment_analysis_results = analysis_results_store
            email.save(update_fields=['attachment_analysis_results', 'updated_at'])
            return False

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
            logger.error(f"Failed to extract text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email.id}): {error_msg}")
            analysis_results_store[str(attachment.id)] = {'error': error_msg}
        
        elif not extracted_text:
            logger.warning(f"No text extracted from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email.id}). Skipping analysis.")
            analysis_results_store[str(attachment.id)] = {'error': 'No text content extracted'}
        
        else:
            # 2. Analyze Extracted Text with AI
            logger.info(f"Analyzing extracted text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email.id})")
            analysis_result = analyzer.analyze_content(extracted_text)
            analysis_results_store[str(attachment.id)] = analysis_result # Store raw result
            
            if analysis_result.get('error'):
                logger.error(f"AI analysis failed for extracted text from {attachment.filename} (Attachment ID: {attachment.id}, Email ID: {email.id}): {analysis_result['error']}")
            else:
                # 3. Process Rows from Successful Analysis
                rows_data = analysis_result.get('rows', [])
                if rows_data:
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
                            if (start_date == mail_date and end_date == mail_date) or (start_date == mail_date and end_date is None):
                                logger.warning(f"Skipping row with same date as email: {mail_date}. Start: {start_date}, End: {end_date}")
                                continue
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
                            logger.info(f"Created EmailRow {email_row.id} from attachment {attachment.filename} (ID: {attachment.id}) for email {email.id}")

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
                            logger.error(f"Error creating EmailRow or setting markets from attachment AI data {row_data} (Attachment ID: {attachment.id}, Email ID: {email.id}): {e}", exc_info=True)

                    if len(created_row_ids) > initial_row_count: 
                        logger.info(f"Attachment {attachment_id} processing yielded {len(created_row_ids) - initial_row_count} new rows. Deleting any existing rows for email {email.id} not extracted from an attachment.")
                        try:
                            with transaction.atomic():
                                deleted_count, deleted_details = EmailRow.objects.filter(
                                    email=email,
                                    extracted_from_attachment=False
                                ).delete()
                            if deleted_count > 0:
                                logger.info(f"Deleted {deleted_count} rows previously extracted from the email body: {deleted_details}")
                            else:
                                logger.info(f"No body-extracted rows found to delete for email {email.id}.")
                        except Exception as delete_error:
                             logger.error(f"Error deleting body-extracted rows for email {email.id}: {delete_error}", exc_info=True)
                else:
                     logger.warning(f"AI analysis for {attachment.filename} (Attachment ID: {attachment.id}) successful but returned no rows after processing.")
                        
        if analysis_results_store:
             email.attachment_analysis_results = analysis_results_store
             logger.debug(f"Stored/Updated attachment analysis results for email {email.id}")
             email.save(update_fields=['attachment_analysis_results', 'updated_at'])

        if created_row_ids:
            logger.info(f"Attachment analysis for attachment {attachment_id} finished. Scheduling BATCH matching for {len(created_row_ids)} newly created rows for email {email.id}.")
            try:
                from .tasks import match_email_rows_batch_task 
                match_email_rows_batch_task.delay(email.id, created_row_ids)
                if email.status not in ['processing', 'processed', 'error']:
                    email.status = 'processing'
                    email.save(update_fields=['status', 'updated_at'])
            except Exception as task_error:
                 logger.error(f"CRITICAL: Error scheduling matching task for email {email.id} (from attachment {attachment_id}): {task_error}", exc_info=True)
                 email.status = 'error'
                 email.save(update_fields=['status', 'updated_at'])
            logger.info(f"Attachment processing task finished successfully for Attachment ID: {attachment_id}. {len(created_row_ids)} rows created and matching scheduled.")
            return True
        else:
            logger.info(f"Attachment processing task finished for Attachment ID: {attachment_id}. No new rows created.")
            return False

    except EmailAttachment.DoesNotExist:
        logger.error(f"Attachment processing task failed: EmailAttachment ID {attachment_id} not found.")
        return False
    except Email.DoesNotExist:
        logger.error(f"Attachment processing task failed: Associated Email not found for EmailAttachment ID {attachment_id}.")
        return False
    except Exception as e:
        logger.error(f"Attachment processing task failed unexpectedly for Attachment ID: {attachment_id}. Error: {str(e)}", exc_info=True)
        try:
            attachment = EmailAttachment.objects.get(pk=attachment_id)
            email = attachment.email
            email.status = 'error'
            email.save(update_fields=['status', 'updated_at'])
            logger.info(f"Marked associated email {email.id} as error due to attachment task failure for attachment {attachment_id}.")
        except EmailAttachment.DoesNotExist:
            logger.warning(f"Could not mark email as error: Attachment {attachment_id} not found during error handling.")
        except Email.DoesNotExist:
             logger.warning(f"Could not mark email as error: Associated Email not found for attachment {attachment_id} during error handling.")
        except Exception as save_error:
            logger.error(f"Failed to mark email as error after attachment task failure (Attachment ID: {attachment_id}): {save_error}", exc_info=True)
        return False

HOTEL_FUZZY_MATCH_THRESHOLD = 75  # 85'den 75'e düşürüldü
ROOM_FUZZY_MATCH_THRESHOLD = 80   # 90'dan 80'e düşürüldü

@shared_task(name="emails.tasks.match_email_rows_batch_task")
def match_email_rows_batch_task(email_id, row_ids):
    """Celery task to match hotels and rooms for a batch of EmailRows."""
    logger.info(f"Starting matching task for Email ID: {email_id}, Row IDs: {row_ids}")
    
    processed_count = 0
    not_found_count = 0
    
    try:
        email = Email.objects.get(pk=email_id)
        rows_to_process = EmailRow.objects.filter(id__in=row_ids, email=email)
        all_hotels = list(Hotel.objects.all())
        all_rooms_by_hotel = {h.id: list(Room.objects.filter(hotel=h)) for h in all_hotels}
        
        # --- Improve learned email-to-hotel mapping check ---
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
                
                # Set the matching hotel from learned mapping
                row.juniper_hotel = learned_hotel
                
                # Calculate similarity for logging purposes
                similarity_score = fuzz.token_set_ratio(str(original_hotel_name).lower(), 
                                                      str(learned_hotel.juniper_hotel_name).lower())
                
                # Store match score (maintain high confidence if good match, otherwise show actual similarity)
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
            
            if best_hotel_match and best_hotel_score >= HOTEL_FUZZY_MATCH_THRESHOLD:
                row.juniper_hotel = best_hotel_match
                row.hotel_match_score = best_hotel_score
                logger.info(f"  [Hotel Match] Row {row.id}: '{hotel_name}' -> '{best_hotel_match.juniper_hotel_name}' (Score: {best_hotel_score:.2f})")
                
                # --- RoomTypeReject blacklist check ---
                market_obj = row.markets.first() if hasattr(row, 'markets') and row.markets.exists() else None
                reject_exists = RoomTypeReject.objects.filter(
                    hotel=best_hotel_match,
                    email_room_type=room_type_input,
                    market=market_obj
                ).exists()
                if reject_exists:
                    logger.info(f"  [RoomTypeReject] Row {row.id}: Found in blacklist, automatic matching will not be performed.")
                    row.juniper_rooms.clear()
                    row.room_match_score = None
                    row.status = 'room_not_found'
                    row.save()
                    processed_count += 1
                    not_found_count += 1
                    continue
                
                matched_juniper_rooms = []
                room_scores = []
                best_single_room_score = 0
                hotel_rooms = all_rooms_by_hotel.get(best_hotel_match.id, [])

                # Check for learned room matches
                learned_matches = RoomTypeMatch.objects.filter(email_room_type=room_type_input)
                learned_rooms = [m.juniper_room for m in learned_matches if m.juniper_room.hotel_id == best_hotel_match.id]
                if learned_rooms:
                    matched_juniper_rooms = learned_rooms
                    logger.info(f"  [RoomTypeMatch] Row {row.id}: Found learned room match: {[room.juniper_room_type for room in matched_juniper_rooms]}")
                    row.room_match_score = None
                elif ',' in room_type_input:
                    # We don't fully support comma-separated room types yet
                    logger.warning(f"  [Room Match] Row {row.id}: Multiple room types detected ('{room_type_input}') - matching not fully implemented yet.")
                    row.room_match_score = None
                    row.juniper_rooms.clear()
                elif room_type_input.upper() in ['ALL ROOM', 'ALL ROOMS', 'ALL ROOM TYPES']:
                    # Special cases like ALL ROOM
                    logger.info(f"  [Room Match] Row {row.id}: '{room_type_input}' detected. Applying to all rooms conceptually.")
                    row.room_match_score = None
                    row.juniper_rooms.clear()
                    matched_juniper_rooms = []
                else:
                    # Skip normalization and segment comparison
                    # Use direct string matching instead
                    matched_juniper_rooms = []
                    room_scores = []
                    input_room_lower = room_type_input.lower()
                    
                    # Calculate fuzzy match score for all rooms
                    best_score = 0
                    best_rooms = []
                    
                    # Show log details
                    logger.info(f"  [Room Match] Row {row.id}: Searching for match for room type '{room_type_input}'")
                    
                    for juniper_room in hotel_rooms:
                        room_name_lower = str(juniper_room.juniper_room_type).lower()
                        
                        # Exact match (full score)
                        if input_room_lower == room_name_lower:
                            score = 100
                            logger.info(f"  [EXACT MATCH] Row {row.id}: '{room_type_input}' = '{juniper_room.juniper_room_type}'")
                        else:
                            # Calculate fuzzy match score
                            score = fuzz.token_set_ratio(input_room_lower, room_name_lower)
                            
                            # --- Word set comparison for better matching ---
                            # This helps match rooms like "Family Room With Bunkbed" and "Bunk Bed Family Room"
                            # which have different word order but same meaning
                            input_words = set(input_room_lower.split())
                            room_words = set(room_name_lower.split())
                            
                            # Find number of common words
                            common_words = input_words.intersection(room_words)
                            
                            # Calculate ratio based on total words
                            if len(input_words) > 0 and len(room_words) > 0:
                                common_word_ratio = len(common_words) / max(len(input_words), len(room_words))
                                # Give more weight to special words like "bunk", "bed", "family", "room"
                                key_term_matches = sum(1 for word in ["family", "bunk", "bed", "room", "suite"] if word in common_words)
                                
                                # If special word matches and high common word ratio, strengthen the score
                                if key_term_matches >= 2 and common_word_ratio >= 0.5:
                                    word_match_score = 85 + (key_term_matches * 3) # Bonus based on number of special words
                                    score = max(score, word_match_score) # Take higher of fuzzy score or word match score
                                    logger.info(f"  [WORD SET MATCH] '{room_type_input}' vs '{juniper_room.juniper_room_type}': {common_words} | Score: {score}")
                            # --- End word set comparison ---
                            
                            logger.debug(f"  [Score] '{room_type_input}' vs '{juniper_room.juniper_room_type}' = {score}")
                        
                        if score > best_score:
                            best_score = score
                            best_rooms = [juniper_room]
                        elif score == best_score and score > 0:
                            best_rooms.append(juniper_room)
                    
                    # Is there a room that passes the threshold?
                    if best_score >= ROOM_FUZZY_MATCH_THRESHOLD:
                        matched_juniper_rooms = best_rooms
                        room_scores = [best_score] * len(best_rooms) 
                        row.room_match_score = best_score
                        logger.info(f"  [Room Match] Row {row.id}: '{room_type_input}' -> {[room.juniper_room_type for room in best_rooms]} (Score: {best_score})")
                        
                        # --- EXTRA: Look for similar room names and add them too ---
                        all_juniper_rooms = all_rooms_by_hotel.get(best_hotel_match.id, [])
                        new_matches = []
                        for best_room in best_rooms:
                            best_name = str(best_room.juniper_room_type).strip().lower()
                            for other_room in all_juniper_rooms:
                                other_name = str(other_room.juniper_room_type).strip().lower()
                                if other_room not in matched_juniper_rooms and (best_name in other_name or other_name in best_name):
                                    matched_juniper_rooms.append(other_room)
                                    new_matches.append(other_room.juniper_room_type)
                        if new_matches:
                            logger.info(f"  [Room Name Contains Extension] Row {row.id}: Added rooms: {new_matches}")
                    else:
                        matched_juniper_rooms = []
                        room_scores = []
                        row.room_match_score = None
                        logger.warning(f"  [Room Match] Row {row.id}: No room match found for '{room_type_input}'. Best score was {best_score} with rooms {[room.juniper_room_type for room in best_rooms]}")

                if matched_juniper_rooms:
                    row.juniper_rooms.set(matched_juniper_rooms)
                else:
                    row.juniper_rooms.clear()

                final_row_status = 'hotel_not_found'
                if best_hotel_match:
                    is_all_room_case = room_type_input.upper() in ['ALL ROOM', 'ALL ROOMS', 'ALL ROOM TYPES']
                    if is_all_room_case or matched_juniper_rooms:
                        final_row_status = 'pending'
                    else:
                        final_row_status = 'room_not_found'

                row.status = final_row_status
            
            else:
                logger.warning(f"  [Hotel Match] Row {row.id}: No hotel match found for '{hotel_name}'")
                row.status = 'hotel_not_found'
                row.hotel_match_score = None
                row.room_match_score = None
                row.juniper_hotel = None
                row.juniper_rooms.clear()
            
            row.save()
            processed_count += 1
            if row.status == 'hotel_not_found' or row.status == 'room_not_found':
                not_found_count += 1

        logger.info(f"Matching task finished for Email ID: {email_id}. Processed: {processed_count}, Not Found: {not_found_count}")

    except Email.DoesNotExist:
        logger.error(f"Matching task failed: Email ID {email_id} not found.")
    except Exception as e:
        logger.error(f"Matching task failed for Email ID: {email_id}, Row IDs: {row_ids}. Error: {str(e)}", exc_info=True)