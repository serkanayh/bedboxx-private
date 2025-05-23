from hotels.models import Room, Hotel
from django.db.models import Count

def check_hotel_140():
    print("140 numaralı oteli kontrol ediyorum...")
    
    # Otel 140'ı bul
    hotel = Hotel.objects.filter(id=140).first()
    if not hotel:
        print("ID 140 olan otel bulunamadı!")
        
        # Veritabanındaki minimum ve maksimum hotel ID'lerini göster
        min_id = Hotel.objects.all().order_by('id').first()
        max_id = Hotel.objects.all().order_by('-id').first()
        if min_id and max_id:
            print(f"Veritabanındaki otel ID aralığı: {min_id.id} - {max_id.id}")
        return
    
    print(f"Otel: {hotel.id} - {hotel.juniper_hotel_name}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=140).order_by('id')
    print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    for room in rooms:
        print(f"  - ID: {room.id}, Oda Adı: {room.room_name}, Oda Tipi: {room.juniper_room_type}")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=140).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        print("\nTekrarlanan oda tipleri:")
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            count = duplicate['count']
            print(f"Oda Tipi: '{room_type}', Tekrar Sayısı: {count}")
            
            # Bu oda tipine ait tüm oda kayıtlarını göster
            rooms = Room.objects.filter(hotel_id=140, juniper_room_type=room_type).order_by('id')
            for room in rooms:
                print(f"  - ID: {room.id}, Oda Adı: {room.room_name}, Oda Tipi: {room.juniper_room_type}")

if __name__ == "__main__":
    check_hotel_140() 