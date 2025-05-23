from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from users.models import User
from hotels.models import Hotel, Room, Market, JuniperContractMarket, RoomTypeGroup, RoomTypeVariant
import os
import logging
import email.header
import re

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
        ('blocked_hotel_not_found', 'Blocked - JP Hotel Not Found'),
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
    
    ROBOT_STATUS_CHOICES = [
        ('pending', 'Bekliyor'),
        ('processing', 'İşleniyor'),
        ('processed', 'Tamamlandı'),
        ('error', 'Hata'),
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
    robot_status = models.CharField(max_length=20, choices=ROBOT_STATUS_CHOICES, default='pending')
    
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
    
    @property
    def decoded_filename(self):
        """
        Decode MIME-encoded filename if needed
        """
        from email.header import decode_header
        
        # If not MIME-encoded, return as is
        if not '=?' in self.filename:
            return self.filename
        
        try:
            decoded_parts = decode_header(self.filename)
            decoded_filename = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_part = part.decode(encoding or 'utf-8', errors='replace')
                else:
                    decoded_part = part
                decoded_filename += decoded_part
            
            return decoded_filename
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error decoding filename {self.filename}: {str(e)}")
            return self.filename
    
    @property
    def file_extension(self):
        """
        Get the file extension from the decoded filename
        """
        decoded_filename = self.decoded_filename.lower()
        # Strip any trailing MIME encoding terminators before extracting extension
        if decoded_filename.endswith('?='):
            decoded_filename = decoded_filename[:-2]
        return os.path.splitext(decoded_filename)[1]
    
    @property
    def is_pdf(self):
        """
        Check if the file is a PDF
        """
        file_ext = self.file_extension
        if file_ext.endswith('?='):
            file_ext = file_ext[:-2]
        return file_ext == '.pdf' or self.content_type == 'application/pdf' or 'pdf' in self.decoded_filename.lower()
    
    @property
    def is_word(self):
        """
        Check if the file is a Word document
        """
        word_extensions = ['.doc', '.docx']
        word_content_types = ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        
        return (self.file_extension in word_extensions or 
                self.content_type in word_content_types or 
                'doc' in self.decoded_filename.lower())
    
    @property
    def is_excel(self):
        """
        Check if the file is an Excel document
        """
        excel_extensions = ['.xls', '.xlsx', '.csv']
        excel_content_types = [
            'application/vnd.ms-excel', 
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv'
        ]
        
        return (self.file_extension in excel_extensions or 
                self.content_type in excel_content_types or 
                any(ext in self.decoded_filename.lower() for ext in ['xls', 'xlsx', 'csv']))
    
    @property
    def is_image(self):
        """Check if file is an image based on extension or content type"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg']
        return (self.file_extension in image_extensions or
                (self.content_type and self.content_type.startswith('image/')))
    
    @property
    def is_text(self):
        """Check if file is a text file based on extension or content type"""
        text_extensions = ['.txt', '.md', '.log', '.json', '.yaml', '.yml']
        text_content_types = ['text/plain', 'text/markdown']
        return (self.file_extension in text_extensions or
                self.content_type in text_content_types)
    
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

    @property
    def pretty_filename(self):
        """
        Returns a formatted display version of the filename, possibly with an icon
        """
        # Clear any remaining encoded parts
        # Remove =?...?= patterns if they still exist
        filename = re.sub(r'=\?.*?\?=', '', self.decoded_filename).strip()
        
        # Remove any non-printable characters
        filename = ''.join(c for c in filename if c.isprintable() or c.isspace())
        
        # If filename is still empty, use a placeholder
        if not filename or filename.strip() == '':
            return f"Ek-{self.id}" + self.file_extension
            
        return filename
    
    @property 
    def icon_class(self):
        """Returns an appropriate Bootstrap icon class based on file type"""
        if self.is_pdf:
            return "bi-file-earmark-pdf text-danger"
        elif self.is_word:
            return "bi-file-earmark-word text-primary"
        elif self.is_excel:
            return "bi-file-earmark-excel text-success"
        elif self.is_image:
            return "bi-file-earmark-image text-info"
        elif self.is_text:
            return "bi-file-earmark-text text-secondary"
        else:
            return "bi-file-earmark"


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
    
    selected_contracts = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated list of selected contracts")
    
    # E-postadan çıkarılan veya manuel girilen orijinal pazar adı
    original_market_name = models.CharField(max_length=255, blank=True, null=True)
    
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

    def match_hotel_and_rooms(self):
        """
        Find and set Juniper hotel and room matches for this email row
        """
        # Fonksiyonları runtime'da import et (dairesel import'u önlemek için)
        from emails.views import get_hotel_suggestions, get_room_suggestions

        logger.info(f"Matching hotel and rooms for EmailRow {self.id} - Hotel: '{self.hotel_name}', Room: '{self.room_type}'")
        
        # Match hotel first
        if self.hotel_name and not self.juniper_hotel:
            # Use the same function used in the UI
            best_hotel_match, hotel_suggestions = get_hotel_suggestions(self.hotel_name)
            
            # Auto-match if the best match has high enough confidence
            if best_hotel_match and hasattr(best_hotel_match, 'match_score') and best_hotel_match.match_score >= 65:
                self.juniper_hotel = best_hotel_match
                self.save(update_fields=['juniper_hotel'])
                logger.info(f"Auto-matched hotel: '{self.hotel_name}' -> '{best_hotel_match.juniper_hotel_name}' (Score: {best_hotel_match.match_score})")
            else:
                logger.info(f"Could not find good hotel match for '{self.hotel_name}'")
                self.status = 'hotel_not_found'
                self.save(update_fields=['status'])
                return
        
        # Then match rooms if we have a hotel match
        if self.juniper_hotel and self.room_type and not self.juniper_rooms.exists():
            # Special handling for "All Room" type
            if self.room_type.strip().upper() in ["ALL ROOM", "ALL ROOMS", "ALL ROOM TYPES", "TÜM ODALAR"]:
                logger.info(f"'All Room' type detected for row {self.id}")
                # No need to match specific rooms for "All Room" type
                self.status = 'pending'
                self.save(update_fields=['status'])
                return
            
            # First check for room type group match
            found_group_match = False
            clean_room_type = self.room_type.strip().upper()
            
            # Try direct match with a room type group
            room_type_group = RoomTypeGroup.objects.filter(
                hotel=self.juniper_hotel,
                name__iexact=clean_room_type
            ).first()
            
            # If not found, try contains match
            if not room_type_group:
                room_type_group = RoomTypeGroup.objects.filter(
                    hotel=self.juniper_hotel,
                    name__icontains=clean_room_type
                ).first()
                
                # Alternative: try if email room type contains a group name
                if not room_type_group:
                    for group in RoomTypeGroup.objects.filter(hotel=self.juniper_hotel):
                        if group.name in clean_room_type:
                            room_type_group = group
                            break
            
            # If we found a room type group, match all variants
            if room_type_group:
                found_group_match = True
                logger.info(f"Found room type group match: '{self.room_type}' -> Group: '{room_type_group.name}'")
                
                selected_rooms = []
                for variant in room_type_group.variants.all():
                    variant_rooms = Room.objects.filter(
                        hotel=self.juniper_hotel,
                        juniper_room_type__icontains=variant.variant_room_name
                    )
                    selected_rooms.extend(variant_rooms)
                
                # Remove duplicates
                selected_rooms = list(set(selected_rooms))
                
                if selected_rooms:
                    self.juniper_rooms.set(selected_rooms)
                    self.status = 'pending'
                    self.save()
                    logger.info(f"Matched {len(selected_rooms)} rooms from group '{room_type_group.name}': {[r.juniper_room_type for r in selected_rooms]}")
                    return
            
            # If no group match found, fall back to direct room matching
            if not found_group_match:
                # Use the same function used in the UI
                best_room_match, room_suggestions, search_pattern = get_room_suggestions(self.room_type, self.juniper_hotel)
                
                if best_room_match:
                    # BURADA DEĞİŞİKLİK: Eğer room_suggestions liste içinde birden fazla oda varsa,
                    # tümünü ekle (oda grubu eşleşmesi durumunda tüm varyantların olacağı bir liste)
                    if len(room_suggestions) > 1:
                        self.juniper_rooms.set(room_suggestions)
                        logger.info(f"Auto-matched multiple rooms for '{self.room_type}': {[r.juniper_room_type for r in room_suggestions]}")
                    else:
                        # Tek bir oda eşleşmesi varsa sadece onu ekle
                        self.juniper_rooms.add(best_room_match)
                        logger.info(f"Auto-matched room: '{self.room_type}' -> '{best_room_match.juniper_room_type}'")
                    
                    self.status = 'pending'
                    self.save()
                else:
                    logger.info(f"Could not find good room match for '{self.room_type}'")
                    self.status = 'room_not_found'
                    self.save(update_fields=['status'])
                    return
        
        # If we got here, update status
        if self.juniper_hotel:
            if self.juniper_rooms.exists() or self.room_type.strip().upper() in ["ALL ROOM", "ALL ROOMS", "ALL ROOM TYPES", "TÜM ODALAR"]:
                self.status = 'pending'
            else:
                self.status = 'room_not_found'
        else:
            self.status = 'hotel_not_found'
        
        self.save(update_fields=['status'])


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
        return f"{self.sender_email} -> {self.hotel.juniper_hotel_name} (Güven: {self.confidence_score})"
    
    def increase_confidence(self, points=1):
        """Güven puanını artırır, maksimum 100."""
        self.confidence_score = min(100, self.confidence_score + points)
        self.match_count += 1
        self.last_matched_at = timezone.now()
        self.save()


class RobotConfiguration(models.Model):
    """
    Configuration for the robot integration
    """
    output_directory = models.CharField(max_length=255, help_text="Directory where robot JSON files will be saved")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Robot Configuration ({self.output_directory})"
    
    class Meta:
        verbose_name = 'Robot Configuration'
        verbose_name_plural = 'Robot Configurations'


# Yeni Öğrenme Modelleri
class EmailMarketMatch(models.Model):
    """
    Öğrenen sistem için e-postadaki pazar bilgisini Juniper pazar nesnesine eşleştiren model.
    """
    email_market_name = models.CharField(max_length=255, verbose_name="E-postadaki Pazar Adı")
    juniper_market = models.ForeignKey(Market, verbose_name="Juniper Pazar", on_delete=models.CASCADE, related_name="email_matches")
    confidence_score = models.IntegerField(verbose_name="Güven Puanı", default=80, help_text="Bu eşleştirmenin güven puanı (0-100)")
    match_count = models.IntegerField(verbose_name="Eşleştirme Sayısı", default=1, help_text="Kaç kez eşleştirildi")
    first_matched_at = models.DateTimeField(verbose_name="İlk Eşleştirme", auto_now_add=True)
    last_matched_at = models.DateTimeField(verbose_name="Son Eşleştirme", auto_now=True)

    class Meta:
        verbose_name = "E-posta Pazar Eşleştirmesi"
        verbose_name_plural = "E-posta Pazar Eşleştirmeleri"
        unique_together = ('email_market_name', 'juniper_market')
        ordering = ('-match_count', 'email_market_name')

    def __str__(self):
        return f"{self.email_market_name} -> {self.juniper_market.name} (Güven: {self.confidence_score})"

    def increase_confidence(self, points=1):
        """Güven puanını artırır, maksimum 100."""
        self.confidence_score = min(100, self.confidence_score + points)
        self.match_count += 1
        self.last_matched_at = timezone.now()
        self.save()

class EmailContractMatch(models.Model):
    """
    Öğrenen sistem için e-postadaki satırın içerdiği bilgilere dayanarak kontrat eşleştirmesini tutan model.
    Bu model, belirli bir otel, oda tipi ve pazar kombinasyonu için hangi kontratların seçildiğini öğrenir.
    """
    # İlişkilendirilecek EmailRow bilgileri (tamamı yerine özet bilgiler veya FK)
    # Basitlik için şimdilik FK kullanalım ve ilgili row'un bilgilerini saklayalım
    # İleri seviyede, EmailRow'un hash'i veya özet bilgileri kullanılabilir
    email_row_sample = models.ForeignKey('EmailRow', on_delete=models.SET_NULL, null=True, blank=True,
                                         verbose_name="Örnek E-posta Satırı",
                                         help_text="Bu eşleşmenin öğrenildiği örnek satır (opsiyonel)")

    # Öğrenme için temel alınan bilgiler
    # EmailRow'dan kopyalanacak veya ilişkilendirilecek alanlar
    source_hotel_name = models.CharField(max_length=255, verbose_name="Kaynak Otel Adı")
    source_room_type = models.CharField(max_length=255, verbose_name="Kaynak Oda Tipi")
    source_market_names = models.CharField(max_length=500, verbose_name="Kaynak Pazar Adları (virgülle ayrılmış)", blank=True, null=True)
    # Diğer potansiyel kaynak bilgiler: sender_email, date range type (season vs specific dates)

    # Eşleşen Juniper bilgileri
    juniper_hotel = models.ForeignKey(Hotel, verbose_name="Juniper Otel", on_delete=models.CASCADE, related_name="contract_matches", null=True, blank=True)
    juniper_rooms = models.ManyToManyField(Room, verbose_name="Juniper Odalar", blank=True, related_name="contract_matches")
    juniper_markets = models.ManyToManyField(Market, verbose_name="Juniper Pazarlar", blank=True, related_name="contract_matches")
    matched_contracts = models.CharField(max_length=500, verbose_name="Eşleşen Kontratlar (virgülle ayrılmış)")

    confidence_score = models.IntegerField(verbose_name="Güven Puanı", default=80, help_text="Bu eşleştirmenin güven puanı (0-100)")
    match_count = models.IntegerField(verbose_name="Eşleştirme Sayısı", default=1, help_text="Kaç kez eşleştirildi")
    first_matched_at = models.DateTimeField(verbose_name="İlk Eşleştirme", auto_now_add=True)
    last_matched_at = models.DateTimeField(verbose_name="Son Eşleştirme", auto_now=True)

    class Meta:
        verbose_name = "E-posta Kontrat Eşleştirmesi"
        verbose_name_plural = "E-posta Kontrat Eşleştirmeleri"
        # Daha karmaşık unique_together veya custom validation gerekebilir
        # unique_together = ('source_hotel_name', 'source_room_type', 'source_market_names', 'matched_contracts') # Çok kısıtlayıcı olabilir
        ordering = ('-match_count', 'source_hotel_name')

    def __str__(self):
        return f"{self.source_hotel_name} / {self.source_room_type} -> {self.matched_contracts} (Güven: {self.confidence_score})"

    def increase_confidence(self, points=1):
        """Güven puanını artırır, maksimum 100."""
        self.confidence_score = min(100, self.confidence_score + points)
        self.match_count += 1
        self.last_matched_at = timezone.now()
        self.save()

class EmailBlockList(models.Model):
    """
    Bloklanan e-posta adreslerini ve nedenlerini tutan model
    """
    sender_email = models.EmailField(verbose_name="Gönderen E-posta", unique=True, 
                                    help_text="Bloklanacak e-posta adresi")
    reason = models.CharField(max_length=100, verbose_name="Bloklanma Nedeni",
                             default="JP Hotel Not Found", 
                             help_text="E-postanın bloklanma nedeni")
    blocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='blocked_emails',
                                 verbose_name="Bloklayan Kullanıcı")
    is_active = models.BooleanField(default=True, verbose_name="Aktif Mi?",
                                  help_text="Blok aktif mi? Geçici olarak devre dışı bırakmak için kapatabilirsiniz.")
    blocked_at = models.DateTimeField(auto_now_add=True, verbose_name="Bloklanma Tarihi")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Son Güncellenme")
    original_email = models.ForeignKey(Email, on_delete=models.SET_NULL, null=True, 
                                     related_name='email_blocks',
                                     verbose_name="Orijinal E-posta",
                                     help_text="Bloklamaya neden olan orijinal e-posta")
    
    class Meta:
        verbose_name = "E-posta Blok Listesi"
        verbose_name_plural = "E-posta Blok Listesi"
        ordering = ['-blocked_at']
    
    def __str__(self):
        return f"{self.sender_email} - {self.reason}" 