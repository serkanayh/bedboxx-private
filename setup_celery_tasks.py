#!/usr/bin/env python
"""
Script to set up periodic tasks for Celery Beat
Usage: python setup_celery_tasks.py
"""
import os
import django
import logging

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_email_check_task():
    """Set up periodic task to check emails every minute"""
    try:
        # Create or get interval schedule (every 1 minute)
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=1,
            period='minutes'
        )
        
        # Create or update periodic task
        task, created = PeriodicTask.objects.update_or_create(
            name='Check Emails Every Minute',
            defaults={
                'task': 'emails.tasks.check_emails_task',
                'interval': schedule,
                'enabled': True,
            }
        )
        
        if created:
            logger.info("Created new periodic task: Check Emails Every Minute")
        else:
            logger.info("Updated existing periodic task: Check Emails Every Minute")
            
        return True
        
    except Exception as e:
        logger.error(f"Error setting up periodic task: {e}")
        return False

if __name__ == '__main__':
    logger.info("Setting up Celery Beat periodic tasks...")
    
    # Set up email check task
    if setup_email_check_task():
        logger.info("Successfully set up email check task.")
    else:
        logger.error("Failed to set up email check task.")