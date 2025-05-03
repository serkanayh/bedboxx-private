from emails.models import EmailRow
from emails.views import match_juniper_entities

try:
    # Get recent email rows that don't have juniper hotel match
    unmatched_rows = EmailRow.objects.filter(juniper_hotel__isnull=True).order_by('-id')[:10]
    
    print(f"Found {unmatched_rows.count()} unmatched rows to process")
    
    # Process each row
    for row in unmatched_rows:
        print(f"\nProcessing row ID: {row.id}, Hotel: {row.hotel_name}, Room: {row.room_type}")
        
        # Apply the better matching algorithm
        updated_row = match_juniper_entities(row)
        
        # Check results
        if updated_row.juniper_hotel:
            print(f"✅ Successfully matched to hotel: {updated_row.juniper_hotel.juniper_hotel_name}")
            if updated_row.juniper_room:
                print(f"✅ Successfully matched to room: {updated_row.juniper_room.juniper_room_type}")
            else:
                print("❌ No room match found")
        else:
            print("❌ No hotel match found")
    
    print("\nMatching process complete!")
    
except Exception as e:
    print(f"Error: {e}") 