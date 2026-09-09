# INFRASTRUCTURE
import json
import os
import re
import subprocess
import time

from ..constants import (
    RESET, GREEN, YELLOW, DIM, CYAN,
    INPUT_POLL_INTERVAL, SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
)
from ..input.click_handler import (
    setup_keyboard_input, restore_terminal, read_keypress, wait_for_input,
    enable_mouse, disable_mouse, read_mouse_event, copy_to_clipboard,
)
# From utils.py: shrinking-rule header layout (decoration yields to the [refresh] button first);
# browser-find-style inline substring highlight
from ..utils import compute_header_rule_len, highlight_query_in_line
from .log_parser import (
    TARGET_COLLECTION, WEBSEARCH_ROOT, read_last_run_ts,
    find_log_file, RUN_START_MARKER, RUN_END_MARKER,
)
# From pane_error_log.py: shared exception-safe pane-error sink
from ..pane_error_log import log_pane_error
# From search_bar.py: shared search-bar mechanics (state, key/mouse handling, drag-select) --
# rollout sub-milestone 8, retrofitting the news pane onto the proxy pane's reference
# implementation. HIGHLIGHT-ONLY, same reduced scope as the gpu pane -- no scroll/viewport
# exists here either, so no jump-to-match; n/N cycles current_idx with zero scroll call. Only
# news_pane/pane.py is in scope -- log_pane.py is EXCLUDED per the approved decision.
from .. import search_bar

NEWS_POLL_INTERVAL      = 2.0
LOG_RUNNING_RECENT_SECS = 60

_ANSI_RE        = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')
_button_regions: dict                      = {}
_pipeline_proc: subprocess.Popen | None   = None

_NEWS_SEARCH_BAR_LINES = 1  # fixed-height search bar row; the rule+[refresh] header (below it) shifts down by exactly this
_NEWS_SEARCH_BAR_LABEL = 'search: '

# Search state -- permanent row-1 search bar. .matches holds 0-based indices into _render_pane's
# OWN (unshifted) lines list -- same design as the gpu pane, no click-interactivity concept for
# matches here (only buttons are clickable).
_news_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

# News pane event loop — 2s tick, SGR mouse, r=refresh
def run_news_loop() -> None:
    global _pipeline_proc
    last_output       = None
    last_data_refresh = 0.0
    status: dict      = {}

    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed, force_refresh = _poll_news_input(status)

                now = time.time()
                if force_refresh or now - last_data_refresh >= NEWS_POLL_INTERVAL:
                    status = _fetch_news_status()
                    last_data_refresh = now
                    input_changed = True

                if input_changed:
                    last_output = _build_news_output(status, last_output)

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('news')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Drain and dispatch all pending keyboard/mouse input for one tick; returns (input_changed,
# force_refresh). Stays physically in this module (bare-name read_keypress/read_mouse_event
# calls -- dev/pane_error_log's exception-survival probe monkeypatches these as module
# attributes of pane.py itself).
def _poll_news_input(status: dict) -> tuple:
    input_changed = False
    force_refresh = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                button, col, row = event
                changed, refresh_hit = _handle_news_mouse(button, col, row)
                if changed:
                    input_changed = True
                if refresh_hit:
                    force_refresh = True
            elif event is not None:
                # (-1,-1,-1) release sentinel -- no-op unless a row-1 drag was active
                if search_bar.handle_search_mouse_release(_news_search, copy_to_clipboard):
                    input_changed = True
            elif _news_search.focused:  # bare ESC -> cancel search
                if search_bar.handle_search_cancel(_news_search):
                    input_changed = True
        elif _news_search.focused:
            on_commit = lambda state: _news_search_on_commit(state, status)
            if search_bar.handle_search_input(_news_search, char, on_commit=on_commit):
                input_changed = True
        elif char == '/':
            _news_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_news_search_match(forward=(char == 'n')):
                input_changed = True
        elif char in ('r', 'R'):
            force_refresh = True
            input_changed = True
    return input_changed, force_refresh


# Process one real mouse button event (press or drag-motion); returns (input_changed,
# force_refresh_hit).
def _handle_news_mouse(button: int, col: int, row: int) -> tuple:
    if button == 0:
        if row == 1:  # search bar row -- focuses; also anchors a potential drag-select
            return search_bar.handle_search_mouse_press(_news_search, col, _NEWS_SEARCH_BAR_LABEL), False
        # Click elsewhere ([refresh]/[run pipeline] or unmapped) clears any lingering
        # drag-selection highlight
        had_selection = _news_search.sel_anchor is not None
        search_bar.clear_selection(_news_search)
        for (sc, ec, er), (action, target) in list(_button_regions.items()):
            if row == er and sc <= col <= ec:
                if action == 'refresh':
                    return True, True
                if not _is_running():
                    _fire_pipeline()
                    return True, False
                break
        return had_selection, False
    if button == 32 and _news_search.dragging:  # motion with left button held (0+32), row-1 drag active
        return search_bar.handle_search_mouse_motion(_news_search, col, _NEWS_SEARCH_BAR_LABEL), False
    return False, False


# Render + shift _button_regions past the search bar + diff-and-print; returns the new
# last_output (unchanged when the rendered output didn't change, matching the pre-split print gate).
def _build_news_output(status: dict, last_output):
    try:
        term = os.get_terminal_size()
        pane_width  = term.columns
        pane_height = term.lines - 1
    except OSError:
        pane_width, pane_height = 80, 24
    running = _is_running()
    current_match_line = (
        _news_search.matches[_news_search.current_idx]
        if _news_search.matches and _news_search.current_idx < len(_news_search.matches)
        else None
    )
    body = _render_pane(pane_width, pane_height, status, running,
                        search_query=_news_search.query,
                        search_match_line_set=_news_search.match_set,
                        search_current_line=current_match_line)
    # _render_pane's own _button_regions rows are relative to ITS OWN top -- shift by
    # _NEWS_SEARCH_BAR_LINES since the search bar now owns physical row 1 (mirrors gpu_pane's
    # identical pattern; _render_pane itself stays unshifted/reusable -- dev/click_ui/
    # p4_gpu_news_button_probe.py calls it directly and needed zero changes).
    shifted = {(sc, ec, er + _NEWS_SEARCH_BAR_LINES): v for (sc, ec, er), v in _button_regions.items()}
    _button_regions.clear()
    _button_regions.update(shifted)
    output = _render_news_search_bar(pane_width) + '\n' + body
    if output != last_output:
        print('\033[2J\033[3J\033[H', end='', flush=True)
        print(output, end='', flush=True)
        return output
    return last_output

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
        [str(WEBSEARCH_ROOT / 'venv' / 'bin' / 'python'), '-m', 'src.news', '--source', 'coindesk'],
        cwd=str(WEBSEARCH_ROOT),
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


# on_commit callback for search_bar.handle_search_input (fires on Enter): calls _render_pane
# ONCE without search kwargs (plain baseline), splits on '\n', ANSI-strips each, and collects
# the 0-based indices whose text contains query, case-insensitive -- same design as the gpu
# pane's matcher (no separate matcher function needed, no collapse/expand state to force-open).
# Always re-runs (not gated on query-unchanged), matching every other pane's convention.
def _news_search_on_commit(state: search_bar.SearchState, status: dict) -> None:
    if not state.query:
        state.matches = []
        state.match_set = set()
        return
    try:
        pane_width = os.get_terminal_size().columns
    except OSError:
        pane_width = 80
    plain = _render_pane(pane_width, 0, status, _is_running())
    q = state.query.lower()
    matches = [i for i, line in enumerate(plain.split('\n')) if q in _strip_ansi(line).lower()]
    state.matches = matches
    state.match_set = set(matches)
    state.current_idx = 0

# Cycle the current match (updating which occurrence gets SEARCH_CURRENT_BG vs SEARCH_MATCH_BG,
# and the N/M counter) -- NO jump/scroll call, per the approved decision: this pane has no
# scroll/viewport infra at all, same as the gpu pane. Returns True if a cycle happened (False
# when there are no matches, e.g. before the first Enter).
def _jump_news_search_match(forward: bool) -> bool:
    if not _news_search.matches:
        return False
    _news_search.current_idx = (_news_search.current_idx + (1 if forward else -1)) % len(_news_search.matches)
    return True

# Render the always-visible search bar (row 1). Thin wrapper binding this pane's own label.
def _render_news_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_news_search, pane_width, label=_NEWS_SEARCH_BAR_LABEL)


# Build full pane content; registers button region as side effect. (2026-08-18, rollout
# sub-milestone 8) search_query/search_match_line_set/search_current_line -- HIGHLIGHT-ONLY,
# applied as a SINGLE post-loop pass right before the final join. No sentinel needed: this pane
# has no per-row background/zebra/hover loop at all -- utils.highlight_query_in_line's default
# restore_bg='\\033[49m' is directly correct, same simple case as the gpu pane and
# core/monitor_display.py's main pane. _button_regions' own row numbering stays relative to
# THIS function's own top -- callers that prepend a search bar shift it externally (see
# news_pane.run_news_loop), so this function stays reusable/directly-testable (dev/click_ui/
# p4_gpu_news_button_probe.py calls it directly and needed zero changes).
def _render_pane(pane_width: int, pane_height: int, status: dict, running: bool,
                  search_query: str = '', search_match_line_set: set | None = None,
                  search_current_line: int | None = None) -> str:
    _button_regions.clear()
    lines: list[str] = []

    header_prefix = '  CoinDesk News Pipeline'
    refresh_btn = '[refresh]'
    rule_len, show_refresh = compute_header_rule_len(header_prefix, refresh_btn, 52, pane_width)
    header_text = f"{DIM}{'═' * rule_len}{RESET}{header_prefix}"
    if show_refresh:
        header_vis_len = len(_strip_ansi(header_text))
        header_pad = pane_width - header_vis_len - len(refresh_btn)
        _button_regions[(header_vis_len + header_pad + 1, header_vis_len + header_pad + len(refresh_btn), 1)] = ('refresh', 'refresh')
        lines.append(header_text + ' ' * header_pad + refresh_btn)
    else:
        lines.append(header_text)

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

    if search_query and search_match_line_set:
        for idx in search_match_line_set:
            if 0 <= idx < len(lines):
                marker = SEARCH_CURRENT_BG if idx == search_current_line else SEARCH_MATCH_BG
                lines[idx] = highlight_query_in_line(lines[idx], search_query, marker)

    return "\n".join(lines)
