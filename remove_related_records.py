#!/usr/bin/env python
"""
İlişkili tabloları düzeltmeden önce, ilişkili kayıtları silen betik.
Bu betik silinecek odaların ilişkili kayıtlarını doğrudan siler.
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

def delete_related_records(juniper_code='140'):
    """Silinecek odaların ilişkili kayıtlarını sil"""
    print(f"Juniper code {juniper_code} olan oteli kontrol ediyorum...")
    
    # Juniper code ile oteli bul
    hotel = Hotel.objects.filter(juniper_code=juniper_code).first()
    if not hotel:
        print(f"Juniper code {juniper_code} olan otel bulunamadı!")
        return False
    
    print(f"Otel bulundu: ID: {hotel.id}, İsim: {hotel.juniper_hotel_name}, Juniper Code: {hotel.juniper_code}")
    
    # Room tablosuna referans veren foreign key'leri belirle
    fk_relations = [
        {'table': 'emails_emailrow_juniper_rooms', 'column': 'room_id'},
        {'table': 'emails_roomtypematch', 'column': 'juniper_room_id'},
        {'table': 'emails_emailcontractmatch_juniper_rooms', 'column': 'room_id'}
    ]
    
    # Bu oteldeki tüm odaları listele
    rooms = Room.objects.filter(hotel_id=hotel.id).order_by('juniper_room_type', 'id')
    print(f"Otelde toplam {rooms.count()} oda kaydı var")
    
    # Duplicate oda tiplerini bul
    duplicates = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1)
    print(f"Toplam {duplicates.count()} adet tekrarlanan oda tipi bulundu")
    
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
                
                # Her bir duplicate oda için işlem yap
                for dup_room in duplicate_rooms:
                    # Her bir foreign key ilişkisi için
                    for relation in fk_relations:
                        table_name = relation['table']
                        column_name = relation['column']
                        
                        try:
                            # İlişkili kayıtları kontrol et
                            with connection.cursor() as cursor:
                                cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = %s", [dup_room.id])
                                related_count = cursor.fetchone()[0]
                                
                                if related_count > 0:
                                    print(f"  - {table_name}.{column_name} sütununda {related_count} ilişkili kayıt bulundu")
                                    
                                    # İlişkili kayıtları sil
                                    cursor.execute(f"DELETE FROM {table_name} WHERE {column_name} = %s", [dup_room.id])
                                    print(f"  - {related_count} kayıt silindi")
                        except Exception as e:
                            print(f"  - {table_name}.{column_name} işlenirken hata: {str(e)}")
                    
                    # İlişkili kayıtlar silindikten sonra odayı silmeyi dene
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM hotels_room WHERE id = %s", [dup_room.id])
                            print(f"  - Oda ID: {dup_room.id} başarıyla silindi")
                    except Exception as e:
                        print(f"  - Oda ID: {dup_room.id} silinemedi: {str(e)}")
        
        # Tüm işlemler bittikten sonra kalan duplicate oda sayısını kontrol et
        duplicate_count_after = Room.objects.filter(hotel_id=hotel.id).values('juniper_room_type').annotate(count=Count('id')).filter(count__gt=1).count()
        if duplicate_count_after == 0:
            print("\nTüm duplicate odalar başarıyla temizlendi!")
        else:
            print(f"\nHala {duplicate_count_after} adet duplicate oda tipi kaldı.")
        
        return True
    else:
        print("\nBu otelde duplicate oda bulunmamaktadır.")
        return True

if __name__ == "__main__":
    juniper_code = '140'  # Varsayılan olarak 140 numaralı otele bakıyoruz
    
    # Eğer komut satırından bir argüman verilmişse, onu juniper_code olarak kullan
    if len(sys.argv) > 1:
        juniper_code = sys.argv[1]
    
    delete_related_records(juniper_code) 