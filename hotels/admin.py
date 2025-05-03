from django.contrib import admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from .models import Hotel, Room, Market, JuniperMarketCode, JuniperContractMarket, MarketAlias

class RoomInline(admin.TabularInline):
    model = Room
    extra = 1
    fields = ('juniper_room_type', 'room_code')

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('juniper_hotel_name', 'juniper_code', 'room_count')
    search_fields = ('juniper_hotel_name', 'juniper_code')
    list_filter = ('created_at',)
    ordering = ('juniper_hotel_name',)
    inlines = [RoomInline]

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
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
        fields = ('id', 'hotel', 'contract_name', 'season', 'market')
        # Exclude model fields not directly in the simple CSV structure
        # Use the declared fields (hotel, market) for lookup based on CSV columns
        export_order = ('id', 'hotel', 'contract_name', 'season', 'market')
        # Import using the combination of fields to avoid duplicates if data is re-imported
        import_id_fields = ('hotel', 'contract_name', 'season', 'market')
        skip_unchanged = True
        report_skipped = True

@admin.register(JuniperContractMarket)
class JuniperContractMarketAdmin(ImportExportModelAdmin):
    resource_class = JuniperContractMarketResource
    list_display = ('hotel', 'contract_name', 'season', 'market', 'updated_at')
    list_filter = ('hotel__juniper_code', 'market__name', 'season', 'updated_at')
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
