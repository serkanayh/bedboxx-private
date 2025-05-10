from django.db import models

class AIPerformanceMetric(models.Model):
    """
    Model for tracking AI performance metrics
    """
    ai_model = models.ForeignKey('emails.AIModel', on_delete=models.CASCADE, related_name='performance_metrics')
    prompt = models.ForeignKey('emails.Prompt', on_delete=models.CASCADE, related_name='performance_metrics')
    total_calls = models.IntegerField(default=0)
    successful_calls = models.IntegerField(default=0)
    token_usage = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.ai_model.name} - {self.date} - {self.success_rate}%"
    
    class Meta:
        verbose_name = 'AI Performance Metric'
        verbose_name_plural = 'AI Performance Metrics'
        ordering = ['-date']
        unique_together = ['ai_model', 'prompt', 'date']
        
    @property
    def success_rate(self):
        if self.total_calls == 0:
            return 0
        return round((self.successful_calls / self.total_calls) * 100, 2)


class HotelAICounter(models.Model):
    """
    Model for tracking AI success counters per hotel
    """
    hotel = models.ForeignKey('hotels.Hotel', on_delete=models.CASCADE, related_name='ai_counters')
    unedited_approvals = models.IntegerField(default=0)
    edited_approvals = models.IntegerField(default=0)
    threshold = models.IntegerField(default=10)
    use_regex = models.BooleanField(default=False)
    last_reset = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.hotel.juniper_hotel_name} - {self.unedited_approvals}/{self.threshold}"
    
    class Meta:
        verbose_name = 'Hotel AI Counter'
        verbose_name_plural = 'Hotel AI Counters'
        ordering = ['hotel__juniper_hotel_name']
        
    def increment_unedited(self):
        self.unedited_approvals += 1
        if self.unedited_approvals >= self.threshold:
            self.use_regex = True
        self.save()
        
    def increment_edited(self):
        self.edited_approvals += 1
        self.unedited_approvals = 0  # Reset counter when edits are made
        self.use_regex = False
        self.save()


class WebhookLog(models.Model):
    """
    Model for tracking webhook calls to RPA system
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    email_row = models.ForeignKey('emails.EmailRow', on_delete=models.CASCADE, related_name='webhook_logs')
    payload = models.JSONField()
    response = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    status_code = models.IntegerField(null=True, blank=True)
    attempt_count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Webhook for {self.email_row} - {self.status}"
    
    class Meta:
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'
        ordering = ['-created_at']


class EmailConfiguration(models.Model):
    """
    Model for storing email server configuration
    Only one record should exist in the database
    """
    # SMTP Settings
    smtp_host = models.CharField(max_length=255, default='smtp.gmail.com')
    smtp_port = models.IntegerField(default=587)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    default_from_email = models.EmailField(default='stopsale@example.com')
    email_subject_prefix = models.CharField(max_length=50, default='[StopSale] ')
    
    # IMAP Settings
    imap_host = models.CharField(max_length=255, default='imap.gmail.com')
    imap_port = models.IntegerField(default=993)
    imap_use_ssl = models.BooleanField(default=True)
    imap_username = models.CharField(max_length=255, blank=True)
    imap_password = models.CharField(max_length=255, blank=True)
    imap_folder = models.CharField(max_length=50, default='INBOX')
    imap_check_interval = models.IntegerField(default=300, help_text='Check interval in seconds')
    imap_label = models.CharField(max_length=50, default='stop_sale', blank=True, 
                                  help_text='Gmail/IMAP label or folder to filter emails by. If specified, the system will only process '
                                           'emails from this label/folder instead of the inbox. For Gmail, create a label named "stop_sale" '
                                           'and apply it to relevant emails.')
    
    # Local Email Folder Settings
    use_local_folder = models.BooleanField(default=False, help_text='Use local folder for emails instead of IMAP')
    local_email_folder = models.CharField(max_length=255, blank=True, help_text='Path to local folder with .eml files')
    process_subdirectories = models.BooleanField(default=False, help_text='Process .eml files in subdirectories')
    delete_after_processing = models.BooleanField(default=False, help_text='Delete .eml files after processing')
    move_to_folder = models.CharField(max_length=255, blank=True, help_text='Path to move processed .eml files (leave blank to not move)')
    
    # Additional Settings
    is_active = models.BooleanField(default=False, help_text='Set to true to enable email checking')
    last_check = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return f"Email Configuration - {self.imap_username}"
    
    class Meta:
        verbose_name = 'Email Configuration'
        verbose_name_plural = 'Email Configurations'
        
    def save(self, *args, **kwargs):
        # Ensure only one record exists
        if not self.pk and EmailConfiguration.objects.exists():
            # Update existing record instead of creating a new one
            first = EmailConfiguration.objects.first()
            self.pk = first.pk
        
        super().save(*args, **kwargs)
        
    @classmethod
    def get_configuration(cls):
        """
        Get the active configuration or create default one
        """
        config, created = cls.objects.get_or_create(pk=1)
        return config


class DatabaseBackup(models.Model):
    """
    Model to store database backup information
    """
    filename = models.CharField(max_length=255)
    backup_type = models.CharField(max_length=20, choices=[
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
    ])
    size = models.IntegerField()  # Size in bytes
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.filename} ({self.get_backup_type_display()}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Database Backup'
        verbose_name_plural = 'Database Backups'
