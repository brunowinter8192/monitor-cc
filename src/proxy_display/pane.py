# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import os
import time

from ..constants import (
    RESET, YELLOW, DIM,
    POLL_INTERVAL, INPUT_POLL_INTERVAL, PROXY_MESSAGES_KEEP_LAST,
)
from .parser import parse_proxy_log_isolated, find_proxy_log_path, _lazy_load_messages
from .format import format_proxy_block, _is_standalone_entry
from ..panes.token_pane import build_cache_turns
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from ..ram_audit import register_ram_dump

proxy_entries: List[dict] = []
proxy_expand_states: Dict[int, bool] = {}
proxy_line_map: Dict[int, int] = {}
proxy_hover_row: Optional[int] = None
proxy_scroll_offset: int = 0
proxy_log_position: int = 0

_proxy_jsonl_position: int = 0
_proxy_cache_turns: list = []
_proxy_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge
_proxy_log_path: Optional[Path] = None  # current log file path, updated each poll cycle for lazy-reload
_proxy_pane_width: int = 80  # updated each render cycle; used by click handler for copy-button column check
_proxy_copy_rows: Set[int] = set()  # phys_rows where ⎘ copy button is rendered; populated by format_proxy_block
_copy_feedback_until: Dict[int, float] = {}  # entry_idx → expiry timestamp for ✓ flash

# FUNCTIONS

# Extract entry_idx from any proxy line_map key variant
def _entry_idx_from_key(key) -> Optional[int]:
    if isinstance(key, int):
        return key
    if isinstance(key, tuple):
        if isinstance(key[0], str):   # ('req', idx), ('sys', idx), ('tools', idx), ('tool', idx, n), ('sys_block', idx, n)
            return key[1]
        if isinstance(key[0], int):   # (idx, 'neg_delta'), (idx, 'warnings'), (idx, 'schema')
            return key[0]
    return None

# Serialize a proxy entry to full untruncated text (all new-message blocks) for clipboard
def _serialize_proxy(key, entries: list) -> str:
    import json
    entry_idx = _entry_idx_from_key(key)
    if entry_idx is None or entry_idx >= len(entries):
        return ''
    entry = entries[entry_idx]
    model = entry.get('model', '?')
    msg_count = entry.get('message_count', 0)
    parts = [f"entry_idx={entry_idx}  model={model}  msgs={msg_count}"]
    diff = entry.get('diff_from_prev') or {}
    start = diff.get('first_diff_index', 0) if diff else 0
    if start < 0:
        start = 0
    for msg_idx, msg in enumerate(entry.get('messages', [])[start:], start=start):
        role = msg.get('role', '?')
        msg_type = msg.get('type', '?')
        blocks = msg.get('blocks', [])
        if blocks:
            for blk in blocks:
                ft = blk.get('full_text', blk.get('preview', ''))
                if ft:
                    parts.append(f"\n--- msg[{msg_idx}] {role} {blk.get('type', '?')} ---")
                    parts.append(ft)
        else:
            ct = msg.get('content_tail', '') or msg.get('content_preview', '')
            if ct:
                parts.append(f"\n--- msg[{msg_idx}] {role} {msg_type} ---")
                parts.append(ct)
    return '\n'.join(parts)

# Walk backward from k-1 to find first non-standalone entry idx (prev_same reference)
def _resolve_prev_same(entries: list, k: int) -> Optional[int]:
    for i in range(k - 1, -1, -1):
        if not _is_standalone_entry(entries[i]):
            return i
    return None

# Strip messages from all entries outside the keep-last window that are not expanded
def _strip_inactive_messages(entries: list, expand_states: dict) -> None:
    cutoff = max(0, len(entries) - PROXY_MESSAGES_KEEP_LAST)
    for i in range(cutoff):
        e = entries[i]
        if e.get('messages') is None:
            continue
        is_active = (
            expand_states.get(i, False) or
            expand_states.get(('req', i), False) or
            expand_states.get((i, 'neg_delta'), False)
        )
        if not is_active:
            del e['messages']

# Runs proxy pane display loop — reads api_requests.jsonl, shows expandable entries
def run_proxy_loop() -> None:
    from ..core import monitor as _monitor
    global proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, proxy_scroll_offset, proxy_log_position
    global _proxy_jsonl_position, _proxy_cache_turns, _proxy_pending_by_rid, _proxy_log_path
    global _proxy_pane_width, _proxy_copy_rows, _copy_feedback_until

    def _ram_state():
        return [
            ('proxy_entries',         proxy_entries),
            ('proxy_expand_states',   proxy_expand_states),
            ('proxy_line_map',        proxy_line_map),
            ('_proxy_cache_turns',    _proxy_cache_turns),
            ('_proxy_pending_by_rid', _proxy_pending_by_rid),
            ('proxy_hover_row',       str(proxy_hover_row)),
            ('proxy_scroll_offset',   proxy_scroll_offset),
            ('proxy_log_position',    proxy_log_position),
            ('_proxy_jsonl_position', _proxy_jsonl_position),
        ]
    register_ram_dump('proxy', _ram_state)
    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    current_main_session = _monitor._get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False
            just_expanded = None
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            key = proxy_line_map.get(row)
                            if key is not None:
                                is_req = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
                                if is_req and col >= _proxy_pane_width - 2 and row in _proxy_copy_rows:
                                    # Copy-button click: right-aligned ⎘ in REQ header
                                    entry_idx = _entry_idx_from_key(key)
                                    if entry_idx is not None and entry_idx < len(proxy_entries) and _proxy_log_path:
                                        e = proxy_entries[entry_idx]
                                        if e.get('messages') is None:
                                            _lazy_load_messages(e, _proxy_log_path)
                                    copy_to_clipboard(_serialize_proxy(key, proxy_entries))
                                    if entry_idx is not None:
                                        _copy_feedback_until[entry_idx] = time.time() + 1.5
                                    input_changed = True
                                else:
                                    new_state = not proxy_expand_states.get(key, False)
                                    proxy_expand_states[key] = new_state
                                    if new_state:
                                        entry_idx = _entry_idx_from_key(key)
                                        if entry_idx is not None and entry_idx < len(proxy_entries) and _proxy_log_path:
                                            e = proxy_entries[entry_idx]
                                            if e.get('messages') is None:
                                                _lazy_load_messages(e, _proxy_log_path)
                                            prev_idx = _resolve_prev_same(proxy_entries, entry_idx)
                                            if prev_idx is not None:
                                                pe = proxy_entries[prev_idx]
                                                if pe.get('messages') is None:
                                                    _lazy_load_messages(pe, _proxy_log_path)
                                        just_expanded = key
                                    input_changed = True
                        elif button == 64:  # wheel up → older content
                            proxy_scroll_offset = max(0, proxy_scroll_offset + 3)
                            input_changed = True
                        elif button == 65:  # wheel down → newer content
                            proxy_scroll_offset = max(0, proxy_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            proxy_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    session_start_ts = _monitor._get_session_start_ts()
                    if session_start_ts is None:
                        session_start_ts = datetime.utcnow().isoformat() + 'Z'
                    proxy_entries.clear()
                    proxy_expand_states.clear()
                    proxy_line_map.clear()
                    proxy_log_position = 0
                    proxy_scroll_offset = 0
                    proxy_hover_row = None
                    _proxy_jsonl_position = 0
                    _proxy_cache_turns = []
                    _proxy_pending_by_rid.clear()
                    _proxy_log_path = None
                    input_changed = True
                new_entries, proxy_log_position = parse_proxy_log_isolated(_monitor.active_project_filter, proxy_log_position, _proxy_pending_by_rid)
                filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
                proxy_entries.extend(filtered)
                _proxy_log_path = find_proxy_log_path(_monitor.active_project_filter)
                _strip_inactive_messages(proxy_entries, proxy_expand_states)
                main_sessions = _monitor.get_main_session_files()
                if main_sessions:
                    filepath = main_sessions[0]
                    _proxy_cache_turns, _proxy_jsonl_position = build_cache_turns(filepath, _proxy_jsonl_position, _proxy_cache_turns)
                last_data_refresh = now
                input_changed = True

            # Cleanup expired copy-flash states; refresh display while any flash is active
            _now_t = time.time()
            _copy_feedback_until = {k: v for k, v in _copy_feedback_until.items() if v > _now_t}
            if _copy_feedback_until:
                input_changed = True

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                _proxy_pane_width = pane_width
                _proxy_copy_rows.clear()
                item_positions: dict = {}
                output, total_lines = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, pane_height, pane_width, proxy_scroll_offset, turns=_proxy_cache_turns, item_positions_out=item_positions, copy_feedback=_copy_feedback_until, copy_rows_out=_proxy_copy_rows)
                if just_expanded is not None and just_expanded in item_positions:
                    item_line = item_positions[just_expanded]
                    viewport_lines_n = pane_height - 1
                    max_scroll = max(0, total_lines - viewport_lines_n)
                    clamped = min(proxy_scroll_offset, max_scroll)
                    start = max(0, total_lines - viewport_lines_n - clamped)
                    if item_line < start or item_line >= start + viewport_lines_n:
                        proxy_scroll_offset = max(0, total_lines - viewport_lines_n - item_line)
                        _proxy_copy_rows.clear()
                        output, total_lines = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, pane_height, pane_width, proxy_scroll_offset, turns=_proxy_cache_turns, copy_feedback=_copy_feedback_until, copy_rows_out=_proxy_copy_rows)
                just_expanded = None
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
