#!/usr/bin/env python
import os
import sys
import django
from difflib import SequenceMatcher

# Django ortamını ayarla - settings modülü yolu düzeltildi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')

try:
    print(f"Django ayarları yükleniyor... ({os.environ['DJANGO_SETTINGS_MODULE']})")
    django.setup()
except Exception as e:
    print(f"Django setup hatası: {str(e)}")
    print("Bu betiği Django proje kök dizininde (manage.py ile aynı seviyede) çalıştırın.")
    sys.exit(1)

# Django modellerini import et
from emails.models import EmailRow
from hotels.models import Hotel, Room, RoomTypeGroup, RoomTypeVariant

def find_best_group_match(room_type, groups):
    """Verilen oda tipi için en iyi grup eşleşmesini bulan yardımcı fonksiyon"""
    best_match = None
    best_score = 0
    
    clean_room_type = room_type.strip().upper()
    
    for group in groups:
        # Tam eşleşme kontrolü
        if group.name.upper() == clean_room_type:
            return group, 1.0  # Tam eşleşme, skor 1.0
        
        # Bulanık eşleşme
        score = SequenceMatcher(None, clean_room_type, group.name.upper()).ratio()
        
        # Kelime içerme kontrolü (ilave puan)
        if clean_room_type in group.name.upper() or group.name.upper() in clean_room_type:
            score += 0.2
            
        if score > best_score:
            best_score = score
            best_match = group
    
    return best_match, best_score

try:
    print("TÜM ODA TIPLERINI GRUPLAMA BAŞLADI")
    # Juniper otelle eşleşmiş ve henüz onaylanmamış bütün satırları bul
    all_rows = EmailRow.objects.filter(
        juniper_hotel__isnull=False, 
        status__in=['pending', 'matching']
    ).order_by('-id')
    
    print(f"Toplam {all_rows.count()} işlenecek satır bulundu.")
    
    fixed_count = 0
    skipped_count = 0
    
    for row in all_rows:
        print(f"\nRow ID: {row.id}, Hotel: {row.hotel_name}, Room Type: {row.room_type}")
        
        if not row.room_type or row.room_type.strip() == '':
            print(f"  Bu satırda oda tipi yok, atlanıyor.")
            skipped_count += 1
            continue
            
        # ALL ROOM tiplerini atla
        if row.room_type.strip().upper() in ["ALL ROOM", "ALL ROOMS", "ALL ROOM TYPES", "TÜM ODALAR"]:
            print(f"  Bu satır 'ALL ROOM' tipi içeriyor, atlanıyor.")
            skipped_count += 1
            continue
            
        hotel = row.juniper_hotel
        print(f"  Juniper Hotel: {hotel.juniper_hotel_name}")
        
        # Oda tipini temizle
        clean_room_type = row.room_type.strip().upper()
        
        # 1. Otele ait tüm oda gruplarını al
        hotel_groups = RoomTypeGroup.objects.filter(hotel=hotel)
        if not hotel_groups.exists():
            print(f"  Bu otel için hiç oda grubu tanımlanmamış, atlanıyor.")
            skipped_count += 1
            continue
        
        # 2. En iyi grup eşleşmesini bul
        best_group, group_score = find_best_group_match(clean_room_type, hotel_groups)
        
        # Eğer iyi bir grup eşleşmesi yoksa atla
        if not best_group or group_score < 0.6:  # 0.6 eşik değeri
            print(f"  Bu oda tipi için uygun grup bulunamadı (En yüksek skor: {group_score:.2f})")
            skipped_count += 1
            continue
            
        print(f"  Oda grubu bulundu: {best_group.name} (Eşleşme skoru: {group_score:.2f})")
        
        # 3. Gruptaki varyantları al
        variants = best_group.variants.all()
        if not variants.exists():
            print(f"  Bu grupta hiç varyant tanımlanmamış, atlanıyor.")
            skipped_count += 1
            continue
            
        print(f"  Varyantlar ({variants.count()}):")
        
        # 4. Bu varyantlara sahip odaları bul
        all_variant_rooms = []
        for variant in variants:
            print(f"    - Variant: {variant.variant_room_name}")
            variant_rooms = Room.objects.filter(
                hotel=hotel, 
                juniper_room_type__icontains=variant.variant_room_name
            )
            if variant_rooms.exists():
                print(f"      - Rooms: {[r.juniper_room_type for r in variant_rooms]}")
                all_variant_rooms.extend(variant_rooms)
            else:
                print(f"      - Bu varyant için oda bulunamadı!")
        
        # 5. Eğer hiç oda bulunamadıysa atla
        if not all_variant_rooms:
            print(f"  Bu grup için hiç oda bulunamadı, atlanıyor.")
            skipped_count += 1
            continue
        
        # 6. Tekrarlanan odaları kaldır
        unique_rooms = list(set(all_variant_rooms))
        print(f"  Toplam eşşiz oda sayısı: {len(unique_rooms)}")
        
        # 7. Önceki oda sayısını kontrol et
        previous_rooms = row.juniper_rooms.all()
        print(f"  Önceki oda sayısı: {previous_rooms.count()}")
        
        # 8. Eğer zaten birden fazla oda eşleşmişse ve sayı aynıysa atla
        if previous_rooms.count() >= len(unique_rooms):
            print(f"  Bu satır için zaten {previous_rooms.count()} oda eşleşmiş, güncellemeye gerek yok.")
            skipped_count += 1
            continue
        
        # 9. Yeni odaları ekle
        row.juniper_rooms.set(unique_rooms)
        
        # 10. Sonucu kontrol et
        updated_rooms = row.juniper_rooms.all()
        print(f"  Güncellenen oda sayısı: {updated_rooms.count()}")
        print(f"  Güncellenen odalar: {[r.juniper_room_type for r in updated_rooms]}")
        
        fixed_count += 1
    
    print(f"\nÇALIŞMA BAŞARILI! Toplam {fixed_count} satır güncellendi, {skipped_count} satır atlandı.")
    
except Exception as e:
    print(f"GENEL HATA: {str(e)}") 