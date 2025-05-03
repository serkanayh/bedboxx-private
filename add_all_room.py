import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

# Import the models
from hotels.models import Hotel, Room

def add_all_rooms():
    # Counter for how many ALL rooms were added
    added_count = 0
    # Get all hotels
    hotels = Hotel.objects.all()
    
    for hotel in hotels:
        # Check if this hotel already has an 'ALL' room
        if not Room.objects.filter(hotel=hotel, room_code='ALL').exists():
            # Create ALL room for this hotel
            Room.objects.create(
                hotel=hotel,
                juniper_room_type='ALL',
                room_code='ALL'
            )
            print(f"Added ALL room for hotel: {hotel.juniper_hotel_name}")
            added_count += 1
        else:
            print(f"Hotel {hotel.juniper_hotel_name} already has ALL room")
    
    # Print summary 
    print(f"Total ALL rooms added: {added_count}")

if __name__ == "__main__":
    add_all_rooms() 