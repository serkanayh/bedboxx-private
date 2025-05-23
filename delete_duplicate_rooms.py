#!/usr/bin/env python
"""
Duplicate odaları temizlemek için bağımsız bir script.
Doğrudan SQL sorgusu kullanarak ilişkili verileri koruyarak silme işlemi yapar.
"""

import os
import sys
import django
from django.db import connection

# Django ortamını kur
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

# Django modelleri artık kullanılabilir
from hotels.models import Room, Hotel
from django.db.models import Count

def delete_duplicates_with_sql(juniper_code='140'):
    """Doğrudan SQL kullanarak duplicate odaları sil"""
    print(f"Juniper code {juniper_code} olan oteli kontrol ediyorum...")
    
    # Juniper code ile oteli bul
    hotel = Hotel.objects.filter(juniper_code=juniper_code).first()
    if not hotel:
        print(f"Juniper code {juniper_code} olan otel bulunamadı!")
        return False
    
    print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"\nToplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        print("\nTekrarlanan oda tipleri:")
        deleted_count = 0
        
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            count = duplicate['count']
            print(f"\nOda Tipi: '{room_type}', Tekrar Sayısı: {count}")
            
            # Bu oda tipine ait tüm oda kayıtlarını göster
            rooms = Room.objects.filter(hotel_id=hotel.id, juniper_room_type=room_type).order_by('id')
            for room in rooms:
                print(f"  - ID: {room.id}, Oda Tipi: {room.juniper_room_type}")
            
            # İlk odayı koruyup diğerlerini sil
            if rooms.count() > 1:
                keep_id = rooms.first().id
                delete_ids = [r.id for r in rooms if r.id != keep_id]
                
                print(f"  Korunan oda ID: {keep_id}")
                print(f"  Silinecek odalar: {delete_ids}")
                
                # Doğrudan SQL ile silme işlemi
                with connection.cursor() as cursor:
                    for room_id in delete_ids:
                        cursor.execute("DELETE FROM hotels_room WHERE id = %s", [room_id])
                        deleted_count += 1
                        print(f"  - ID: {room_id} silindi")
        
        print(f"\nİşlem tamamlandı. Toplam {deleted_count} adet fazlalık oda silindi.")
        return True
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")
        return True

if __name__ == "__main__":
    juniper_code = '140'  # Varsayılan olarak 140 numaralı otele bakıyoruz
    
    # Eğer komut satırından bir argüman verilmişse, onu juniper_code olarak kullan
    if len(sys.argv) > 1:
        juniper_code = sys.argv[1]
    
    delete_duplicates_with_sql(juniper_code) 