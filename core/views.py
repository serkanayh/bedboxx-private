from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
import json
from emails.models import Email, EmailRow, UserLog, AIModel, Prompt, RegexRule, EmailFilter
from hotels.models import Hotel
from users.models import User
from .models import AIPerformanceMetric, HotelAICounter, WebhookLog, EmailConfiguration
from django.http import JsonResponse
from rest_framework.test import APIClient
import email
import chardet
from django.urls import reverse
import logging
import email.parser as email_parser

# Set up logger
logger = logging.getLogger(__name__)

# Helper functions for AI models and prompts
def get_active_ai_model():
    """
    Helper function to get the currently active AI model.
    Returns the first active AI model or None if no active models exist.
    """
    try:
        return AIModel.objects.filter(active=True).first()
    except Exception as e:
        logger.error(f"Error getting active AI model: {str(e)}")
        return None

def get_active_prompt():
    """
    Helper function to get the currently active prompt.
    Returns the first active prompt or None if no active prompts exist.
    """
    try:
        return Prompt.objects.filter(active=True).first()
    except Exception as e:
        logger.error(f"Error getting active prompt: {str(e)}")
        return None

@login_required
def dashboard(request):
    """
    View for the main dashboard
    """
    # Calculate statistics
    stats = {
        'processed_emails': Email.objects.exclude(status='pending').count(),
        'pending_emails': Email.objects.filter(status='pending').count(),
        'approved_rows': EmailRow.objects.filter(status='approved').count(),
        'manual_edits': EmailRow.objects.filter(manually_edited=True).count(),
    }
    
    # Calculate rates
    total_rows = EmailRow.objects.count()
    if total_rows > 0:
        stats['approval_rate'] = round((stats['approved_rows'] / total_rows) * 100, 1)
        stats['edit_rate'] = round((stats['manual_edits'] / total_rows) * 100, 1)
    else:
        stats['approval_rate'] = 0
        stats['edit_rate'] = 0
    
    # Calculate AI success rate (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    ai_metrics = AIPerformanceMetric.objects.filter(date__gte=seven_days_ago)
    if ai_metrics.exists():
        total_calls = ai_metrics.aggregate(Sum('total_calls'))['total_calls__sum'] or 0
        successful_calls = ai_metrics.aggregate(Sum('successful_calls'))['successful_calls__sum'] or 0
        if total_calls > 0:
            stats['ai_success_rate'] = round((successful_calls / total_calls) * 100, 1)
        else:
            stats['ai_success_rate'] = 0
    else:
        stats['ai_success_rate'] = 0
    
    # Get user performance data
    user_performance = []
    users = User.objects.filter(is_active=True)
    max_processed = 1  # Avoid division by zero
    
    for user in users:
        processed_count = EmailRow.objects.filter(processed_by=user).count()
        if processed_count > max_processed:
            max_processed = processed_count
        
        user_performance.append({
            'username': user.username,
            'processed_count': processed_count,
            'rate': 0  # Will be calculated after finding max
        })
    
    # Calculate relative rates
    for user_data in user_performance:
        user_data['rate'] = round((user_data['processed_count'] / max_processed) * 100)
    
    # Sort by processed count (descending)
    user_performance.sort(key=lambda x: x['processed_count'], reverse=True)
    
    # Get recent activity
    recent_activity = UserLog.objects.select_related('user', 'email', 'email_row').order_by('-timestamp')[:10]
    
    # Prepare chart data
    chart_data = {
        'processing_trend': {
            'labels': [],
            'processed': [],
            'approved': []
        },
        'processing_trend_week': {
            'labels': [],
            'processed': [],
            'approved': []
        },
        'processing_trend_month': {
            'labels': [],
            'processed': [],
            'approved': []
        },
        'ai_performance': {
            'labels': [],
            'success_rate': []
        },
        'hotel_correction': {
            'labels': [],
            'rates': []
        }
    }
    
    # Processing trend data (last 7 days)
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        chart_data['processing_trend_week']['labels'].append(date.strftime('%d %b'))
        
        processed_count = Email.objects.filter(
            created_at__date=date,
            status__in=['approved', 'manual_processed', 'sent_to_robot', 'robot_processed']
        ).count()
        
        approved_count = EmailRow.objects.filter(
            created_at__date=date,
            status__in=['approved', 'sent_to_robot', 'robot_processed']
        ).count()
        
        chart_data['processing_trend_week']['processed'].append(processed_count)
        chart_data['processing_trend_week']['approved'].append(approved_count)
    
    # Processing trend data (last 30 days)
    for i in range(29, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        if i % 3 == 0:  # Show every 3rd day for readability
            chart_data['processing_trend_month']['labels'].append(date.strftime('%d %b'))
        else:
            chart_data['processing_trend_month']['labels'].append('')
        
        processed_count = Email.objects.filter(
            created_at__date=date,
            status__in=['approved', 'manual_processed', 'sent_to_robot', 'robot_processed']
        ).count()
        
        approved_count = EmailRow.objects.filter(
            created_at__date=date,
            status__in=['approved', 'sent_to_robot', 'robot_processed']
        ).count()
        
        chart_data['processing_trend_month']['processed'].append(processed_count)
        chart_data['processing_trend_month']['approved'].append(approved_count)
    
    # Use weekly data as default
    chart_data['processing_trend'] = chart_data['processing_trend_week']
    
    # AI performance data (last 14 days)
    for i in range(13, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        chart_data['ai_performance']['labels'].append(date.strftime('%d %b'))
        
        metrics = AIPerformanceMetric.objects.filter(date=date)
        if metrics.exists():
            total_calls = metrics.aggregate(Sum('total_calls'))['total_calls__sum'] or 0
            successful_calls = metrics.aggregate(Sum('successful_calls'))['successful_calls__sum'] or 0
            if total_calls > 0:
                success_rate = round((successful_calls / total_calls) * 100, 1)
            else:
                success_rate = 0
        else:
            success_rate = 0
        
        chart_data['ai_performance']['success_rate'].append(success_rate)
    
    # Hotel correction rates
    top_hotels = Hotel.objects.annotate(
        row_count=Count('email_rows')
    ).filter(row_count__gt=0).order_by('-row_count')[:5]
    
    for hotel in top_hotels:
        chart_data['hotel_correction']['labels'].append(hotel.juniper_hotel_name)
        
        total_rows = hotel.email_rows.count()
        edited_rows = hotel.email_rows.filter(manually_edited=True).count()
        
        if total_rows > 0:
            correction_rate = round((edited_rows / total_rows) * 100, 1)
        else:
            correction_rate = 0
        
        chart_data['hotel_correction']['rates'].append(correction_rate)
    
    # Convert chart data to JSON for JavaScript
    for key, value in chart_data.items():
        for subkey, subvalue in value.items():
            chart_data[key][subkey] = json.dumps(subvalue)
    
    context = {
        'stats': stats,
        'user_performance': user_performance,
        'recent_activity': recent_activity,
        'chart_data': chart_data,
    }
    
    return render(request, 'core/dashboard.html', context)

@login_required
def ai_performance(request):
    """
    View for AI performance metrics
    """
    # Get date range from query parameters or use default (last 30 days)
    days = int(request.GET.get('days', 30))
    start_date = timezone.now().date() - timedelta(days=days)
    
    # Get metrics
    metrics = AIPerformanceMetric.objects.filter(
        date__gte=start_date
    ).select_related('ai_model', 'prompt').order_by('-date')
    
    # Calculate summary statistics
    summary = {
        'total_calls': metrics.aggregate(Sum('total_calls'))['total_calls__sum'] or 0,
        'successful_calls': metrics.aggregate(Sum('successful_calls'))['successful_calls__sum'] or 0,
        'token_usage': metrics.aggregate(Sum('token_usage'))['token_usage__sum'] or 0,
        'total_cost': metrics.aggregate(Sum('cost'))['cost__sum'] or 0,
    }
    
    if summary['total_calls'] > 0:
        summary['success_rate'] = round((summary['successful_calls'] / summary['total_calls']) * 100, 1)
    else:
        summary['success_rate'] = 0
    
    # Group metrics by model
    models = AIModel.objects.all()
    model_metrics = []
    
    for model in models:
        model_data = {
            'model': model,
            'total_calls': metrics.filter(ai_model=model).aggregate(Sum('total_calls'))['total_calls__sum'] or 0,
            'successful_calls': metrics.filter(ai_model=model).aggregate(Sum('successful_calls'))['successful_calls__sum'] or 0,
            'token_usage': metrics.filter(ai_model=model).aggregate(Sum('token_usage'))['token_usage__sum'] or 0,
            'cost': metrics.filter(ai_model=model).aggregate(Sum('cost'))['cost__sum'] or 0,
        }
        
        if model_data['total_calls'] > 0:
            model_data['success_rate'] = round((model_data['successful_calls'] / model_data['total_calls']) * 100, 1)
        else:
            model_data['success_rate'] = 0
        
        model_metrics.append(model_data)
    
    # Sort by total calls (descending)
    model_metrics.sort(key=lambda x: x['total_calls'], reverse=True)
    
    context = {
        'metrics': metrics,
        'summary': summary,
        'model_metrics': model_metrics,
        'days': days,
    }
    
    return render(request, 'core/ai_performance.html', context)

@login_required
def ai_model_list(request):
    """
    View for listing AI models
    """
    models = AIModel.objects.all().order_by('-active', 'name')
    
    context = {
        'models': models,
    }
    
    return render(request, 'core/ai_model_list.html', context)

@login_required
def ai_model_create(request):
    """
    View for creating a new AI model
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create AI models.')
        return redirect('core:ai_model_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        api_key = request.POST.get('api_key')
        active = 'active' in request.POST
        
        if not name or not api_key:
            messages.error(request, 'Both name and API key are required.')
            return redirect('core:ai_model_list')
        
        # Create new model
        model = AIModel(
            name=name,
            api_key=api_key,
            active=active
        )
        model.save()
        
        messages.success(request, f'AI model "{name}" created successfully.')
        return redirect('core:ai_model_list')
    
    # Should not happen - form is in a modal
    return redirect('core:ai_model_list')

@login_required
def ai_model_detail(request, model_id):
    """
    View for AI model details and editing
    """
    model = get_object_or_404(AIModel, id=model_id)
    
    if request.method == 'POST':
        if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
            messages.error(request, 'You do not have permission to edit AI models.')
            return redirect('core:ai_model_list')
            
        # Update model
        model.name = request.POST.get('name')
        
        # Only update API key if provided
        new_api_key = request.POST.get('api_key')
        if new_api_key:
            model.api_key = new_api_key
            
        model.active = 'active' in request.POST
        model.save()
        
        messages.success(request, 'AI model updated successfully.')
        return redirect('core:ai_model_list')
    
    context = {
        'model': model,
    }
    
    return render(request, 'core/ai_model_detail.html', context)

@login_required
def ai_model_delete(request, model_id):
    """
    View for deleting an AI model
    """
    model = get_object_or_404(AIModel, id=model_id)
    
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete AI models.')
        return redirect('core:ai_model_list')
    
    if request.method == 'POST':
        model_name = model.name
        model.delete()
        messages.success(request, f'AI model "{model_name}" deleted successfully.')
    
    return redirect('core:ai_model_list')

@login_required
def prompt_list(request):
    """
    View for listing prompts
    """
    prompts = Prompt.objects.all().order_by('-active', '-success_rate')
    
    context = {
        'prompts': prompts,
    }
    
    return render(request, 'core/prompt_list.html', context)

@login_required
def prompt_create(request):
    """
    View for creating a new prompt
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create prompts.')
        return redirect('core:prompt_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        active = 'active' in request.POST
        
        if not title or not content:
            messages.error(request, 'Both title and content are required.')
            return redirect('core:prompt_list')
        
        # Create new prompt
        prompt = Prompt(
            title=title,
            content=content,
            active=active
        )
        prompt.save()
        
        messages.success(request, f'Prompt "{title}" created successfully.')
        return redirect('core:prompt_list')
    
    # Should not happen - form is in a modal
    return redirect('core:prompt_list')

@login_required
def prompt_detail(request, prompt_id):
    """
    View for prompt details and editing
    """
    prompt = get_object_or_404(Prompt, id=prompt_id)
    
    if request.method == 'POST':
        if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
            messages.error(request, 'You do not have permission to edit prompts.')
            return redirect('core:prompt_list')
            
        # Update prompt
        prompt.title = request.POST.get('title')
        prompt.content = request.POST.get('content')
        prompt.active = 'active' in request.POST
        prompt.save()
        
        messages.success(request, 'Prompt updated successfully.')
        return redirect('core:prompt_list')
    
    context = {
        'prompt': prompt,
    }
    
    return render(request, 'core/prompt_detail.html', context)

@login_required
def prompt_delete(request, prompt_id):
    """
    View for deleting a prompt
    """
    prompt = get_object_or_404(Prompt, id=prompt_id)
    
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete prompts.')
        return redirect('core:prompt_list')
    
    if request.method == 'POST':
        prompt_title = prompt.title
        prompt.delete()
        messages.success(request, f'Prompt "{prompt_title}" deleted successfully.')
    
    return redirect('core:prompt_list')

@login_required
def regex_rule_list(request):
    """
    View for listing regex rules
    """
    rules = RegexRule.objects.all().order_by('-success_count')
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    
    context = {
        'rules': rules,
        'hotels': hotels,
    }
    
    return render(request, 'core/regex_rule_list.html', context)

@login_required
def regex_rule_create(request):
    """
    View for creating a new regex rule
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create regex rules.')
        return redirect('core:regex_rule_list')
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel')
        rule_type = request.POST.get('rule_type')
        pattern = request.POST.get('pattern')
        
        if not rule_type or not pattern:
            messages.error(request, 'Both rule type and pattern are required.')
            return redirect('core:regex_rule_list')
        
        # Create new rule
        rule = RegexRule(
            rule_type=rule_type,
            pattern=pattern
        )
        
        # Set hotel if provided
        if hotel_id:
            try:
                hotel = Hotel.objects.get(id=hotel_id)
                rule.hotel = hotel
            except Hotel.DoesNotExist:
                messages.warning(request, 'The selected hotel could not be found. Rule created without hotel association.')
        
        rule.save()
        
        messages.success(request, 'Regex rule created successfully.')
        return redirect('core:regex_rule_list')
    
    # Should not happen - form is in a modal
    return redirect('core:regex_rule_list')

@login_required
def regex_rule_detail(request, rule_id):
    """
    View for regex rule details and editing
    """
    rule = get_object_or_404(RegexRule, id=rule_id)
    hotels = Hotel.objects.all().order_by('juniper_hotel_name')
    
    if request.method == 'POST':
        if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
            messages.error(request, 'You do not have permission to edit regex rules.')
            return redirect('core:regex_rule_list')
            
        # Update rule
        hotel_id = request.POST.get('hotel')
        rule.rule_type = request.POST.get('rule_type')
        rule.pattern = request.POST.get('pattern')
        
        # Update hotel
        if hotel_id:
            try:
                rule.hotel = Hotel.objects.get(id=hotel_id)
            except Hotel.DoesNotExist:
                rule.hotel = None
        else:
            rule.hotel = None
            
        rule.save()
        
        messages.success(request, 'Regex rule updated successfully.')
        return redirect('core:regex_rule_list')
    
    context = {
        'rule': rule,
        'hotels': hotels,
    }
    
    return render(request, 'core/regex_rule_detail.html', context)

@login_required
def regex_rule_delete(request, rule_id):
    """
    View for deleting a regex rule
    """
    rule = get_object_or_404(RegexRule, id=rule_id)
    
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete regex rules.')
        return redirect('core:regex_rule_list')
    
    if request.method == 'POST':
        rule.delete()
        messages.success(request, 'Regex rule deleted successfully.')
    
    return redirect('core:regex_rule_list')

@login_required
def regex_rule_bulk_action(request):
    """
    View for handling bulk actions on regex rules
    """
    if request.method == 'POST':
        if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
            messages.error(request, 'You do not have permission to perform bulk actions on regex rules.')
            return redirect('core:regex_rule_list')
        
        action = request.POST.get('action')
        rule_ids = request.POST.getlist('rule_ids')
        
        if not action or not rule_ids:
            messages.error(request, 'Invalid request. Please select rules and an action.')
            return redirect('core:regex_rule_list')
        
        rules = RegexRule.objects.filter(id__in=rule_ids)
        count = rules.count()
        
        if action == 'approve':
            rules.update(status='approved')
            messages.success(request, f'{count} regex rules approved successfully.')
        elif action == 'reject':
            rules.update(status='rejected')
            messages.success(request, f'{count} regex rules rejected successfully.')
        elif action == 'delete':
            rules.delete()
            messages.success(request, f'{count} regex rules deleted successfully.')
        else:
            messages.error(request, 'Invalid action specified.')
    
    return redirect('core:regex_rule_list')

@login_required
def email_filter_list(request):
    """
    View for listing email filters
    """
    filters = EmailFilter.objects.all().order_by('filter_type', 'name')
    
    context = {
        'filters': filters,
    }
    
    return render(request, 'core/email_filter_list.html', context)

@login_required
def email_filter_create(request):
    """
    View for creating a new email filter
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to create email filters.')
        return redirect('core:email_filter_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        filter_type = request.POST.get('filter_type')
        pattern = request.POST.get('pattern')
        is_active = 'is_active' in request.POST
        
        if not name or not filter_type or not pattern:
            messages.error(request, 'All fields are required.')
            return redirect('core:email_filter_list')
        
        # Create new filter
        filter_obj = EmailFilter(
            name=name,
            filter_type=filter_type,
            pattern=pattern,
            is_active=is_active,
            created_by=request.user
        )
        filter_obj.save()
        
        messages.success(request, f'Email filter "{name}" created successfully.')
        return redirect('core:email_filter_list')
    
    # Should not happen - form is in a modal
    return redirect('core:email_filter_list')

@login_required
def email_filter_detail(request, filter_id):
    """
    View for email filter details and editing
    """
    filter_obj = get_object_or_404(EmailFilter, id=filter_id)
    
    if request.method == 'POST':
        if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
            messages.error(request, 'You do not have permission to edit email filters.')
            return redirect('core:email_filter_list')
            
        # Update filter
        filter_obj.name = request.POST.get('name')
        filter_obj.filter_type = request.POST.get('filter_type')
        filter_obj.pattern = request.POST.get('pattern')
        filter_obj.is_active = 'is_active' in request.POST
        filter_obj.save()
        
        messages.success(request, 'Email filter updated successfully.')
        return redirect('core:email_filter_list')
    
    context = {
        'filter': filter_obj,
    }
    
    return render(request, 'core/email_filter_detail.html', context)

@login_required
def email_filter_delete(request, filter_id):
    """
    View for deleting an email filter
    """
    filter_obj = get_object_or_404(EmailFilter, id=filter_id)
    
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to delete email filters.')
        return redirect('core:email_filter_list')
    
    if request.method == 'POST':
        filter_name = filter_obj.name
        filter_obj.delete()
        messages.success(request, f'Email filter "{filter_name}" deleted successfully.')
    
    return redirect('core:email_filter_list')

@login_required
def webhook_log_list(request):
    """
    View for listing webhook logs
    """
    # Get query parameters
    status = request.GET.get('status', '')
    
    # Base queryset
    logs = WebhookLog.objects.all()
    
    # Apply filters
    if status:
        logs = logs.filter(status=status)
    
    # Sort by created date (newest first)
    logs = logs.order_by('-created_at')
    
    context = {
        'logs': logs,
    }
    
    return render(request, 'core/webhook_log_list.html', context)

@login_required
def user_log_list(request):
    """
    View for listing user logs
    """
    # Get query parameters
    action = request.GET.get('action', '')
    user_id = request.GET.get('user', '')
    
    # Base queryset
    logs = UserLog.objects.all()
    
    # Apply filters
    if action:
        logs = logs.filter(action_type=action)
    
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    # Sort by timestamp (newest first)
    logs = logs.order_by('-timestamp')
    
    # Get all active users for filter dropdown
    users = User.objects.filter(is_active=True).order_by('username')
    
    context = {
        'logs': logs,
        'users': users,
    }
    
    return render(request, 'core/user_log_list.html', context)

@login_required
def email_config(request):
    """
    View for configuring email server settings
    """
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('core:dashboard')
    
    # Get or create configuration
    config = EmailConfiguration.get_configuration()
    
    if request.method == 'POST':
        # SMTP Settings
        config.smtp_host = request.POST.get('smtp_host')
        config.smtp_port = int(request.POST.get('smtp_port', 587))
        config.smtp_use_tls = request.POST.get('smtp_use_tls') == 'on'
        config.smtp_username = request.POST.get('smtp_username')
        
        # Only update password if provided
        if request.POST.get('smtp_password'):
            config.smtp_password = request.POST.get('smtp_password')
            
        config.default_from_email = request.POST.get('default_from_email')
        config.email_subject_prefix = request.POST.get('email_subject_prefix')
        
        # IMAP Settings
        config.imap_host = request.POST.get('imap_host')
        config.imap_port = int(request.POST.get('imap_port', 993))
        config.imap_use_ssl = request.POST.get('imap_use_ssl') == 'on'
        config.imap_username = request.POST.get('imap_username')
        
        # Only update password if provided
        if request.POST.get('imap_password'):
            config.imap_password = request.POST.get('imap_password')
            
        config.imap_folder = request.POST.get('imap_folder')
        config.imap_check_interval = int(request.POST.get('imap_check_interval', 300))
        
        # Local Email Folder Settings
        config.use_local_folder = request.POST.get('use_local_folder') == 'on'
        config.local_email_folder = request.POST.get('local_email_folder')
        config.process_subdirectories = request.POST.get('process_subdirectories') == 'on'
        config.delete_after_processing = request.POST.get('delete_after_processing') == 'on'
        config.move_to_folder = request.POST.get('move_to_folder')
        
        # Activation status
        config.is_active = request.POST.get('is_active') == 'on'
        
        config.save()
        
        # Create success message
        messages.success(request, 'Email configuration updated successfully.')
        
        # Redirect to avoid form resubmission
        return redirect('core:email_config')
    
    context = {
        'config': config
    }
    
    return render(request, 'core/email_config.html', context)

@login_required
def list_folders(request):
    """API to list folders for the folder browser"""
    if not request.user.is_admin and not getattr(request.user, 'is_supervisor', False):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    import os
    from pathlib import Path
    
    # Get user's home directory as default
    home_dir = str(Path.home())
    
    # Get requested path or use home directory as default
    path = request.GET.get('path', home_dir)
    
    # If path is '/', use home directory
    if path == '/':
        path = home_dir
    
    # For security, don't allow browsing outside home directory
    if not path.startswith(home_dir) and path != home_dir:
        path = home_dir
    
    try:
        # Get the directories in the given path
        directories = []
        files = []
        
        if os.path.isdir(path):
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    directories.append({
                        'name': item,
                        'path': full_path,
                    })
                # Only include .eml files
                elif item.endswith('.eml'):
                    files.append({
                        'name': item,
                        'path': full_path,
                    })
                    
            return JsonResponse({
                'current_path': path,
                'directories': directories,
                'files': files
            })
        else:
            return JsonResponse({'error': 'Path is not a directory'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def ai_test(request):
    """
    View for testing AI with a pasted email
    """
    if request.method == 'POST':
        # Get form data
        email_id = request.POST.get('email_id')
        email_content = request.POST.get('email_content')
        email_file = request.FILES.get('email_file')
        
        # Use active AI model and prompt or specified ones
        model_id = request.POST.get('model_id')
        prompt_id = request.POST.get('prompt_id')
        
        # If neither content nor file is provided
        if not email_content and not email_file and not email_id:
            messages.error(request, 'Please paste email content or upload an .eml file.')
            return redirect('core:ai_test')
        
        # If an email file is uploaded
        if email_file:
            if not email_file.name.endswith('.eml'):
                messages.error(request, 'Only .eml files are supported.')
                return redirect('core:ai_test')
            
            try:
                # Parse the email file
                email_message = email_parser.message_from_bytes(email_file.read())
                
                # Extract subject and body
                subject = email_message.get('Subject', '(No Subject)')
                
                # Extract body
                body_text = ""
                body_html = ""
                
                # Process multipart messages
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        # Skip attachments
                        if "attachment" in content_disposition:
                            continue
                        
                        # Get the payload
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Try to decode with different encodings
                            if content_type == 'text/plain':
                                try:
                                    body_text = payload.decode()
                                except UnicodeDecodeError:
                                    try:
                                        body_text = payload.decode('latin-1')
                                    except:
                                        body_text = str(payload)
                            elif content_type == 'text/html':
                                try:
                                    body_html = payload.decode()
                                except UnicodeDecodeError:
                                    try:
                                        body_html = payload.decode('latin-1')
                                    except:
                                        body_html = str(payload)
                else:
                    # Not multipart - get the payload directly
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        content_type = email_message.get_content_type()
                        try:
                            # Try to decode with different encodings
                            if content_type == 'text/plain':
                                body_text = payload.decode()
                            elif content_type == 'text/html':
                                body_html = payload.decode()
                        except UnicodeDecodeError:
                            try:
                                if content_type == 'text/plain':
                                    body_text = payload.decode('latin-1')
                                elif content_type == 'text/html':
                                    body_html = payload.decode('latin-1')
                            except:
                                body_text = str(payload)
                
                # Use the parsed content
                email_content = body_text or body_html
                
            except Exception as e:
                messages.error(request, f'Error parsing email file: {str(e)}')
                return redirect('core:ai_test')
        
        # If an email ID is provided (test an existing email)
        email_subject = ''
        if email_id:
            try:
                email_obj = Email.objects.get(pk=email_id)
                email_content = email_obj.body_text or email_obj.body_html
                email_subject = email_obj.subject
                body_html = email_obj.body_html
            except Email.DoesNotExist:
                messages.error(request, f'Email with ID {email_id} not found.')
                return redirect('core:ai_test')
        
        # Create a client to call our API
        client = APIClient()
        client.force_authenticate(user=request.user)
        
        # Prepare payload
        payload = {
            'email_content': email_content,
            'email_subject': email_subject
        }
        
        # Add email_html if available
        if 'body_html' in locals() and body_html:
            payload['email_html'] = body_html
            
        # Add email_id if testing from existing email
        if email_id:
            payload['email_id'] = email_id
        
        # Call the API
        try:
            logger.debug(f"Sending API request with payload: {payload}")
            response = client.post(reverse('api:parse_email_content'), payload, format='json')
            
            if response.status_code == 200:
                analysis_result = response.data
                # Şablonun kullandığı yapıya göre rows'u doğru konuma taşı
                if 'data' in analysis_result and 'rows' in analysis_result['data']:
                    # Mevcut yapı: {'data': {'rows': [...]}, 'message': '...', 'success': true}
                    # Template'in beklediği yapı: {'rows': [...], 'message': '...', 'success': true}
                    analysis_result['rows'] = analysis_result['data']['rows']
                    
                if not analysis_result.get('rows', []):
                    messages.warning(request, "The AI analysis did not extract any rows from the email content.")
                else:
                    messages.success(request, f"Successfully extracted {len(analysis_result.get('rows', []))} row(s) from the email content.")
            else:
                logger.error(f"API Error: {response.data}")
                messages.error(request, f"API Error: {response.data.get('detail', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error calling API: {e}", exc_info=True)
            messages.error(request, f"Error calling API: {e}")
    
    # Check if content is HTML for proper display
    is_html_content = False
    if email_content:
        email_content_lower = email_content.lower()
        html_indicators = ['<html', '<!doctype html', '<table', '<div', '<p>', '<body', '<head', '<style']
        is_html_content = any(indicator in email_content_lower for indicator in html_indicators)
    
    context = {
        'email_content': email_content,
        'email_headers': {},
        'is_html_content': is_html_content, 
        'email_source': '',
        'analysis_result': analysis_result,
        'active_ai_model': get_active_ai_model(),
        'active_prompt': get_active_prompt(),
    }
    
    return render(request, 'core/ai_test.html', context)
