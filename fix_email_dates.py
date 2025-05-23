#!/usr/bin/env python
"""
Script to fix email date filtering issues
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from emails.models import Email, EmailRow
from django.db.models import F

def find_problematic_rows():
    """
    Find all rows with start date matching email received date
    """
    print("Scanning for EmailRows with start_date matching email received_date...")
    rows = EmailRow.objects.filter(
        email__received_date__date=F('start_date'),
        ai_extracted=True
    )
    
    count = rows.count()
    print(f"Found {count} rows with start_date matching email received date")
    
    for row in rows:
        print(f"Row {row.id}: Email {row.email.id}, Start date: {row.start_date}, End date: {row.end_date}")
        print(f"  Email received: {row.email.received_date.date()}")
        print(f"  Hotel: {row.hotel_name}")
        print(f"  Room: {row.room_type}")
        print(f"  Sale type: {row.sale_type}")
        print("  ----")
    
    # Also check end dates
    end_date_rows = EmailRow.objects.filter(
        email__received_date__date=F('end_date'),
        ai_extracted=True
    ).exclude(
        email__received_date__date=F('start_date')
    )
    
    end_count = end_date_rows.count()
    print(f"Found {end_count} rows with end_date matching email received date (but not start_date)")
    
    for row in end_date_rows:
        print(f"Row {row.id}: Email {row.email.id}, Start date: {row.start_date}, End date: {row.end_date}")
        print(f"  Email received: {row.email.received_date.date()}")
        print(f"  Hotel: {row.hotel_name}")
        print(f"  Room: {row.room_type}")
        print(f"  Sale type: {row.sale_type}")
        print("  ----")
    
    return rows, end_date_rows

def fix_rows(rows, operation="skip"):
    """
    Fix problematic rows by either skipping or adjusting dates
    """
    if operation == "skip":
        print(f"Skipping {rows.count()} rows...")
        for row in rows:
            print(f"  Deleting row {row.id}")
            row.delete()
        print("Rows deleted.")
    else:  # adjust
        print(f"Adjusting dates for {rows.count()} rows...")
        for row in rows:
            old_start = row.start_date
            old_end = row.end_date
            
            # Adjust start date if it matches email date
            if row.start_date == row.email.received_date.date():
                row.start_date = row.start_date + timedelta(days=1)
            
            # Adjust end date if it matches email date or is now before start date
            if row.end_date == row.email.received_date.date() or row.end_date < row.start_date:
                row.end_date = row.start_date
            
            row.save()
            print(f"  Fixed Row {row.id}: {old_start} -> {row.start_date}, {old_end} -> {row.end_date}")
        print("Dates adjusted.")

def main():
    """Main function"""
    start_date_rows, end_date_rows = find_problematic_rows()
    
    if start_date_rows.count() == 0 and end_date_rows.count() == 0:
        print("No problematic rows found. Nothing to do.")
        return

    print("\nOptions:")
    print("1. Skip these rules (delete them)")
    print("2. Fix by adding one day to dates matching email receipt date")
    print("3. Exit without making changes")
    
    try:
        choice = input("Enter your choice (1-3): ")
        
        if choice == "1":
            fix_rows(start_date_rows, "skip")
            fix_rows(end_date_rows, "skip")
        elif choice == "2":
            fix_rows(start_date_rows, "adjust")
            fix_rows(end_date_rows, "adjust")
        else:
            print("No changes made.")
    except KeyboardInterrupt:
        print("\nOperation cancelled. No changes made.")
    
    print("Done!")

if __name__ == "__main__":
    main() 