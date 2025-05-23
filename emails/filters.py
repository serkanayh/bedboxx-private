from datetime import datetime, timedelta
from django.utils import timezone

def get_date_filter_params(pattern=None):
    """
    Generate date filter parameters based on pattern strings.
    This is especially useful for common date range patterns like 'last3days'.
    
    Args:
        pattern (str): Date filter pattern, e.g., 'last3days', 'last7days', 'thismonth', etc.
        
    Returns:
        tuple: (start_date, end_date) in 'YYYY-MM-DD' format suitable for URL parameters
    """
    today = timezone.now().date()
    
    if not pattern:
        return None, None
    
    # Last X days patterns
    if pattern == 'last3days':
        start_date = today - timedelta(days=3)
        end_date = today
    elif pattern == 'last7days':
        start_date = today - timedelta(days=7)
        end_date = today
    elif pattern == 'last14days':
        start_date = today - timedelta(days=14)
        end_date = today
    elif pattern == 'last30days':
        start_date = today - timedelta(days=30)
        end_date = today
    # This month pattern
    elif pattern == 'thismonth':
        start_date = today.replace(day=1)
        end_date = today
    # Last month pattern
    elif pattern == 'lastmonth':
        # Start with first day of current month
        first_day_current_month = today.replace(day=1)
        # Go back one day to get last day of previous month
        last_day_prev_month = first_day_current_month - timedelta(days=1)
        # First day of previous month
        start_date = last_day_prev_month.replace(day=1)
        # Last day is the last day we calculated
        end_date = last_day_prev_month
    # Custom date (format: YYYY-MM-DD)
    elif pattern.startswith('date:'):
        try:
            date_str = pattern.split(':', 1)[1]
            custom_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_date = custom_date
            end_date = custom_date
        except (ValueError, IndexError):
            return None, None
    # Custom range (format: YYYY-MM-DD:YYYY-MM-DD)
    elif pattern.startswith('range:'):
        try:
            range_str = pattern.split(':', 1)[1]
            start_str, end_str = range_str.split(':')
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except (ValueError, IndexError):
            return None, None
    # Unknown pattern
    else:
        return None, None
    
    # Format dates for URL parameters
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    return start_date_str, end_date_str 