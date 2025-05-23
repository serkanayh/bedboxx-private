from django.db import models

class Hotel(models.Model):
    """
    Model representing a hotel in the Juniper system
    """
    juniper_hotel_name = models.CharField(max_length=255)
    juniper_code = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.juniper_hotel_name} ({self.juniper_code})"
    
    class Meta:
        verbose_name = 'Hotel'
        verbose_name_plural = 'Hotels'
        ordering = ['juniper_hotel_name']
        
    @property
    def room_count(self):
        return self.rooms.count()


class Room(models.Model):
    """
    Model representing a room type in a hotel
    """
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='rooms')
    juniper_room_type = models.CharField(max_length=255)
    room_code = models.CharField(max_length=50)
    group_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.juniper_room_type} ({self.room_code}) - {self.hotel.juniper_hotel_name}"
    
    class Meta:
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'
        ordering = ['hotel__juniper_hotel_name', 'juniper_room_type']
        unique_together = ['hotel', 'room_code']


class Market(models.Model):
    """
    Market (Pazar) bilgilerini temsil eden model
    Örnek: İngiltere, Almanya, Rusya, vb.
    """
    name = models.CharField(max_length=100, unique=True)
    juniper_code = models.CharField(max_length=50, blank=True, null=True, help_text="Eski kodlar için (geriye dönük uyumluluk)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Market'
        verbose_name_plural = 'Markets'
        ordering = ['name']


class JuniperMarketCode(models.Model):
    """
    Juniper markete ait kodları temsil eden model
    Bir markete ait birden fazla Juniper kodu olabilir
    """
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='juniper_codes')
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.market.name} - {self.code}"

    class Meta:
        verbose_name = 'Juniper Market Code'
        verbose_name_plural = 'Juniper Market Codes'
        ordering = ['market__name', 'code']
        unique_together = ['market', 'code']


# === NEW MODELS START HERE ===

class JuniperContractMarket(models.Model):
    """
    Links a specific Hotel's Contract/Season to allowed Juniper Markets.
    Based on the provided Excel structure. Each row in Excel = one instance here.
    """
    ACCESS_CHOICES = [
        ('Allowed', 'Allowed'),
        ('Denied', 'Denied'),
    ]
    
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='contract_markets',
        help_text="The hotel this contract applies to."
    )
    market = models.ForeignKey(
        Market,
        on_delete=models.CASCADE,
        related_name='contracts',
        help_text="The specific Juniper Market included in this contract."
    )
    contract_name = models.CharField(
        max_length=255,
        help_text="Name of the allotment contract (e.g., 'Summer 2025 EURO')."
    )
    season = models.CharField(
        max_length=50,
        blank=True, # Allow blank season if applicable
        help_text="Season code (e.g., 'S25')."
    )
    access = models.CharField(
        max_length=10,
        choices=ACCESS_CHOICES,
        default='Allowed',
        help_text="Whether this market has access to this contract (Allowed/Denied)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hotel.juniper_code} - {self.contract_name} ({self.season}) -> {self.market.name}"

    class Meta:
        verbose_name = 'Juniper Contract Market'
        verbose_name_plural = 'Juniper Contract Markets'
        # Ensure a hotel+contract+season+market combination is unique
        unique_together = [['hotel', 'contract_name', 'season', 'market']]
        ordering = ['hotel__juniper_code', 'contract_name', 'season', 'market__name']


class MarketAlias(models.Model):
    """
    Maps various market names/terms found in emails to one or more canonical Market objects.
    e.g., "Avrupa Pazarı" -> {Market(name="Balkan Market"), Market(name="Baltic Market"), ...}
    """
    alias = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="The market name variation as found in emails (case-insensitive matching recommended during lookup)."
    )
    markets = models.ManyToManyField(
        Market,
        related_name='aliases',
        help_text="The canonical Juniper Market(s) this alias maps to."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        market_names = ", ".join([m.name for m in self.markets.all()])
        return f"'{self.alias}' -> [{market_names}]"

    class Meta:
        verbose_name = 'Market Alias'
        verbose_name_plural = 'Market Aliases'
        ordering = ['alias']


class RoomTypeGroup(models.Model):
    """
    Stores the master (normalized) room type name for grouping variants.
    Each hotel can have its own set of room type groups.
    """
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='room_type_groups', null=True, blank=True)
    name = models.CharField(max_length=255, db_index=True, help_text="Normalized group name like STANDARD, DELUXE, etc.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.hotel:
            return f"{self.name} ({self.hotel.juniper_code})"
        return self.name
    
    class Meta:
        unique_together = ('hotel', 'name')
        ordering = ['hotel__juniper_hotel_name', 'name']


class RoomTypeVariant(models.Model):
    """
    Maps a room group to actual Juniper room types for a specific hotel.
    Each variant represents a specific room type in Juniper system.
    """
    group = models.ForeignKey(RoomTypeGroup, on_delete=models.CASCADE, related_name='variants')
    variant_room_name = models.CharField(max_length=255, help_text="Specific Juniper room name/type that belongs to this group")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('group', 'variant_room_name')
        indexes = [models.Index(fields=['group'])]

    def __str__(self):
        return f"{self.variant_room_name} (Group: {self.group.name}, Hotel: {self.group.hotel.juniper_code if self.group.hotel else 'Unknown'})"


class RoomTypeGroupLearning(models.Model):
    """
    Stores learned mappings from email room type descriptions to standard room type groups.
    Used to automatically match room types in future emails.
    """
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='room_type_learnings')
    mail_room_type = models.CharField(max_length=255, help_text="Original room name as found in email")
    group = models.ForeignKey(RoomTypeGroup, on_delete=models.CASCADE, related_name='learnings', null=True)
    juniper_room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='learnings', null=True, blank=True)
    confidence = models.FloatField(default=0.8, help_text="Confidence score for this match (0.0-1.0)")
    frequency = models.IntegerField(default=1, help_text="How many times this mapping has been confirmed")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        unique_together = ('hotel', 'mail_room_type')
        ordering = ['-confidence', '-frequency']
        
    def __str__(self):
        group_name = self.group.name if self.group else "Unknown"
        return f"{self.mail_room_type} → {group_name} ({self.confidence:.2f})"


class HotelLearning(models.Model):
    """
    Stores learned mappings from hotel names in emails to actual Juniper hotels.
    Used to automatically match hotels in future emails.
    """
    mail_hotel_name = models.CharField(max_length=255, unique=True, help_text="Original hotel name as found in email")
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='name_learnings')
    confidence = models.FloatField(default=0.8, help_text="Confidence score for this match (0.0-1.0)")
    frequency = models.IntegerField(default=1, help_text="How many times this mapping has been confirmed")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        ordering = ['-confidence', '-frequency']
        
    def __str__(self):
        return f"{self.mail_hotel_name} → {self.hotel.juniper_hotel_name} ({self.confidence:.2f})"
    
    def increase_confidence(self):
        """
        Her onaylama işleminde güven puanını artır.
        Maksimum güven puanı 0.99'a sınırlandırılır.
        """
        # Frekansı artır
        self.frequency += 1
        
        # Güven puanını artır (üst sınır 0.99)
        new_confidence = self.confidence + ((1.0 - self.confidence) * 0.2)
        self.confidence = min(new_confidence, 0.99)
        
        self.save()


# === NEW MODELS END HERE ===
