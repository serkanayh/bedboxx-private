from emails.models import Email
from emails.signals import auto_analyze_email

try:
    # Get the most recent email
    email = Email.objects.latest('id')
    print(f"Testing auto-analysis for email ID: {email.id}, Subject: {email.subject}")
    
    # Get the row count before analysis
    row_count_before = email.rows.count()
    print(f"Rows before analysis: {row_count_before}")
    
    # Manually trigger the signal function with created=True
    auto_analyze_email(sender=Email, instance=email, created=True)
    
    # Refresh from database and get updated row count
    email.refresh_from_db()
    row_count_after = email.rows.count()
    print(f"Rows after analysis: {row_count_after}")
    print(f"New rows created: {row_count_after - row_count_before}")
    
    # Display the rows if any were created
    if row_count_after > row_count_before:
        for row in email.rows.all():
            print(f"Row ID: {row.id}, Hotel: {row.hotel_name}, Room: {row.room_type}, Dates: {row.start_date} to {row.end_date}")
    else:
        print("No new rows were created by the analysis")
        
except Exception as e:
    print(f"Error: {e}") 