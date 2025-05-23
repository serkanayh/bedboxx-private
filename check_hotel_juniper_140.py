from hotels.models import Room, Hotel
from django.db.models import Count

def check_and_clean_hotel():
    print("Juniper code 140 olan oteli kontrol ediyorum...")
    
    # Juniper code 140 olan oteli bul
    hotel = Hotel.objects.filter(juniper_code='140').first()
    if not hotel:
        print("Juniper code 140 olan otel bulunamadı!")
        # Bazı otellerin juniper code'larını gösterelim
        sample_hotels = Hotel.objects.all()[:10]
        print("\nÖrnek oteller ve juniper kodları:")
        for h in sample_hotels:
            print(f"ID: {h.id}, İsim: {h.juniper_hotel_name}, Juniper Code: {h.juniper_code}")
        return
    
    print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"\nToplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        print("\nTekrarlanan oda tipleri:")
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            count = duplicate['count']
            print(f"\nOda Tipi: '{room_type}', Tekrar Sayısı: {count}")
            
            # Bu oda tipine ait tüm oda kayıtlarını göster
            rooms = Room.objects.filter(hotel_id=hotel.id, juniper_room_type=room_type).order_by('id')
            for room in rooms:
                print(f"  - ID: {room.id}, Oda Adı: {room.room_name}")
        
        # Silme işlemini başlat
        print("\n\nDuplicate odalar siliniyor...")
        total_deleted = 0
        
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            rooms = Room.objects.filter(hotel_id=hotel.id, juniper_room_type=room_type).order_by('id')
            
            if rooms.count() > 1:
                # İlk oda hariç diğerlerini sil
                to_delete = list(rooms)[1:]
                to_delete_ids = [r.id for r in to_delete]
                deleted_count = len(to_delete_ids)
                
                # Silme işlemi
                Room.objects.filter(id__in=to_delete_ids).delete()
                total_deleted += deleted_count
                print(f"'{room_type}' tipindeki {deleted_count} adet fazlalık oda silindi")
        
        print(f"\nİşlem tamamlandı. Toplam {total_deleted} adet fazlalık oda silindi.")
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")

if __name__ == "__main__":
    check_and_clean_hotel() 