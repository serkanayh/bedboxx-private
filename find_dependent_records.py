#!/usr/bin/env python
"""
Duplicate odaların ilişkili kayıtlarını bulmak ve taşımak için script.
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

def find_and_fix_dependent_records(juniper_code='140'):
    """Duplicate odaların ilişkili kayıtlarını bul ve düzelt"""
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
    
    # ilişkili tabloları bul
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND 
            (sql LIKE '%REFERENCES hotels_room%' OR sql LIKE '%FOREIGN KEY%hotels_room%')
        """)
        related_tables = cursor.fetchall()
    
    print("\nOda tablosuna referans veren tablolar:")
    for table in related_tables:
        print(f"  - {table[0]}")
    
    # Duplicate odalar için işlem yap
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
                
                # Her bir ilişkili tablo için kontrol et
                for table_name in [t[0] for t in related_tables]:
                    for dup_room in duplicate_rooms:
                        # İlişkili kayıtları bul ve taşı veya sil
                        with connection.cursor() as cursor:
                            # İlişkili kayıtları bul
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = cursor.fetchall()
                            
                            # "room_id" veya "juniper_room_id" gibi muhtemel foreign key sütunlarını bul
                            fk_columns = []
                            for col in columns:
                                col_name = col[1].lower()
                                if 'room_id' in col_name or 'room' == col_name:
                                    fk_columns.append(col[1])
                            
                            if fk_columns:
                                print(f"\nTablo: {table_name}, Muhtemel FK sütunları: {fk_columns}")
                                
                                for fk_col in fk_columns:
                                    # İlişkili kayıtları sayısını kontrol et
                                    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {fk_col} = %s", [dup_room.id])
                                    related_count = cursor.fetchone()[0]
                                    
                                    if related_count > 0:
                                        print(f"  - {fk_col} sütununda {related_count} ilişkili kayıt bulundu")
                                        
                                        # Kaydın ilişkili kayıtlarını ana oda kaydına taşı
                                        cursor.execute(f"UPDATE {table_name} SET {fk_col} = %s WHERE {fk_col} = %s", 
                                                       [keep_room.id, dup_room.id])
                                        print(f"  - {related_count} kayıt {keep_room.id} ID'li odaya taşındı")
                
                # Tüm ilişkiler düzeltildikten sonra duplicate odaları silmeyi dene
                for dup_room in duplicate_rooms:
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM hotels_room WHERE id = %s", [dup_room.id])
                            print(f"  - ID: {dup_room.id} başarıyla silindi")
                    except Exception as e:
                        print(f"  - ID: {dup_room.id} silinemedi: {str(e)}")
        
        return True
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")
        return True

if __name__ == "__main__":
    juniper_code = '140'  # Varsayılan olarak 140 numaralı otele bakıyoruz
    
    # Eğer komut satırından bir argüman verilmişse, onu juniper_code olarak kullan
    if len(sys.argv) > 1:
        juniper_code = sys.argv[1]
    
    find_and_fix_dependent_records(juniper_code) 