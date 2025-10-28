from datetime import datetime, timedelta
import pandas as pd

def parse_source_date(date_str):
    """
    Parse the mixed format date string from LPBS
    Example: '10/1/2025 4:08:17 PM'
    """
    try:
        # Handle '01/10/2025 4:08:17 PM' format
        return pd.to_datetime(date_str, format='%m/%d/%Y %I:%M:%S %p')
    except:
        try:
            # Fallback for other formats
            return pd.to_datetime(date_str, errors='coerce')
        except:
            return None

def get_extraction_time_range():
    """
    Get time range for incremental extraction
    Morning run: yesterday 06:00 to today 06:00
    Afternoon run: today 06:00 to now
    """
    now = datetime.now()
    current_hour = now.hour
    
    if current_hour < 12:  # Morning run
        start_time = (now - timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    else:  # Afternoon run
        start_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
        end_time = now
    
    return start_time, end_time