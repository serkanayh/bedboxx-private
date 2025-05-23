from django import forms
from django.forms import inlineformset_factory
from .models import Hotel, Room, Market, JuniperContractMarket, RoomTypeGroup, RoomTypeVariant

class HotelForm(forms.ModelForm):
    """Hotel form with basic hotel information fields"""
    class Meta:
        model = Hotel
        fields = ['juniper_hotel_name', 'juniper_code']
        widgets = {
            'juniper_hotel_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Otel Adı'}),
            'juniper_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Otel Kodu'}),
        }

class RoomForm(forms.ModelForm):
    """Room form with room information fields"""
    group_name = forms.CharField(
        max_length=255, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Oda Grubu (ör: STANDARD, DELUXE)',
            'style': 'width: 100%; min-width: 300px;'  # Genişlik ayarı eklendi
        }),
        help_text="Oda tipinin ait olduğu grup (örn: STANDARD, DELUXE vb.)"
    )
    
    class Meta:
        model = Room
        fields = ['juniper_room_type', 'room_code', 'group_name']
        widgets = {
            'juniper_room_type': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Oda Tipi Adı',
                'style': 'width: 100%; min-width: 300px;'  # Genişlik ayarı eklendi
            }),
            'room_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Oda Kodu'}),
        }

class JuniperContractMarketForm(forms.ModelForm):
    """Contract-Market form for assigning markets to contracts"""
    markets = forms.ModelMultipleChoiceField(
        queryset=Market.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Bu kontrat için geçerli pazarları seçin"
    )
    
    class Meta:
        model = JuniperContractMarket
        fields = ['contract_name', 'season', 'access']
        widgets = {
            'contract_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kontrat Adı (örn: SUMMER 2025)'}),
            'season': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sezon Kodu (örn: S25)'}),
            'access': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['access'].initial = 'Allowed'

# Formset for adding multiple rooms to a hotel
RoomFormSet = inlineformset_factory(
    Hotel, 
    Room, 
    form=RoomForm, 
    extra=3,
    can_delete=True
)

# Custom formset for contract-markets (not directly linked to Hotel model)
ContractMarketFormSet = forms.formset_factory(
    JuniperContractMarketForm,
    extra=2,
    can_delete=True
) 