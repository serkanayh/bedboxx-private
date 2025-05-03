from rest_framework import serializers
from emails.models import Email, EmailAttachment, EmailRow
from hotels.models import Hotel, Room, Market
from users.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_active']


class HotelSerializer(serializers.ModelSerializer):
    room_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Hotel
        fields = ['id', 'juniper_hotel_name', 'juniper_code', 'room_count', 'created_at', 'updated_at']


class RoomSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.juniper_hotel_name', read_only=True)
    
    class Meta:
        model = Room
        fields = ['id', 'hotel', 'hotel_name', 'juniper_room_type', 'room_code', 'created_at', 'updated_at']


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ['id', 'name', 'juniper_code', 'is_active']


class EmailAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailAttachment
        fields = ['id', 'filename', 'content_type', 'size', 'file_url', 'created_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(f'/emails/attachment/{obj.id}/')
        return None


class EmailRowSerializer(serializers.ModelSerializer):
    juniper_hotel_name = serializers.CharField(source='juniper_hotel.juniper_hotel_name', read_only=True)
    juniper_room_type = serializers.CharField(source='juniper_room.juniper_room_type', read_only=True)
    juniper_markets_list = MarketSerializer(source='juniper_markets', many=True, read_only=True)
    processed_by_username = serializers.CharField(source='processed_by.username', read_only=True)
    status_display = serializers.CharField(read_only=True)
    sale_type_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = EmailRow
        fields = [
            'id', 'email', 'hotel_name', 'room_type', 'market', 'start_date', 'end_date', 
            'sale_type', 'status', 'juniper_hotel', 'juniper_hotel_name', 'juniper_room', 
            'juniper_room_type', 'juniper_markets', 'juniper_markets_list', 'ai_extracted', 
            'regex_extracted', 'manually_edited', 'processed_by', 'processed_by_username', 
            'processed_at', 'created_at', 'updated_at', 'status_display', 'sale_type_display'
        ]


class EmailSerializer(serializers.ModelSerializer):
    attachments = EmailAttachmentSerializer(many=True, read_only=True)
    rows = EmailRowSerializer(many=True, read_only=True)
    processed_by_username = serializers.CharField(source='processed_by.username', read_only=True)
    status_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Email
        fields = [
            'id', 'subject', 'sender', 'recipient', 'received_date', 'message_id', 
            'body_text', 'body_html', 'status', 'has_attachments', 'processed_by', 
            'processed_by_username', 'assigned_to', 'created_at', 'updated_at', 
            'attachments', 'rows', 'status_display'
        ]
