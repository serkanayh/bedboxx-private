from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    AIModel, Prompt, RegexRule, Email, EmailAttachment, 
    EmailRow, UserLog, EmailFilter, RoomTypeMatch, RoomTypeReject,
    EmailHotelMatch, EmailBlockList
)

@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'created_at', 'updated_at')
    list_filter = ('active', 'created_at')
    search_fields = ('name',)
    ordering = ('-active', 'name')

@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'success_rate', 'created_at', 'updated_at')
    list_filter = ('active', 'created_at')
    search_fields = ('title', 'content')
    ordering = ('-active', '-success_rate')

@admin.register(RegexRule)
class RegexRuleAdmin(admin.ModelAdmin):
    list_display = ('rule_type', 'hotel', 'pattern', 'success_count', 'created_at')
    list_filter = ('rule_type', 'hotel', 'created_at')
    search_fields = ('pattern', 'hotel__juniper_hotel_name')
    ordering = ('-success_count',)

@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'received_date', 'status', 'match_status_display', 'has_attachments', 'processed_by')
    list_filter = ('status', 'has_attachments', 'received_date', 'created_at')
    search_fields = ('subject', 'sender', 'recipient', 'body_text')
    ordering = ('-received_date',)
    date_hierarchy = 'received_date'
    
    @admin.display(description='Eşleşme')
    def match_status_display(self, obj):
        """Eşleşme oranını renkli bir şekilde gösterir"""
        total = obj.total_rules_count
        matched = obj.matched_rules_count
        
        if total == 0:
            return "-"
            
        # Eşleşme yüzdesi hesapla
        match_percent = (matched / total) * 100
        
        # Eşleşme durumuna göre renk belirle
        if match_percent == 100:
            color = 'green'  # Tam eşleşme: Yeşil
        elif match_percent >= 75:
            color = 'orange'  # Yüksek eşleşme: Turuncu
        else:
            color = 'red'  # Düşük eşleşme: Kırmızı
            
        # HTML olarak renkli metin döndür
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.matching_ratio_display
        )

class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0

@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'email', 'content_type', 'size', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('filename', 'email__subject')
    ordering = ('-created_at',)

class EmailRowInline(admin.TabularInline):
    model = EmailRow
    extra = 0
    fields = ('hotel_name', 'room_type', 'start_date', 'end_date', 'sale_type', 'status', 'market_summary', 'juniper_hotel', 'juniper_rooms')
    readonly_fields = ('market_summary', 'created_at', 'updated_at')
    raw_id_fields = ('juniper_hotel', 'juniper_rooms')
    filter_horizontal = ('juniper_rooms',)

@admin.register(EmailRow)
class EmailRowAdmin(admin.ModelAdmin):
    list_display = ('hotel_name', 'room_type', 'display_markets', 'start_date', 'end_date', 'sale_type', 'status', 'email')
    list_filter = ('status', 'sale_type', 'start_date', 'markets', 'ai_extracted', 'regex_extracted', 'manually_edited')
    search_fields = ('hotel_name', 'room_type', 'markets__name', 'email__subject')
    ordering = ('-email__received_date', 'hotel_name')
    date_hierarchy = 'created_at'
    filter_horizontal = ('markets', 'juniper_rooms')

    @admin.display(description='Markets')
    def display_markets(self, obj):
        return ", ".join([market.name for market in obj.markets.all()[:3]])

@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'email', 'email_row', 'ip_address', 'timestamp')
    list_filter = ('action_type', 'timestamp', 'user')
    search_fields = ('user__username', 'details', 'email__subject')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

@admin.register(EmailFilter)
class EmailFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'filter_type', 'pattern', 'is_active', 'created_by', 'created_at')
    list_filter = ('filter_type', 'is_active', 'created_at')
    search_fields = ('name', 'pattern')
    ordering = ('filter_type', 'name')

@admin.register(RoomTypeMatch)
class RoomTypeMatchAdmin(admin.ModelAdmin):
    list_display = ('email_room_type', 'juniper_room', 'created_at', 'updated_at')
    search_fields = ('email_room_type', 'juniper_room__juniper_room_type', 'juniper_room__room_code')
    list_filter = ('created_at', 'updated_at')
    ordering = ('-updated_at',)

@admin.register(RoomTypeReject)
class RoomTypeRejectAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'email_room_type', 'market', 'reason', 'created_at')
    search_fields = ('hotel__juniper_hotel_name', 'email_room_type', 'market__name', 'reason')
    list_filter = ('reason', 'created_at', 'hotel', 'market')
    ordering = ('-created_at',)

@admin.register(EmailHotelMatch)
class EmailHotelMatchAdmin(admin.ModelAdmin):
    list_display = ('sender_email', 'hotel_display', 'match_count', 'confidence_score', 'last_matched_at')
    list_filter = ('hotel', 'confidence_score', 'match_count')
    search_fields = ('sender_email', 'hotel__juniper_hotel_name')
    readonly_fields = ('first_matched_at', 'last_matched_at', 'match_count')
    ordering = ('-match_count', '-confidence_score')
    
    def hotel_display(self, obj):
        if obj.hotel:
            return format_html('<a href="{}">{}</a>', 
                reverse('admin:hotels_hotel_change', args=[obj.hotel.id]),
                obj.hotel.juniper_hotel_name
            )
        return "-"
    hotel_display.short_description = 'Otel'

@admin.register(EmailBlockList)
class EmailBlockListAdmin(admin.ModelAdmin):
    list_display = ('sender_email', 'reason', 'is_active', 'blocked_by', 'blocked_at', 'original_email_link')
    list_filter = ('is_active', 'reason', 'blocked_at', 'blocked_by')
    search_fields = ('sender_email', 'reason')
    readonly_fields = ('blocked_at', 'last_updated')
    actions = ['activate_blocks', 'deactivate_blocks']
    
    def original_email_link(self, obj):
        if obj.original_email:
            return format_html('<a href="{}">{}</a>', 
                reverse('admin:emails_email_change', args=[obj.original_email.id]),
                f"E-posta #{obj.original_email.id}: {obj.original_email.subject[:30]}..."
            )
        return "-"
    original_email_link.short_description = 'Orijinal E-posta'
    
    def activate_blocks(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} blok aktifleştirildi.")
    activate_blocks.short_description = "Seçili blokları aktifleştir"
    
    def deactivate_blocks(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} blok devre dışı bırakıldı.")
    deactivate_blocks.short_description = "Seçili blokları devre dışı bırak"
