# INFRASTRUCTURE
import os
import time

from src.colors import RESET, DIM, YELLOW, RED
from src.news_pane.log_parser import (
    find_log_file, find_current_run_lines, filter_events, parse_line,
)
from src.pane_error_log import log_pane_error

LOG_POLL_INTERVAL = 0.5
MAX_LOG_LINES     = 40

# ORCHESTRATOR

def run_news_log_loop() -> None:
    loop_state = {'last_output': None}
    _loop_forever(loop_state)

# FUNCTIONS

def _loop_forever(loop_state: dict) -> None:
    while True:
        _run_iteration_guarded(loop_state)

def _run_iteration_guarded(loop_state: dict) -> None:
    try:
        _run_iteration(loop_state)
    except Exception:
        log_pane_error('news_log')
        time.sleep(LOG_POLL_INTERVAL)

def _run_iteration(loop_state: dict) -> None:
    term = os.get_terminal_size()
    pane_width  = term.columns
    pane_height = term.lines - 1
    log_path = find_log_file()
    events = _load_events(log_path)
    output = _render_log_pane(pane_width, pane_height, log_path, events)
    if output != loop_state['last_output']:
        print('\033[2J\033[3J\033[H', end='', flush=True)
        print(output, end='', flush=True)
        loop_state['last_output'] = output
    time.sleep(LOG_POLL_INTERVAL)

def _load_events(log_path) -> list:
    if log_path is None:
        return []
    return filter_events(find_current_run_lines(log_path))

def _render_log_pane(pane_width: int, pane_height: int,
                     log_path, events: list[str]) -> str:
    lines: list[str] = []
    lines.append(f"{DIM}{'═' * min(pane_width, 52)}{RESET}  Pipeline Log")

    if log_path is None:
        lines.append(f"  {DIM}waiting for log…{RESET}")
        return "\n".join(lines)

    lines.append(f"  {DIM}{log_path.name}{RESET}")

    available = max(0, pane_height - len(lines) - 1)
    recent    = events[-MAX_LOG_LINES:][-max(1, available):]

    for raw in recent:
        lines.append(_format_event_line(raw, pane_width))

    return "\n".join(lines)

def _format_event_line(raw: str, max_width: int) -> str:
    parsed = parse_line(raw)
    if parsed is None:
        return f"  {raw[:max(0, max_width - 2)]}"
    ts, level, msg = parsed
    prefix_plain = f"  {ts}  "
    max_msg = max(0, max_width - len(prefix_plain))
    if len(msg) > max_msg:
        msg = msg[:max_msg - 1] + '…'
    prefix = f"  {DIM}{ts}{RESET}  "
    if level == 'WARNING':
        return f"{prefix}{YELLOW}{msg}{RESET}"
    if level == 'ERROR':
        return f"{prefix}{RED}{msg}{RESET}"
    return f"{prefix}{msg}"
