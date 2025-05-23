from hotels.models import Room, Hotel
from django.db.models import Count

def check_hotel(hotel_id=None):
    try:
        # Eğer hotel_id belirtilmemişse tüm otelleri göster
        if hotel_id is None:
            hotels = Hotel.objects.all().order_by('id')
            print(f"Sistemde toplam {hotels.count()} otel bulunuyor:")
            for hotel in hotels:
                print(f"ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}")
            return
        
        # Belirli bir oteli kontrol et
        hotel = Hotel.objects.filter(id=hotel_id).first()
        if not hotel:
            print(f'ID {hotel_id} olan otel bulunamadı!')
            return
        
        print(f'Otel: {hotel.id} - {hotel.juniper_hotel_name}')
        
        # Bu oteldeki oda tiplerini ve sayılarını göster
        rooms = Room.objects.filter(hotel_id=hotel_id)
        print(f'Otelde toplam {rooms.count()} oda kaydı var')
        
        # Duplicate oda tiplerini bul
        duplicates = Room.objects.filter(hotel_id=hotel_id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
        print(f'Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu')
        
        if duplicates.count() > 0:
            print("\nTekrarlanan oda tipleri:")
            for duplicate in duplicates:
                room_type = duplicate['juniper_room_type']
                count = duplicate['count']
                print(f"Oda Tipi: '{room_type}', Tekrar Sayısı: {count}")
                
                # Bu oda tipine ait tüm oda kayıtlarını göster
                rooms = Room.objects.filter(hotel_id=hotel_id, juniper_room_type=room_type).order_by('id')
                for room in rooms:
                    print(f"  - ID: {room.id}, Oda Adı: {room.room_name}, Oda Tipi: {room.juniper_room_type}")
    
    except Exception as e:
        print(f'Hata: {str(e)}')

if __name__ == "__main__":
    # Bütün otelleri listele
    check_hotel()
    
    # Specific oteli kontrol et
    # check_hotel(140) 