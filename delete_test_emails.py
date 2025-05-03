from emails.models import Email

try:
    # Find emails with the test subject
    test_emails = Email.objects.filter(subject='Test Auto Analysis')
    count = test_emails.count()
    
    if count > 0:
        # Delete the emails
        test_emails.delete()
        print(f"Successfully deleted {count} test email(s)")
    else:
        print("No test emails found")
        
except Exception as e:
    print(f"Error: {e}") 