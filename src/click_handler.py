# INFRASTRUCTURE
import logging
import select
import sys
import termios
import tty
from typing import Dict, Optional

# From utils.py: Logging utility
from .utils import log_tagged
# From constants.py: Colors
from .constants import RESET, CYAN, BLUE, GREEN, PURPLE

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_input = logging.getLogger('input_handler')
input_handler = logging.FileHandler('src/logs/09_input_handling.log')
input_handler.setFormatter(log_format)
logger_input.addHandler(input_handler)
logger_input.setLevel(logging.INFO)

_original_terminal_settings = None

# ORCHESTRATOR
def setup_keyboard_input() -> bool:
    success = set_raw_stdin()
    if success:
        log_tagged(logger_input, "SETUP", GREEN, "Keyboard input enabled (digits 1-9 for toggle)")
    return success

# FUNCTIONS

# Sets stdin to raw mode for reading keypresses
def set_raw_stdin() -> bool:
    global _original_terminal_settings
    try:
        fd = sys.stdin.fileno()
        _original_terminal_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        log_tagged(logger_input, "RAW_STDIN", BLUE, "Set stdin to cbreak mode")
        return True
    except Exception as e:
        log_tagged(logger_input, "RAW_ERR", PURPLE, f"Failed to set raw stdin: {e}")
        return False

# Restores original terminal settings
def restore_terminal() -> None:
    global _original_terminal_settings
    if _original_terminal_settings is not None:
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_terminal_settings)
            log_tagged(logger_input, "RESTORE", BLUE, "Restored terminal settings")
        except Exception as e:
            log_tagged(logger_input, "RESTORE_ERR", PURPLE, f"Failed to restore terminal: {e}")

# Reads keypress from stdin without blocking
def read_keypress() -> Optional[str]:
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            char = sys.stdin.read(1)
            if char:
                log_tagged(logger_input, "KEYPRESS", CYAN, f"Received key: {repr(char)}")
                return char
        except Exception as e:
            log_tagged(logger_input, "READ_ERR", PURPLE, f"Error reading stdin: {e}")
    return None

# Returns subagent index (1-9) if digit pressed, None otherwise
def parse_digit_key(char: str) -> Optional[int]:
    if char and char in '123456789':
        index = int(char)
        log_tagged(logger_input, "DIGIT_KEY", GREEN, f"Digit key pressed: {index}")
        return index
    return None

# Gets agent_id by index from sorted metadata
def get_agent_by_index(index: int, subagent_metadata: Dict[str, dict]) -> Optional[str]:
    if not subagent_metadata:
        return None
    sorted_agents = sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp'])
    if 1 <= index <= len(sorted_agents):
        agent_id = sorted_agents[index - 1][0]
        log_tagged(logger_input, "AGENT_LOOKUP", BLUE, f"Index {index} -> agent {agent_id}")
        return agent_id
    log_tagged(logger_input, "INDEX_OOB", BLUE, f"Index {index} out of bounds (have {len(sorted_agents)} agents)")
    return None
