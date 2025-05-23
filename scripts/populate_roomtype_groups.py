from hotels.models import Room, RoomTypeGroup, RoomTypeVariant
import re

def normalize_room_type_name(name: str) -> str:
    if not name:
        return ""
    name = name.upper().strip()
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'^(SNG|DBL|TPL|QDL|TWIN|SINGLE|DOUBLE|TRIPLE|QUAD|QUADRUPLE|FAMILY|SUITE|ROOM|\d+/\d+ PAX|\d+ PAX|\d+PAX)\s+', '', name)
    name = re.sub(r'^\d+\s*', '', name)
    name = re.sub(r'(\d+/\d+[A-Z]*\+\d+/\d+[A-Z]*CH?)', '', name)
    name = re.sub(r'(\d+\s*PAX)', '', name)
    name = re.sub(r'[\d\+]+', '', name)
    name = re.sub(r'\s+', ' ', name)
    # Remove 'ROOM' as a word anywhere
    words = [w for w in name.strip().split() if w != 'ROOM']
    # Sort words alphabetically for order-insensitive grouping
    words = sorted(words)
    return ' '.join(words)

def run():
    count_groups = 0
    count_variants = 0
    for room in Room.objects.all():
        norm = normalize_room_type_name(room.juniper_room_type)
        group, created = RoomTypeGroup.objects.get_or_create(name=norm)
        if created:
            count_groups += 1
        variant, created = RoomTypeVariant.objects.get_or_create(
            group=group,
            room=room,
            defaults={'original_name': room.juniper_room_type}
        )
        if created:
            count_variants += 1
    print(f"Created {count_groups} groups and {count_variants} variants.") 