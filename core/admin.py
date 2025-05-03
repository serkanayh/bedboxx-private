from django.contrib import admin
from .models import AIPerformanceMetric, HotelAICounter, WebhookLog, EmailConfiguration, DatabaseBackup
from django.shortcuts import redirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
import os
import datetime
import subprocess
import sqlite3

@admin.register(AIPerformanceMetric)
class AIPerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ('ai_model', 'prompt', 'date', 'total_calls', 'successful_calls', 'success_rate', 'token_usage', 'cost')
    list_filter = ('date', 'ai_model', 'prompt')
    date_hierarchy = 'date'

@admin.register(HotelAICounter)
class HotelAICounterAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'unedited_approvals', 'edited_approvals', 'threshold', 'use_regex', 'last_reset')
    list_filter = ('use_regex', 'hotel__juniper_hotel_name')
    search_fields = ('hotel__juniper_hotel_name',)

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('email_row', 'status', 'status_code', 'attempt_count', 'created_at', 'updated_at')
    list_filter = ('status', 'status_code', 'created_at')
    search_fields = ('email_row__hotel_name', 'email_row__email__subject')
    date_hierarchy = 'created_at'

@admin.register(EmailConfiguration)
class EmailConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ('SMTP Settings', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_use_tls', 'smtp_username', 'smtp_password', 
                       'default_from_email', 'email_subject_prefix')
        }),
        ('IMAP Settings', {
            'fields': ('imap_host', 'imap_port', 'imap_use_ssl', 'imap_username', 'imap_password', 
                       'imap_folder', 'imap_check_interval')
        }),
        ('Local Email Folder Settings', {
            'fields': ('use_local_folder', 'local_email_folder', 'process_subdirectories', 
                      'delete_after_processing', 'move_to_folder')
        }),
        ('Status', {
            'fields': ('is_active', 'last_check')
        }),
    )
    
    readonly_fields = ('last_check', 'created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow adding if no configuration exists
        return not EmailConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Do not allow deleting the configuration
        return False

@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ('filename', 'backup_type', 'get_size_display', 'created_at', 'actions_column')
    list_filter = ('backup_type', 'created_at')
    search_fields = ('filename',)
    readonly_fields = ('filename', 'backup_type', 'size', 'created_at')
    
    def get_size_display(self, obj):
        """Convert size in bytes to human readable format"""
        size_bytes = obj.size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    get_size_display.short_description = 'Size'
    
    def actions_column(self, obj):
        """Actions column with download and delete buttons"""
        download_url = f"/admin/core/database_backup/{obj.id}/download/"
        delete_url = f"/admin/core/database_backup/{obj.id}/delete/"
        
        return format_html(
            '<a href="{}" class="button">Download</a> '
            '<a href="{}" class="button" style="background-color: #e74c3c; color: white;">Delete</a>',
            download_url, delete_url
        )
    
    actions_column.short_description = 'Actions'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create_backup/', self.admin_site.admin_view(self.create_backup_view), name='core_create_backup'),
            path('<int:backup_id>/download/', self.admin_site.admin_view(self.download_backup_view), name='core_download_backup'),
            path('<int:backup_id>/delete/', self.admin_site.admin_view(self.delete_backup_view), name='core_delete_backup'),
            path('check_database/', self.admin_site.admin_view(self.check_database_view), name='core_check_database'),
        ]
        return custom_urls + urls
    
    def create_backup_view(self, request):
        """View to manually create a database backup"""
        if request.method == 'POST':
            try:
                # Create backup directory if it doesn't exist
                backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # Generate backup filename with timestamp
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"db_backup_{timestamp}.sqlite3"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # Get path to the SQLite database
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3')
                
                # Create backup using SQLite's .backup command
                conn = sqlite3.connect(db_path)
                with conn:
                    conn.execute(f"VACUUM INTO '{backup_path}'")
                
                # Get file size
                file_size = os.path.getsize(backup_path)
                
                # Create backup record
                DatabaseBackup.objects.create(
                    filename=backup_filename,
                    backup_type='manual',
                    size=file_size
                )
                
                messages.success(request, f"Database backup created successfully: {backup_filename}")
            except Exception as e:
                messages.error(request, f"Error creating backup: {str(e)}")
        
        return redirect('admin:core_databasebackup_changelist')
    
    def download_backup_view(self, request, backup_id):
        """View to download a backup file"""
        try:
            backup = DatabaseBackup.objects.get(id=backup_id)
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
            backup_path = os.path.join(backup_dir, backup.filename)
            
            if os.path.exists(backup_path):
                from django.http import FileResponse
                response = FileResponse(open(backup_path, 'rb'))
                response['Content-Disposition'] = f'attachment; filename="{backup.filename}"'
                return response
            else:
                messages.error(request, f"Backup file not found: {backup.filename}")
        except DatabaseBackup.DoesNotExist:
            messages.error(request, "Backup not found")
        except Exception as e:
            messages.error(request, f"Error downloading backup: {str(e)}")
        
        return redirect('admin:core_databasebackup_changelist')
    
    def delete_backup_view(self, request, backup_id):
        """View to delete a backup file"""
        try:
            backup = DatabaseBackup.objects.get(id=backup_id)
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
            backup_path = os.path.join(backup_dir, backup.filename)
            
            # Delete file if it exists
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            # Delete record
            backup.delete()
            
            messages.success(request, f"Backup deleted: {backup.filename}")
        except DatabaseBackup.DoesNotExist:
            messages.error(request, "Backup not found")
        except Exception as e:
            messages.error(request, f"Error deleting backup: {str(e)}")
        
        return redirect('admin:core_databasebackup_changelist')
    
    def check_database_view(self, request):
        """View to check database integrity"""
        try:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3')
            
            # Use SQLite command to check integrity
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            if result == "ok":
                messages.success(request, "Database integrity check passed!")
            else:
                messages.error(request, f"Database integrity check failed: {result}")
        except Exception as e:
            messages.error(request, f"Error checking database: {str(e)}")
        
        return redirect('admin:core_databasebackup_changelist')
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist view to add custom action buttons"""
        extra_context = extra_context or {}
        extra_context['create_backup_url'] = "create_backup/"
        extra_context['check_database_url'] = "check_database/"
        return super().changelist_view(request, extra_context=extra_context)
