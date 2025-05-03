from emails.models import Email

try:
    email = Email.objects.get(subject='Test Auto Analysis')
    print(f'Email ID: {email.id}')
    print(f'Email has rows: {email.rows.exists()}')
    print(f'Number of rows: {email.rows.count()}')
    
    rows = email.rows.all()
    for row in rows:
        print(f'Row: {row.id} - Hotel: {row.hotel_name}, Room: {row.room_type}')
except Email.DoesNotExist:
    print('Email not found')
except Exception as e:
    print(f'Error: {e}') 