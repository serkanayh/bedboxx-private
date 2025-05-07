from django.utils import timezone
from django.core.management import call_command
from celery import shared_task
from .models import Email, EmailRow, RoomTypeMatch, RoomTypeReject, EmailHotelMatch
from hotels.models import Hotel, Room, Market
from core.ai_analyzer import ClaudeAnalyzer
from difflib import SequenceMatcher
from thefuzz import fuzz
import os
import logging
import json
from datetime import datetime, timedelta
import subprocess
import io
import time

logger = logging.getLogger(__name__)

def extract_text_from_file(file_path):
    """
    Extracts text from various file types using basic methods
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Extracted text content or empty string if extraction fails
    """
    file_lower = file_path.lower()
    
    try:
        # PDF files
        if file_lower.endswith('.pdf'):
            return extract_text_from_pdf(file_path)
            
        # Text files
        elif file_lower.endswith(('.txt', '.csv', '.json', '.html')):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading text file {file_path}: {e}")
                return ""
                
        # Try system utilities as fallback for other formats
        else:
            try:
                # Try using 'strings' command for binary files
                result = subprocess.run(['strings', file_path], capture_output=True, text=True)
                return result.stdout
            except Exception as e:
                logger.error(f"Error extracting text from {file_path}: {e}")
                # Last resort: try basic binary reading
                try:
                    with open(file_path, 'rb') as f:
                        binary_content = f.read()
                    # Filter printable ASCII characters
                    text = ''.join(chr(b) for b in binary_content if 32 <= b < 127 or b in (9, 10, 13))
                    return text
                except:
                    return ""
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        return ""
        
def extract_text_from_pdf(file_path):
    """
    Extract text from PDF files using pdftotext if available,
    or fallback to strings command
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        str: Extracted text
    """
    try:
        # Try pdftotext (part of poppler-utils)
        try:
            result = subprocess.run(['pdftotext', file_path, '-'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except FileNotFoundError:
            logger.warning("pdftotext not found, falling back to strings command")
            
        # Fallback to strings command
        result = subprocess.run(['strings', file_path], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}")
        return ""

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
    """
    Scheduled task to check for new emails.
    """
    logger.info("Running check_emails management command via Celery task.")
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
    logger.info(f"====== ATTACHMENT PROCESSING STARTED: Processing attachments for Email ID: {email_id} ======")
    try:
        # Fetch the Email object
        email = Email.objects.get(pk=email_id)
        
        # EKLERI KONTROL ET - doğrudan attachment sayısı ile
        attachment_count = email.attachments.count()
        logger.info(f"ATTACHMENT COUNT CHECK: Email {email_id} has {attachment_count} attachment(s) directly in database")
        
        # Ek bulunamadı ise uyarı ver
        if attachment_count == 0:
            logger.warning(f"No attachments found in database for email {email_id}. Marking has_attachments=False.")
            if email.has_attachments:
                email.has_attachments = False
                email.save(update_fields=['has_attachments', 'updated_at'])
                logger.info(f"Fixed has_attachments flag for email {email_id}")
            return None  # İşlemi sonlandır

        # Continue only if there are attachments
        attachment_list = list(email.attachments.values_list('filename', flat=True))
        logger.info(f"Processing {attachment_count} attachment(s) for email {email_id}: {', '.join(attachment_list)}")
        
        # Ensure the has_attachments flag is set correctly
        if not email.has_attachments:
            email.has_attachments = True
            email.save(update_fields=['has_attachments', 'updated_at'])
            logger.info(f"Set has_attachments=True for email {email_id}")
        
        # Initialize the ClaudeAnalyzer
        from .utils.ai_analyzer import ClaudeAnalyzer
        analyzer = ClaudeAnalyzer()
        
        # Initialize a list to store all rows created from attachments
        created_row_ids = []
        
        # Process each attachment
        for attachment in email.attachments.all():
            try:
                logger.info(f"Processing attachment: {attachment.filename} (ID: {attachment.id}) for email {email_id}")
                
                # Skip processing if filename contains 'chart' (as per requirements)
                if is_stop_sale_chart_file(attachment.filename):
                    logger.info(f"Skipping chart file: {attachment.filename}")
                    continue
                
                # Extract text from attachment
                text = extract_text_from_file(attachment.file.path)
                
                if not text or text.strip() == "":
                    logger.warning(f"Failed to extract text from attachment {attachment.filename} for email {email_id}")
                    continue
                
                # Analyze the attachment text
                logger.info(f"Analyzing text from attachment {attachment.filename} for email {email_id}")
                rows = analyzer.analyze_attachment(email, text, attachment.filename)
                
                if not rows:
                    logger.warning(f"No data extracted from attachment {attachment.filename} for email {email_id}")
                    continue
                
                logger.info(f"Successfully extracted {len(rows)} row(s) from attachment {attachment.filename} for email {email_id}")
                
                # Create EmailRow objects for each extracted row
                for row_data in rows:
                    try:
                        # Create EmailRow object and add to created_row_ids
                        row = create_email_row_from_data(email, row_data, is_from_attachment=True)
                        if row:
                            created_row_ids.append(row.id)
                            logger.info(f"Created EmailRow {row.id} from attachment {attachment.filename} for email {email_id}")
                    except Exception as row_err:
                        logger.error(f"Error creating EmailRow from attachment data: {str(row_err)}", exc_info=True)
                
            except Exception as att_err:
                logger.error(f"Error processing attachment {attachment.filename}: {str(att_err)}", exc_info=True)
        
        # Schedule matching task for all created rows if any
        if created_row_ids:
            from .tasks import match_email_rows_batch_task
            logger.info(f"Scheduling matching task for {len(created_row_ids)} rows from attachments for email {email_id}")
            match_email_rows_batch_task.delay(email_id, created_row_ids)
            
            # Update email status if needed
            if email.status in ['pending', 'pending_analysis', 'processing_attachments']:
                email.status = 'processing'
                email.save(update_fields=['status', 'updated_at'])
                logger.info(f"Updated email {email_id} status to 'processing'")
        else:
            logger.warning(f"No rows were created from attachments for email {email_id}")
        
        logger.info(f"====== ATTACHMENT PROCESSING COMPLETED: Email {email_id} attachments processed successfully ======")
        return created_row_ids
    
    except Email.DoesNotExist:
        logger.error(f"Email with ID {email_id} does not exist")
        return None
    except Exception as e:
        logger.error(f"Error processing attachments for email {email_id}: {str(e)}", exc_info=True)
        return None

def is_stop_sale_chart_file(filename):
    """
    Check if a filename indicates it's a stop sale chart or summary file that should not be processed
    as it doesn't contain individual stop sale entries but rather a summary.
    """
    filename_lower = filename.lower()
    patterns = [
        'stop sale chart', 
        'stopsale chart', 
        'stop-sale-chart',
        'chart of stop', 
        'report of stop',
        'özet', 'summary',
        'tüm stop', 'all stop',
        'genel stop', 'general stop',
        'chart'  # Eklenen yeni kelime - bu ifadeyi içeren dosyalar işlenmemeli
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
        logger.error(f"Matching task failed for Email ID: {email_id}, Row IDs: {row_ids}. Error: {str(e)}", exc_info=True)

def create_email_row_from_data(email, row_data, is_from_attachment=False):
    """
    Creates an EmailRow object from parsed data.
    Args:
        email: The Email object to associate the row with
        row_data: Dictionary containing extracted data
        is_from_attachment: Boolean indicating if data came from an attachment
    Returns:
        EmailRow object if created successfully, None otherwise
    """
    try:
        # Parse dates
        start_date_str = row_data.get('start_date', '')
        end_date_str = row_data.get('end_date', '')
        
        # Skip rows with uncertain dates
        if start_date_str == "UNCERTAIN" or end_date_str == "UNCERTAIN":
            logger.warning(f"Skipping row with uncertain dates from {'attachment' if is_from_attachment else 'email body'}")
            return None
            
        # Parse start date
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                start_date = datetime.strptime(start_date_str, '%d.%m.%Y').date()
            except ValueError:
                logger.warning(f"Invalid start date format: {start_date_str}")
                return None
                
        # Parse end date
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                end_date = datetime.strptime(end_date_str, '%d.%m.%Y').date()
            except ValueError:
                logger.info(f"Using start date as fallback for end date: {start_date}")
                end_date = start_date  # Use start_date as fallback
        
        # Get other fields
        sale_type = row_data.get('sale_status', row_data.get('sale_type', 'stop'))
        hotel_name_raw = row_data.get('hotel_name', 'Unknown Hotel')
        room_type_raw = row_data.get('room_type', 'All Room Types')
        
        # Create the EmailRow
        row = EmailRow.objects.create(
            email=email,
            hotel_name=hotel_name_raw,
            room_type=room_type_raw,
            start_date=start_date,
            end_date=end_date,
            sale_type=sale_type,
            status='needs_review' if is_from_attachment else 'matching',
            ai_extracted=True,
            notes=f"Extracted from {'attachment' if is_from_attachment else 'email body'}"
        )
        
        # Process markets
        markets_data = row_data.get('markets', ['ALL'])
        if not isinstance(markets_data, list):
            markets_data = ['ALL']
            
        # Set markets
        resolved_markets = []
        for market_name in markets_data:
            market = Market.objects.filter(name__iexact=market_name.strip()).first()
            if market:
                resolved_markets.append(market)
            else:
                # Try to find by alias
                alias = MarketAlias.objects.filter(alias__iexact=market_name.strip()).first()
                if alias and alias.markets.exists():
                    resolved_markets.extend(alias.markets.all())
                    
        # Default to ALL if no markets resolved
        if not resolved_markets:
            all_market = Market.objects.filter(name__iexact='ALL').first()
            if all_market:
                resolved_markets.append(all_market)
                
        if resolved_markets:
            row.markets.set(resolved_markets)
            logger.info(f"Set markets for row {row.id}: {[m.name for m in resolved_markets]}")
            
        return row
        
    except Exception as e:
        logger.error(f"Error creating EmailRow: {str(e)}", exc_info=True)
        return None