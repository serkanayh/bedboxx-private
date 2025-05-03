from emails.models import Email
from emails.signals import auto_analyze_email

try:
    # Get all pending emails that don't have rows yet
    emails_to_analyze = Email.objects.filter(status='pending')
    
    # Count emails without rows
    emails_without_rows = [email for email in emails_to_analyze if not email.rows.exists()]
    
    print(f"Found {len(emails_without_rows)} emails without analysis results")
    
    # Process each email
    for email in emails_without_rows:
        print(f"\nAnalyzing email ID: {email.id}, Subject: {email.subject}")
        
        # Manually trigger the signal function with created=True
        auto_analyze_email(sender=Email, instance=email, created=True)
        
        # Refresh from database and check results
        email.refresh_from_db()
        rows = email.rows.all()
        print(f"Analysis complete - {rows.count()} rows created")
        
        # Display the rows
        for row in rows:
            print(f"Row ID: {row.id}, Hotel: {row.hotel_name}, Room: {row.room_type}, Dates: {row.start_date} to {row.end_date}")
    
    print("\nAnalysis complete for all emails")
    
except Exception as e:
    print(f"Error: {e}") 