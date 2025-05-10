#!/bin/bash

# Script to manage Celery workers and beat

case "$1" in
  start)
    echo "Starting Celery workers and beat..."
    celery -A stopsale_automation worker --loglevel=info --detach
    celery -A stopsale_automation beat --loglevel=info --detach
    ;;
  stop)
    echo "Stopping Celery workers and beat..."
    pkill -f 'celery worker'
    pkill -f 'celery beat'
    ;;
  restart)
    echo "Restarting Celery workers and beat..."
    $0 stop
    $0 start
    ;;
  status)
    echo "Checking status of Celery workers and beat..."
    pgrep -fl 'celery worker'
    pgrep -fl 'celery beat'
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac

exit 0