# INFRASTRUCTURE
import os
import select
import subprocess
import sys
import termios
import tty
from typing import Any, Dict, Optional, Tuple

from src.pane_error_log import log_pane_error

_original_terminal_settings = None
_stdin_fd: int = -1

# ORCHESTRATOR
def setup_keyboard_input() -> bool:
    success = set_raw_stdin()
    return success

# FUNCTIONS

def set_raw_stdin() -> bool:
    global _original_terminal_settings, _stdin_fd
    _stdin_fd = sys.stdin.fileno()
    _original_terminal_settings = termios.tcgetattr(_stdin_fd)
    tty.setcbreak(_stdin_fd)
    return True

def restore_terminal() -> None:
    global _original_terminal_settings
    if _original_terminal_settings is not None:
        try:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_terminal_settings)
        except Exception:
            log_pane_error('input')

def wait_for_input(timeout: float) -> None:
    select.select([_stdin_fd], [], [], timeout)

def read_keypress() -> Optional[str]:
    if select.select([_stdin_fd], [], [], 0)[0]:
        data = os.read(_stdin_fd, 1)
        if not data:
            return None
        n_continuation = _utf8_continuation_count(data[0])
        for _ in range(n_continuation):
            if not select.select([_stdin_fd], [], [], 0.005)[0]:
                break
            more = os.read(_stdin_fd, 1)
            if not more:
                break
            data += more
        return data.decode('utf-8', errors='replace')
    return None

def _utf8_continuation_count(lead_byte: int) -> int:
    if lead_byte & 0x80 == 0x00:
        return 0
    if lead_byte & 0xE0 == 0xC0:
        return 1
    if lead_byte & 0xF0 == 0xE0:
        return 2
    if lead_byte & 0xF8 == 0xF0:
        return 3
    return 0

def parse_digit_key(char: str) -> Optional[int]:
    if char and char in '123456789':
        index = int(char)
        return index
    return None

def get_agent_by_index(index: int, subagent_metadata: Dict[str, dict]) -> Optional[str]:
    if not subagent_metadata:
        return None
    sorted_agents = sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp'])
    if 1 <= index <= len(sorted_agents):
        agent_id = sorted_agents[index - 1][0]
        return agent_id
    return None

def enable_mouse() -> None:
    sys.stdout.write('\033[?1003h\033[?1006h')
    sys.stdout.flush()

def disable_mouse() -> None:
    sys.stdout.write('\033[?1003l\033[?1006l')
    sys.stdout.flush()

def enable_mouse_clicks() -> None:
    sys.stdout.write('\033[?1000h\033[?1006h')
    sys.stdout.flush()

def disable_mouse_clicks() -> None:
    sys.stdout.write('\033[?1000l\033[?1006l')
    sys.stdout.flush()

def resolve_parent_key(line_map: Dict[int, Any], hover_row: Optional[int]) -> Any:
    if hover_row is None:
        return None
    for r in range(hover_row, 0, -1):
        k = line_map.get(r)
        if k is not None:
            return k
    return None

def copy_to_clipboard(text: str) -> None:
    subprocess.run(['pbcopy'], input=text, text=True, capture_output=True, check=True)

def read_mouse_event(first_char: str) -> Optional[Tuple[int, int, int]]:
    if first_char != '\033':
        return None

    seq = ''
    terminator = None

    for _ in range(32):
        ready = select.select([_stdin_fd], [], [], 0.005)[0]
        if not ready:
            return None
        data = os.read(_stdin_fd, 1)
        if not data:
            return None
        ch = data.decode('utf-8', errors='replace')
        if ch in ('M', 'm'):
            terminator = ch
            break
        seq += ch

    if terminator != 'M':
        return (-1, -1, -1) if terminator == 'm' else None

    if not seq.startswith('[<'):
        return None

    button, col, row = (int(part) for part in seq[2:].split(';'))
    return (button, col, row)
