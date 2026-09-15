# INFRASTRUCTURE
from typing import Dict, Optional, Set, Tuple
import os
import time

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from ..colors import RESET, YELLOW, DIM, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from ..panes.cache_turns import build_cache_turns
from ..panes.token_search import build_token_search_matches
from ..format.token_format import format_cache_tracker
from ..input.click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event, resolve_parent_key,
    copy_to_clipboard, wait_for_input,
)
from ..utils import truncate_visible, visual_line_count
from ..ram_audit import register_ram_dump
from ..pane_error_log import log_pane_error
from .. import search_bar
from .worker_tmux import list_workers, find_worker_jsonl, attach_worker_stats
from .worker_selection import get_selection_file_path, _write_selection as write_selection
from .worker_switch_header import format_worker_switch_header

worker_tokens_expand_states: Dict[tuple, bool] = {}
worker_tokens_line_map: Dict[int, tuple] = {}
worker_tokens_hover_row: Optional[int] = None
worker_tokens_scroll_offset: int = 0
worker_tokens_copy_rows: Set[int] = set()
_worker_tokens_copy_feedback_until: Dict[tuple, float] = {}
_worker_tokens_pane_width: int = 80

_worker_tokens_jsonl_position: int = 0
_worker_tokens_turns: list = []
_worker_tokens_workers: list = []
_worker_tokens_current_name: Optional[str] = None
_worker_tokens_force_reload: bool = False
_worker_tokens_header_regions: Dict[Tuple[int, int, int], str] = {}
_worker_tokens_header_lines: int = 2
_worker_tokens_stats_cache: dict = {}

_WT_SEARCH_BAR_LINES = 1
_WT_SEARCH_BAR_LABEL = 'search: '

_worker_tokens_search: search_bar.SearchState = search_bar.SearchState()
_worker_tokens_nav: dict = {}

# ORCHESTRATOR

def run_worker_tokens_loop() -> None:
    from ..core import monitor as _monitor
    global _worker_tokens_copy_feedback_until

    register_ram_dump('worker_tokens', _worker_tokens_ram_state)
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed = _poll_worker_tokens_input(_monitor)
                now = time.time()
                input_changed, last_data_refresh = _refresh_worker_tokens_data(now, input_changed, last_data_refresh, _monitor)
                _worker_tokens_copy_feedback_until = {k: v for k, v in _worker_tokens_copy_feedback_until.items() if v > now}
                if _worker_tokens_copy_feedback_until:
                    input_changed = True
                if input_changed:
                    output, header = _build_worker_tokens_output(_monitor)
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output, end='', flush=True)
                            print(f"\033[H{header}\033[K", end='', flush=True)
                        last_output = output
                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('worker_tokens')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _poll_worker_tokens_input(monitor) -> bool:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                if _handle_worker_tokens_mouse(*event, monitor):
                    input_changed = True
            elif event is not None:
                if _handle_worker_tokens_search_release():
                    input_changed = True
            elif _worker_tokens_search.focused:
                if _handle_worker_tokens_search_cancel():
                    input_changed = True
        elif _worker_tokens_search.focused:
            if _handle_worker_tokens_search_input(char):
                input_changed = True
        elif char == '/':
            _worker_tokens_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_worker_tokens_search_match(forward=(char == 'n')):
                input_changed = True
        else:
            if _handle_worker_tokens_key(char, monitor):
                input_changed = True
    return input_changed

def _worker_tokens_ram_state() -> list:
    return [
        ('worker_tokens_expand_states', worker_tokens_expand_states),
        ('worker_tokens_line_map',      worker_tokens_line_map),
        ('_worker_tokens_turns',        _worker_tokens_turns),
        ('worker_tokens_scroll_offset', worker_tokens_scroll_offset),
        ('worker_tokens_hover_row',     str(worker_tokens_hover_row)),
        ('_worker_tokens_jsonl_position', _worker_tokens_jsonl_position),
        ('_worker_tokens_current_name', str(_worker_tokens_current_name)),
        ('_worker_tokens_search_query', _worker_tokens_search.query),
        ('_worker_tokens_search_matches', _worker_tokens_search.matches),
    ]

def _serialize_worker_tokens(key: tuple) -> str:
    import json
    turn_idx, call_idx = key
    if turn_idx >= len(_worker_tokens_turns):
        return ''
    turn = _worker_tokens_turns[turn_idx]
    calls = turn.get('api_calls', [])
    if call_idx >= len(calls):
        return ''
    call = calls[call_idx]
    parts = [f"Turn {turn_idx + 1}, Call {call_idx + 1}  CR:{call.get('cache_read', 0)}  CC:{call.get('cache_creation', 0)}  D:{call.get('direct', 0)}  out:{call.get('output_tokens', 0)}"]
    for blk in call.get('content_blocks', []):
        btype = blk.get('type', '')
        if btype == 'tool_use':
            tool_name = blk.get('tool_name', 'Unknown')
            inp = blk.get('preview', {})
            parts.append(f"\n--- tool_use: {tool_name} ---")
            parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
        elif btype == 'text':
            text = blk.get('preview', '')
            parts.append(f"\n--- text ---")
            parts.append(text)
        elif btype == 'thinking':
            parts.append(f"\n--- thinking ({blk.get('chars', 0):,}c) ---")
    return '\n'.join(parts)

def _handle_worker_tokens_mouse(button: int, col: int, row: int, monitor) -> bool:
    global worker_tokens_hover_row, worker_tokens_scroll_offset, _worker_tokens_force_reload, _worker_tokens_copy_feedback_until
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_worker_tokens_search, col, _WT_SEARCH_BAR_LABEL)
        had_selection = _worker_tokens_search.sel_anchor is not None
        search_bar.clear_selection(_worker_tokens_search)
        for (sc, ec, er), name in _worker_tokens_header_regions.items():
            if row == er and sc <= col <= ec:
                if any(w['name'] == name for w in _worker_tokens_workers):
                    write_selection(monitor.active_project_filter, name)
                    _worker_tokens_force_reload = True
                return True
        key = worker_tokens_line_map.get(row)
        if key is None:
            return had_selection
        if col >= _worker_tokens_pane_width - 2 and row in worker_tokens_copy_rows:
            copy_to_clipboard(_serialize_worker_tokens(key))
            _worker_tokens_copy_feedback_until[key] = time.time() + 1.5
            return True
        worker_tokens_expand_states[key] = not worker_tokens_expand_states.get(key, False)
        return True
    if button == 64:
        worker_tokens_scroll_offset = max(0, worker_tokens_scroll_offset + 3)
        return True
    if button == 65:
        worker_tokens_scroll_offset = max(0, worker_tokens_scroll_offset - 3)
        return True
    if button == 32 and _worker_tokens_search.dragging:
        return search_bar.handle_search_mouse_motion(_worker_tokens_search, col, _WT_SEARCH_BAR_LABEL)
    if button >= 32:
        worker_tokens_hover_row = row
        return True
    return False

def _handle_worker_tokens_key(char: str, monitor) -> bool:
    global _worker_tokens_force_reload
    idx = parse_digit_key(char)
    if idx is not None and _worker_tokens_workers and 1 <= idx <= len(_worker_tokens_workers):
        write_selection(monitor.active_project_filter, _worker_tokens_workers[idx - 1]['name'])
        _worker_tokens_force_reload = True
        return True
    if char == 'y':
        key = resolve_parent_key(worker_tokens_line_map, worker_tokens_hover_row)
        if key is not None:
            copy_to_clipboard(_serialize_worker_tokens(key))
        return False
    return False

def _handle_worker_tokens_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_worker_tokens_search)

def _handle_worker_tokens_search_input(char: str) -> bool:
    return search_bar.handle_search_input(_worker_tokens_search, char, on_commit=_worker_tokens_search_on_commit)

def _worker_tokens_search_on_commit(state: search_bar.SearchState) -> None:
    state.matches = build_token_search_matches(state.query, _worker_tokens_turns, _worker_tokens_pane_width)
    state.match_set = set(state.matches)
    state.current_idx = 0
    _ensure_worker_tokens_match_visible()

def _jump_worker_tokens_search_match(forward: bool) -> bool:
    if not _worker_tokens_search.matches:
        return False
    _worker_tokens_search.current_idx = (_worker_tokens_search.current_idx + (1 if forward else -1)) % len(_worker_tokens_search.matches)
    _ensure_worker_tokens_match_visible()
    return True

def _ensure_worker_tokens_match_visible() -> None:
    global worker_tokens_scroll_offset
    if not _worker_tokens_search.matches or _worker_tokens_search.current_idx >= len(_worker_tokens_search.matches):
        return
    target_key = _worker_tokens_search.matches[_worker_tokens_search.current_idx]
    target_line = _worker_tokens_nav.get(target_key)
    total_lines = _worker_tokens_nav.get('total_lines')
    if target_line is None or total_lines is None:
        return
    term = os.get_terminal_size()
    pane_height = term.lines - 1
    viewport_lines = max(1, (pane_height - _worker_tokens_header_lines) - 1)
    new_start = max(0, target_line - 2)
    worker_tokens_scroll_offset = max(0, total_lines - viewport_lines - new_start)

def _handle_worker_tokens_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_worker_tokens_search, copy_to_clipboard)

def _render_worker_tokens_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_worker_tokens_search, pane_width, label=_WT_SEARCH_BAR_LABEL)

def _read_selected_worker_name(monitor) -> Optional[str]:
    sel_path = get_selection_file_path(monitor.active_project_filter)
    try:
        with open(sel_path, 'r', encoding='utf-8') as f:
            return f.read().strip() or None
    except OSError:
        return None

def _reset_worker_tokens_state(worker_name: Optional[str]) -> None:
    global _worker_tokens_jsonl_position, _worker_tokens_turns, _worker_tokens_current_name
    global worker_tokens_scroll_offset, worker_tokens_hover_row
    worker_tokens_expand_states.clear()
    _worker_tokens_jsonl_position = 0
    _worker_tokens_turns = []
    _worker_tokens_current_name = worker_name
    worker_tokens_scroll_offset = 0
    worker_tokens_hover_row = None
    search_bar.handle_search_cancel(_worker_tokens_search)
    _worker_tokens_nav.clear()

def _refresh_worker_tokens_data(now: float, input_changed: bool, last_data_refresh: float, monitor) -> tuple:
    global _worker_tokens_workers, _worker_tokens_force_reload, _worker_tokens_jsonl_position, _worker_tokens_turns
    if not _worker_tokens_force_reload and now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh
    _worker_tokens_force_reload = False
    worker_name = _read_selected_worker_name(monitor)
    _worker_tokens_workers = list_workers(monitor.active_project_filter) if monitor.active_project_filter else []
    attach_worker_stats(_worker_tokens_workers, _worker_tokens_stats_cache)
    if not _worker_tokens_workers:
        worker_name = None
    elif worker_name is not None and worker_name not in {w['name'] for w in _worker_tokens_workers}:
        worker_name = None
    if worker_name != _worker_tokens_current_name:
        _reset_worker_tokens_state(worker_name)
        input_changed = True
    if worker_name:
        worker_session = next((w.get('session', '') for w in _worker_tokens_workers if w.get('name') == worker_name), '')
        jsonl_path = find_worker_jsonl(worker_session) if worker_session else None
        if jsonl_path:
            _worker_tokens_turns, _worker_tokens_jsonl_position = build_cache_turns(
                jsonl_path, _worker_tokens_jsonl_position, _worker_tokens_turns
            )
    return True, now

def _build_worker_tokens_header_block(monitor, pane_width: int) -> tuple:
    global _worker_tokens_header_lines
    current_worker = _read_selected_worker_name(monitor)
    search_bar_line = _render_worker_tokens_search_bar(pane_width)
    worker_header = format_worker_switch_header(
        _worker_tokens_workers, current_worker, pane_width, _worker_tokens_header_regions, label='WORKER-TOKENS',
    )
    if _worker_tokens_header_regions:
        shifted_regions = {(sc, ec, er + _WT_SEARCH_BAR_LINES): name for (sc, ec, er), name in _worker_tokens_header_regions.items()}
        _worker_tokens_header_regions.clear()
        _worker_tokens_header_regions.update(shifted_regions)
    total_header_lines = _WT_SEARCH_BAR_LINES + visual_line_count(worker_header, pane_width)
    _worker_tokens_header_lines = total_header_lines
    return search_bar_line + '\n' + worker_header, total_header_lines, current_worker

def _render_worker_tokens_rows(visible_lines: list, visible_keys: list, phys_row: int, parent_count: int,
                                pane_width: int, hover_row, line_map: dict, copy_rows: set) -> list:
    result_lines = []
    for line, key in zip(visible_lines, visible_keys):
        if key is not None:
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = (key is not None and hover_row is not None and phys_row == hover_row)
        if is_hovered:
            chosen_bg = HOVER_BG
        elif LIGHT_RED_BG in line:
            chosen_bg = LIGHT_RED_BG
        else:
            chosen_bg = zebra_bg
        line = search_bar.resolve_bg_restore(line, chosen_bg)
        if key is not None and ('⎘' in line or '✓' in line):
            copy_rows.add(phys_row)
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
        if key is not None:
            line_map[phys_row] = key
        phys_row += 1
    return result_lines

def _render_worker_tokens_body(pane_width: int, content_height: int, total_header_lines: int) -> str:
    global worker_tokens_line_map, worker_tokens_copy_rows
    current_match_key = (
        _worker_tokens_search.matches[_worker_tokens_search.current_idx]
        if _worker_tokens_search.matches and _worker_tokens_search.current_idx < len(_worker_tokens_search.matches)
        else None
    )
    visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count = format_cache_tracker(
        _worker_tokens_turns, worker_tokens_expand_states, content_height, pane_width, worker_tokens_scroll_offset,
        copy_feedback=_worker_tokens_copy_feedback_until,
        search_match_set=_worker_tokens_search.match_set, search_current_key=current_match_key,
        search_query=_worker_tokens_search.query, nav_out=_worker_tokens_nav,
    )
    result_lines = []
    if sticky_header is not None:
        trunc = truncate_visible(search_bar.resolve_bg_restore(sticky_header, ZEBRA_BG_A), pane_width)
        result_lines.append(f"{ZEBRA_BG_A}{trunc}\033[K{RESET}")
    worker_tokens_line_map.clear()
    worker_tokens_copy_rows.clear()
    phys_row = total_header_lines + 1 + (1 if sticky_header is not None else 0)
    result_lines.extend(_render_worker_tokens_rows(
        visible_lines, visible_keys, phys_row, initial_parent_count, pane_width,
        worker_tokens_hover_row, worker_tokens_line_map, worker_tokens_copy_rows,
    ))
    return '\n'.join(result_lines)

def _build_worker_tokens_output(monitor) -> tuple:
    global _worker_tokens_pane_width
    term = os.get_terminal_size()
    pane_height, pane_width = term.lines - 1, term.columns
    _worker_tokens_pane_width = pane_width
    header, total_header_lines, current_worker = _build_worker_tokens_header_block(monitor, pane_width)
    content_height = max(1, pane_height - total_header_lines)
    if not current_worker:
        body = f"{DIM}Select a worker with digit keys 1-9{RESET}"
    elif not _worker_tokens_turns:
        body = f"{YELLOW}Worker: {current_worker}{RESET}\n{DIM}No token data yet{RESET}"
    else:
        body = _render_worker_tokens_body(pane_width, content_height, total_header_lines)
    return header + '\n' + body, header
