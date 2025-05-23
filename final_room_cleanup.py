#!/usr/bin/env python
"""
Duplicate odaları temizlemek için son ve en kapsamlı betik.
Tüm ilişkili tabloları tespit eder ve foreign key ilişkilerini düzeltir.
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

def find_all_foreign_keys_to_room():
    """Room tablosuna referans veren tüm foreign key ilişkilerini bul"""
    with connection.cursor() as cursor:
        # SQLite'da foreign key ilişkilerini bulmak için pragma foreign_key_list kullanılır
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'hotels_room'")
        tables = cursor.fetchall()
        
        foreign_keys = []
        
        # Her tabloyu kontrol et
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fks = cursor.fetchall()
            
            for fk in fks:
                if fk[2] == 'hotels_room':  # Referans verilen tablo hotels_room ise
                    foreign_keys.append({
                        'table': table_name,
                        'from_column': fk[3],
                        'to_table': fk[2],
                        'to_column': fk[4]
                    })
        
        return foreign_keys

def clean_duplicate_rooms(juniper_code='140'):
    """Duplicate odaları temizle - tüm foreign key ilişkilerini düzelterek"""
    print(f"Juniper code {juniper_code} olan oteli kontrol ediyorum...")
    
    # Juniper code ile oteli bul
    hotel = Hotel.objects.filter(juniper_code=juniper_code).first()
    if not hotel:
        print(f"Juniper code {juniper_code} olan otel bulunamadı!")
        return False
    
    print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # Hotels_room tablosuna referans veren foreign key'leri bul
    fk_relations = find_all_foreign_keys_to_room()
    print("\nRoom tablosuna referans veren foreign key ilişkileri:")
    for fk in fk_relations:
        print(f"  - Tablo: {fk['table']}, Sütun: {fk['from_column']}, -> {fk['to_table']}.{fk['to_column']}")
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    print(f"\nOtelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
    if duplicates.count() > 0:
        total_deleted = 0
        
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
                
                # Her bir duplicate oda için işlem yap
                for dup_room in duplicate_rooms:
                    # Her bir foreign key ilişkisi için
                    for fk in fk_relations:
                        table_name = fk['table']
                        column_name = fk['from_column']
                        
                        # İlişkili kayıtları kontrol et
                        with connection.cursor() as cursor:
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = %s", [dup_room.id])
                            related_count = cursor.fetchone()[0]
                            
                            if related_count > 0:
                                print(f"  - {table_name}.{column_name} sütununda {related_count} ilişkili kayıt bulundu")
                                
                                # İlişkili kayıtları korunacak odaya taşı
                                cursor.execute(f"UPDATE {table_name} SET {column_name} = %s WHERE {column_name} = %s", 
                                              [keep_room.id, dup_room.id])
                                print(f"  - {related_count} kayıt {keep_room.id} ID'li odaya taşındı")
                    
                    # İlişkiler düzeltildikten sonra odayı silmeyi dene
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM hotels_room WHERE id = %s", [dup_room.id])
                            total_deleted += 1
                            print(f"  - ID: {dup_room.id} başarıyla silindi")
                    except Exception as e:
                        print(f"  - ID: {dup_room.id} silinemedi: {str(e)}")
                        
                        # Debug: Hala kalan ilişkili kayıtları bul
                        for fk in fk_relations:
                            with connection.cursor() as cursor:
                                cursor.execute(f"SELECT COUNT(*) FROM {fk['table']} WHERE {fk['from_column']} = %s", [dup_room.id])
                                count = cursor.fetchone()[0]
                                if count > 0:
                                    print(f"    - Hala {fk['table']}.{fk['from_column']} üzerinde {count} kayıt var")
        
        print(f"\nİşlem tamamlandı. Toplam {total_deleted} adet fazlalık oda silindi.")
        return True
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")
        return True

if __name__ == "__main__":
    juniper_code = '140'  # Varsayılan olarak 140 numaralı otele bakıyoruz
    
    # Eğer komut satırından bir argüman verilmişse, onu juniper_code olarak kullan
    if len(sys.argv) > 1:
        juniper_code = sys.argv[1]
    
    clean_duplicate_rooms(juniper_code) 