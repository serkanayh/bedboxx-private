from hotels.models import Hotel

# Sistemdeki tüm otelleri göster
hotels = Hotel.objects.all().order_by('id')
print(f"Sistemde toplam {hotels.count()} otel var:")
for hotel in hotels:
    print(f"ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}") 