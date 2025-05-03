from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging
import datetime
from rest_framework.test import APIClient
from hotels.models import Hotel, Room, Market, MarketAlias
from .models import Email, AIModel, Prompt, EmailRow
from users.models import User

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Email)
def auto_analyze_email(sender, instance, created, **kwargs):
    """
    Signal to automatically analyze new emails when they are created
    """
    # Only analyze newly created emails that are in pending status and don't have rows yet
    if created and instance.status == 'pending' and not instance.rows.exists():
        logger.info(f"Auto-analyzing email: {instance.id} - {instance.subject}")
        print(f"AUTO-ANALYZE: Starting analysis for email {instance.id} - {instance.subject}")
        
        try:
            # Create a client for API calls and authenticate it
            client = APIClient()
            
            # Get a superuser for authentication (first superuser found)
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                logger.error("No superuser found for API authentication in auto_analyze_email signal")
                print("AUTO-ANALYZE ERROR: No superuser found for API authentication")
                return
                
            client.force_authenticate(user=superuser)
            
            # Get active AI model and prompt
            active_model = AIModel.objects.filter(active=True).first()
            active_prompt = Prompt.objects.filter(active=True).first()
            
            if active_model and active_prompt:
                print(f"AUTO-ANALYZE: Using model '{active_model.name}' and prompt '{active_prompt.title}'")
                
                # Prepare payload
                payload = {
                    'email_content': instance.body_text,
                    'email_subject': instance.subject,
                    'email_html': instance.body_html,
                    'email_id': instance.id,
                    'model_id': active_model.id,
                    'prompt_id': active_prompt.id,
                }
                
                print(f"AUTO-ANALYZE: Calling API with payload for email {instance.id}")
                response = client.post('/api/parse-email-content/', payload, format='json')
                
                # --- Handle API Response (Simplified - No Attachment Logic Here) --- 
                api_success = False
                used_fallback = False
                rows_data = []

                if response.status_code == 200 and response.data and response.data.get('success'):
                    api_data = response.data
                    if api_data.get('used_fallback') == True:
                        # --- Fallback was used --- 
                        logger.warning(f"AI analysis for email {instance.id} used keyword fallback. Data might be incomplete/inaccurate.")
                        print(f"AUTO-ANALYZE WARNING: Fallback used for email {instance.id}. Setting status to needs_review_check_attachments.")
                        used_fallback = True
                        rows_data = api_data.get('data', {}).get('rows', [])
                        if rows_data: 
                             api_success = True
                        else:
                             api_success = False
                    else:
                        # --- AI Success (No Fallback) --- 
                        logger.info(f"Successfully auto-analyzed email {instance.id} using AI.")
                        print(f"AUTO-ANALYZE SUCCESS: Email {instance.id} analyzed successfully using AI")
                        api_success = True
                        rows_data = api_data.get('data', {}).get('rows', [])
                else:
                    # --- API Call Failed or returned success=False --- 
                    logger.warning(f"AI analysis API call failed (Status: {response.status_code}, Success: {response.data.get('success', 'N/A') if response.data else 'N/A'}) for email {instance.id}. Flagging for attachment check.")
                    print(f"AUTO-ANALYZE WARNING: AI analysis failed (Status: {response.status_code}) for email {instance.id}. Flagging for attachment check.")
                    api_success = False

                # --- Process results if AI or Fallback was successful AND returned data --- 
                if api_success and rows_data:
                    created_row_ids = []
                    for row_data in rows_data:
                        try:
                            # --- Date Parsing (Existing logic) ---
                            start_date_str = row_data.get('start_date', '')
                            end_date_str = row_data.get('end_date', '')
                            start_date = None
                            end_date = None
                            try:
                                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y').date()
                                except ValueError:
                                    start_date = timezone.now().date()
                            try:
                                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    end_date = datetime.datetime.strptime(end_date_str, '%d.%m.%Y').date()
                                except ValueError:
                                    end_date = start_date # Use start_date as fallback
                            # --- End Date Parsing ---

                            # --- YENİ: Eğer veri mail tarihi ile aynı gün ise bu veriyi atla ---
                            mail_date = instance.received_date.date()
                            if (start_date == mail_date and end_date == mail_date) or (start_date == mail_date and end_date is None):
                                logger.warning(f"[Signal] Skipping row with same date as email: {mail_date}. Start: {start_date}, End: {end_date}")
                                print(f"AUTO-ANALYZE: Skipping row with same date as email {instance.id}. Mail date: {mail_date}, Row date: {start_date}")
                                continue
                            # --- END YENİ ---

                            # --- Market Resolution Logic --- 
                            ai_market_names = row_data.get('markets', ['ALL']) # Expects a list from analyzer
                            resolved_markets = set() # Use a set for unique Market objects

                            if not isinstance(ai_market_names, list):
                                logger.warning(f"[Signal] Market data for email {instance.id} rule is not a list: {ai_market_names}. Defaulting to ['ALL'].")
                                ai_market_names = ['ALL']
                            if not ai_market_names: # Handle empty list
                                logger.warning(f"[Signal] Market data for email {instance.id} rule is empty. Defaulting to ['ALL'].")
                                ai_market_names = ['ALL']

                            for market_name in ai_market_names:
                                market_name_stripped = market_name.strip()
                                if not market_name_stripped:
                                    continue

                                try:
                                    # 1. Try direct match (case-insensitive)
                                    direct_market = Market.objects.filter(name__iexact=market_name_stripped).first()
                                    if direct_market:
                                        resolved_markets.add(direct_market)
                                        logger.debug(f"[Signal] Found direct market match for '{market_name_stripped}'")
                                    else:
                                        # 2. Try alias match (case-insensitive)
                                        alias_obj = MarketAlias.objects.prefetch_related('markets').filter(alias__iexact=market_name_stripped).first()
                                        if alias_obj:
                                            found_markets_from_alias = alias_obj.markets.all()
                                            if found_markets_from_alias:
                                                resolved_markets.update(found_markets_from_alias)
                                                logger.debug(f"[Signal] Found alias match for '{market_name_stripped}', resolved to: {[m.name for m in found_markets_from_alias]}")
                                            else:
                                                logger.warning(f"[Signal] Market alias '{market_name_stripped}' found for email {instance.id}, but it maps to no Markets.")
                                        else:
                                             # Only log warning if it wasn't found directly either
                                             logger.warning(f"[Signal] Could not find direct match or alias for market name '{market_name_stripped}' from AI for email {instance.id}.")
                                except Exception as market_lookup_error:
                                    logger.error(f"[Signal] Error looking up market/alias '{market_name_stripped}' for email {instance.id}: {market_lookup_error}", exc_info=True)
                            
                            # 3. Fallback if no markets were resolved
                            if not resolved_markets:
                                logger.warning(f"[Signal] No markets could be resolved for rule {row_data} in email {instance.id}. Defaulting to 'ALL'.")
                                all_market = Market.objects.filter(name__iexact='ALL').first()
                                if all_market:
                                    resolved_markets.add(all_market)
                                else:
                                    logger.error(f"[Signal] CRITICAL: Default 'ALL' market not found in database for email {instance.id}. Skipping row creation for this rule.")
                                    continue # Skip this rule if ALL market doesn't exist

                            final_market_objects = list(resolved_markets)
                            logger.info(f"[Signal] Resolved markets for rule in email {instance.id}: {[m.name for m in final_market_objects]}")
                            # --- End Market Resolution Logic --- 
                            
                            # --- Get other fields (Existing logic) ---
                            sale_type = row_data.get('sale_status', row_data.get('sale_type', 'stop'))
                            row_status = 'needs_review' if used_fallback else 'matching'
                            hotel_name_raw = row_data.get('hotel_name', 'Unknown Hotel' if used_fallback else '')
                            room_type_raw = row_data.get('room_type', 'All Room Types' if used_fallback else '')
                            # --- End Get other fields ---
                            
                            # --- Create EmailRow instance --- 
                            row = EmailRow.objects.create(
                                email=instance,
                                hotel_name=hotel_name_raw,
                                room_type=room_type_raw, # Store raw room type text
                                # market field removed
                                start_date=start_date,
                                end_date=end_date,
                                sale_type=sale_type,
                                status=row_status, 
                                ai_extracted=True
                            )
                            
                            # --- Set the ManyToManyField for markets --- 
                            if final_market_objects:
                                row.markets.set(final_market_objects)
                                
                            created_row_ids.append(row.id)
                            log_prefix = "FALLBACK" if used_fallback else "AI"
                            logger.info(f"[Signal] Created EmailRow {row.id} from {log_prefix} data for email {instance.id} with markets: {[m.name for m in final_market_objects]}.")
                            # print is less useful than logging here
                            # print(f"[Signal] Created EmailRow {row.id} from {log_prefix} with status '{row_status}' for email {instance.id}.")

                        except Exception as row_error:
                            logger.error(f"[Signal] Error processing/creating EmailRow from AI data {row_data} for email {instance.id}: {row_error}", exc_info=True)

                    # --- Update Email Status based on outcome --- 
                    if created_row_ids:
                        # --- Activate Matching Task Call --- 
                        logger.info(f"Scheduling BATCH matching task for email {instance.id} with {len(created_row_ids)} rows.")
                        print(f"AUTO-ANALYZE: Scheduling BATCH matching task for email {instance.id}.")
                        try:
                             from .tasks import match_email_rows_batch_task # Import task here
                             match_email_rows_batch_task.delay(instance.id, created_row_ids)
                             # Set email status to processing since task is scheduled
                             final_status = 'processing' 
                             logger.info(f"Matching task scheduled successfully for email {instance.id}.")
                             
                             # YENİ: E-Posta içeriğinden başarıyla veri çıkarıldıysa, ekleri işlemeyi atla
                             logger.info(f"Successfully extracted data from email body for {instance.id}. Skipping attachments.")
                             print(f"AUTO-ANALYZE: Successfully extracted data from email body for {instance.id}. Skipping attachments.")
                             
                        except ImportError:
                             logger.error(f"CRITICAL: Could not import match_email_rows_batch_task from .tasks! Matching will not run for email {instance.id}.")
                             final_status = 'error' # Set to error if task cannot be imported
                        except Exception as task_error:
                             logger.error(f"CRITICAL: Error scheduling matching task for email {instance.id}: {task_error}", exc_info=True)
                             final_status = 'error' # Set to error if task scheduling fails
                        
                        # Update status based on fallback and task scheduling outcome
                        if used_fallback and final_status != 'error':
                             # YENİ: Fallback kullanıldıysa bile, gövdeden başarılı veri çıktıysa _check_attachments ekini kaldır
                             final_status = 'needs_review'
                             
                        instance.status = final_status
                        instance.save(update_fields=['status', 'updated_at'])
                        logger.info(f"Email {instance.id} status set to '{final_status}'.")
                        # --- End Activate Matching Task Call --- 
                    else:
                        # AI/Fallback was successful according to API, but yielded no rows 
                        logger.warning(f"AI/Fallback analysis successful for email {instance.id} but no rows were created. Status set to 'processing_attachments' and triggering attachment check.")
                        # Also flag for attachment check in this edge case
                        instance.status = 'processing_attachments'
                        instance.save(update_fields=['status', 'updated_at'])
                        from .tasks import process_email_attachments_task # Import the NEW task
                        process_email_attachments_task.delay(instance.id) # Trigger the NEW task
                        
                elif not api_success:
                    # --- AI and Fallback (if attempted) FAILED --- 
                    logger.warning(f"AI/Fallback analysis failed for email {instance.id}. Setting status to 'processing_attachments' and triggering attachment check.")
                    print(f"AUTO-ANALYZE WARNING: AI/Fallback failed for email {instance.id}. Setting status to processing_attachments.")
                    instance.status = 'processing_attachments' # Set status for attachment processing
                    instance.save(update_fields=['status', 'updated_at'])
                    from .tasks import process_email_attachments_task # Import the NEW task
                    process_email_attachments_task.delay(instance.id) # Trigger the NEW task
            else:
                # No active AI model or prompt found
                logger.warning("No active AI model or prompt found. Setting status to 'processing_attachments' and triggering attachment check.")
                print("AUTO-ANALYZE WARNING: No active AI model or prompt. Setting status to processing_attachments.")
                instance.status = 'processing_attachments' # Set status for attachment processing
                instance.save(update_fields=['status', 'updated_at'])
                from .tasks import process_email_attachments_task # Import the NEW task
                process_email_attachments_task.delay(instance.id) # Trigger the NEW task
                
        except Exception as e:
            logger.error(f"Error in auto_analyze_email signal for email {instance.id}: {str(e)}", exc_info=True)
            print(f"AUTO-ANALYZE CRITICAL ERROR: for email {instance.id}: {str(e)}")
            try:
                if Email.objects.filter(pk=instance.pk).exists(): 
                    instance.status = 'error' # Critical error in signal itself
                    instance.save(update_fields=['status', 'updated_at'])
            except Exception as save_error:
                 logger.error(f"Failed to mark email {instance.id} as error after signal failure: {save_error}", exc_info=True)

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