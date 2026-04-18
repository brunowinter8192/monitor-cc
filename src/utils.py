# INFRASTRUCTURE
from datetime import datetime
import re

# From constants.py: Unified color palette
from .constants import RESET, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, ORANGE

_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')

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

# Return number of terminal rows a logical line occupies after visual wrap
def visual_line_count(line: str, pane_width: int) -> int:
    visible = _ANSI_ESCAPE_RE.sub('', line)
    if not visible:
        return 1
    return max(1, (len(visible) + pane_width - 1) // pane_width)
