from django.contrib import admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from .models import Hotel, Room, Market, JuniperMarketCode, JuniperContractMarket, MarketAlias, RoomTypeGroup, RoomTypeVariant, RoomTypeGroupLearning, HotelLearning
from django.urls import path
from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1
    fields = ('juniper_room_type', 'room_code')

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('juniper_code', 'juniper_hotel_name')

@admin.register(RoomTypeGroupLearning)
class RoomTypeGroupLearningAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'mail_room_type', 'group', 'juniper_room', 'confidence', 'frequency')
    list_filter = ('hotel', 'confidence')
    search_fields = ('mail_room_type', 'group__name')
    raw_id_fields = ('hotel', 'group', 'juniper_room')

@admin.register(HotelLearning)
class HotelLearningAdmin(admin.ModelAdmin):
    list_display = ('mail_hotel_name', 'hotel', 'confidence', 'frequency', 'updated_at')
    list_filter = ('confidence',)
    search_fields = ('mail_hotel_name', 'hotel__juniper_hotel_name')
    raw_id_fields = ('hotel',)

class RoomResource(resources.ModelResource):
    hotel = fields.Field(
        column_name='hotel_id',
        attribute='hotel',
        widget=ForeignKeyWidget(Hotel, 'id')
    )
    hotel_juniper = fields.Field(
        column_name='hotel_juniper_code',
        attribute='hotel',
        widget=ForeignKeyWidget(Hotel, 'juniper_code')
    )

    class Meta:
        model = Room
        fields = ('id', 'juniper_room_type', 'room_code', 'hotel', 'hotel_juniper')
        export_order = ('id', 'juniper_room_type', 'room_code', 'hotel_id', 'hotel_juniper_code')
        import_id_fields = ('juniper_room_type', 'hotel_juniper')
        skip_unchanged = True
        report_skipped = True

@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin):
    resource_class = RoomResource
    list_display = ('juniper_room_type', 'room_code', 'hotel')
    search_fields = ('juniper_room_type', 'room_code', 'hotel__juniper_hotel_name')
    list_filter = ('hotel', 'created_at')
    ordering = ('hotel__juniper_hotel_name', 'juniper_room_type')

class JuniperMarketCodeInline(admin.TabularInline):
    model = JuniperMarketCode
    extra = 1
    fields = ('code', 'description', 'is_active')

class MarketResource(resources.ModelResource):
    class Meta:
        model = Market
        fields = ('id', 'name', 'juniper_code', 'is_active')
        import_id_fields = ('name',)
        skip_unchanged = True
        report_skipped = True

@admin.register(Market)
class MarketAdmin(ImportExportModelAdmin):
    resource_class = MarketResource
    list_display = ('name', 'juniper_code', 'is_active', 'juniper_code_count')
    search_fields = ('name', 'juniper_code')
    list_filter = ('is_active', 'created_at')
    ordering = ('name',)
    inlines = [JuniperMarketCodeInline]

    def juniper_code_count(self, obj):
        return obj.juniper_codes.count()
    juniper_code_count.short_description = 'Juniper Kod Sayısı'

@admin.register(JuniperMarketCode)
class JuniperMarketCodeAdmin(admin.ModelAdmin):
    list_display = ('market', 'code', 'description', 'is_active')
    search_fields = ('market__name', 'code', 'description')
    list_filter = ('market', 'is_active', 'created_at')
    ordering = ('market__name', 'code')

# Resource for JuniperContractMarket
class JuniperContractMarketResource(resources.ModelResource):
    # Define ForeignKey widgets to look up related objects using specific fields from CSV
    hotel = fields.Field(
        column_name='hotel_code', # CSV column header
        attribute='hotel',       # Model field name
        widget=ForeignKeyWidget(Hotel, 'juniper_code') # Lookup Hotel by juniper_code
    )
    market = fields.Field(
        column_name='market_name', # CSV column header
        attribute='market',       # Model field name
        widget=ForeignKeyWidget(Market, 'name') # Lookup Market by name
    )

    class Meta:
        model = JuniperContractMarket
        # Specify fields to include in import/export (match CSV headers + model fields)
        fields = ('id', 'hotel', 'contract_name', 'season', 'market', 'access')
        # Exclude model fields not directly in the simple CSV structure
        # Use the declared fields (hotel, market) for lookup based on CSV columns
        export_order = ('id', 'hotel', 'contract_name', 'season', 'market', 'access')
        # Import using the combination of fields to avoid duplicates if data is re-imported
        import_id_fields = ('hotel', 'contract_name', 'season', 'market')
        skip_unchanged = True
        report_skipped = True

@admin.register(JuniperContractMarket)
class JuniperContractMarketAdmin(ImportExportModelAdmin):
    resource_class = JuniperContractMarketResource
    list_display = ('hotel', 'contract_name', 'season', 'market', 'access', 'updated_at')
    list_filter = ('hotel__juniper_code', 'market__name', 'season', 'access', 'updated_at')
    search_fields = ('hotel__juniper_code', 'hotel__juniper_hotel_name', 'contract_name', 'market__name')
    # Make foreign key fields searchable in raw id fields popup
    raw_id_fields = ('hotel', 'market')
    ordering = ('hotel__juniper_code', 'contract_name', 'season')

# Simple admin for MarketAlias for now
@admin.register(MarketAlias)
class MarketAliasAdmin(admin.ModelAdmin):
    list_display = ('alias', 'display_markets', 'created_at')
    search_fields = ('alias', 'markets__name')
    list_filter = ('markets',)
    filter_horizontal = ('markets',)
    ordering = ('alias',)

    def display_markets(self, obj):
        return ", ".join([market.name for market in obj.markets.all()[:5]])
    display_markets.short_description = 'Associated Markets'

class RoomTypeGroupResource(resources.ModelResource):
    hotel = fields.Field(
        column_name='hotel_code',
        attribute='hotel',
        widget=ForeignKeyWidget(Hotel, 'juniper_code')
    )
    
    class Meta:
        model = RoomTypeGroup
        fields = ('id', 'hotel', 'name')
        import_id_fields = ('hotel', 'name')
        skip_unchanged = True
        report_skipped = True

class RoomTypeVariantResource(resources.ModelResource):
    """
    Basitleştirilmiş import/export resource.
    """
    # CSV'den alınan veriler
    hotel_juniper_code = fields.Field(
        column_name='hotel_juniper_code',
        attribute=None,
        readonly=True
    )
    
    group_name = fields.Field(
        column_name='group_name',
        attribute=None,
        readonly=True
    )
    
    def before_import_row(self, row, **kwargs):
        """
        CSV satırı import edilmeden önce
        """
        try:
            from hotels.models import Hotel, RoomTypeGroup
            
            # Otel kodu ve grup adıyla RoomTypeGroup nesnesini bul
            hotel_code = row.get('hotel_juniper_code', '')
            group_name = row.get('group_name', '')
            
            if hotel_code and group_name:
                hotel = Hotel.objects.filter(juniper_code=hotel_code).first()
                if hotel:
                    group = RoomTypeGroup.objects.filter(hotel=hotel, name=group_name).first()
                    if group:
                        row['group'] = group.id
        except Exception as e:
            print(f"Import hatası: {e}")
            
        return row
    
    def get_instance(self, instance_loader, row):
        """
        Hem grup_id hem de variant_room_name kullanarak
        benzersiz bir şekilde mevcut kayıt bul
        """
        try:
            from hotels.models import RoomTypeVariant
            
            if 'group' in row and row['group'] and 'variant_room_name' in row:
                group_id = row['group']
                variant_name = row['variant_room_name']
                
                # Tam olarak bu grup ve variant_room_name kombinasyonuna sahip tek bir kayıt ara
                try:
                    variant = RoomTypeVariant.objects.get(
                        group_id=group_id,
                        variant_room_name=variant_name
                    )
                    return variant
                except (RoomTypeVariant.DoesNotExist, RoomTypeVariant.MultipleObjectsReturned):
                    # Bir kayıt bulunamadı veya birden fazla kayıt varsa, yeni kayıt oluştur
                    return None
        except Exception as e:
            print(f"get_instance hatası: {e}")
            
        return None
    
    def skip_row(self, instance, original, row, import_validation_errors=None):
        """
        Group alanı ayarlanmamışsa satırı atla
        """
        if not row.get('group'):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)
    
    def dehydrate_hotel_juniper_code(self, obj):
        """
        Export sırasında otel kodunu göster
        """
        if obj.group and obj.group.hotel:
            return obj.group.hotel.juniper_code
        return ""
    
    def dehydrate_group_name(self, obj):
        """
        Export sırasında grup adını göster
        """
        if obj.group:
            return obj.group.name
        return ""

    class Meta:
        model = RoomTypeVariant
        fields = ('id', 'group', 'variant_room_name', 'hotel_juniper_code', 'group_name')
        export_order = ('id', 'hotel_juniper_code', 'group_name', 'variant_room_name')
        import_id_fields = ('variant_room_name',)
        skip_unchanged = True
        report_skipped = False

@admin.register(RoomTypeGroup)
class RoomTypeGroupAdmin(ImportExportModelAdmin):
    resource_class = RoomTypeGroupResource
    list_display = ('name', 'hotel', 'created_at', 'updated_at')
    search_fields = ('name', 'hotel__juniper_hotel_name', 'hotel__juniper_code')
    list_filter = ('hotel',)
    raw_id_fields = ('hotel',)
    ordering = ('hotel__juniper_hotel_name', 'name')

@admin.register(RoomTypeVariant)
class RoomTypeVariantAdmin(ImportExportModelAdmin):
    resource_class = RoomTypeVariantResource
    list_display = ('variant_room_name', 'group', 'hotel_code')
    search_fields = ('variant_room_name', 'group__name', 'group__hotel__juniper_code')
    list_filter = ('group__hotel', 'group')
    
    def hotel_code(self, obj):
        return obj.group.hotel.juniper_code if obj.group.hotel else "-"
    hotel_code.short_description = "Hotel Code"

# Otel Portal linkini eklemek için AdminSite sınıfını genişletelim
admin.site.index_template = 'admin/custom_index.html'

# Otel portal kısayolunu admin sayfasına eklemek için model admin içine de koyabiliriz
class HotelPortalAdmin(admin.ModelAdmin):
    model = Hotel
    list_display = ('juniper_code', 'juniper_hotel_name', 'get_portal_link')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('portal/create/', self.admin_site.admin_view(self.hotel_portal_view), name='hotel_portal_create'),
            path('portal/edit/<int:hotel_id>/', self.admin_site.admin_view(self.hotel_portal_edit_view), name='hotel_portal_edit'),
        ]
        return custom_urls + urls
    
    def hotel_portal_view(self, request):
        # Bu fonksiyon hotels.views.hotel_portal_create view'ına yönlendirecek
        from hotels.views import hotel_portal_create
        return hotel_portal_create(request)
    
    def hotel_portal_edit_view(self, request, hotel_id):
        # Bu fonksiyon hotels.views.hotel_portal_edit view'ına yönlendirecek
        from hotels.views import hotel_portal_edit
        return hotel_portal_edit(request, hotel_id)
    
    def get_portal_link(self, obj):
        """Her otel için portalda düzenleme linki ekle"""
        url = reverse('admin:hotel_portal_edit', args=[obj.id])
        return format_html('<a href="{}">Portal Düzenle</a>', url)
    get_portal_link.short_description = 'Otel Portal'
    
    def changelist_view(self, request, extra_context=None):
        """Hotel listesi görünümüne portal linkini ekle"""
        extra_context = extra_context or {}
        extra_context['hotel_portal_url'] = reverse('admin:hotel_portal_create')
        return super().changelist_view(request, extra_context=extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Otel detay sayfasına portal düzenleme linkini ekle"""
        extra_context = extra_context or {}
        extra_context['portal_edit_url'] = reverse('admin:hotel_portal_edit', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

# Mevcut HotelAdmin sınıfının yerine yeni sınıfı koy
admin.site.unregister(Hotel)
admin.site.register(Hotel, HotelPortalAdmin)
