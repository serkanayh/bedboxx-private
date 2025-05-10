from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin, xframe_options_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from urllib.parse import urlencode

from .models import Email, EmailRow, UserLog, EmailAttachment
from hotels.models import Hotel, Room, Market
from core.models import AIPerformanceMetric

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta

# Set up logger
logger = logging.getLogger(__name__)

# Try to import the AI analyzer
try:
    from ai.analyzer import ClaudeAnalyzer
    AI_ANALYZER_AVAILABLE = True
    logger.info("ClaudeAnalyzer successfully imported")
except ImportError as e:
    logger.error(f"Failed to import ClaudeAnalyzer: {e}")
    AI_ANALYZER_AVAILABLE = False


@login_required
def email_list(request):
    """
    View for listing emails
    """
    # Get query parameters
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    sort_order = request.GET.get('sort', 'asc')  # Default is ascending (oldest first)
    
    # Base queryset
    queryset = Email.objects.all()
    
    # Apply filters
    if status:
        queryset = queryset.filter(status=status)
    
    if search:
        queryset = queryset.filter(
            Q(subject__icontains=search) | 
            Q(sender__icontains=search) |
            Q(body_text__icontains=search)
        )
    
    # Order by received date (oldest first by default, user can change)
    if sort_order == 'desc':
        queryset = queryset.order_by('-received_date')  # Newest first
    else:
        queryset = queryset.order_by('received_date')   # Oldest first
    
    # Hesaplanan özellikler: Önceden hesaplayıp template'e gönder
    for email in queryset:
        email.total_count = email.total_rules_count
        
        # Güncellenmiş matched_rules_count mantığını kullan
        # Juniper otel eşleşmesi olan ve juniper_rooms ilişkisinde kayıt olan satırlar
        rows_with_rooms = email.rows.filter(
            juniper_hotel__isnull=False
        ).filter(
            juniper_rooms__isnull=False
        ).distinct()
        
        # Juniper otel eşleşmesi olan ve ALL ROOM tipi olan satırlar
        all_room_rows = email.rows.filter(
            juniper_hotel__isnull=False, 
            room_type__iregex=r'all\s*room'  # "ALL ROOM", "All Room", "ALLROOM" gibi varyasyonlar
        ).distinct()
        
        # İki sorgu sonucunu birleştir ve tekrar sayısını say (distinct)
        email.matched_count = (rows_with_rooms | all_room_rows).distinct().count()
        
        # Eşleşme oranı rengini belirle
        if email.total_count == 0:
            email.match_status_color = "secondary"  # Gri renk (eşleşme yok)
        elif email.matched_count == email.total_count:
            email.match_status_color = "success"    # Yeşil renk (tam eşleşme)
        elif email.matched_count >= email.total_count * 0.75:
            email.match_status_color = "warning"    # Turuncu renk (yüksek eşleşme)
        else:
            email.match_status_color = "danger"     # Kırmızı renk (düşük eşleşme)
    
    # Paginate
    paginator = Paginator(queryset, 20)  # Show 20 emails per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status,
        'search_query': search,
        'sort_order': sort_order,  # Pass current sort order to template
    }
    
    return render(request, 'emails/email_list.html', context)


@login_required
def email_detail(request, email_id):
    """
    View for displaying email details
    """
    email = get_object_or_404(Email, id=email_id)
    rows = email.rows.all().order_by('id')
    attachments = email.attachments.all().order_by('id')

    # Filtreleme
    match = request.GET.get('match')
    if match == 'danger':
        rows = rows.filter(juniper_rooms__isnull=True)
    elif match == 'success':
        rows = [r for r in rows if hasattr(r, 'get_match_status') and r.get_match_status() == 'success']
    elif match == 'warning':
        rows = [r for r in rows if hasattr(r, 'get_match_status') and r.get_match_status() == 'warning']

    # --- ADD analysis result to each attachment --- 
    attachment_analysis_results = email.attachment_analysis_results or {}
    for att in attachments:
        try:
            att_id_str = str(att.id)
            att.analysis_result = attachment_analysis_results.get(att_id_str, None)
        except Exception as e:
            logger.error(f"Error assigning analysis result to attachment {att.id} for email {email.id}: {e}")
            att.analysis_result = None
    # --- END ADD --- 

    # Process HTML content for display with embedded images
    processed_html = process_html_for_display(email)

    # AI önerilerini oluştur
    ai_suggestions = []
    
    # Eşleşmesi olmayan satırlar için öneriler üret
    unmatched_rows = [r for r in rows if (r.status == 'pending' or r.status == 'matching' or r.status == 'hotel_not_found' or r.status == 'room_not_found') and (not r.juniper_hotel or (not r.juniper_rooms.exists() and not r.room_type.lower().strip() in ['all room', 'all rooms', 'all room types']))]
    
    if unmatched_rows:
        # EmailHotelMatch ve RoomTypeMatch modellerini kullanarak öneriler oluştur
        from .models import EmailHotelMatch, RoomTypeMatch
        
        for row in unmatched_rows[:5]:  # İlk 5 eşleşmemiş satır için öneriler göster
            # 1. Gönderen e-postaya göre otel önerisi
            if row.email.sender and not row.juniper_hotel:
                sender_email = row.email.sender
                if '<' in sender_email and '>' in sender_email:
                    sender_email = sender_email.split('<')[1].split('>')[0].strip()
                
                hotel_matches = EmailHotelMatch.objects.filter(sender_email=sender_email).order_by('-confidence_score')[:3]
                
                for hotel_match in hotel_matches:
                    # Otel önerisi oluştur
                    suggestion = {
                        'row_id': row.id,
                        'hotel_id': hotel_match.hotel.id,
                        'hotel_name': hotel_match.hotel.juniper_hotel_name,
                        'room_type': "Sistem tarafından belirlenecek",
                        'room_ids': [],
                        'confidence': min(hotel_match.confidence_score, 95),  # En fazla %95 güven
                        'reason': f"Bu gönderici ({sender_email}) daha önce bu otel için eşleştirme yapmış"
                    }
                    
                    # Oda önerileri ekle
                    if row.room_type:
                        room_matches = RoomTypeMatch.objects.filter(
                            email_room_type__icontains=row.room_type,
                            juniper_room__hotel=hotel_match.hotel
                        )[:3]  # Remove the problematic order_by('-match_score')
                        
                        if room_matches:
                            suggestion['room_type'] = ', '.join([rm.juniper_room.juniper_room_type for rm in room_matches])
                            suggestion['room_ids'] = [rm.juniper_room.id for rm in room_matches]
                            suggestion['reason'] += f" ve benzer oda tipleri için kullanılmış"
                    
                    ai_suggestions.append(suggestion)
            
            # 2. Benzer otel adı ve oda tipi eşleştirmesi
            if row.hotel_name and not row.juniper_hotel:
                from difflib import SequenceMatcher
                from hotels.models import Hotel
                
                hotels = Hotel.objects.all()
                best_matches = []
                
                for hotel in hotels:
                    score = SequenceMatcher(None, row.hotel_name.lower(), hotel.juniper_hotel_name.lower()).ratio()
                    if score > 0.6:  # %60 üzerinde benzerlik
                        best_matches.append((hotel, score))
                
                # En iyi 3 eşleşme için öneriler oluştur
                best_matches.sort(key=lambda x: x[1], reverse=True)
                for hotel, score in best_matches[:3]:
                    suggestion = {
                        'row_id': row.id,
                        'hotel_id': hotel.id,
                        'hotel_name': hotel.juniper_hotel_name,
                        'room_type': "Sistem tarafından belirlenecek",
                        'room_ids': [],
                        'confidence': int(score * 100),
                        'reason': f"Otel adı benzerliği: {int(score * 100)}%"
                    }
                    
                    # Oda önerileri ekleme mantığı
                    if row.room_type:
                        from hotels.models import Room
                        rooms = Room.objects.filter(hotel=hotel)
                        room_best_matches = []
                        
                        for room in rooms:
                            room_score = SequenceMatcher(None, row.room_type.lower(), room.juniper_room_type.lower()).ratio()
                            if room_score > 0.5:  # %50 üzerinde benzerlik
                                room_best_matches.append((room, room_score))
                        
                        room_best_matches.sort(key=lambda x: x[1], reverse=True)
                        if room_best_matches:
                            suggestion['room_type'] = ', '.join([rm[0].juniper_room_type for rm in room_best_matches[:3]])
                            suggestion['room_ids'] = [rm[0].id for rm in room_best_matches[:3]]
                            suggestion['reason'] += f" ve oda tipi benzerliği"
                    
                    ai_suggestions.append(suggestion)
    
    # Yüksek güvenden düşük güvene doğru sırala
    ai_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Eğer birden fazla öneri varsa, en iyi 5 tanesi ile sınırla
    ai_suggestions = ai_suggestions[:5] if ai_suggestions else []

    has_analyzed_attachments = rows.filter(extracted_from_attachment=True).exists() if hasattr(rows, 'filter') else any(getattr(r, 'extracted_from_attachment', False) for r in rows)
    first_matched_row = rows.filter(juniper_hotel__isnull=False).first() if hasattr(rows, 'filter') else None
    unique_hotel_names = list(rows.exclude(hotel_name__isnull=True).exclude(hotel_name__exact='').values_list('hotel_name', flat=True).distinct().order_by('hotel_name')) if hasattr(rows, 'exclude') else []

    context = {
        'email': email,
        'rows': rows,
        'attachments': attachments,
        'has_analyzed_attachments': has_analyzed_attachments,
        'first_matched_row': first_matched_row,
        'unique_hotel_names': unique_hotel_names,
        'ai_suggestions': ai_suggestions,  # AI önerilerini context'e ekle
        'processed_html': processed_html,  # Add processed HTML to context
    }
    return render(request, 'emails/email_detail.html', context)


@login_required
@xframe_options_exempt
def email_attachment_view(request, attachment_id):
    """
    View for displaying email attachment (allows embedding anywhere)
    """
    attachment = get_object_or_404(EmailAttachment, id=attachment_id)
    
    # Check if the file exists
    if not os.path.exists(attachment.file.path):
        return HttpResponse("Attachment file not found", status=404)
    
    # Determine content type
    content_type = attachment.content_type
    if not content_type:
        content_type = 'application/octet-stream'  # Default content type
    
    # Define safely previewable content types
    safe_preview_types = [
        'application/pdf',
        'text/plain',
        'text/html',
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/svg+xml'
    ]
    
    # Check file extension for common problematic formats that may cause 415 errors
    filename = attachment.filename.lower()
    problematic_extensions = ['.xlsx', '.xls', '.doc', '.docx', '.pptx', '.ppt', '.msg']
    
    force_download = False
    # If content type isn't safely previewable or has problematic extension, force download
    if content_type not in safe_preview_types or any(filename.endswith(ext) for ext in problematic_extensions):
        force_download = True
    
    # Get force_preview parameter from query string
    force_preview = request.GET.get('force_preview', '').lower() == 'true'
    if force_preview:
        force_download = False
    
    try:
        with open(attachment.file.path, 'rb') as f:
            file_content = f.read()
            
            response = HttpResponse(file_content, content_type=content_type)
            
            # Use 'attachment' disposition for download (to prevent 415 errors)
            # Use 'inline' for preview attempt
            if force_download:
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment.filename)}"'
            else:
                response['Content-Disposition'] = f'inline; filename="{os.path.basename(attachment.filename)}"'
            
            return response
    except FileNotFoundError:
        logger.error(f"File not found during serving: {attachment.file.path}")
        return HttpResponse("Attachment file physically not found on server", status=404)
    except Exception as e:
        logger.error(f"Error serving attachment {attachment_id}: {e}", exc_info=True)
        return HttpResponse("Error serving attachment", status=500)


@login_required
def process_email_with_ai(request, email_id):
    """
    View for processing an email with AI
    """
    email = get_object_or_404(Email, id=email_id)
    
    if not AI_ANALYZER_AVAILABLE:
        messages.error(request, "AI analyzer is not available")
        return redirect('emails:email_detail', email_id=email_id)
    
    # Check if the email already has rows
    if email.rows.exists():
        messages.warning(request, "This email has already been processed")
        return redirect('emails:email_detail', email_id=email_id)
    
    try:
        # Create an instance of the AI analyzer
        analyzer = ClaudeAnalyzer()
        
        # Process the email content
        start_time = timezone.now()
        result = analyzer.analyze_email(email.body_text, email.subject)
        end_time = timezone.now()
        
        # Log AI performance
        AIPerformanceMetric.objects.create(
            email=email,
            processing_time=(end_time - start_time).total_seconds(),
            model_name=analyzer.get_model_name(),
            prompt_tokens=analyzer.get_prompt_tokens(),
            completion_tokens=analyzer.get_completion_tokens(),
            success=result.get('success', False)
        )
        
        if result.get('success', False):
            rows_data = result.get('data', [])
            created_rows = [] # Keep track of created rows for batch matching
            for row_data in rows_data:
                
                # --- Parse dates using the helper function --- 
                start_date_str = row_data.get('start_date')
                end_date_str = row_data.get('end_date')
                
                parsed_start_date = parse_ai_date(start_date_str)
                parsed_end_date = parse_ai_date(end_date_str)
                # --- End date parsing --- 
                
                try:
                    email_row = EmailRow.objects.create(
                        email=email,
                        hotel_name=row_data.get('hotel_name', ''),
                        room_type=row_data.get('room_type', ''),
                        market=row_data.get('market', ''), # Assuming market is a string from AI
                        start_date=parsed_start_date, # Use parsed date
                        end_date=parsed_end_date,   # Use parsed date
                        sale_type=row_data.get('sale_type', 'stop'),
                        status='matching', # Start with matching status for the task
                        ai_extracted=True
                    )
                    created_rows.append(email_row.id)

                except Exception as create_error:
                     logger.error(f"Error creating EmailRow for data: {row_data}. Error: {create_error}", exc_info=True)
                     continue # Skip to the next row_data

            # --- Trigger batch matching task --- 
            if created_rows:
                logger.info(f"Scheduling BATCH matching task for email {email.id} with {len(created_rows)} rows.")
                from .tasks import match_email_rows_batch_task # Import task here
                match_email_rows_batch_task.delay(email.id, created_rows)
                email.status = 'processing' # Or a more specific status
                email.save()
            else:
                 logger.warning(f"AI analysis successful for email {email.id} but no rows were created.")
                 email.status = 'processed_nodata' 
                 email.save()

            messages.success(request, f"AI processing initiated for email {email.id}. Rows are being matched.") # Updated message
        else:
            # If AI processing failed but email has attachments, try to analyze attachments
            if email.has_attachments and email.attachments.exists():
                success = process_email_attachments(email, request.user)
                if success:
                    messages.success(request, "Email processed using attachment analysis")
                else:
                    messages.error(request, f"Failed to process email with AI: {result.get('error', 'Unknown error')}")
            else:
                messages.error(request, f"Failed to process email with AI: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"Error processing email with AI: {e}", exc_info=True)
        messages.error(request, f"Error processing email: {str(e)}")
    
    return redirect('emails:email_detail', email_id=email_id)


def process_email_attachments(email, user):
    """
    Process email attachments to extract stop sale/open sale information
    """
    try:
        # Check if email has attachments
        attachments = email.attachments.all()
        if not attachments.exists():
            logger.warning(f"No attachments found for email {email.id}")
            return False
        
        # Track if any attachment was successfully analyzed
        any_success = False
        # --- Define allowed file extensions --- 
        allowed_extensions = ('.pdf', '.docx', '.xlsx', '.xls', '.doc')
        
        created_row_ids = []
        for attachment in attachments:
            # --- Check file extension --- 
            filename = attachment.filename.lower()
            if not filename.endswith(allowed_extensions):
                logger.info(f"Skipping attachment analysis for {attachment.filename} (Email ID: {email.id}) - Unsupported file type.")
                continue # Skip to the next attachment
            
            # Skip if file doesn't exist
            if not os.path.exists(attachment.file.path):
                logger.warning(f"Attachment file not found: {attachment.file.path}")
                continue
            
            logger.info(f"Analyzing attachment: {attachment.filename} (Email ID: {email.id}) - Type OK.") # Log analysis start
            # Analyze the attachment
            result = attachment_analyzer.analyze(attachment.file.path)
            
            # Skip if analysis failed
            if 'error' in result:
                logger.warning(f"Failed to analyze attachment {attachment.id}: {result['error']}")
                continue
            
            # Process extracted rules
            hotels_data = result.get('hotels', [])
            if hotels_data:
                for hotel_data in hotels_data:
                    # Parse date range
                    date_range = hotel_data.get('date_range', '')
                    start_date, end_date = parse_date_range(date_range)
                    
                    # Create email row
                    email_row = EmailRow.objects.create(
                        email=email,
                        hotel_name=hotel_data.get('name', ''),
                        room_type=hotel_data.get('room_type', ''),
                        market=hotel_data.get('market', ''),
                        start_date=start_date,
                        end_date=end_date,
                        sale_type='stop' if hotel_data.get('action') == 'stop_sale' else 'open',
                        status='matching', # Set initial status to matching
                        ai_extracted=False, # Not extracted by body AI
                        extracted_from_attachment=True # Extracted from attachment
                    )
                    
                    # Append row ID to list for batch matching
                    created_row_ids.append(email_row.id)

            # After loop, if rows were created, schedule batch matching
            if created_row_ids:
                logger.info(f"Scheduling BATCH matching task for email {email.id} (from attachment) with {len(created_row_ids)} rows.")
                from .tasks import match_email_rows_batch_task # Import task here
                match_email_rows_batch_task.delay(email.id, created_row_ids)
                email.status = 'processing' # Update email status
                any_success = True
            else:
                # No valid data found in this attachment
                logger.warning(f"No valid rows extracted from attachment {attachment.filename} for email {email.id}")

        # Update email status based on whether any attachment yielded rows
        if any_success:
            pass 
        else:
            logger.warning(f"Attachment analysis completed for email {email.id}, but no valid data found in any attachment.")
            email.status = 'processed_nodata'
            
        email.save() # Save email status change
        
        # Log the action
        UserLog.objects.create(
            user=user,
            action_type='process_email_attachments',
            email=email,
            ip_address='127.0.0.1',  # Default for non-request context
            details='Processed via attachment analysis'
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error processing email attachments: {e}", exc_info=True)
        return False


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
    
    today = timezone.now().date()
    return today, today + timedelta(days=7)


@login_required
def approve_row(request, row_id):
    """
    View for approving a row
    """
    from .models import EmailHotelMatch
    row = get_object_or_404(EmailRow, id=row_id)
    
    if row.status != 'pending':
        messages.error(request, "Only pending rows can be approved")
        return redirect('emails:email_detail', email_id=row.email.id)
    
    is_all_room_type = row.room_type.strip().upper() in ['ALL ROOM', 'ALL ROOMS', 'ALL ROOM TYPES']
    if not row.juniper_hotel or (not row.juniper_rooms.exists() and not is_all_room_type):
        messages.error(request, "Cannot approve row without hotel match and either a room match or 'All Room' type.")
        return redirect('emails:email_detail', email_id=row.email.id)
    
    row.status = 'approved'
    row.processed_by = request.user
    row.processed_at = timezone.now()
    row.save()
    
    UserLog.objects.create(
        user=request.user,
        action_type='approve_row',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # --- E-posta ve otel eşleşme veritabanına ekle/güncelle ---
    try:
        # E-posta göndericisini ayıkla
        sender_email = row.email.sender
        if '<' in sender_email and '>' in sender_email:
            # Format: "İsim Soyisim <email@domain.com>"
            sender_email = sender_email.split('<')[1].split('>')[0].strip()
        elif '@' in sender_email:
            # Format: email@domain.com
            sender_email = sender_email.strip()
            
        # Öğrenilen eşleştirmeyi kaydet/güncelle
        hotel_match, created = EmailHotelMatch.objects.get_or_create(
            sender_email=sender_email,
            hotel=row.juniper_hotel
        )
        
        if not created:
            # Kaydı güncelleyerek güven puanını artır
            hotel_match.increase_confidence()
            logger.info(f"Öğrenilen eşleştirme güncellendi: {sender_email} -> {row.juniper_hotel.juniper_hotel_name} (Güven: {hotel_match.confidence_score})")
        else:
            logger.info(f"Yeni öğrenilen eşleştirme kaydedildi: {sender_email} -> {row.juniper_hotel.juniper_hotel_name}")
            
    except Exception as e:
        logger.error(f"Öğrenilen eşleştirme kaydı sırasında hata: {str(e)}")
    # --- E-posta ve otel eşleşme güncellemesi sonu ---
    
    email = row.email
    all_rows = email.rows.all()
    if not all_rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).exists():
        if all_rows.filter(status='approved').count() == all_rows.count():
            email.status = 'approved'
            email.processed_by = request.user
            email.processed_at = timezone.now()
            email.save()
        elif all_rows.filter(status='rejected').count() == all_rows.count():
             email.status = 'rejected'
             email.processed_by = request.user
             email.processed_at = timezone.now()
             email.save()
        else:
             email.status = 'processed'
             email.processed_by = request.user
             email.processed_at = timezone.now()
             email.save()

    messages.success(request, "Row approved successfully")
    # Filtre parametrelerini koru
    query_string = request.META.get('QUERY_STRING', '')
    if query_string:
        return redirect(f"{reverse('emails:email_detail', args=[row.email.id])}?{query_string}")
    return redirect('emails:email_detail', email_id=row.email.id)


@login_required
def reject_row(request, row_id):
    """Reject a single row."""
    row = get_object_or_404(EmailRow, id=row_id)
    row.status = 'rejected'
    row.processed_by = request.user
    row.processed_at = timezone.now()
    row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_row',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected row {row_id}"
    )
    
    # Update email status if all rows have been processed
    email = row.email
    pending_rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).count()
    
    if pending_rows == 0:
        # All rows have been processed, update the email status
        email.status = 'rejected'  # Keep 'rejected' for general rejection
        email.processed_by = request.user
        email.processed_at = timezone.now()
        email.save()
    
    messages.success(request, f"Row {row_id} has been rejected.")
    return redirect('emails:email_detail', email_id=row.email.id)


@login_required
def reject_row_hotel_not_found(request, row_id):
    """Reject a single row with reason: JP Hotel Not Found."""
    row = get_object_or_404(EmailRow, id=row_id)
    row.status = 'rejected_hotel_not_found'
    row.reject_reason = 'JP Hotel Not Found'
    row.processed_by = request.user
    row.processed_at = timezone.now()
    row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_row_hotel_not_found',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected row {row_id} - JP Hotel Not Found"
    )
    
    # Update email status if all rows have been processed
    email = row.email
    pending_rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).count()
    
    if pending_rows == 0:
        # All rows have been processed, update the email status
        email.status = 'rejected_hotel_not_found'  # Use specific rejection reason
        email.processed_by = request.user
        email.processed_at = timezone.now()
        email.save()
    
    messages.success(request, f"Row {row_id} has been rejected: JP Hotel Not Found.")
    return redirect('emails:email_detail', email_id=row.email.id)


@login_required
def reject_row_room_not_found(request, row_id):
    """Reject a single row with reason: JP Room Not Found."""
    row = get_object_or_404(EmailRow, id=row_id)
    row.status = 'rejected_room_not_found'
    row.reject_reason = 'JP Room Not Found'
    row.processed_by = request.user
    row.processed_at = timezone.now()
    row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_row_room_not_found',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected row {row_id} - JP Room Not Found"
    )
    
    # Update email status if all rows have been processed
    email = row.email
    pending_rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).count()
    
    if pending_rows == 0:
        # All rows have been processed, update the email status
        email.status = 'rejected_room_not_found'  # Use specific rejection reason
        email.processed_by = request.user
        email.processed_at = timezone.now()
        email.save()
    
    messages.success(request, f"Row {row_id} has been rejected: JP Room Not Found.")
    return redirect('emails:email_detail', email_id=row.email.id)


@login_required
def send_to_robot(request, row_id):
    """
    View for sending a row to the RPA robot
    """
    row = get_object_or_404(EmailRow, id=row_id)
    
    if row.status != 'approved':
        messages.error(request, "Only approved rows can be sent to the robot")
        return redirect('emails:email_detail', email_id=row.email.id)
    
    row.status = 'sent_to_robot'
    row.save()
    
    UserLog.objects.create(
        user=request.user,
        action_type='send_to_robot',
        email=row.email,
        email_row=row,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    messages.success(request, "Row sent to robot successfully")
    return redirect('emails:email_detail', email_id=row.email.id)


@csrf_exempt
def webhook_robot_callback(request):
    """
    Webhook endpoint for RPA robot callback
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        row_id = data.get('row_id')
        success = data.get('success', False)
        message = data.get('message', '')
        
        if not row_id:
            return JsonResponse({'error': 'Row ID is required'}, status=400)
        
        row = get_object_or_404(EmailRow, id=row_id)
        
        if success:
            row.status = 'robot_processed'
        else:
            row.status = 'error'
        
        row.save()
        
        UserLog.objects.create(
            user=None,  # No user for webhook
            action_type='robot_callback',
            email=row.email,
            email_row=row,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=message
        )
        
        return JsonResponse({'status': 'success'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in robot callback: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def match_hotel(request, row_id):
    """
    View for matching a row to a hotel
    """
    row = get_object_or_404(EmailRow, id=row_id)
    
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel_id')
        
        if hotel_id:
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                row.juniper_hotel = hotel
                row.save()
                
                UserLog.objects.create(
                    user=request.user,
                    action_type='match_hotel',
                    email=row.email,
                    email_row=row,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Row matched to hotel: {hotel.juniper_hotel_name}")
            except Hotel.DoesNotExist:
                messages.error(request, "Selected hotel not found")
        else:
            messages.error(request, "No hotel selected")
        
        return redirect('emails:email_detail', email_id=row.email.id)
    
    context = {
        'row': row,
        'hotels': hotels,
    }
    
    return render(request, 'emails/match_hotel.html', context)


def get_room_suggestions(room_type, hotel):
    """
    Enhanced room matching algorithm that first finds the highest scoring single room match,
    then uses that room's name to suggest related rooms.
    
    Args:
        room_type (str): The room type from the email
        hotel (Hotel): The hotel object to search rooms for
        
    Returns:
        tuple: (best_match, suggestions, search_pattern)
            - best_match: The room with highest match score
            - suggestions: List of suggested related rooms
            - search_pattern: The pattern used to find related rooms
    """
    from difflib import SequenceMatcher
    from re import search, IGNORECASE
    
    # Get all rooms for this hotel
    available_rooms = Room.objects.filter(hotel=hotel)
    if not available_rooms:
        return None, [], None
    
    # Find the best matching room
    highest_score = 0
    best_match = None
    
    # Clean the room type for better matching
    clean_room_type = room_type.strip().upper()
    
    for room in available_rooms:
        # Calculate similarity score using SequenceMatcher
        juniper_room_type = room.juniper_room_type.strip().upper()
        score = SequenceMatcher(None, clean_room_type, juniper_room_type).ratio()
        
        # Update best match if score is higher
        if score > highest_score:
            highest_score = score
            best_match = room
    
    if best_match is None:
        return None, [], None
        
    # Extract pattern from best match room name
    # Look for patterns after "PAX" or "SNG" in the room name
    pattern = None
    juniper_room_name = best_match.juniper_room_type.upper()
    
    # Try to find pattern after "PAX" or "SNG"
    pax_match = search(r'(\d+)\s*PAX\s*(.*?)(?:\s|$)', juniper_room_name, IGNORECASE)
    sng_match = search(r'SNG\s*(.*?)(?:\s|$)', juniper_room_name, IGNORECASE)
    
    if pax_match:
        pattern = pax_match.group(2).strip()
    elif sng_match:
        pattern = sng_match.group(1).strip()
    
    # If no pattern found after PAX/SNG, try to use the part after room type (SUITE, ROOM, etc.)
    if not pattern or pattern == '':
        type_match = search(r'(SUITE|ROOM|DBL|DOUBLE|TWIN|SINGLE)\s*(.*?)(?:\s|$)', juniper_room_name, IGNORECASE)
        if type_match:
            pattern = type_match.group(2).strip()
    
    suggestions = []
    
    # If a pattern was found, find related rooms
    if pattern and pattern != '':
        for room in available_rooms:
            if pattern.upper() in room.juniper_room_type.upper() and room != best_match:
                suggestions.append(room)
    
    # Add the best match to the beginning of the suggestions
    if best_match and best_match not in suggestions:
        suggestions.insert(0, best_match)
        
    return best_match, suggestions, pattern


@login_required
def match_room(request, row_id):
    """
    View for matching a row to one or more rooms (multi-select)
    """
    from .models import RoomTypeMatch
    row = get_object_or_404(EmailRow, id=row_id)
    if not row.juniper_hotel:
        messages.error(request, "Must match hotel before matching room")
        return redirect('emails:email_detail', email_id=row.email.id)
    
    # Get all rooms for this hotel
    rooms = Room.objects.filter(hotel=row.juniper_hotel).order_by('juniper_room_type')
    
    # Get suggestions using the enhanced algorithm
    best_match, suggestions, search_pattern = get_room_suggestions(row.room_type, row.juniper_hotel)
    
    if request.method == 'POST':
        room_ids = request.POST.getlist('room_ids')
        if room_ids:
            selected_rooms = Room.objects.filter(id__in=room_ids, hotel=row.juniper_hotel)
            row.juniper_rooms.set(selected_rooms)
            # Oda eşleştirmesi sonrası status 'pending' yapılır (manuel mapping ile aynı mantık)
            if row.status != 'approved':
                row.status = 'pending'
            row.save()
            # Öğrenen sistem için RoomTypeMatch kaydı
            for room in selected_rooms:
                RoomTypeMatch.objects.get_or_create(email_room_type=row.room_type, juniper_room=room)
            UserLog.objects.create(
                user=request.user,
                action_type='match_room',
                email=row.email,
                email_row=row,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, "Room(s) matched successfully.")
        else:
            row.juniper_rooms.clear()
            messages.error(request, "No room selected.")
        return redirect('emails:email_detail', email_id=row.email.id)
    
    context = {
        'row': row,
        'rooms': rooms,
        'best_match': best_match,
        'suggestions': suggestions,
        'search_pattern': search_pattern,
    }
    return render(request, 'emails/match_room.html', context)


@login_required
def confirm_attachment_analysis(request, email_id):
    """
    View for confirming attachment analysis results
    """
    email = get_object_or_404(Email, id=email_id)
    
    attachment_rows = email.rows.filter(from_attachment=True)
    
    if not attachment_rows.exists():
        messages.error(request, "No attachment analysis results found for this email")
        return redirect('emails:email_detail', email_id=email.id)
    
    if request.method == 'POST':
        row_ids = request.POST.getlist('row_ids')
        
        if not row_ids:
            messages.error(request, "No rows selected for confirmation")
            return redirect('emails:email_detail', email_id=email.id)
        
        selected_rows = EmailRow.objects.filter(id__in=row_ids)
        
        email.rows.filter(from_attachment=True).exclude(id__in=row_ids).delete()
        
        for row in selected_rows:
            row.status = 'pending'
            row.save()
        
        email.status = 'processed'
        email.save()
        
        UserLog.objects.create(
            user=request.user,
            action_type='confirm_attachment_analysis',
            email=email,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Confirmed {len(selected_rows)} rows from attachment analysis"
        )
        
        messages.success(request, f"Successfully confirmed {len(selected_rows)} rows from attachment analysis")
        return redirect('emails:email_detail', email_id=email.id)
    
    context = {
        'email': email,
        'attachment_rows': attachment_rows,
    }
    
    return render(request, 'emails/confirm_attachment_analysis.html', context)


@login_required
def manual_mapping(request, row_id):
    """
    View for manually mapping email row data
    """
    row = get_object_or_404(EmailRow, id=row_id)
    
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    markets = Market.objects.all().order_by('name')
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel_id')
        room_types = request.POST.getlist('room_types')
        market_id = request.POST.get('market_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        sale_type = request.POST.get('sale_type')

        if not hotel_id or not room_types or not market_id or not start_date or not end_date or not sale_type:
            messages.error(request, "All fields are required")
            return redirect('emails:manual_mapping', row_id=row.id) 
            
        try:
            hotel = Hotel.objects.get(id=hotel_id)
            
            market = Market.objects.get(id=market_id)
            
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            row.juniper_hotel = hotel
            row.hotel_name = hotel.juniper_hotel_name
            row.start_date = start_date_obj
            row.end_date = end_date_obj
            row.sale_type = sale_type
            
            if hasattr(row, 'juniper_rooms'):
                 row.juniper_rooms.clear()
                 row.room_type = None 

            if 'all' in room_types:
                row.room_type = "All Room" 
            else:
                 selected_rooms = Room.objects.filter(hotel=hotel, id__in=room_types)
                 if selected_rooms.exists():
                     row.juniper_rooms.set(selected_rooms)
                     row.room_type = ", ".join(selected_rooms.values_list('juniper_room_type', flat=True))
                 else:
                      logger.warning(f"Invalid room IDs {room_types} selected for hotel {hotel_id} in manual mapping for row {row.id}")
                      row.room_type = "Invalid Selection" 

            if row.status != 'approved': 
                 row.status = 'pending' 

            row.save()
            
            UserLog.objects.create(
                user=request.user,
                action_type='manual_mapping',
                email=row.email,
                email_row=row,
                ip_address=request.META.get('REMOTE_ADDR'),
                details='Manual mapping of row data completed successfully.'
            )
            
            messages.success(request, "Row data mapped successfully")
            return redirect('emails:email_detail', email_id=row.email.id) 
    
        except (Hotel.DoesNotExist, Market.DoesNotExist, Room.DoesNotExist) as e:
            logger.error(f"Entity not found during manual mapping for row {row.id}: {e}", exc_info=True)
            messages.error(request, f"Selected entity not found: {e}")
        except ValueError as e:
            logger.error(f"Invalid date format during manual mapping for row {row.id}: {e}", exc_info=True)
            messages.error(request, f"Invalid date format: {e}")
        except Exception as e:
            logger.error(f"Error in manual mapping for row {row.id}: {e}", exc_info=True)
            messages.error(request, f"An unexpected error occurred: {str(e)}")
        
        return redirect('emails:manual_mapping', row_id=row.id)
    
    rooms = []
    if row.juniper_hotel:
        rooms = Room.objects.filter(hotel=row.juniper_hotel).order_by('juniper_room_type')
        
    selected_room_ids = []
    if hasattr(row, 'juniper_rooms'):
        selected_room_ids = list(row.juniper_rooms.values_list('id', flat=True))
    elif row.juniper_room:
        selected_room_ids = [row.juniper_room.id]

    context = {
        'row': row,
        'hotels': hotels,
        'rooms': rooms, 
        'markets': markets,
        'selected_room_ids': selected_room_ids, 
    }

    return render(request, 'emails/manual_mapping.html', context)


@login_required
def get_rooms_by_hotel(request, hotel_id):
    """
    AJAX view to get rooms for a hotel
    """
    try:
        hotel = Hotel.objects.get(id=hotel_id)
        rooms = Room.objects.filter(hotel=hotel).order_by('juniper_room_type')
        
        rooms_data = [
            {'id': room.id, 'name': room.juniper_room_type}
            for room in rooms
        ]
        
        return JsonResponse({'rooms': rooms_data})
    
    except Hotel.DoesNotExist:
        return JsonResponse({'error': 'Hotel not found'}, status=404)
    
    except Exception as e:
        logger.error(f"Error getting rooms by hotel: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


def parse_ai_date(date_str, default_date=None):
    """Parse date string from AI, trying multiple formats."""
    if not date_str:
        return default_date or timezone.now().date()
    
    formats_to_try = [
        '%d.%m.%Y',  
        '%Y-%m-%d',  
        '%d/%m/%Y',  
        '%m/%d/%Y',  
    ]
    
    for fmt in formats_to_try:
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except (ValueError, TypeError):
            continue
            
    logger.warning(f"Could not parse date string '{date_str}' using formats {formats_to_try}. Using default.")
    return default_date or timezone.now().date()


@login_required
def reanalyze_email(request, email_id):
    """
    Deletes existing analysis results (EmailRows) and resets the email status
    to 'pending' to trigger automatic re-analysis via the post_save signal.
    """
    email = get_object_or_404(Email, id=email_id)
    
    try:
        with transaction.atomic():
            logger.info(f"User {request.user.username} initiated re-analysis for email {email.id} - {email.subject}")
            UserLog.objects.create(
                user=request.user,
                action_type='reanalyze_email',
                email=email,
                ip_address=request.META.get('REMOTE_ADDR'),
                details=f'Deleting {email.rows.count()} existing rows and resetting status to pending.'
            )
            
            email.rows.all().delete()
            
            email.status = 'pending'
            email.processed_by = None 
            email.processed_at = None 
            email.robot_status = 'pending' 
            email.save()
        
        messages.success(request, f"Email '{email.subject}' has been queued for re-analysis.")
    except Exception as e:
        logger.error(f"Error during re-analysis trigger for email {email.id}: {e}", exc_info=True)
        messages.error(request, f"An error occurred while trying to re-analyze the email: {str(e)}")

    return redirect('emails:email_detail', email_id=email.id)


@login_required
@require_POST
def confirm_match_ajax(request, row_id):
    row = get_object_or_404(EmailRow, id=row_id)
    row.status = 'approved'
    row.save()
    logger.info(f"Match confirmed for row {row_id} by user {request.user.username}")
    return JsonResponse({'status': 'success', 'message': 'Match confirmed successfully.'})


@login_required
def select_alternative_ajax(request, row_id):
    row = get_object_or_404(EmailRow, id=row_id)
    logger.info(f"Alternative selection requested for row {row_id} by user {request.user.username}")
    alternatives = [
        {'hotel_name': 'Alternative Hotel 1', 'hotel_code': 'ALT001', 'score': 85},
        {'hotel_name': 'Alternative Hotel 2', 'hotel_code': 'ALT002', 'score': 80},
    ]
    return JsonResponse({'status': 'info', 'message': 'Alternative selection UI/logic not fully implemented.'})


@login_required
@require_POST
def mark_not_found_ajax(request, row_id):
    row = get_object_or_404(EmailRow, id=row_id)
    row.status = 'hotel_not_found'
    row.juniper_hotel = None
    row.juniper_rooms.clear()
    row.save()
    logger.info(f"Row {row_id} marked as not found by user {request.user.username}")
    return JsonResponse({'status': 'success', 'message': 'Row marked as not found.'})


@login_required
def create_alias_ajax(request, row_id):
    row = get_object_or_404(EmailRow, id=row_id)
    logger.info(f"Alias creation requested for row {row_id} by user {request.user.username}")
    return JsonResponse({'status': 'info', 'message': 'Alias creation UI/logic not fully implemented.'})


def get_hotel_suggestions(hotel_name):
    """
    E-postadaki otel adına göre benzer otelleri bulmak için algoritma
    
    Args:
        hotel_name (str): E-postadaki otel adı
        
    Returns:
        tuple: (best_match, suggestions)
            - best_match: En yüksek puanlı otel eşleşmesi
            - suggestions: Önerilen benzer oteller listesi
    """
    from difflib import SequenceMatcher
    
    # Tüm otelleri al
    available_hotels = Hotel.objects.all()
    if not available_hotels:
        return None, []
    
    # En iyi eşleşen oteli bul
    highest_score = 0
    best_match = None
    suggestions = []
    
    # Otel adını temizle
    clean_hotel_name = hotel_name.strip().upper()
    
    for hotel in available_hotels:
        # SequenceMatcher kullanarak benzerlik puanı hesapla
        juniper_hotel_name = hotel.juniper_hotel_name.strip().upper()
        score = SequenceMatcher(None, clean_hotel_name, juniper_hotel_name).ratio()
        
        # Puanı yüksekse en iyi eşleşmeyi güncelle
        if score > highest_score:
            highest_score = score
            best_match = hotel
        
        # Benzerlik puanı 0.8'dan yüksekse önerilere ekle (0.6 yerine %80 ve üzeri)
        if score >= 0.8:
            hotel.match_score = int(score * 100)  # Yüzdelik gösterimi için
            suggestions.append(hotel)
    
    # En iyi eşleşmeyi önerilerin başına ekle (eğer zaten eklenmemişse)
    if best_match and best_match not in suggestions and highest_score >= 0.8:
        best_match.match_score = int(highest_score * 100)
        suggestions.insert(0, best_match)
    
    # Puanlara göre sırala
    suggestions.sort(key=lambda x: x.match_score, reverse=True)
    
    return best_match, suggestions


@login_required
def smart_match(request, row_id):
    """
    Tek sayfada hem otel hem de oda eşleştirmesini gerçekleştiren akıllı eşleştirme görünümü
    """
    from .models import RoomTypeMatch, EmailHotelMatch
    row = get_object_or_404(EmailRow, id=row_id)
    
    # Tüm otelleri al
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    
    # Otel önerilerini al
    best_hotel_match, hotel_suggestions = get_hotel_suggestions(row.hotel_name)
    
    # Şu anki otele ait odaları ve seçilen odaları hazırla
    rooms = []
    selected_room_ids = []
    best_room_match = None
    room_suggestions = []
    search_pattern = None
    
    # Eğer bir otel seçilmişse oda eşleştirme önerilerini göster
    if row.juniper_hotel:
        rooms = Room.objects.filter(hotel=row.juniper_hotel).order_by('juniper_room_type')
        
        # Seçili odaları al
        if hasattr(row, 'juniper_rooms'):
            selected_room_ids = list(row.juniper_rooms.values_list('id', flat=True))
        
        # Oda önerilerini al
        best_room_match, room_suggestions, search_pattern = get_room_suggestions(row.room_type, row.juniper_hotel)
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel_id')
        room_ids = request.POST.getlist('room_ids')
        
        if hotel_id:
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                row.juniper_hotel = hotel
                
                # Eğer oda seçimi yapıldıysa
                if room_ids:
                    selected_rooms = Room.objects.filter(id__in=room_ids, hotel=hotel)
                    row.juniper_rooms.set(selected_rooms)
                    
                    # Öğrenen sistem için RoomTypeMatch kaydı
                    for room in selected_rooms:
                        RoomTypeMatch.objects.get_or_create(email_room_type=row.room_type, juniper_room=room)
                else:
                    # Oda seçilmediyse önceki seçimleri temizle
                    row.juniper_rooms.clear()
                
                # Eşleştirme sonrası durumu 'pending' yap (onay bekliyor)
                if row.status != 'approved':
                    row.status = 'pending'
                
                row.save()
                
                # Kullanıcı işlemini kaydet
                UserLog.objects.create(
                    user=request.user,
                    action_type='smart_match',
                    email=row.email,
                    email_row=row,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details='Akıllı eşleştirme ile otel ve oda eşleştirmesi yapıldı'
                )
                
                # Öğrenen sistem için gönderen e-posta ve otel eşleştirmesini kaydet
                if row.email and row.email.sender and row.juniper_hotel:
                    sender_email = row.email.sender
                    try:
                        # E-posta adresini @ ve sonrasını ayıklama
                        if '<' in sender_email and '>' in sender_email:
                            # Format: "İsim Soyisim <email@domain.com>"
                            sender_email = sender_email.split('<')[1].split('>')[0].strip()
                        elif '@' in sender_email:
                            # Format: email@domain.com
                            sender_email = sender_email.strip()
                        
                        # Eğer bir kayıt varsa güncelle, yoksa yeni kayıt oluştur
                        hotel_match, created = EmailHotelMatch.objects.get_or_create(
                            sender_email=sender_email,
                            hotel=hotel
                        )
                        
                        if not created:
                            # Daha önce kaydedilmiş bir eşleşme ise güven puanını artır
                            hotel_match.increase_confidence()
                            
                        logger.info(f"Öğrenen sistem için kaydedildi: {sender_email} → {hotel.juniper_hotel_name}")
                    except Exception as e:
                        logger.error(f"Öğrenen sistem kaydı oluşturulurken hata: {str(e)}")
                
                messages.success(request, "Eşleştirme başarıyla tamamlandı")
                return redirect('emails:email_detail', email_id=row.email.id)
                
            except Hotel.DoesNotExist:
                messages.error(request, "Seçilen otel bulunamadı")
        else:
            messages.error(request, "Otel seçimi yapılmadı")
    
    context = {
        'row': row,
        'hotels': hotels,
        'hotel_suggestions': hotel_suggestions,
        'best_hotel_match': best_hotel_match,
        'rooms': rooms,
        'best_room_match': best_room_match,
        'room_suggestions': room_suggestions,
        'search_pattern': search_pattern,
        'selected_room_ids': selected_room_ids,
    }
    
    return render(request, 'emails/smart_match.html', context)


def get_room_suggestions(email_room_type, hotel):
    """
    E-postadaki oda tipine göre benzer odaları bulmak için algoritma
    
    Args:
        email_room_type (str): E-postadaki oda tipi
        hotel (Hotel): Seçilen otel
        
    Returns:
        tuple: (best_match, suggestions, search_pattern)
            - best_match: En yüksek puanlı oda eşleşmesi
            - suggestions: Önerilen benzer odalar listesi
            - search_pattern: Kullanılan arama deseni
    """
    from difflib import SequenceMatcher
    import re
    
    # Eğer "all room/rooms" vb. bir ifade varsa, özel durum
    if email_room_type.lower() in ["all room", "all rooms", "all room types", "tüm odalar"]:
        return None, [], "ALL_ROOMS"
    
    # Oda tipini temizle ve arama için hazırla
    clean_room_type = email_room_type.strip().upper()
    
    # Otele ait odaları al
    rooms = Room.objects.filter(hotel=hotel)
    if not rooms:
        return None, [], None
    
    # En iyi eşleşen odayı bul
    highest_score = 0
    best_match = None
    suggestions = []
    search_pattern = clean_room_type
    
    for room in rooms:
        # SequenceMatcher kullanarak benzerlik puanı hesapla
        juniper_room_type = room.juniper_room_type.strip().upper()
        score = SequenceMatcher(None, clean_room_type, juniper_room_type).ratio()
        
        # Puanı yüksekse en iyi eşleşmeyi güncelle
        if score > highest_score:
            highest_score = score
            best_match = room
        
        # Benzerlik puanı 0.5'dan yüksekse önerilere ekle
        if score > 0.5:
            suggestions.append(room)
    
    # Benzer özelliklere sahip odaları ara
    room_keywords = re.findall(r'\b\w+\b', clean_room_type)
    for keyword in room_keywords:
        if len(keyword) < 3:  # Çok kısa kelimeleri atla
            continue
            
        for room in rooms:
            juniper_room_type = room.juniper_room_type.strip().upper()
            if keyword in juniper_room_type and room not in suggestions:
                suggestions.append(room)
    
    # Önerileri puanlarına göre sırala
    suggestions.sort(key=lambda r: SequenceMatcher(None, clean_room_type, r.juniper_room_type.strip().upper()).ratio(), reverse=True)
    
    # En iyi eşleşmeyi bulunamadıysa oda listesindeki ilk odayı kullan
    if not best_match and suggestions:
        best_match = suggestions[0]
    
    return best_match, suggestions, search_pattern

@login_required
def get_rooms_by_hotel_ajax(request, hotel_id, row_id=None):
    """
    AJAX ile otel ID'sine göre oda listesini getir
    """
    import logging
    from difflib import SequenceMatcher
    logger = logging.getLogger(__name__)
    
    try:
        logger.debug(f"get_rooms_by_hotel_ajax çağrıldı: hotel_id={hotel_id}, row_id={row_id}")
        hotel = Hotel.objects.get(id=hotel_id)
        rooms = Room.objects.filter(hotel=hotel).order_by('juniper_room_type')
        
        # Eğer row_id verilmişse, bu satırın oda tipi için önerileri getir
        best_room_match = None
        room_suggestions = []
        search_pattern = None
        row = None
        
        if row_id:
            try:
                row = EmailRow.objects.get(id=row_id)
                logger.debug(f"EmailRow bulundu: {row.id}, oda tipi: {row.room_type}")
                best_room_match, room_suggestions, search_pattern = get_room_suggestions(row.room_type, hotel)
            except EmailRow.DoesNotExist:
                logger.error(f"EmailRow bulunamadı, ID: {row_id}")
                return JsonResponse({'success': False, 'message': f'Satır bulunamadı (ID: {row_id})'}, status=404)
            except Exception as e:
                logger.error(f"Oda önerileri hesaplanırken hata: {str(e)}")
                return JsonResponse({'success': False, 'message': f'Oda önerileri hesaplanırken hata: {str(e)}'}, status=500)
        
        # Odaları JSON formatına çevir
        rooms_data = []
        for room in rooms:
            match_score = 0
            if row:
                match_score = int(SequenceMatcher(None, row.room_type, room.juniper_room_type).ratio() * 100)
            
            rooms_data.append({
                'id': room.id,
                'name': room.juniper_room_type,
                'code': room.room_code,
                'is_best_match': best_room_match and room.id == best_room_match.id,
                'is_suggestion': room in room_suggestions if room_suggestions else False,
                'match_score': match_score
            })
        
        # Öneri bilgilerini oluştur
        suggestions_data = []
        if best_room_match:
            suggestions_data.append({
                'id': best_room_match.id,
                'name': best_room_match.juniper_room_type,
                'code': best_room_match.room_code,
                'is_best_match': True
            })
        
        if room_suggestions:
            for room in room_suggestions:
                if not best_room_match or room.id != best_room_match.id:
                    suggestions_data.append({
                        'id': room.id,
                        'name': room.juniper_room_type,
                        'code': room.room_code,
                        'is_best_match': False
                    })
        
        logger.debug(f"Başarılı: {len(rooms_data)} oda, {len(suggestions_data)} öneri bulundu")
        return JsonResponse({
            'success': True,
            'rooms': rooms_data,
            'best_match': {
                'id': best_room_match.id,
                'name': best_room_match.juniper_room_type,
                'code': best_room_match.room_code
            } if best_room_match else None,
            'suggestions': suggestions_data,
            'search_pattern': search_pattern
        })
    except Hotel.DoesNotExist:
        logger.error(f"Hotel bulunamadı, ID: {hotel_id}")
        return JsonResponse({'success': False, 'message': f'Otel bulunamadı (ID: {hotel_id}).'}, status=404)
    except Exception as e:
        import traceback
        logger.error(f"Odalar getirilirken hata: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'Beklenmeyen hata: {str(e)}'}, status=500)


@login_required
def email_bulk_approve(request):
    """
    View for approving multiple emails at once
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    email_ids = request.POST.getlist('email_ids')
    
    if not email_ids:
        messages.error(request, "No emails selected for approval")
        return redirect('emails:email_list')
    
    try:
        emails = Email.objects.filter(id__in=email_ids)
        approved_count = 0
        
        for email in emails:
            # Only process emails that are in a pending-type status
            if email.status in ['pending', 'processing', 'processed']:
                # Mark all rows as approved
                rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found'])
                for row in rows:
                    if row.juniper_hotel:  # Only approve rows that have at least a hotel match
                        row.status = 'approved'
                        row.processed_by = request.user
                        row.processed_at = timezone.now()
                        row.save()
                        
                        UserLog.objects.create(
                            user=request.user,
                            action_type='bulk_approve_row',
                            email=email,
                            email_row=row,
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                
                # Update email status if all rows are now approved
                if not email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).exists():
                    email.status = 'approved'
                    email.processed_by = request.user
                    email.processed_at = timezone.now()
                    email.save()
                    approved_count += 1
        
        if approved_count > 0:
            messages.success(request, f"Successfully approved {approved_count} emails")
        else:
            messages.warning(request, "No emails were approved. Check if the selected emails have valid hotel matches.")
    
    except Exception as e:
        logger.error(f"Error in bulk approve: {e}", exc_info=True)
        messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('emails:email_list')


@login_required
def email_bulk_reject(request):
    """Bulk reject selected emails."""
    if request.method == 'POST':
        try:
            # Try to parse JSON data first
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email_ids = data.get('ids', [])
            else:
                # Then try form data
                email_ids = request.POST.getlist('email_ids')
            
            emails = Email.objects.filter(id__in=email_ids)
            processed_count = 0
            
            for email in emails:
                rows = EmailRow.objects.filter(email=email)
                for row in rows:
                    row.status = 'rejected'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    row.save()
                
                # Update email status directly
                email.status = 'rejected'  # Keep 'rejected' for general rejection
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                processed_count += 1
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='bulk_reject',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details=f"Bulk rejected email {email.id}"
                )
            
            # Return JSON response for AJAX requests, redirect for normal form submissions
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f"{processed_count} emails have been rejected.",
                    'details': {
                        'success': [email.id for email in emails],
                        'errors': []
                    }
                })
            else:
                messages.success(request, f"{processed_count} emails have been rejected.")
                return redirect('emails:email_list')
                
        except json.JSONDecodeError:
            if request.content_type == 'application/json':
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            messages.error(request, "Invalid request data")
        except Exception as e:
            logger.error(f"Error in bulk reject: {e}", exc_info=True)
            if request.content_type == 'application/json':
                return JsonResponse({'error': str(e)}, status=500)
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('emails:email_list')


@login_required
def email_bulk_reject_hotel_not_found(request):
    """Bulk reject selected emails with reason: JP Hotel Not Found."""
    if request.method == 'POST':
        try:
            # Try to parse JSON data first
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email_ids = data.get('ids', [])
            else:
                # Then try form data
                email_ids = request.POST.getlist('email_ids')
            
            emails = Email.objects.filter(id__in=email_ids)
            processed_count = 0
            
            for email in emails:
                rows = EmailRow.objects.filter(email=email)
                for row in rows:
                    row.status = 'rejected_hotel_not_found'
                    row.reject_reason = 'JP Hotel Not Found'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    row.save()
                
                # Update email status directly
                email.status = 'rejected_hotel_not_found'  # Use specific status for hotel not found
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                processed_count += 1
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='bulk_reject_hotel_not_found',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details=f"Bulk rejected email {email.id} - JP Hotel Not Found"
                )
            
            # Return JSON response for AJAX requests, redirect for normal form submissions
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f"{processed_count} emails have been rejected: JP Hotel Not Found",
                    'details': {
                        'success': [email.id for email in emails],
                        'errors': []
                    }
                })
            else:
                messages.success(request, f"{processed_count} emails have been rejected: JP Hotel Not Found.")
                return redirect('emails:email_list')
                
        except json.JSONDecodeError:
            if request.content_type == 'application/json':
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            messages.error(request, "Invalid request data")
        except Exception as e:
            logger.error(f"Error in bulk reject hotel not found: {e}", exc_info=True)
            if request.content_type == 'application/json':
                return JsonResponse({'error': str(e)}, status=500)
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('emails:email_list')


@login_required
def email_bulk_reject_room_not_found(request):
    """Bulk reject selected emails with reason: JP Room Not Found."""
    if request.method == 'POST':
        try:
            # Try to parse JSON data first
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email_ids = data.get('ids', [])
            else:
                # Then try form data
                email_ids = request.POST.getlist('email_ids')
            
            emails = Email.objects.filter(id__in=email_ids)
            processed_count = 0
            
            for email in emails:
                rows = EmailRow.objects.filter(email=email)
                for row in rows:
                    row.status = 'rejected_room_not_found'
                    row.reject_reason = 'JP Room Not Found'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    row.save()
                
                # Update email status directly
                email.status = 'rejected_room_not_found'  # Use specific status for room not found
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                processed_count += 1
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='bulk_reject_room_not_found',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details=f"Bulk rejected email {email.id} - JP Room Not Found"
                )
            
            # Return JSON response for AJAX requests, redirect for normal form submissions
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f"{processed_count} emails have been rejected: JP Room Not Found",
                    'details': {
                        'success': [email.id for email in emails],
                        'errors': []
                    }
                })
            else:
                messages.success(request, f"{processed_count} emails have been rejected: JP Room Not Found.")
                return redirect('emails:email_list')
                
        except json.JSONDecodeError:
            if request.content_type == 'application/json':
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            messages.error(request, "Invalid request data")
        except Exception as e:
            logger.error(f"Error in bulk reject room not found: {e}", exc_info=True)
            if request.content_type == 'application/json':
                return JsonResponse({'error': str(e)}, status=500)
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('emails:email_list')


@login_required
def email_bulk_delete(request):
    """View for deleting multiple emails at once"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    email_ids = request.POST.getlist('email_ids')
    
    if not email_ids:
        messages.error(request, "No emails selected for deletion")
        return redirect('emails:email_list')
    
    try:
        emails = Email.objects.filter(id__in=email_ids)
        deleted_count = 0
        
        for email in emails:
            # Log the deletion before deleting
            UserLog.objects.create(
                user=request.user,
                action_type='delete_email',
                email=email,
                ip_address=request.META.get('REMOTE_ADDR'),
                details=f"Deleted email ID: {email.id}, Subject: {email.subject}"
            )
            
            # Delete associated rows first to avoid potential orphaned data
            email.rows.all().delete()
            
            # Delete the email
            email.delete()
            deleted_count += 1
        
        messages.success(request, f"Successfully deleted {deleted_count} emails")
    
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}", exc_info=True)
        messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('emails:email_list')


@login_required
def approve_email(request, email_id):
    """
    View for approving all rows in an email
    """
    email = get_object_or_404(Email, id=email_id)
    
    if email.status != 'pending':
        messages.error(request, "Only pending emails can be approved")
        return redirect('emails:email_detail', email_id=email.id)
    
    # Mark all rows with a hotel match as approved
    rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found'])
    for row in rows:
        if row.juniper_hotel:  # Only approve rows that have at least a hotel match
            row.status = 'approved'
            row.processed_by = request.user
            row.processed_at = timezone.now()
            row.save()
            
            UserLog.objects.create(
                user=request.user,
                action_type='approve_row',
                email=email,
                email_row=row,
                ip_address=request.META.get('REMOTE_ADDR')
            )
    
    # Update email status if all rows are now approved
    if not email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).exists():
        email.status = 'approved'
        email.processed_by = request.user
        email.processed_at = timezone.now()
        email.save()
    
    messages.success(request, "All matching rows in email approved successfully")
    return redirect('emails:email_detail', email_id=email.id)


@login_required
def reject_email(request, email_id):
    """Reject all rows in an email."""
    email = get_object_or_404(Email, id=email_id)
    rows = EmailRow.objects.filter(email=email)
    
    for row in rows:
        row.status = 'rejected'
        row.processed_by = request.user
        row.processed_at = timezone.now()
        row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_email',
        email=email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected all rows in email {email_id}"
    )
    
    # Update email status directly
    email.status = 'rejected'  # Keep 'rejected' for general rejection
    email.processed_by = request.user
    email.processed_at = timezone.now()
    email.save()
    
    messages.success(request, f"All rows in email {email_id} have been rejected.")
    
    # AJAX request için JSON yanıtı döndür, normal request için redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f"All rows in email {email_id} have been rejected.",
            'status': email.status
        })
    else:
        return redirect('emails:email_detail', email_id=email_id)


@login_required
def reject_email_hotel_not_found(request, email_id):
    """Reject all rows in an email with reason: JP Hotel Not Found."""
    email = get_object_or_404(Email, id=email_id)
    rows = EmailRow.objects.filter(email=email)
    
    for row in rows:
        row.status = 'rejected_hotel_not_found'
        row.reject_reason = 'JP Hotel Not Found'
        row.processed_by = request.user
        row.processed_at = timezone.now()
        row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_email_hotel_not_found',
        email=email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected all rows in email {email_id} - JP Hotel Not Found"
    )
    
    # Update email status directly
    email.status = 'rejected_hotel_not_found'
    email.processed_by = request.user
    email.processed_at = timezone.now()
    email.save()
    
    messages.success(request, f"All rows in email {email_id} have been rejected: JP Hotel Not Found.")
    
    # AJAX request için JSON yanıtı döndür, normal request için redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f"All rows in email {email_id} have been rejected: JP Hotel Not Found",
            'status': email.status
        })
    else:
        return redirect('emails:email_detail', email_id=email_id)


@login_required
def reject_email_room_not_found(request, email_id):
    """Reject all rows in an email with reason: JP Room Not Found."""
    email = get_object_or_404(Email, id=email_id)
    rows = EmailRow.objects.filter(email=email)
    
    for row in rows:
        row.status = 'rejected_room_not_found'
        row.reject_reason = 'JP Room Not Found'
        row.processed_by = request.user
        row.processed_at = timezone.now()
        row.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='reject_email_room_not_found',
        email=email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Rejected all rows in email {email_id} - JP Room Not Found"
    )
    
    # Update email status directly
    email.status = 'rejected_room_not_found'
    email.processed_by = request.user
    email.processed_at = timezone.now()
    email.save()
    
    messages.success(request, f"All rows in email {email_id} have been rejected: JP Room Not Found.")
    
    # AJAX request için JSON yanıtı döndür, normal request için redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f"All rows in email {email_id} have been rejected: JP Room Not Found",
            'status': email.status
        })
    else:
        return redirect('emails:email_detail', email_id=email_id)


@login_required
@require_POST
def apply_suggestion(request, row_id):
    """
    AI önerisini satıra uygulayan API endpoint'i
    """
    try:
        row = get_object_or_404(EmailRow, id=row_id)
        
        # Gelen veriyi parse et
        data = json.loads(request.body)
        hotel_id = data.get('hotel_id')
        room_ids = data.get('room_ids', [])
        
        # Hotel ve Room modellerini import et
        from hotels.models import Hotel, Room
        
        # Oteli bul ve satıra ekle
        hotel = get_object_or_404(Hotel, id=hotel_id)
        row.juniper_hotel = hotel
        
        # Odaları ekle (eğer mevcutsa)
        if room_ids:
            rooms = Room.objects.filter(id__in=room_ids, hotel=hotel)
            row.juniper_rooms.set(rooms)
            
            # Oda tipini güncelle
            room_names = [room.juniper_room_type for room in rooms]
            row.room_type = ", ".join(room_names)
        
        # Durumu pending olarak güncelle
        row.status = 'pending'
        row.save()
        
        # İşlemi kaydet
        UserLog.objects.create(
            user=request.user,
            action_type='apply_suggestion',
            email=row.email,
            email_row=row,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"AI önerisi uygulandı - Otel: {hotel.juniper_hotel_name}"
        )
        
        # Başarılı yanıt
        return JsonResponse({
            'success': True,
            'message': 'Öneri başarıyla uygulandı',
            'hotel': hotel.juniper_hotel_name,
            'rooms': [room.juniper_room_type for room in rooms] if room_ids else []
        })
    
    except json.JSONDecodeError:
        logger.error("JSON parse error in apply_suggestion")
        return JsonResponse({'success': False, 'error': 'Geçersiz JSON formatı'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in apply_suggestion: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def check_new_emails_api(request):
    """
    API endpoint to check for new emails since a given timestamp
    """
    try:
        last_check_time = request.GET.get('last_check')
        if not last_check_time:
            # If no timestamp is provided, default to checking the last 5 minutes
            last_check_time = (timezone.now() - timedelta(minutes=5)).isoformat()
        
        # Parse the timestamp
        try:
            last_check_datetime = datetime.fromisoformat(last_check_time)
            # Ensure it's timezone aware
            if last_check_datetime.tzinfo is None:
                last_check_datetime = timezone.make_aware(last_check_datetime)
        except (ValueError, TypeError):
            # Invalid timestamp format, default to 5 minutes ago
            last_check_datetime = timezone.now() - timedelta(minutes=5)
        
        # Query for new emails received after the timestamp
        new_emails = Email.objects.filter(received_date__gt=last_check_datetime).order_by('-received_date')
        
        # Prepare the response data
        emails_data = []
        for email in new_emails:
            emails_data.append({
                'id': email.id,
                'subject': email.subject,
                'sender': email.sender,
                'received_date': email.received_date.isoformat(),
                'status': email.status,
                'has_attachments': email.has_attachments,
                'url': reverse('emails:email_detail', args=[email.id])
            })
        
        # Return the response with new emails and current server time
        return JsonResponse({
            'success': True,
            'new_emails_count': len(emails_data),
            'new_emails': emails_data,
            'server_time': timezone.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error in check_new_emails_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'server_time': timezone.now().isoformat()
        }, status=500)


@login_required
def bulk_action_rows(request, action):
    """
    Handle bulk actions on multiple rows (rules) at once.
    Supports:
    - approve: Approve selected rows
    - reject: Reject selected rows with general rejection
    - reject-hotel-not-found: Reject selected rows with JP Hotel Not Found reason
    - reject-room-not-found: Reject selected rows with JP Room Not Found reason
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        # Parse request data based on content type
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            row_ids = data.get('ids', [])
        else:
            row_ids = request.POST.getlist('row_ids')
        
        if not row_ids:
            return JsonResponse({'error': 'No rows selected'}, status=400)
        
        # Get selected rows
        rows = EmailRow.objects.filter(id__in=row_ids)
        
        # Apply action based on parameter
        processed_count = 0
        emails_updated = set()  # Keep track of emails to update
        
        for row in rows:
            try:
                # Apply specific action to each row
                if action == 'approve':
                    if row.juniper_hotel:  # Only approve rows with a hotel match
                        row.status = 'approved'
                        row.processed_by = request.user
                        row.processed_at = timezone.now()
                        processed_count += 1
                elif action == 'reject':
                    row.status = 'rejected'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    processed_count += 1
                elif action == 'reject-hotel-not-found':
                    row.status = 'rejected_hotel_not_found'
                    row.reject_reason = 'JP Hotel Not Found'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    processed_count += 1
                elif action == 'reject-room-not-found':
                    row.status = 'rejected_room_not_found'
                    row.reject_reason = 'JP Room Not Found'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    processed_count += 1
                else:
                    continue  # Skip unsupported actions
                
                row.save()
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type=f'bulk_{action}',
                    email=row.email,
                    email_row=row,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details=f"Bulk action '{action}' on row {row.id}"
                )
                
                # Add this row's email to the set of emails to update
                emails_updated.add(row.email)
                
            except Exception as e:
                logger.error(f"Error processing row {row.id} with action {action}: {e}", exc_info=True)
        
        # Now update all affected emails' statuses
        for email in emails_updated:
            # Check remaining rows status to decide the email status
            pending_rows = email.rows.filter(status__in=['pending', 'matching', 'hotel_not_found', 'room_not_found']).count()
            
            if pending_rows == 0:
                # All rows have been processed
                if action == 'approve':
                    if email.rows.filter(status='approved').count() == email.rows.count():
                        email.status = 'approved'
                elif action == 'reject':
                    email.status = 'rejected'
                elif action == 'reject-hotel-not-found':
                    email.status = 'rejected_hotel_not_found'
                elif action == 'reject-room-not-found':
                    email.status = 'rejected_room_not_found'
                
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
        
        # Prepare success response
        action_display = {
            'approve': 'approved',
            'reject': 'rejected',
            'reject-hotel-not-found': 'rejected: JP Hotel Not Found',
            'reject-room-not-found': 'rejected: JP Room Not Found'
        }.get(action, action)
        
        return JsonResponse({
            'success': True,
            'message': f"{processed_count} rows have been {action_display}.",
            'details': {
                'success': [r.id for r in rows if r.status == action.replace('-', '_') or 
                            (action == 'approve' and r.status == 'approved')],
                'errors': []
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in bulk action {action}: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# Belirli bir ekin görüntüleme/indirme fonksiyonunu bulmak için
@login_required
def download_attachment(request, attachment_id):
    """
    View for downloading an attachment
    """
    attachment = get_object_or_404(EmailAttachment, id=attachment_id)
    
    if not attachment.file:
        messages.error(request, "Attachment file not found")
        return redirect('emails:email_detail', email_id=attachment.email.id)
    
    # Check if file exists on disk
    if not os.path.exists(attachment.file.path):
        messages.error(request, "Attachment file not found on disk")
        return redirect('emails:email_detail', email_id=attachment.email.id)
    
    # Log attachment access
    UserLog.objects.create(
        user=request.user,
        action_type='download_attachment',
        email=attachment.email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Downloaded attachment: {attachment.filename}"
    )
    
    # Create response with file
    file_path = attachment.file.path
    with open(file_path, 'rb') as f:
        file_data = f.read()
        
    # Determine content type
    content_type = attachment.content_type
    if not content_type:
        content_type = 'application/octet-stream'  # Default content type
    
    # Determine if this file is analyzed (only PDF and Word files are analyzed)
    file_ext = os.path.splitext(attachment.filename.lower())[1]
    is_analyzed = file_ext in ['.pdf', '.doc', '.docx']
    
    # Set filename
    response = HttpResponse(file_data, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    
    return response


def process_html_for_display(email):
    """Process HTML content to make it displayable in a browser"""
    if not email.body_html:
        return None
        
    # Process CID references if attachments exist
    html_content = email.body_html
    attachments = email.attachments.all()
    
    if attachments:
        import re
        
        # Create a mapping of Content-IDs to attachment URLs
        for attachment in attachments:
            # Create a URL to the attachment
            attachment_id = attachment.id
            attachment_url = reverse('emails:email_attachment_view', args=[attachment_id])
            
            # Try to replace CID references with the attachment URL using different patterns
            patterns = []
            
            # Use the stored content_id if available
            if attachment.content_id:
                patterns.append(f'src=["\']cid:{re.escape(attachment.content_id)}["\']')
            
            # Filename based pattern (fallback)
            filename = attachment.filename
            patterns.append(f'src=["\']cid:{re.escape(filename)}["\']')
            
            # Generic pattern for image CIDs (last resort)
            patterns.append(f'src=["\']cid:image[^"\']*["\']')
            
            # Apply all patterns
            for pattern in patterns:
                html_content = re.sub(pattern, f'src="{attachment_url}"', html_content)
    
    # Add base target to open links in new tab
    html_content = html_content.replace('<head>', '<head><base target="_blank">')
    
    # Handle character encoding issues
    html_content = html_content.replace('\x00', '')
    
    return html_content


@login_required
def mark_email_juniper_manual(request, email_id):
    """Mark email as processed manually in Juniper"""
    email = get_object_or_404(Email, id=email_id)
    
    # Update the email status
    email.status = 'juniper_manual'
    email.processed_by = request.user
    email.processed_at = timezone.now()
    email.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='mark_juniper_manual',
        email=email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Marked email {email_id} as Juniper(M) - manually processed in Juniper"
    )
    
    messages.success(request, f"Email has been marked as Juniper(M) - manually processed in Juniper.")
    
    # AJAX request için JSON yanıtı döndür, normal request için redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f"Email has been marked as Juniper(M).",
            'status': email.status
        })
    else:
        return redirect('emails:email_detail', email_id=email_id)


@login_required
def mark_email_juniper_robot(request, email_id):
    """Mark email as processed by robot in Juniper"""
    email = get_object_or_404(Email, id=email_id)
    
    # Update the email status
    email.status = 'juniper_robot'
    email.processed_by = request.user
    email.processed_at = timezone.now()
    email.save()
    
    # Log the action
    UserLog.objects.create(
        user=request.user,
        action_type='mark_juniper_robot',
        email=email,
        ip_address=request.META.get('REMOTE_ADDR'),
        details=f"Marked email {email_id} as Juniper(R) - processed by robot in Juniper"
    )
    
    messages.success(request, f"Email has been marked as Juniper(R) - processed by robot in Juniper.")
    
    # AJAX request için JSON yanıtı döndür, normal request için redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f"Email has been marked as Juniper(R).",
            'status': email.status
        })
    else:
        return redirect('emails:email_detail', email_id=email_id)
