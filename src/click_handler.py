# INFRASTRUCTURE
import select
import sys
import termios
import tty
from typing import Dict, Optional

_original_terminal_settings = None

# ORCHESTRATOR
def setup_keyboard_input() -> bool:
    success = set_raw_stdin()
    return success

# FUNCTIONS

# Sets stdin to raw mode for reading keypresses
def set_raw_stdin() -> bool:
    global _original_terminal_settings
    try:
        fd = sys.stdin.fileno()
        _original_terminal_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return True
    except Exception:
        return False

# Restores original terminal settings
def restore_terminal() -> None:
    global _original_terminal_settings
    if _original_terminal_settings is not None:
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_terminal_settings)
        except Exception:
            pass

# Reads keypress from stdin without blocking
def read_keypress() -> Optional[str]:
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            char = sys.stdin.read(1)
            if char:
                return char
        except Exception:
            pass
    return None

# Returns subagent index (1-9) if digit pressed, None otherwise
def parse_digit_key(char: str) -> Optional[int]:
    if char and char in '123456789':
        index = int(char)
        return index
    return None

# Gets agent_id by index from sorted metadata
def get_agent_by_index(index: int, subagent_metadata: Dict[str, dict]) -> Optional[str]:
    if not subagent_metadata:
        return None
    sorted_agents = sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp'])
    if 1 <= index <= len(sorted_agents):
        agent_id = sorted_agents[index - 1][0]
        return agent_id
    return None
