# INFRASTRUCTURE
from typing import Dict, List, Optional, Set, Tuple
import time

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from ..jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns
from ..input.click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    copy_to_clipboard, wait_for_input,
)
from .worker_format import extract_worker_tokens, extract_worker_context_pct, format_workers_block
from .worker_tmux import list_workers, find_worker_jsonl
from .worker_selection import get_selection_file_path, _write_selection
from .worker_clipboard import _serialize_workers
from . import worker_render
from . import worker_search
from ..ram_audit import register_ram_dump
from ..pane_error_log import log_pane_error
from .. import search_bar

worker_expand_states: Dict[str, bool] = {}
worker_scroll_offsets: Dict[str, int] = {}
worker_line_map: Dict[int, str] = {}
worker_hover_row: Optional[int] = None
worker_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
worker_cache_line_map: Dict[int, tuple] = {}
worker_selected_name: Optional[str] = None
worker_scroll_offset: int = 0
worker_turns: Dict[str, list] = {}
worker_copy_rows: Set[int] = set()
_worker_copy_feedback_until: Dict = {}
_worker_pane_width: int = 80
_worker_header_regions: Dict[Tuple[int, int, int], str] = {}

_WORKERS_SEARCH_BAR_LINES = 1
_WORKERS_SEARCH_BAR_LABEL = 'search: '

_worker_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

def run_workers_loop() -> None:
    from ..core import monitor as _monitor
    global worker_expand_states, worker_scroll_offsets, worker_line_map, worker_hover_row, worker_cache_expand_states, worker_cache_line_map, worker_selected_name, worker_scroll_offset, worker_turns, _worker_copy_feedback_until

    register_ram_dump('workers', _workers_ram_state)
    last_output = None
    workers: list = []
    worker_turns.clear()
    last_data_refresh = 0.0
    frozen = False
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed, frozen = _poll_workers_input(workers, frozen, _monitor.active_project_filter)

                now = time.time()
                workers, input_changed, last_data_refresh = _refresh_workers_data(
                    workers, now, frozen, input_changed, last_data_refresh,
                    _monitor.active_project_filter,
                )

                _worker_copy_feedback_until = {k: v for k, v in _worker_copy_feedback_until.items() if v > now}
                if _worker_copy_feedback_until:
                    input_changed = True

                if input_changed:
                    output = _build_workers_output(workers, frozen)
                    if output != last_output:
                        print("\033[2J\033[3J\033[H", end='', flush=True)
                        if output:
                            print(output)
                        last_output = output

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('workers')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _poll_workers_input(workers: list, frozen: bool, project_filter: Optional[str]) -> tuple:
    input_changed = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                changed, frozen = _handle_workers_mouse(*event, project_filter, frozen)
                if changed:
                    input_changed = True
            elif event is not None:
                if _handle_workers_search_release():
                    input_changed = True
            elif _worker_search.focused:
                if _handle_workers_search_cancel():
                    input_changed = True
        elif _worker_search.focused:
            if _handle_workers_search_input(char, workers, project_filter):
                input_changed = True
        elif char == '/':
            _worker_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_workers_search_match(char == 'n', workers, project_filter):
                input_changed = True
        else:
            changed, frozen = _handle_workers_key(char, workers, frozen, project_filter)
            if changed:
                input_changed = True
    return input_changed, frozen

def _workers_ram_state() -> list:
    return [
        ('worker_expand_states',       worker_expand_states),
        ('worker_scroll_offsets',      worker_scroll_offsets),
        ('worker_line_map',            worker_line_map),
        ('worker_cache_expand_states', worker_cache_expand_states),
        ('worker_cache_line_map',      worker_cache_line_map),
        ('worker_turns',               worker_turns),
        ('worker_hover_row',           str(worker_hover_row)),
        ('worker_selected_name',       str(worker_selected_name)),
        ('worker_scroll_offset',       worker_scroll_offset),
        ('_worker_search_query',       _worker_search.query),
        ('_worker_search_matches',     _worker_search.matches),
    ]

def _handle_workers_body_click(col: int, row: int, project_filter: Optional[str], frozen: bool) -> tuple:
    global worker_selected_name, _worker_copy_feedback_until
    had_selection = _worker_search.sel_anchor is not None
    search_bar.clear_selection(_worker_search)
    for (sc, ec, er), action in _worker_header_regions.items():
        if row == er and sc <= col <= ec:
            if action == 'freeze':
                return True, not frozen
            return had_selection, frozen
    is_copy_click = col >= _worker_pane_width - 2 and row in worker_copy_rows
    cache_key = worker_cache_line_map.get(row)
    if cache_key:
        if is_copy_click:
            copy_to_clipboard(_serialize_workers(cache_key, worker_turns))
            _worker_copy_feedback_until[cache_key] = time.time() + 1.5
            return True, frozen
        w_name, t_idx, c_idx = cache_key
        states = worker_cache_expand_states.setdefault(w_name, {})
        states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
        return True, frozen
    name = worker_line_map.get(row)
    if name:
        if is_copy_click:
            copy_to_clipboard(_serialize_workers(name, worker_turns))
            _worker_copy_feedback_until[name] = time.time() + 1.5
            return True, frozen
        is_now_expanded = not worker_expand_states.get(name, False)
        worker_expand_states[name] = is_now_expanded
        if is_now_expanded:
            worker_scroll_offsets[name] = 0
        worker_selected_name = name
        _write_selection(project_filter, name)
        return True, frozen
    return had_selection, frozen

def _handle_workers_mouse(button: int, col: int, row: int, project_filter: Optional[str], frozen: bool) -> tuple:
    global worker_hover_row
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_worker_search, col, _WORKERS_SEARCH_BAR_LABEL), frozen
        return _handle_workers_body_click(col, row, project_filter, frozen)
    if button in (64, 65):
        changed = worker_render.apply_scroll(button, row, worker_cache_line_map, worker_line_map, worker_selected_name, worker_scroll_offsets)
        return changed, frozen
    if button == 32 and _worker_search.dragging:
        return search_bar.handle_search_mouse_motion(_worker_search, col, _WORKERS_SEARCH_BAR_LABEL), frozen
    if button >= 32:
        worker_hover_row = row
        return True, frozen
    return False, frozen

def _handle_workers_key(char: str, workers: list, frozen: bool, project_filter: Optional[str]) -> tuple:
    global worker_selected_name
    if char == 'y':
        key = worker_render._resolve_workers_hover_key(worker_hover_row, worker_cache_line_map, worker_line_map)
        if key is not None:
            copy_to_clipboard(_serialize_workers(key, worker_turns))
        return False, frozen
    if char == 'f':
        return True, not frozen
    idx = parse_digit_key(char)
    if idx is not None and 1 <= idx <= len(workers):
        name = workers[idx - 1]['name']
        is_now_expanded = not worker_expand_states.get(name, False)
        worker_expand_states[name] = is_now_expanded
        if is_now_expanded:
            worker_scroll_offsets[name] = 0
        worker_selected_name = name
        _write_selection(project_filter, name)
        return True, frozen
    return False, frozen

def _handle_workers_search_cancel() -> bool:
    return search_bar.handle_search_cancel(_worker_search)

def _handle_workers_search_input(char: str, workers: list, project_filter: Optional[str]) -> bool:
    on_commit = lambda state: worker_search.workers_search_on_commit(
        state, workers, project_filter, _worker_pane_width, worker_turns,
        _load_worker_turns, lambda: _jump_to_workers_match(workers, project_filter),
    )
    return search_bar.handle_search_input(_worker_search, char, on_commit=on_commit)

def _jump_workers_search_match(forward: bool, workers: list, project_filter: Optional[str]) -> bool:
    if not _worker_search.matches:
        return False
    _worker_search.current_idx = (_worker_search.current_idx + (1 if forward else -1)) % len(_worker_search.matches)
    _jump_to_workers_match(workers, project_filter)
    return True

def _jump_to_workers_match(workers: list, project_filter: Optional[str]) -> None:
    global worker_selected_name
    state = _worker_search
    if not state.matches or state.current_idx >= len(state.matches):
        return
    key = state.matches[state.current_idx]
    name = key if isinstance(key, str) else key[0]
    worker_expand_states[name] = True
    worker_selected_name = name
    _write_selection(project_filter, name)
    w = next((w for w in workers if w.get('name') == name), None)
    if w is None:
        return
    turns = _load_worker_turns(w.get('session', ''))
    if turns is None:
        return
    worker_turns[name] = turns
    if isinstance(key, str):
        return
    per_worker_expand = worker_cache_expand_states.get(name, {})
    new_offset = worker_render.compute_jump_scroll_offset(key, turns, per_worker_expand, _worker_pane_width)
    if new_offset is not None:
        worker_scroll_offsets[name] = new_offset

def _handle_workers_search_release() -> bool:
    return search_bar.handle_search_mouse_release(_worker_search, copy_to_clipboard)

def _render_workers_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_worker_search, pane_width, label=_WORKERS_SEARCH_BAR_LABEL)

def _parse_worker_turns(jsonl_path) -> list:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    return extract_cache_turns(messages)

def _load_worker_turns(session: str) -> Optional[list]:
    jsonl_path = find_worker_jsonl(session)
    if jsonl_path is None:
        return None
    return _parse_worker_turns(jsonl_path)

def _refresh_workers_data(workers: list, now: float, frozen: bool, input_changed: bool,
                           last_data_refresh: float, project_filter: Optional[str]) -> tuple:
    global worker_turns, worker_selected_name
    if not frozen and now - last_data_refresh >= POLL_INTERVAL:
        workers = list_workers(project_filter) if project_filter else []
        if worker_selected_name is None and workers:
            worker_selected_name = workers[0]['name']
            _write_selection(project_filter, worker_selected_name)
        worker_turns.clear()
        for w in workers:
            name = w.get('name', '')
            jsonl_path = find_worker_jsonl(w.get('session', ''))
            if jsonl_path:
                w['tokens'] = extract_worker_tokens(jsonl_path)
                w['context_pct'] = extract_worker_context_pct(jsonl_path)
                if worker_expand_states.get(name, False):
                    worker_turns[name] = _parse_worker_turns(jsonl_path)
        return workers, True, now
    if input_changed:
        for w in workers:
            name = w.get('name', '')
            if worker_expand_states.get(name, False) and name not in worker_turns:
                jsonl_path = find_worker_jsonl(w.get('session', ''))
                if jsonl_path:
                    worker_turns[name] = _parse_worker_turns(jsonl_path)
    return workers, input_changed, last_data_refresh

def _build_workers_output(workers: list, frozen: bool) -> str:
    global worker_scroll_offset, _worker_pane_width, _worker_header_regions
    _worker_freeze_span: dict = {}
    current_match_key = (
        _worker_search.matches[_worker_search.current_idx]
        if _worker_search.matches and _worker_search.current_idx < len(_worker_search.matches)
        else None
    )
    all_lines, line_keys = format_workers_block(
        workers, worker_expand_states, worker_turns,
        worker_scroll_offsets, worker_cache_expand_states,
        frozen=frozen, selected_name=worker_selected_name,
        copy_feedback=_worker_copy_feedback_until,
        regions_out=_worker_freeze_span,
        search_match_set=_worker_search.match_set, search_current_key=current_match_key,
        search_query=_worker_search.query,
    )
    pane_height, pane_width = worker_render._workers_terminal_size()
    _worker_pane_width = pane_width
    content_height = pane_height - _WORKERS_SEARCH_BAR_LINES
    total_lines = len(all_lines)
    worker_scroll_offset, vp_start = worker_render._compute_viewport(total_lines, content_height, worker_scroll_offset)
    visible_all = all_lines[vp_start:vp_start + content_height]
    visible_keys = line_keys[vp_start:vp_start + content_height]
    worker_line_map.clear()
    worker_cache_line_map.clear()
    worker_copy_rows.clear()
    _worker_header_regions.clear()
    if 'freeze' in _worker_freeze_span and vp_start == 0 and visible_all:
        sc, ec = _worker_freeze_span['freeze']
        _worker_header_regions[(sc, ec, 1 + _WORKERS_SEARCH_BAR_LINES)] = 'freeze'
    parent_count = sum(1 for k in line_keys[:vp_start] if isinstance(k, str))
    body_lines = worker_render._render_workers_rows(
        visible_all, visible_keys, worker_hover_row, 1 + _WORKERS_SEARCH_BAR_LINES, parent_count,
        pane_width, worker_line_map, worker_cache_line_map, worker_copy_rows,
    )
    result_lines = [_render_workers_search_bar(pane_width)] + body_lines
    return '\n'.join(result_lines)
