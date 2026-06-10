# INFRASTRUCTURE
import json
import os
import re
import subprocess
import time

from ..constants import (
    RESET, GREEN, YELLOW, DIM, CYAN, ORANGE,
    INPUT_POLL_INTERVAL,
)
from ..input.click_handler import (
    setup_keyboard_input, restore_terminal, read_keypress, wait_for_input,
    enable_mouse, disable_mouse,
)
from .log_parser import TARGET_COLLECTION, LAST_RUN_FILE, read_last_run_ts

NEWS_POLL_INTERVAL        = 2.0
COLLECTIONS_POLL_INTERVAL = 30.0

_ANSI_RE      = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')
_button_regions: dict = {}

# ORCHESTRATOR

# News pane event loop — 2s tick, r=refresh
def run_news_loop() -> None:
    last_output           = None
    last_data_refresh     = 0.0
    last_coll_refresh     = 0.0
    force_refresh         = False
    status: dict          = {}

    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False

            while True:
                char = read_keypress()
                if char is None:
                    break
                if char in ('r', 'R'):
                    force_refresh = True
                    input_changed = True
                elif char == '\033':
                    pass  # mouse events wired in Stage 3

            now = time.time()
            if force_refresh or now - last_data_refresh >= NEWS_POLL_INTERVAL:
                status = _fetch_news_status()
                last_data_refresh = now
                input_changed = True

            force_refresh = False

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_width  = term.columns
                    pane_height = term.lines - 1
                except OSError:
                    pane_width, pane_height = 80, 24
                output = _render_pane(pane_width, pane_height, status)
                if output != last_output:
                    print('\033[2J\033[3J\033[H', end='', flush=True)
                    print(output, end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Gather doc count, chunk count, last-run timestamp for searxng_crypto
def _fetch_news_status() -> dict:
    return {
        'doc_count':   _fetch_doc_count(),
        'chunk_count': _fetch_chunk_count(),
        'last_run_ts': read_last_run_ts(),
    }


# Count documents in searxng_crypto via rag-cli list_documents; None on failure
def _fetch_doc_count() -> int | None:
    try:
        r = subprocess.run(
            ['rag-cli', 'list_documents', TARGET_COLLECTION],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return sum(1 for ln in r.stdout.splitlines() if re.search(r'\.md \(\d+ chunks\)', ln))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# Fetch chunk count for searxng_crypto from rag-cli list_collections --json; None on failure
def _fetch_chunk_count() -> int | None:
    try:
        r = subprocess.run(
            ['rag-cli', 'list_collections', '--json'],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for entry in json.loads(r.stdout):
                if entry.get('collection') == TARGET_COLLECTION:
                    return entry.get('chunks')
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
    return None


# Remove ANSI codes for visual-width measurement
def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


# Build full pane content
def _render_pane(pane_width: int, pane_height: int, status: dict) -> str:
    _button_regions.clear()
    lines: list[str] = []

    lines.append(f"{DIM}{'═' * min(pane_width, 52)}{RESET}  CoinDesk News Pipeline")

    doc_str   = str(status.get('doc_count'))   if status.get('doc_count')   is not None else f"{DIM}?{RESET}"
    chunk_str = str(status.get('chunk_count')) if status.get('chunk_count') is not None else f"{DIM}?{RESET}"
    ts_str    = status.get('last_run_ts') or f"{DIM}(never){RESET}"

    lines.append(f"  Collection  {CYAN}{TARGET_COLLECTION}{RESET}")
    lines.append(f"  Documents   {GREEN}{doc_str}{RESET}")
    lines.append(f"  Chunks      {GREEN}{chunk_str}{RESET}")
    lines.append(f"  Last run    {ts_str}")
    lines.append("")
    lines.append(f"  {DIM}[run pipeline] — wired in Stage 3{RESET}")

    return "\n".join(lines)
