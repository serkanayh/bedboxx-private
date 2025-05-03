#!/usr/bin/env python
"""
A daemon script to check emails periodically
Run this script in the background to automatically check for new emails

Usage:
    python scripts/check_emails_daemon.py
"""
import os
import sys
import time
import logging
import traceback
import signal
import django
from logging.handlers import RotatingFileHandler

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stopsale_automation.settings')
django.setup()

from django.utils import timezone
from core.models import EmailConfiguration
from django.core.management import call_command

# Set up logging with rotation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(
            'email_checker.log',
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Signal handling
running = True

def signal_handler(sig, frame):
    global running
    logger.info("Received stop signal, shutting down...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main function to run the email checking daemon"""
    logger.info("Starting email checking daemon")
    
    try:
        while running:
            try:
                # Get configuration
                config = EmailConfiguration.objects.first()
                
                if not config:
                    logger.warning("No email configuration found")
                    time.sleep(60)  # Wait for a minute before checking again
                    continue
                
                if not config.is_active:
                    logger.info("Email checking is not active in configuration")
                    time.sleep(60)  # Wait for a minute before checking again
                    continue
                
                # Force the check interval to be 120 seconds (2 minutes) regardless of DB setting
                check_interval = 120  # FORCED to 2 minutes ignoring DB setting (config.imap_check_interval)
                
                if config.last_check:
                    now = timezone.now()
                    time_since_last_check = (now - config.last_check).total_seconds()
                    
                    if time_since_last_check < check_interval:
                        # Wait until it's time for the next check
                        wait_time = check_interval - time_since_last_check
                        logger.info(f"Waiting {wait_time:.1f} seconds until next check")
                        
                        # Sleep in small increments to allow for clean shutdown
                        while wait_time > 0 and running:
                            sleep_time = min(wait_time, 5)  # Sleep at most 5 seconds at a time
                            time.sleep(sleep_time)
                            wait_time -= sleep_time
                        
                        if not running:
                            break
                    
                # Run the check_emails command
                logger.info("Running email check")
                call_command('check_emails')
                
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                logger.error(traceback.format_exc())
                time.sleep(60)  # Wait a minute before retrying after an error
        
        logger.info("Email checking daemon stopped")
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 