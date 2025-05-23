from hotels.models import Room, Hotel
from django.db.models import Count
import sys

def clean_duplicates(hotel_id):
    try:
        hotel = Hotel.objects.filter(id=hotel_id).first()
        if not hotel:
            print(f'ID {hotel_id} olan otel bulunamadı!')
            return False
        
        print(f'Otel: {hotel.juniper_hotel_name}')
        
        duplicates = Room.objects.filter(hotel_id=hotel_id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
        print(f'Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu')
        
        total_deleted = 0
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            rooms = Room.objects.filter(hotel_id=hotel_id, juniper_room_type=room_type).order_by('id')
            
            if rooms.count() > 1:
                to_delete = list(rooms)[1:]
                to_delete_ids = [r.id for r in to_delete]
                deleted_count = len(to_delete_ids)
                
                # Her silinecek odanın ID'sini ve detaylarını görelim
                for room in to_delete:
                    print(f"  - Siliniyor: ID:{room.id}, Oda Tipi:{room.juniper_room_type}, Oda Adı:{room.room_name}")
                
                # Silme işlemi
                Room.objects.filter(id__in=to_delete_ids).delete()
                total_deleted += deleted_count
                print(f"  '{room_type}' tipindeki {deleted_count} adet fazlalık oda silindi")
                
        print(f"İşlem tamamlandı. Toplam {total_deleted} adet fazlalık oda silindi.")
        return True
    
    except Exception as e:
        print(f'Hata: {str(e)}')
        return False

if __name__ == "__main__":
    hotel_id = 140
    clean_duplicates(hotel_id) 