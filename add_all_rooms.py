import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from hotels.models import Hotel, Room

def add_all_rooms():
    count = 0
    for hotel in Hotel.objects.all():
        # Eğer bu otel için zaten "All Rooms" varsa atla
        if not Room.objects.filter(hotel=hotel, juniper_room_type='All Rooms').exists():
            Room.objects.create(
                hotel=hotel,
                juniper_room_type='All Rooms',
                room_code='ALL'
            )
            count += 1
    return count

if __name__ == '__main__':
    count = add_all_rooms()
    print(f'{count} otele "All Rooms" oda tipi eklendi.') 