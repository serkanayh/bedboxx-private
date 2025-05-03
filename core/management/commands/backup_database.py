import os
import sqlite3
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import DatabaseBackup

class Command(BaseCommand):
    help = 'Creates a backup of the SQLite database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-backups',
            type=int,
            default=10,
            help='Maximum number of automatic backups to keep (default: 10)',
        )

    def handle(self, *args, **options):
        try:
            max_backups = options['max_backups']
            
            # Create backup directory if it doesn't exist
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"db_backup_auto_{timestamp}.sqlite3"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Get path to the SQLite database
            db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
            
            # Create backup using SQLite's .backup command
            self.stdout.write(f"Creating backup: {backup_filename}")
            conn = sqlite3.connect(db_path)
            with conn:
                conn.execute(f"VACUUM INTO '{backup_path}'")
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            
            # Create backup record
            DatabaseBackup.objects.create(
                filename=backup_filename,
                backup_type='auto',
                size=file_size
            )
            
            self.stdout.write(self.style.SUCCESS(f"Database backup created: {backup_filename} ({file_size} bytes)"))
            
            # Clean up old automatic backups if needed
            auto_backups = DatabaseBackup.objects.filter(backup_type='auto').order_by('-created_at')
            if auto_backups.count() > max_backups:
                old_backups = auto_backups[max_backups:]
                for backup in old_backups:
                    old_backup_path = os.path.join(backup_dir, backup.filename)
                    if os.path.exists(old_backup_path):
                        os.remove(old_backup_path)
                    backup.delete()
                    self.stdout.write(f"Removed old backup: {backup.filename}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating backup: {str(e)}")) 