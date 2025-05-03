#!/bin/bash
# Script to backup the database automatically
# Recommended to run daily via cron job
# Add to crontab: 0 3 * * * /path/to/project/scripts/backup_cron.sh

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if using one (adjust path if needed)
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

# Change to project directory
cd "$PROJECT_DIR"

# Run the backup command
python manage.py backup_database --max-backups=10

# Log the backup
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "$TIMESTAMP - Database backup completed" >> "$PROJECT_DIR/backups/backup_log.txt" 