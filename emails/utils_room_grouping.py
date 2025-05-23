import re
from collections import defaultdict
from hotels.models import Room, RoomTypeGroup, RoomTypeVariant

def normalize_room_type_name(name: str) -> str:
    """
    Normalize a Juniper room type name to its 'master' group.
    Removes PAX info, SNG/DBL/TPL, parenthesis, and extra spaces.
    Example: "Sng Superior Side Sea View (1/1A+0/2ch)" -> "SUPERIOR SIDE SEA VIEW"
    """
    if not name:
        return ""
    name = name.upper().strip()
    # Remove parenthesis and their content
    name = re.sub(r'\([^)]*\)', '', name)
    # Remove SNG, DBL, TPL, QDL, 1/2 PAX, etc. at the start
    name = re.sub(r'^(SNG|DBL|TPL|QDL|TWIN|SINGLE|DOUBLE|TRIPLE|QUAD|QUADRUPLE|FAMILY|SUITE|\d+/\d+ PAX|\d+ PAX|\d+PAX)\s+', '', name)
    # Remove any remaining numbers or PAX info at the start
    name = re.sub(r'^(\d+\s*)+', '', name)
    # Remove any remaining PAX info at the start
    name = re.sub(r'(\d+/\d+[A-Z]*\+\d+/\d+[A-Z]*CH?)', '', name)
    name = re.sub(r'(\d+\s*PAX)', '', name)
    # Remove any remaining numbers or PAX info at the start
    name = re.sub(r'[\d\+]+', '', name)
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

def build_room_type_group_mapping(hotel_code: str):
    """
    Returns a mapping: {normalized_name: [Room objects]} for all room types of a hotel.
    """
    mapping = defaultdict(list)
    rooms = Room.objects.filter(hotel__juniper_code=hotel_code)
    for room in rooms:
        norm = normalize_room_type_name(room.juniper_room_type)
        mapping[norm].append(room)
    return mapping

def get_stop_sale_room_variants(hotel_code: str, incoming_room_type: str):
    """
    Given a hotel and an incoming room type (from STOP SALE), return all Room objects
    in the same normalized group.
    """
    mapping = build_room_type_group_mapping(hotel_code)
    norm = normalize_room_type_name(incoming_room_type)
    return mapping.get(norm, [])

def get_stop_sale_roomtype_variants(hotel_code: str, incoming_room_type: str):
    """
    Given a hotel and an incoming room type (from STOP SALE), return all RoomTypeVariant records
    in the same normalized group for that hotel.
    """
    norm = normalize_room_type_name(incoming_room_type)
    try:
        group = RoomTypeGroup.objects.get(name=norm)
    except RoomTypeGroup.DoesNotExist:
        return []
    # Only return variants for rooms in the given hotel
    return group.variants.filter(room__hotel__juniper_code=hotel_code).select_related('room') 