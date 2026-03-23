# INFRASTRUCTURE
from datetime import datetime

# From constants.py: Unified color palette
from .constants import RESET, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, ORANGE

# FUNCTIONS

# Convert ISO timestamp to HH:MM:SS local time
def format_timestamp(iso_timestamp: str) -> str:
    if not iso_timestamp:
        return '00:00:00'
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except ValueError:
        return '00:00:00'
