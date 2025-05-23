from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
import json

from .models import Email, EmailRow, UserLog

@login_required
@require_POST
def bulk_action(request):
    """
    Handle various bulk actions on emails
    """
    try:
        # Get the selected email IDs and action from the request
        email_ids_json = request.POST.get('email_ids')
        action = request.POST.get('action')
        
        if not email_ids_json or not action:
            return JsonResponse({
                'success': False,
                'message': 'Missing required parameters'
            })
        
        # Parse the email IDs
        try:
            email_ids = json.loads(email_ids_json)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid email IDs format'
            })
        
        # Get the emails
        emails = Email.objects.filter(id__in=email_ids)
        
        # Check if any emails were found
        if not emails.exists():
            return JsonResponse({
                'success': False,
                'message': 'No valid emails found'
            })
        
        # Process the action
        if action == 'approve':
            # Approve all emails
            for email in emails:
                # Use the existing approve_email function logic
                rows = EmailRow.objects.filter(email=email)
                
                for row in rows:
                    row.status = 'approved'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    row.save()
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='approve_email',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    details=f"Approved email {email.id}"
                )
                
                # Update email status
                email.status = 'approved'
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
            return JsonResponse({
                'success': True,
                'message': f'{emails.count()} e-posta onaylandı'
            })
            
        elif action == 'reject':
            # Reject all emails
            for email in emails:
                # Use the existing reject_email function logic
                rows = EmailRow.objects.filter(email=email)
                
                for row in rows:
                    row.status = 'rejected'
                    row.reject_reason = 'General'
                    row.processed_by = request.user
                    row.processed_at = timezone.now()
                    row.save()
                
                # Log the action
                UserLog.objects.create(
                    user=request.user,
                    action_type='reject_email',
                    email=email,
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    details=f"Rejected email {email.id}"
                )
                
                # Update email status
                email.status = 'rejected'
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
            return JsonResponse({
                'success': True,
                'message': f'{emails.count()} e-posta reddedildi'
            })
            
        elif action == 'reject-hotel-not-found':
            # Reject all emails with hotel not found reason
            for email in emails:
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
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    details=f"Rejected email {email.id} - JP Hotel Not Found"
                )
                
                # Update email status
                email.status = 'rejected_hotel_not_found'
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
            return JsonResponse({
                'success': True,
                'message': f'{emails.count()} e-posta "JP Otel Yok" olarak işaretlendi'
            })
            
        elif action == 'block-hotel-not-found':
            # Block all emails with hotel not found reason
            for email in emails:
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
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    details=f"Rejected email {email.id} - JP Hotel Not Found (Blocked)"
                )
                
                # Update email status - mark as blocked
                email.status = 'blocked_hotel_not_found'
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
            return JsonResponse({
                'success': True,
                'message': f'{emails.count()} e-posta bloklandı'
            })
            
        elif action == 'reject-room-not-found':
            # Reject all emails with room not found reason
            for email in emails:
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
                    ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    details=f"Rejected email {email.id} - JP Room Not Found"
                )
                
                # Update email status
                email.status = 'rejected_room_not_found'
                email.processed_by = request.user
                email.processed_at = timezone.now()
                email.save()
                
            return JsonResponse({
                'success': True,
                'message': f'{emails.count()} e-posta "JP Oda Yok" olarak işaretlendi'
            })
            
        else:
            return JsonResponse({
                'success': False,
                'message': f'Bilinmeyen işlem: {action}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'İşlem sırasında hata oluştu: {str(e)}'
        }) 