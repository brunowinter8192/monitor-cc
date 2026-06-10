# INFRASTRUCTURE
import os
import time

from ..constants import RESET, DIM, GREEN
from .log_parser import find_log_file

LOG_POLL_INTERVAL = 0.5
MAX_LOG_LINES     = 40

# ORCHESTRATOR

# News log pane loop — tails pipeline log file, no mouse (tmux scroll active)
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
        output   = _render_log_pane(pane_width, pane_height, log_path)
        if output != last_output:
            print('\033[2J\033[3J\033[H', end='', flush=True)
            print(output, end='', flush=True)
            last_output = output

        time.sleep(LOG_POLL_INTERVAL)

# FUNCTIONS

# Build log pane content; Stage 1 skeleton — full parsing added in Stage 2
def _render_log_pane(pane_width: int, pane_height: int, log_path) -> str:
    lines: list[str] = []
    lines.append(f"{DIM}{'═' * min(pane_width, 52)}{RESET}  Pipeline Log")

    if log_path is None:
        lines.append(f"  {DIM}waiting for log…{RESET}")
    else:
        lines.append(f"  {DIM}{log_path.name}{RESET}")
        lines.append(f"  {DIM}waiting for log… (Stage 2){RESET}")

    return "\n".join(lines)
