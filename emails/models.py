from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from users.models import User
from hotels.models import Hotel, Room, Market, JuniperContractMarket
import os
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class AIModel(models.Model):
    """
    Model representing an AI model (Claude/GPT) for parsing emails
    """
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=255)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.active else 'Inactive'})"
    
    class Meta:
        verbose_name = 'AI Model'
        verbose_name_plural = 'AI Models'
        ordering = ['-active', 'name']
        
    def save(self, *args, **kwargs):
        # Ensure only one model is active at a time
        if self.active:
            AIModel.objects.filter(active=True).exclude(id=self.id).update(active=False)
        super().save(*args, **kwargs)


class Prompt(models.Model):
    """
    Model representing a prompt for AI models
    """
    title = models.CharField(max_length=255)
    content = models.TextField()
    active = models.BooleanField(default=False)
    success_rate = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({'Active' if self.active else 'Inactive'})"
    
    class Meta:
        verbose_name = 'Prompt'
        verbose_name_plural = 'Prompts'
        ordering = ['-active', '-success_rate']
        
    def save(self, *args, **kwargs):
        # Ensure only one prompt is active at a time
        if self.active:
            Prompt.objects.filter(active=True).exclude(id=self.id).update(active=False)
        super().save(*args, **kwargs)


class RegexRule(models.Model):
    """
    Model representing regex rules for parsing emails
    """
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='regex_rules', null=True, blank=True)
    rule_type = models.CharField(max_length=50, choices=[
        ('hotel_name', 'Hotel Name'),
        ('room_type', 'Room Type'),
        ('market', 'Market'),
        ('date_range', 'Date Range'),
        ('sale_type', 'Sale Type'),
    ])
    pattern = models.CharField(max_length=500)
    success_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        hotel_name = self.hotel.juniper_hotel_name if self.hotel else 'All Hotels'
        return f"{self.rule_type} rule for {hotel_name}"
    
    class Meta:
        verbose_name = 'Regex Rule'
        verbose_name_plural = 'Regex Rules'
        ordering = ['-success_count']


def attachment_upload_path(instance, filename):
    # Sanitize filename if necessary
    filename = os.path.basename(filename) 
    # File will be uploaded to MEDIA_ROOT/attachments/<email_id>/<filename>
    return f'attachments/{instance.email.id}/{filename}'

class Email(models.Model):
    """
    Model representing an email received by the system
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('rejected_hotel_not_found', 'Rejected - JP Hotel Not Found'),
        ('rejected_room_not_found', 'Rejected - JP Room Not Found'),
        ('manual_processed', 'Manual Processed'),
        ('sent_to_robot', 'Sent to Robot'),
        ('robot_processed', 'Robot Processed'),
        ('juniper_manual', 'Juniper(M)'),
        ('juniper_robot', 'Juniper(R)'),
        ('processing', 'Processing'),
        ('processed_nodata', 'No Data Found'),
        ('ignored', 'Ignored'),
        ('error', 'Error'),
    ]
    
    subject = models.CharField(max_length=500)
    sender = models.CharField(max_length=255)
    recipient = models.CharField(max_length=255)
    received_date = models.DateTimeField()
    message_id = models.CharField(max_length=500, unique=True)
    body_text = models.TextField()
    body_html = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    has_attachments = models.BooleanField(default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_emails')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_emails')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attachment_analysis_results = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.subject} ({self.sender})"
    
    class Meta:
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'
        ordering = ['-received_date']
        
    @property
    def status_display(self):
        status_dict = dict(self.STATUS_CHOICES)
        if self.status == 'rejected_hotel_not_found':
            return 'Rejected - JP Hotel Not Found'
        elif self.status == 'rejected_room_not_found':
            return 'Rejected - JP Room Not Found'
        return status_dict.get(self.status, self.status.replace('_', ' ').title())
    
    @property
    def is_processed(self):
        return self.status in ['approved', 'manual_processed', 'robot_processed']
        
    @property
    def total_rules_count(self):
        """Toplam kural sayısını döndürür"""
        return self.rows.count()
    
    @property
    def matched_rules_count(self):
        """Başarılı eşleşmiş kural sayısını döndürür"""
        # Bir kuralın eşleşmiş sayılması için hem otel hem de oda eşleşmesi olmalı
        # Ya da oda tipi "ALL ROOM" vb. olmalı

        # Juniper otel eşleşmesi olan ve juniper_rooms ilişkisinde kayıt olan satırlar
        rows_with_rooms = self.rows.filter(
            juniper_hotel__isnull=False
        ).filter(
            juniper_rooms__isnull=False
        ).distinct()
        
        # Juniper otel eşleşmesi olan ve ALL ROOM tipi olan satırlar
        all_room_rows = self.rows.filter(
            juniper_hotel__isnull=False, 
            room_type__iregex=r'all\s*room'  # "ALL ROOM", "All Room", "ALLROOM" gibi varyasyonlar
        ).distinct()
        
        # İki sorgu sonucunu birleştir ve tekrar sayısını say (distinct)
        return (rows_with_rooms | all_room_rows).distinct().count()
    
    @property
    def matching_ratio_display(self):
        """Eşleşme oranını görsel olarak gösterir (örn: 4/5)"""
        total = self.total_rules_count
        matched = self.matched_rules_count
        
        if total == 0:
            return "(0/0)"
        
        # Eşleşme oranını hesapla ve göster
        return f"({matched}/{total})"


class EmailAttachment(models.Model):
    """
    Model representing an attachment to an email
    """
    email = models.ForeignKey(Email, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    size = models.PositiveIntegerField(null=True, blank=True)
    content_id = models.CharField(max_length=255, null=True, blank=True, help_text="Content-ID header from email")
    extracted_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment {self.filename} for Email {self.email.id}"
    
    def save(self, *args, **kwargs):
        if self.file and not self.size:
            try:
                self.size = self.file.size
            except Exception as e:
                 print(f"Error getting file size for {self.filename}: {e}") # Basic logging
                 self.size = 0 # Default size if error
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete the file from storage when the model instance is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)


class EmailRow(models.Model):
    """
    Model representing a parsed row from an email
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('matching', 'Matching in Progress'),
        ('hotel_not_found', 'Hotel Not Found'),
        ('room_not_found', 'Room Not Found'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('rejected_hotel_not_found', 'Rejected - JP Hotel Not Found'),
        ('rejected_room_not_found', 'Rejected - JP Room Not Found'),
        ('robot_processing', 'Robot Processing'),
        ('robot_success', 'Robot Success'),
        ('robot_failed', 'Robot Failed'),
        ('ignored', 'Ignored'),
    ]
    
    SALE_TYPE_CHOICES = [
        ('stop', 'Stop Sale'),
        ('open', 'Open Sale'),
    ]
    
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='rows')
    hotel_name = models.CharField(max_length=255)
    room_type = models.CharField(max_length=255)
    markets = models.ManyToManyField('hotels.Market', blank=True, related_name='email_rows')
    start_date = models.DateField()
    end_date = models.DateField()
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='stop')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    reject_reason = models.CharField(max_length=100, blank=True, null=True)
    
    juniper_hotel = models.ForeignKey(Hotel, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_rows')
    juniper_rooms = models.ManyToManyField(Room, blank=True, related_name='email_rows')
    
    ai_extracted = models.BooleanField(default=False)
    extracted_from_attachment = models.BooleanField(default=False)
    source_attachment = models.ForeignKey(
        EmailAttachment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_rows', 
        help_text="The specific attachment this row was extracted from, if any."
    )
    regex_extracted = models.BooleanField(default=False)
    manually_edited = models.BooleanField(default=False)
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_rows')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Matching scores
    hotel_match_score = models.FloatField(null=True, blank=True)
    room_match_score = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.hotel_name} - {self.room_type} - {self.sale_type}"
    
    class Meta:
        verbose_name = 'Email Row'
        verbose_name_plural = 'Email Rows'
        # ordering = ['email__received_date', 'hotel_name', 'room_type'] # Yorum satırı yapıldı
        ordering = ['id'] # veya ID'ye göre sırala
        
    def mark_as_processed(self, user):
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
        
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status)
    
    @property
    def sale_type_display(self):
        return dict(self.SALE_TYPE_CHOICES).get(self.sale_type)
    
    @property
    def market_summary(self):
        """Returns a comma-separated string of ALL associated market names."""
        # Check if the instance has an ID, otherwise M2M is inaccessible
        if not self.pk:
            return "N/A (unsaved)"
        markets = self.markets.all()
        if not markets:
            return "-"
        # Return ALL market names
        names = [m.name for m in markets]
        return ", ".join(names)
    
    @property
    def get_matching_contracts_info(self):
        """
        Finds JuniperContractMarket entries matching the row's hotel and resolved markets.
        If markets include 'ALL', it fetches all contracts for the hotel.
        Returns a tuple: (comma_separated_contract_names, count_string, has_market_match)
        e.g., ("Summer 2025 EUR", "(1/5)", True) or ("-", "(0/5)", False)
        Uses SQLite compatible method for distinct contract names.
        """
        if not self.pk or not self.juniper_hotel:
            # No hotel matched
            return ("-", "", False)

        row_market_names = [m.name.strip().upper() for m in self.markets.all()]
        is_all_market = "ALL" in row_market_names or not row_market_names # Treat empty market list same as ALL

        # Get total distinct contracts for this hotel (for the count denominator)
        total_contracts_queryset = JuniperContractMarket.objects.filter(
            hotel=self.juniper_hotel
        )
        total_distinct_contracts = sorted(list(set(total_contracts_queryset.values_list('contract_name', flat=True))))
        total_contracts_count = len(total_distinct_contracts)

        matching_contract_names = []
        has_market_match = False

        if is_all_market:
            # If market is ALL, consider all hotel contracts as matching
            matching_contract_names = total_distinct_contracts
            has_market_match = True # 'ALL' market means contracts are inherently matched
            logger.debug(f"Row {self.id}: Market is ALL. Fetching all {total_contracts_count} contracts for hotel {self.juniper_hotel.juniper_code}.")
        else:
            # Specific markets assigned, filter contracts by those markets
            row_market_ids = self.markets.values_list('id', flat=True)
            matching_contracts_queryset = JuniperContractMarket.objects.filter(
                hotel=self.juniper_hotel,
                market_id__in=row_market_ids
            ).values_list('contract_name', flat=True)
            matching_contract_names = sorted(list(set(matching_contracts_queryset)))
            has_market_match = len(matching_contract_names) > 0
            logger.debug(f"Row {self.id}: Specific markets {row_market_names}. Found {len(matching_contract_names)} matching contracts out of {total_contracts_count} total.")

        contract_names_str = ", ".join(matching_contract_names)
        # Count string reflects matched contracts vs total for the hotel
        count_str = f"({len(matching_contract_names)}/{total_contracts_count})" if total_contracts_count > 0 else "(0/0)"

        # Return names, count string, and the boolean market match status
        return (contract_names_str if contract_names_str else "-", count_str, has_market_match)
    
    @property
    def juniper_direct_link(self):
        if self.juniper_hotel:
            return f"https://bedboxx.juniperbetemp.com/intranet/alojamiento/mantenimientoV2.aspx?alojamiento={self.juniper_hotel.juniper_code}"
        return None


class RoomTypeMatch(models.Model):
    email_room_type = models.CharField(max_length=255)
    juniper_room = models.ForeignKey('hotels.Room', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email_room_type} → {self.juniper_room.juniper_room_type} [{self.juniper_room.room_code}]"

    class Meta:
        unique_together = ('email_room_type', 'juniper_room')
        verbose_name = 'Room Type Match'
        verbose_name_plural = 'Room Type Matches'


class RoomTypeReject(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    email_room_type = models.CharField(max_length=255)
    market = models.ForeignKey(Market, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=32, choices=[
        ('room', 'Room Not Matched'),
        ('hotel', 'Hotel Not Matched'),
        ('market', 'Market Not Matched'),
        ('other', 'Other'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hotel} - {self.email_room_type} - {self.market or '-'} ({self.reason})"

    class Meta:
        verbose_name = 'Room Type Reject'
        verbose_name_plural = 'Room Type Rejects'
        unique_together = ('hotel', 'email_room_type', 'market', 'reason')


class UserLog(models.Model):
    """
    Model for tracking user actions
    """
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('approve_row', 'Approve Row'),
        ('edit_row', 'Edit Row'),
        ('send_to_robot', 'Send to Robot'),
        ('mark_hotel_not_found', 'Mark Hotel Not Found'),
        ('mark_room_not_found', 'Mark Room Not Found'),
        ('ignore_email', 'Ignore Email'),
        ('assign_email', 'Assign Email'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs')
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    email = models.ForeignKey(Email, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    email_row = models.ForeignKey(EmailRow, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action_type} - {self.timestamp}"
    
    class Meta:
        verbose_name = 'User Log'
        verbose_name_plural = 'User Logs'
        ordering = ['-timestamp']


class EmailFilter(models.Model):
    """
    Model for email filtering rules
    """
    FILTER_TYPE_CHOICES = [
        ('subject', 'Subject'),
        ('sender', 'Sender'),
        ('keyword', 'Keyword'),
        ('date', 'Date'),
    ]
    
    name = models.CharField(max_length=100)
    filter_type = models.CharField(max_length=20, choices=FILTER_TYPE_CHOICES)
    pattern = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_filters')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.filter_type})"
    
    class Meta:
        verbose_name = 'Email Filter'
        verbose_name_plural = 'Email Filters'
        ordering = ['filter_type', 'name']


class EmailHotelMatch(models.Model):
    """
    Öğrenen sistem için gönderen e-posta adresi ile otel arasındaki ilişkiyi tutan model.
    Bu ilişki, her eşleştirme yapıldığında öğrenilir ve gelecekteki eşleştirmelerde kullanılır.
    """
    sender_email = models.EmailField(verbose_name="Gönderen E-posta", help_text="E-posta gönderenin adresi")
    hotel = models.ForeignKey(Hotel, verbose_name="Otel", on_delete=models.CASCADE, related_name="email_matches")
    confidence_score = models.IntegerField(verbose_name="Güven Puanı", default=80, help_text="Bu eşleştirmenin güven puanı (0-100)")
    match_count = models.IntegerField(verbose_name="Eşleştirme Sayısı", default=1, help_text="Kaç kez eşleştirildi")
    first_matched_at = models.DateTimeField(verbose_name="İlk Eşleştirme", auto_now_add=True)
    last_matched_at = models.DateTimeField(verbose_name="Son Eşleştirme", auto_now=True)
    
    class Meta:
        verbose_name = "E-posta Otel Eşleştirmesi"
        verbose_name_plural = "E-posta Otel Eşleştirmeleri"
        unique_together = ('sender_email', 'hotel')
        ordering = ('-match_count', 'sender_email')
    
    def __str__(self):
        return f"{self.sender_email} → {self.hotel.juniper_hotel_name}"
    
    def increase_confidence(self):
        """Güven puanını ve eşleştirme sayısını artır"""
        self.match_count += 1
        # Her eşleştirmede güven puanını artır, maksimum 100
        if self.confidence_score < 100:
            self.confidence_score = min(100, self.confidence_score + 5)
        self.last_matched_at = timezone.now()
        self.save()
