#!/usr/bin/env python
"""
hotels_roomtypegrouplearning tablosundaki ilişkili kayıtları düzelten ve odaları silen betik.
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

def fix_dependent_records(juniper_code='140'):
    """Duplicate odaların ilişkili kayıtlarını hotels_roomtypegrouplearning tablosunda düzelt"""
    print(f"Juniper code {juniper_code} olan oteli kontrol ediyorum...")
    
    # Juniper code ile oteli bul
    hotel = Hotel.objects.filter(juniper_code=juniper_code).first()
    if not hotel:
        print(f"Juniper code {juniper_code} olan otel bulunamadı!")
        return False
    
    print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # hotels_roomtypegrouplearning tablosundaki sütunları bul
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(hotels_roomtypegrouplearning)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        print(f"\nhotels_roomtypegrouplearning tablosunun sütunları: {column_names}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"\nToplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        for duplicate in duplicates:
            room_type = duplicate['juniper_room_type']
            print(f"\n## Oda Tipi: '{room_type}' ##")
            
            # Bu oda tipine ait odaları bul
            rooms = Room.objects.filter(hotel_id=hotel.id, juniper_room_type=room_type).order_by('id')
            
            if rooms.count() > 1:
                keep_room = rooms.first()
                duplicate_rooms = list(rooms)[1:]
                
                print(f"Korunacak oda ID: {keep_room.id}")
                print(f"Silinecek oda ID'leri: {[r.id for r in duplicate_rooms]}")
                
                # Her bir duplicate oda için ilişkili kayıtları düzelt
                for dup_room in duplicate_rooms:
                    with connection.cursor() as cursor:
                        # İlişkili kayıtları bul - juniper_room_id veya room_id sütunlarını ara
                        for fk_col in ["juniper_room_id", "room_id"]:
                            if fk_col in column_names:
                                # İlişkili kayıtları sayısını kontrol et
                                cursor.execute(f"SELECT COUNT(*) FROM hotels_roomtypegrouplearning WHERE {fk_col} = %s", [dup_room.id])
                                related_count = cursor.fetchone()[0]
                                
                                if related_count > 0:
                                    print(f"  - {fk_col} sütununda {related_count} ilişkili kayıt bulundu")
                                    
                                    # Kaydın ilişkili kayıtlarını ana oda kaydına taşı
                                    cursor.execute(f"UPDATE hotels_roomtypegrouplearning SET {fk_col} = %s WHERE {fk_col} = %s", 
                                                  [keep_room.id, dup_room.id])
                                    print(f"  - {related_count} kayıt {keep_room.id} ID'li odaya taşındı")
                    
                    # Odayı silmeyi dene
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM hotels_room WHERE id = %s", [dup_room.id])
                            print(f"  - ID: {dup_room.id} başarıyla silindi")
                    except Exception as e:
                        print(f"  - ID: {dup_room.id} silinemedi: {str(e)}")
                        
                        # Debug: İlişkili kayıtları ekrana yazdır
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT * FROM hotels_roomtypegrouplearning WHERE juniper_room_id = %s OR room_id = %s", 
                                          [dup_room.id, dup_room.id])
                            related_records = cursor.fetchall()
                            if related_records:
                                print(f"    İlişkili kayıtlar: {related_records}")
        
        return True
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")
        return True

if __name__ == "__main__":
    juniper_code = '140'  # Varsayılan olarak 140 numaralı otele bakıyoruz
    
    # Eğer komut satırından bir argüman verilmişse, onu juniper_code olarak kullan
    if len(sys.argv) > 1:
        juniper_code = sys.argv[1]
    
    fix_dependent_records(juniper_code) 