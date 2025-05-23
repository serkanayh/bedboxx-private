#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Django ayarlarını yükle
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from hotels.models import Room, RoomTypeGroup, RoomTypeVariant
from django.db.models import Q

def assign_room_groups():
    """
    Mevcut odaları oda gruplarına otomatik olarak eşleştir
    Bu script örnek olarak, oda tipine göre benzerlik kontrolü yapar
    """
    print("Oda grupları eşleştirilmeye başlıyor...")
    
    # Eşleşme sayacı
    matched_count = 0
    
    # Tüm odaları al
    rooms = Room.objects.all()
    print(f"{rooms.count()} oda bulundu")
    
    # Tüm oda gruplarını al
    groups = RoomTypeGroup.objects.all()
    print(f"{groups.count()} oda grubu tanımlı")
    
    # Tüm odaları dön
    for room in rooms:
        room_name = room.juniper_room_type.upper()
        
        # Grubu belirle
        matched_group = None
        
        # Önce tam eşleşmeye bak
        exact_variant = RoomTypeVariant.objects.filter(
            Q(original_name__iexact=room_name) | 
            Q(variant_room_name__iexact=room_name)
        ).first()
        
        if exact_variant:
            matched_group = exact_variant.group
        else:
            # Kısmi eşleşme
            for group in groups:
                group_name = group.name.upper()
                
                # Oda adında grup adı geçiyorsa
                if group_name in room_name:
                    matched_group = group
                    break
        
        # Eğer bir grup bulunduysa
        if matched_group:
            # Bir RoomTypeVariant kaydı oluştur
            variant, created = RoomTypeVariant.objects.get_or_create(
                room=room,
                defaults={
                    'group': matched_group,
                    'original_name': room.juniper_room_type
                }
            )
            
            if not created:
                # Zaten varsa grubu güncelle
                variant.group = matched_group
                variant.save()
            
            # Odanın group_name alanını güncelle
            room.group_name = matched_group.name
            room.save()
            
            matched_count += 1
            print(f"Eşleştirme: {room.juniper_room_type} -> {matched_group.name}")
    
    print(f"Toplam {matched_count}/{rooms.count()} oda gruplanmıştır.")

if __name__ == "__main__":
    assign_room_groups() 