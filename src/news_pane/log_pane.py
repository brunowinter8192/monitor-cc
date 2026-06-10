# INFRASTRUCTURE
import os
import time

from ..constants import RESET, DIM, YELLOW, RED
from .log_parser import (
    find_log_file, find_current_run_lines, filter_events, parse_line,
)

LOG_POLL_INTERVAL = 0.5
MAX_LOG_LINES     = 40

# ORCHESTRATOR

# News log pane loop — tails pipeline log, no mouse (tmux scroll active)
def run_news_log_loop() -> None:
    last_output = None
    while True:
        try:
            term = os.get_terminal_size()
            pane_width  = term.columns
            pane_height = term.lines - 1
        except OSError:
            pane_width, pane_height = 80, 24

        log_path = find_log_file()
        events: list[str] = []
        if log_path is not None:
            events = filter_events(find_current_run_lines(log_path))

        output = _render_log_pane(pane_width, pane_height, log_path, events)
        if output != last_output:
            print('\033[2J\033[3J\033[H', end='', flush=True)
            print(output, end='', flush=True)
            last_output = output

        time.sleep(LOG_POLL_INTERVAL)

# FUNCTIONS

# Format a single filtered log line for display; truncates to max_width
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


# Build full log pane content; events top-anchored, newest visible on overflow
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
