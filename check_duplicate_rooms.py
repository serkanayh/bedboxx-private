from hotels.models import Room, Hotel
from django.db.models import Count

def list_all_duplicate_rooms():
    print("Sistemdeki tüm duplicate odaları listeliyorum...")
    
    # Duplicate odaları bul - hotel_id ve juniper_room_type kombinasyonuna göre grupla
    duplicates = Room.objects.values('hotel_id', 'juniper_room_type').annotate(count=Count('id')).filter(count__gt=1).order_by('hotel_id')
    
    print(f"Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu.")
    
    if duplicates.count() > 0:
        current_hotel_id = None
        total_duplicate_count = 0
        
        for duplicate in duplicates:
            hotel_id = duplicate['hotel_id']
            room_type = duplicate['juniper_room_type']
            count = duplicate['count']
            
            # Yeni bir otele geçtiğimizde otel bilgisini yazdır
            if current_hotel_id != hotel_id:
                if current_hotel_id is not None:
                    print("")  # Oteller arasında boşluk bırak
                
                current_hotel_id = hotel_id
                hotel = Hotel.objects.filter(id=hotel_id).first()
                hotel_name = hotel.juniper_hotel_name if hotel else f"Otel ID: {hotel_id} (Otel bulunamadı)"
                print(f"\n--- Otel ID: {hotel_id}, İsim: {hotel_name} ---")
            
            # Duplicate odaların detaylarını göster
            print(f"Oda Tipi: '{room_type}', Tekrar Sayısı: {count}")
            
            # Bu oda tipine ait tüm oda kayıtlarını göster
            rooms = Room.objects.filter(hotel_id=hotel_id, juniper_room_type=room_type).order_by('id')
            for room in rooms:
                print(f"  - ID: {room.id}, Oda Adı: {room.room_name}, Oda Tipi: {room.juniper_room_type}")
            
            total_duplicate_count += count - 1  # Her tip için fazla olan oda sayısı
        
        print(f"\nSilinebilecek toplam fazlalık oda sayısı: {total_duplicate_count}")

if __name__ == "__main__":
    list_all_duplicate_rooms() 