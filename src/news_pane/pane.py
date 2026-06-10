# INFRASTRUCTURE
import json
import os
import re
import subprocess
import time

from ..constants import (
    RESET, GREEN, YELLOW, DIM, CYAN,
    INPUT_POLL_INTERVAL,
)
from ..input.click_handler import (
    setup_keyboard_input, restore_terminal, read_keypress, wait_for_input,
    enable_mouse, disable_mouse, read_mouse_event,
)
from .log_parser import (
    TARGET_COLLECTION, SEARXNG_ROOT, read_last_run_ts,
    find_log_file, RUN_START_MARKER, RUN_END_MARKER,
)

NEWS_POLL_INTERVAL      = 2.0
LOG_RUNNING_RECENT_SECS = 60

_ANSI_RE        = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')
_button_regions: dict                      = {}
_pipeline_proc: subprocess.Popen | None   = None

# ORCHESTRATOR

# News pane event loop — 2s tick, SGR mouse, r=refresh
def run_news_loop() -> None:
    global _pipeline_proc
    last_output       = None
    last_data_refresh = 0.0
    force_refresh     = False
    status: dict      = {}

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
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            for (sc, ec, er), (action, target) in list(_button_regions.items()):
                                if row == er and sc <= col <= ec:
                                    if not _is_running():
                                        _fire_pipeline()
                                        input_changed = True
                                    break

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
                running = _is_running()
                output  = _render_pane(pane_width, pane_height, status, running)
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


# Launch pipeline subprocess; store handle; stdout/stderr to DEVNULL
def _fire_pipeline() -> None:
    global _pipeline_proc
    _pipeline_proc = subprocess.Popen(
        [str(SEARXNG_ROOT / 'venv' / 'bin' / 'python'), '-m', 'src.news', '--source', 'coindesk'],
        cwd=str(SEARXNG_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# True if Popen handle alive or log shows in-flight run (start marker, no end, recent mtime)
def _is_running() -> bool:
    if _pipeline_proc is not None and _pipeline_proc.poll() is None:
        return True
    return _is_running_via_log()


# Log-based fallback: start-marker present, no subsequent end-marker, mtime < LOG_RUNNING_RECENT_SECS
def _is_running_via_log() -> bool:
    lf = find_log_file()
    if lf is None:
        return False
    try:
        if time.time() - lf.stat().st_mtime > LOG_RUNNING_RECENT_SECS:
            return False
        text       = lf.read_text(errors='replace')
        last_start = text.rfind(RUN_START_MARKER)
        if last_start < 0:
            return False
        return text.find(RUN_END_MARKER, last_start) < 0
    except OSError:
        return False


# Remove ANSI codes for visual-width measurement
def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


# Build full pane content; registers button region as side effect
def _render_pane(pane_width: int, pane_height: int, status: dict, running: bool) -> str:
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

    if running:
        content = f"  {YELLOW}⟳ running…{RESET}"
        btn     = '[running…]'
    else:
        content = f"  {DIM}idle{RESET}"
        btn     = '[run pipeline]'

    vis_len  = len(_strip_ansi(content))
    pad      = max(1, pane_width - vis_len - len(btn))
    phys_row = len(lines) + 1
    if not running:
        _button_regions[(vis_len + pad + 1, vis_len + pad + len(btn), phys_row)] = ('run', 'pipeline')
    lines.append(content + ' ' * pad + btn)

    return "\n".join(lines)
