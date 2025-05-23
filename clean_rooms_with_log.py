from hotels.models import Room, Hotel
from django.db.models import Count
import sys
import os

def check_and_clean_hotel(juniper_code='140'):
    # Log dosyasını aç
    log_file = open('room_cleanup.log', 'w')
    
    # print fonksiyonunu hem konsola hem de log dosyasına yazacak şekilde değiştir
    def log_print(*args, **kwargs):
        # Orijinal print ile konsola yaz
        print(*args, **kwargs)
        # Ayrıca log dosyasına yaz
        print(*args, **kwargs, file=log_file)
    
    log_print(f"Juniper code {juniper_code} olan oteli kontrol ediyorum...")
    
    # Juniper code 140 olan oteli bul
    hotel = Hotel.objects.filter(juniper_code=juniper_code).first()
    if not hotel:
        log_print(f"Juniper code {juniper_code} olan otel bulunamadı!")
        # Bazı otellerin juniper code'larını gösterelim
        sample_hotels = Hotel.objects.all()[:10]
        log_print("\nÖrnek oteller ve juniper kodları:")
        for h in sample_hotels:
            log_print(f"ID: {h.id}, İsim: {h.juniper_hotel_name}, Juniper Code: {h.juniper_code}")
        log_file.close()
        return
    
    log_print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    log_print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    log_print(f"\nToplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        log_print("\nTekrarlanan oda tipleri:")
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            count = duplicate['count']
            log_print(f"\nOda Tipi: '{room_type}', Tekrar Sayısı: {count}")
            
            # Bu oda tipine ait tüm oda kayıtlarını göster
            rooms = Room.objects.filter(hotel_id=hotel.id, juniper_room_type=room_type).order_by('id')
            for room in rooms:
                log_print(f"  - ID: {room.id}, Oda Adı: {room.room_name}")
        
        # Silme işlemini başlat
        log_print("\n\nDuplicate odalar siliniyor...")
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
                log_print(f"'{room_type}' tipindeki {deleted_count} adet fazlalık oda silindi")
        
        log_print(f"\nİşlem tamamlandı. Toplam {total_deleted} adet fazlalık oda silindi.")
    else:
        log_print("\nBu otelde duplicate oda bulunmamaktadır.")
    
    log_file.close()
    log_print(f"İşlem tamamlandı. Log dosyası: {os.path.abspath('room_cleanup.log')}")

if __name__ == "__main__":
    check_and_clean_hotel() 