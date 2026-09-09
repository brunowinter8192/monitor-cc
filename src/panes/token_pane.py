# INFRASTRUCTURE
from typing import Dict, Optional, Set
from pathlib import Path
import os
import time

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from ..colors import RESET, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from .cache_turns import build_cache_turns
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from ..format.token_format import format_cache_tracker
from ..utils import truncate_visible
from ..ram_audit import register_ram_dump
from ..pane_error_log import log_pane_error
from .token_search import build_token_search_matches
from .. import search_bar

cache_expand_states: Dict[tuple, bool] = {}
cache_line_map: Dict[int, tuple] = {}
cache_hover_row: Optional[int] = None
cache_scroll_offset: int = 0
cache_copy_rows: Set[int] = set()
_cache_copy_feedback_until: Dict[tuple, float] = {}
_cache_pane_width: int = 80

_cache_jsonl_position: int = 0
_cache_turns: list = []
_cache_current_filepath = None
_response_log_pos: int = 0
_response_rid_map: dict = {}

_TOKENS_SEARCH_BAR_LINES = 1
_TOKENS_SEARCH_BAR_LABEL = 'search: '

_tokens_search: search_bar.SearchState = search_bar.SearchState()
_tokens_nav: dict = {}

# ORCHESTRATOR

def run_tokens_loop() -> None:
    global cache_expand_states, cache_line_map, cache_hover_row, cache_scroll_offset
    global _cache_jsonl_position, _cache_turns, _cache_current_filepath, _cache_copy_feedback_until

    register_ram_dump('tokens', _tokens_ram_state)
    last_output = None
    last_data_refresh = 0.0
    last_janitor_ts = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed = _poll_tokens_input()

                now = time.time()
                input_changed, last_data_refresh, last_janitor_ts = _refresh_tokens_data(
                    now, input_changed, last_data_refresh, last_janitor_ts
                )

                _cache_copy_feedback_until = {k: v for k, v in _cache_copy_feedback_until.items() if v > now}
                if _cache_copy_feedback_until:
                    input_changed = True

                if input_changed:
                    output = _build_tokens_output()
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output)
                        last_output = output

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('tokens')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _poll_tokens_input() -> bool:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                if _handle_tokens_mouse(*event):
                    input_changed = True
            elif event is not None:
                if _handle_tokens_search_release():
                    input_changed = True
            elif _tokens_search.focused:
                if _handle_tokens_search_cancel():
                    input_changed = True
        elif _tokens_search.focused:
            if _handle_tokens_search_input(char):
                input_changed = True
        elif char == '/':
            _tokens_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_tokens_search_match(forward=(char == 'n')):
                input_changed = True
        else:
            if _handle_tokens_key(char):
                input_changed = True
    return input_changed

def _serialize_tokens(key: tuple) -> str:
    import json
    turn_idx, call_idx = key
    if turn_idx >= len(_cache_turns):
        return ''
    turn = _cache_turns[turn_idx]
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

def _tokens_ram_state() -> list:
    return [
        ('cache_expand_states',     cache_expand_states),
        ('cache_line_map',          cache_line_map),
        ('_cache_turns',            _cache_turns),
        ('cache_scroll_offset',     cache_scroll_offset),
        ('cache_hover_row',         str(cache_hover_row)),
        ('_cache_jsonl_position',   _cache_jsonl_position),
        ('_cache_current_filepath', str(_cache_current_filepath)),
        ('_tokens_search_query',    _tokens_search.query),
        ('_tokens_search_matches',  _tokens_search.matches),
    ]

def _handle_tokens_mouse(button: int, col: int, row: int) -> bool:
    global cache_hover_row, cache_scroll_offset, cache_expand_states, _cache_copy_feedback_until
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_tokens_search, col, _TOKENS_SEARCH_BAR_LABEL)
        had_selection = _tokens_search.sel_anchor is not None
        search_bar.clear_selection(_tokens_search)
        key = cache_line_map.get(row)
        if key is None:
            return had_selection
        if col >= _cache_pane_width - 2 and row in cache_copy_rows:
            copy_to_clipboard(_serialize_tokens(key))
            _cache_copy_feedback_until[key] = time.time() + 1.5
            return True
        cache_expand_states[key] = not cache_expand_states.get(key, False)
        return True
    if button == 64:
        cache_scroll_offset = max(0, cache_scroll_offset + 3)
        return True
    if button == 65:
        cache_scroll_offset = max(0, cache_scroll_offset - 3)
        return True
    if button == 32 and _tokens_search.dragging:
        return search_bar.handle_search_mouse_motion(_tokens_search, col, _TOKENS_SEARCH_BAR_LABEL)
    if button >= 32:
        cache_hover_row = row
        return True
    return False

def _handle_tokens_key(char: str) -> bool:
    if char == 'y':
        key = resolve_parent_key(cache_line_map, cache_hover_row)
        if key is not None:
            copy_to_clipboard(_serialize_tokens(key))
        return False
    return False

def _handle_tokens_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_tokens_search)

def _handle_tokens_search_input(char: str) -> bool:
    return search_bar.handle_search_input(_tokens_search, char, on_commit=_tokens_search_on_commit)

def _tokens_search_on_commit(state: search_bar.SearchState) -> None:
    state.matches = build_token_search_matches(state.query, _cache_turns, _cache_pane_width, _response_rid_map)
    state.match_set = set(state.matches)
    state.current_idx = 0
    _ensure_tokens_match_visible()

def _jump_tokens_search_match(forward: bool) -> bool:
    if not _tokens_search.matches:
        return False
    _tokens_search.current_idx = (_tokens_search.current_idx + (1 if forward else -1)) % len(_tokens_search.matches)
    _ensure_tokens_match_visible()
    return True

def _ensure_tokens_match_visible() -> None:
    global cache_scroll_offset
    if not _tokens_search.matches or _tokens_search.current_idx >= len(_tokens_search.matches):
        return
    target_key = _tokens_search.matches[_tokens_search.current_idx]
    target_line = _tokens_nav.get(target_key)
    total_lines = _tokens_nav.get('total_lines')
    if target_line is None or total_lines is None:
        return
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
    except OSError:
        pane_height = 50
    viewport_lines = (pane_height - _TOKENS_SEARCH_BAR_LINES) - 1
    new_start = max(0, target_line - 2)
    cache_scroll_offset = max(0, total_lines - viewport_lines - new_start)

def _handle_tokens_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_tokens_search, copy_to_clipboard)

def _render_tokens_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_tokens_search, pane_width, label=_TOKENS_SEARCH_BAR_LABEL)

def _refresh_tokens_data(now: float, input_changed: bool, last_data_refresh: float, last_janitor_ts: float) -> tuple:
    from ..core import monitor as _monitor
    from ..proxy_display.parser import find_response_log_path
    from ..proxy_display.side_logs import read_response_log
    global _cache_current_filepath, _cache_jsonl_position, _cache_turns
    global cache_expand_states, cache_scroll_offset, cache_hover_row
    global _response_log_pos, _response_rid_map
    if now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh, last_janitor_ts
    main_sessions = _monitor.get_main_session_files()
    filepath = main_sessions[0] if main_sessions else None
    if filepath != _cache_current_filepath:
        _cache_current_filepath = filepath
        _cache_jsonl_position = 0
        _cache_turns = []
        cache_expand_states.clear()
        cache_scroll_offset = 0
        cache_hover_row = None
        _response_log_pos = 0
        _response_rid_map.clear()
        search_bar.handle_search_cancel(_tokens_search)
        _tokens_nav.clear()
    if filepath is not None:
        _cache_turns, _cache_jsonl_position = build_cache_turns(
            filepath, _cache_jsonl_position, _cache_turns
        )
    resp_path = find_response_log_path(_monitor.active_project_filter)
    new_entries, _response_log_pos = read_response_log(resp_path, _response_log_pos)
    _response_rid_map.update(new_entries)
    if now - last_janitor_ts >= 86400:
        from .log_janitor import cleanup_old_jsonl, sweep_eligible_specs
        _logs = Path(__file__).parent.parent / 'logs'
        for _, _path in sweep_eligible_specs(_logs):
            cleanup_old_jsonl(_path)
        last_janitor_ts = now
    return True, now, last_janitor_ts

def _build_tokens_output() -> str:
    global cache_line_map, cache_copy_rows, _cache_pane_width
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    _cache_pane_width = pane_width
    content_height = pane_height - _TOKENS_SEARCH_BAR_LINES
    current_match_key = (
        _tokens_search.matches[_tokens_search.current_idx]
        if _tokens_search.matches and _tokens_search.current_idx < len(_tokens_search.matches)
        else None
    )
    visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count = format_cache_tracker(
        _cache_turns, cache_expand_states, content_height, pane_width, cache_scroll_offset,
        response_rid_map=_response_rid_map, copy_feedback=_cache_copy_feedback_until,
        search_match_set=_tokens_search.match_set, search_current_key=current_match_key,
        search_query=_tokens_search.query, nav_out=_tokens_nav,
    )
    result_lines = [_render_tokens_search_bar(pane_width)]
    if sticky_header is not None:
        trunc = truncate_visible(search_bar.resolve_bg_restore(sticky_header, ZEBRA_BG_A), pane_width)
        result_lines.append(f"{ZEBRA_BG_A}{trunc}\033[K{RESET}")
    cache_line_map.clear()
    cache_copy_rows.clear()
    phys_row = 1 + _TOKENS_SEARCH_BAR_LINES + (1 if sticky_header is not None else 0)
    result_lines.extend(_render_tokens_rows(
        visible_lines, visible_keys, phys_row, initial_parent_count, pane_width,
        cache_hover_row, cache_line_map, cache_copy_rows,
    ))
    return '\n'.join(result_lines)


def _render_tokens_rows(visible_lines: list, visible_keys: list, phys_row: int, parent_count: int,
                         pane_width: int, hover_row, cache_line_map: dict, cache_copy_rows: set) -> list:
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
            cache_copy_rows.add(phys_row)
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
        if key is not None:
            cache_line_map[phys_row] = key
        phys_row += 1
    return result_lines
