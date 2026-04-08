# INFRASTRUCTURE
from typing import Dict, Set
import time

from .constants import YELLOW, RESET, POLL_INTERVAL

INDENT = '  '

warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}

# FUNCTIONS

# Track unknown JSONL message type for warnings pane
def track_unknown_type(unknown_entry: dict) -> None:
    global warned_unknown_types, unknown_type_counts
    msg_type = unknown_entry.get('type', '')
    if not msg_type:
        return
    count = unknown_entry.get('count', 1)
    unknown_type_counts[msg_type] = unknown_type_counts.get(msg_type, 0) + count

# Format unknown JSONL type warning for warnings pane
def format_unknown_type_warning(msg_type: str, count: int) -> str:
    return f"{INDENT}{YELLOW}[!] Unknown JSONL type: {msg_type} (seen {count}x){RESET}"

# Format warnings block for dedicated pane
def format_warnings_block() -> str:
    if not unknown_type_counts:
        return ''
    header = f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){RESET}"
    lines = [header]
    for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
        warning = format_unknown_type_warning(msg_type, count)
        lines.append(warning)
    return '\n'.join(lines)

# Load historical warnings from newest main session
def load_historical_warnings() -> None:
    from . import monitor as _monitor
    main_sessions = _monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _monitor.file_positions[filepath] = 0
        _monitor.tool_use_caches[filepath] = {}

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    from . import monitor as _monitor
    load_historical_warnings()
    last_output = None
    while True:
        _monitor.monitor_sessions()
        output = format_warnings_block()
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            if output:
                print(output)
            last_output = output
        time.sleep(POLL_INTERVAL)
