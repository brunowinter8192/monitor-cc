# INFRASTRUCTURE
import logging
import re
import select
import sys
import termios
import tty
from typing import Dict, Optional, Tuple

RESET = '\033[0m'
CYAN = '\033[96m'
BLUE = '\033[94m'
GREEN = '\033[92m'
PURPLE = '\033[38;5;135m'

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_click = logging.getLogger('click_handler')
click_handler = logging.FileHandler('src/logs/09_click_handling.log')
click_handler.setFormatter(log_format)
logger_click.addHandler(click_handler)
logger_click.setLevel(logging.INFO)

SGR_MOUSE_PATTERN = re.compile(rb'\x1b\[<(\d+);(\d+);(\d+)([Mm])')

_original_terminal_settings = None

# Tagged logging helper
def log_tagged(tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET}"
    logger_click.info(f"{colored_tag} {message}")

# ORCHESTRATOR
def setup_mouse_tracking() -> bool:
    success = enable_mouse_mode()
    if success:
        set_raw_stdin()
        log_tagged("SETUP", GREEN, "Mouse tracking enabled")
    return success

# FUNCTIONS

# Enables SGR mouse tracking mode
def enable_mouse_mode() -> bool:
    try:
        sys.stdout.write('\033[?1000h')
        sys.stdout.write('\033[?1006h')
        sys.stdout.flush()
        log_tagged("MOUSE_ON", CYAN, "Enabled mouse mode 1000h + 1006h")
        return True
    except Exception as e:
        log_tagged("MOUSE_ERR", PURPLE, f"Failed to enable mouse mode: {e}")
        return False

# Disables mouse tracking mode
def disable_mouse_mode() -> None:
    sys.stdout.write('\033[?1006l')
    sys.stdout.write('\033[?1000l')
    sys.stdout.flush()
    log_tagged("MOUSE_OFF", CYAN, "Disabled mouse mode")

# Sets stdin to raw mode for reading escape sequences
def set_raw_stdin() -> None:
    global _original_terminal_settings
    try:
        fd = sys.stdin.fileno()
        _original_terminal_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        log_tagged("RAW_STDIN", BLUE, "Set stdin to cbreak mode")
    except Exception as e:
        log_tagged("RAW_ERR", PURPLE, f"Failed to set raw stdin: {e}")

# Restores original terminal settings
def restore_terminal() -> None:
    global _original_terminal_settings
    if _original_terminal_settings is not None:
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_terminal_settings)
            log_tagged("RESTORE", BLUE, "Restored terminal settings")
        except Exception as e:
            log_tagged("RESTORE_ERR", PURPLE, f"Failed to restore terminal: {e}")
    disable_mouse_mode()

# Reads mouse event from stdin without blocking
def read_mouse_event() -> Optional[bytes]:
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            data = sys.stdin.buffer.read(32)
            if data:
                log_tagged("MOUSE_EVENT", CYAN, f"Received {len(data)} bytes")
                return data
        except Exception as e:
            log_tagged("READ_ERR", PURPLE, f"Error reading stdin: {e}")
    return None

# Parses SGR mouse escape sequence
def parse_sgr_mouse(data: bytes) -> Optional[Dict]:
    match = SGR_MOUSE_PATTERN.search(data)
    if not match:
        return None

    button = int(match.group(1))
    col = int(match.group(2))
    row = int(match.group(3))
    event_type = match.group(4)

    is_press = event_type == b'M'
    is_release = event_type == b'm'

    result = {
        'button': button,
        'col': col,
        'row': row,
        'is_press': is_press,
        'is_release': is_release
    }

    log_tagged("CLICK_PARSE", BLUE, f"Parsed: button={button}, col={col}, row={row}, press={is_press}")
    return result

# Checks if click is in toggle area (first few columns)
def is_toggle_click(col: int) -> bool:
    return col <= 4

# Processes click and returns agent_id to toggle
def process_click(click_data: Dict, line_to_agent: Dict[int, str]) -> Optional[str]:
    if not click_data.get('is_press'):
        return None

    if click_data.get('button') != 0:
        return None

    row = click_data.get('row', 0)
    col = click_data.get('col', 0)

    if not is_toggle_click(col):
        log_tagged("CLICK_SKIP", BLUE, f"Click at col={col} outside toggle area")
        return None

    agent_id = line_to_agent.get(row)
    if agent_id:
        log_tagged("TOGGLE_CLICK", GREEN, f"Toggle agent {agent_id} at row {row}")
    else:
        log_tagged("CLICK_MISS", BLUE, f"No agent at row {row}")

    return agent_id
