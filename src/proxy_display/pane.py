# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import os
import time

from ..constants import (
    RESET, YELLOW, DIM,
    POLL_INTERVAL, INPUT_POLL_INTERVAL, PROXY_MESSAGES_KEEP_LAST,
    PROXY_REPARSE_INTERVAL_SECONDS,
)
from .parser import (
    parse_proxy_log_forwarded, _lazy_load_messages_forwarded, find_proxy_log_path,
    accumulate_dual_log, _find_dual_log_paths, _infer_model_family,
)
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
_proxy_fwd_pos: int = 0          # forwarded-log byte position for incremental reads
_proxy_acc_fwd: dict = {}        # family accumulator for _parse_forwarded_log
_proxy_stripped_pos: int = 0     # dual-log read position for _stripped.jsonl
_proxy_injected_pos: int = 0     # dual-log read position for _injected.jsonl
_proxy_acc_stripped: dict = {}   # family → {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
_proxy_acc_injected: dict = {}   # same — both mutated in-place; entries hold references
_proxy_log_path: Optional[Path] = None  # current log file path, updated each poll cycle for lazy-reload
_proxy_pane_width: int = 80  # updated each render cycle; used by click handler for copy-button column check
_proxy_copy_rows: Set[int] = set()  # phys_rows where ⎘ copy button is rendered; populated by format_proxy_block
_copy_feedback_until: Dict[int, float] = {}  # entry_idx → expiry timestamp for ✓ flash
_last_full_parse_ts: float = 0.0  # timestamp of last re-init to position 0 (time-triggered reset)
_proxy_just_expanded = None  # line_map key set by mouse handler on expand; cleared by _build_proxy_output
_proxy_current_main_session: Optional[str] = None  # tracks session change for full state reset
_proxy_session_start_ts: Optional[str] = None  # filters new entries to current session window

# ORCHESTRATOR

# Runs proxy pane display loop — reads api_requests.jsonl, shows expandable entries
def run_proxy_loop() -> None:
    from ..core import monitor as _monitor
    global _proxy_current_main_session, _proxy_session_start_ts, _copy_feedback_until

    register_ram_dump('proxy', _proxy_ram_state)
    _proxy_current_main_session = _monitor._get_newest_main_session()
    _proxy_session_start_ts = _monitor._get_session_start_ts()
    if _proxy_session_start_ts is None:
        _proxy_session_start_ts = datetime.utcnow().isoformat() + 'Z'
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        if _handle_proxy_mouse(*event):
                            input_changed = True

            now = time.time()
            input_changed, last_data_refresh = _refresh_proxy_data(
                now, input_changed, last_data_refresh, _monitor
            )

            _copy_feedback_until = {k: v for k, v in _copy_feedback_until.items() if v > now}
            if _copy_feedback_until:
                input_changed = True

            if input_changed:
                output = _build_proxy_output()
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

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
    prev_same_idx = _resolve_prev_same(entries, entry_idx)
    start = entries[prev_same_idx].get('message_count', 0) if prev_same_idx is not None else 0
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

# Return module-level state snapshot for RAM audit
def _proxy_ram_state() -> list:
    return [
        ('proxy_entries',         proxy_entries),
        ('proxy_expand_states',   proxy_expand_states),
        ('proxy_line_map',        proxy_line_map),
        ('_proxy_cache_turns',    _proxy_cache_turns),
        ('_proxy_fwd_pos',        _proxy_fwd_pos),
        ('_proxy_acc_fwd',        _proxy_acc_fwd),
        ('proxy_hover_row',       str(proxy_hover_row)),
        ('proxy_scroll_offset',   proxy_scroll_offset),
        ('proxy_log_position',    proxy_log_position),
        ('_proxy_jsonl_position', _proxy_jsonl_position),
    ]

# Process one mouse event; returns True if display should refresh
def _handle_proxy_mouse(button: int, col: int, row: int) -> bool:
    global proxy_expand_states, proxy_scroll_offset, proxy_hover_row
    global _proxy_just_expanded, _copy_feedback_until
    if button == 0:
        key = proxy_line_map.get(row)
        if key is None:
            return False
        is_req = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
        if is_req and col >= _proxy_pane_width - 2 and row in _proxy_copy_rows:
            entry_idx = _entry_idx_from_key(key)
            if entry_idx is not None and entry_idx < len(proxy_entries) and _proxy_log_path:
                e = proxy_entries[entry_idx]
                if e.get('messages') is None:
                    fwd_path = _proxy_log_path.parent / 'dual_log' / f'{_proxy_log_path.stem}_forwarded.jsonl'
                    _lazy_load_messages_forwarded(e, fwd_path)
            copy_to_clipboard(_serialize_proxy(key, proxy_entries))
            if entry_idx is not None:
                _copy_feedback_until[entry_idx] = time.time() + 1.5
        else:
            new_state = not proxy_expand_states.get(key, False)
            proxy_expand_states[key] = new_state
            if new_state:
                entry_idx = _entry_idx_from_key(key)
                if entry_idx is not None and entry_idx < len(proxy_entries) and _proxy_log_path:
                    e = proxy_entries[entry_idx]
                    fwd_path = _proxy_log_path.parent / 'dual_log' / f'{_proxy_log_path.stem}_forwarded.jsonl'
                    if e.get('messages') is None:
                        _lazy_load_messages_forwarded(e, fwd_path)
                    prev_idx = _resolve_prev_same(proxy_entries, entry_idx)
                    if prev_idx is not None:
                        pe = proxy_entries[prev_idx]
                        if pe.get('messages') is None:
                            _lazy_load_messages_forwarded(pe, fwd_path)
                _proxy_just_expanded = key
        return True
    if button == 64:
        proxy_scroll_offset = max(0, proxy_scroll_offset + 3)
        return True
    if button == 65:
        proxy_scroll_offset = max(0, proxy_scroll_offset - 3)
        return True
    if button >= 32:
        proxy_hover_row = row
        return True
    return False

# Tick-boundary proxy data refresh; returns (input_changed, new_last_data_refresh)
def _refresh_proxy_data(now: float, input_changed: bool, last_data_refresh: float, monitor) -> tuple:
    global proxy_entries, proxy_expand_states, proxy_line_map, proxy_scroll_offset, proxy_hover_row
    global proxy_log_position, _proxy_jsonl_position, _proxy_cache_turns
    global _proxy_fwd_pos, _proxy_acc_fwd
    global _proxy_log_path, _last_full_parse_ts
    global _proxy_current_main_session, _proxy_session_start_ts
    global _proxy_stripped_pos, _proxy_injected_pos, _proxy_acc_stripped, _proxy_acc_injected
    if now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh
    newest = monitor._get_newest_main_session()
    if newest != _proxy_current_main_session and newest is not None:
        _proxy_current_main_session = newest
        _proxy_session_start_ts = monitor._get_session_start_ts()
        if _proxy_session_start_ts is None:
            _proxy_session_start_ts = datetime.utcnow().isoformat() + 'Z'
        proxy_entries.clear()
        proxy_expand_states.clear()
        proxy_line_map.clear()
        proxy_log_position = 0
        proxy_scroll_offset = 0
        proxy_hover_row = None
        _proxy_jsonl_position = 0
        _proxy_cache_turns = []
        _proxy_fwd_pos = 0
        _proxy_acc_fwd.clear()
        _proxy_log_path = None
        _last_full_parse_ts = now
        _proxy_stripped_pos = 0
        _proxy_injected_pos = 0
        _proxy_acc_stripped.clear()
        _proxy_acc_injected.clear()
        input_changed = True
    if _last_full_parse_ts == 0.0:
        _last_full_parse_ts = now
    elif now - _last_full_parse_ts >= PROXY_REPARSE_INTERVAL_SECONDS:
        proxy_entries.clear()
        proxy_line_map.clear()
        proxy_log_position = 0
        _proxy_jsonl_position = 0
        _proxy_cache_turns = []
        _proxy_fwd_pos = 0
        _proxy_acc_fwd.clear()
        _last_full_parse_ts = now
        _proxy_stripped_pos = 0
        _proxy_injected_pos = 0
        _proxy_acc_stripped.clear()
        _proxy_acc_injected.clear()
        input_changed = True
    new_entries, _proxy_fwd_pos = parse_proxy_log_forwarded(
        monitor.active_project_filter, _proxy_fwd_pos, _proxy_acc_fwd
    )
    filtered = [e for e in new_entries if e.get('timestamp', '') >= _proxy_session_start_ts]
    proxy_entries.extend(filtered)
    _proxy_log_path = find_proxy_log_path(monitor.active_project_filter)
    # Accumulate dual-logs and attach references to all newly-added entries.
    # Entries hold a Python reference to the acc dict; in-place mutations propagate automatically.
    stripped_path, injected_path = _find_dual_log_paths(_proxy_log_path)
    _proxy_stripped_pos = accumulate_dual_log(stripped_path, _proxy_stripped_pos, _proxy_acc_stripped)
    _proxy_injected_pos = accumulate_dual_log(injected_path, _proxy_injected_pos, _proxy_acc_injected)
    for entry in filtered:
        family = _infer_model_family(entry.get('model', ''))
        if family not in _proxy_acc_stripped:
            _proxy_acc_stripped[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}, '_fns_by_flow_id': {}}
            _proxy_acc_injected[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}, '_fns_by_flow_id': {}}
        entry['_stripped_spans'] = _proxy_acc_stripped[family]
        entry['_injected_spans'] = _proxy_acc_injected[family]
        entry['_strip_fns_lookup'] = _proxy_acc_stripped[family].setdefault('_fns_by_flow_id', {})
        entry['_inject_fns_lookup'] = _proxy_acc_injected[family].setdefault('_fns_by_flow_id', {})
    _strip_inactive_messages(proxy_entries, proxy_expand_states)
    main_sessions = monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _proxy_cache_turns, _proxy_jsonl_position = build_cache_turns(
            filepath, _proxy_jsonl_position, _proxy_cache_turns
        )
    return True, now

# Build ANSI output for proxy pane; auto-scrolls to just_expanded entry; clears _proxy_just_expanded
def _build_proxy_output() -> str:
    global proxy_scroll_offset, _proxy_pane_width, _proxy_copy_rows, _proxy_just_expanded
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
    output, total_lines = format_proxy_block(
        proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row,
        pane_height, pane_width, proxy_scroll_offset,
        turns=_proxy_cache_turns, item_positions_out=item_positions,
        copy_feedback=_copy_feedback_until, copy_rows_out=_proxy_copy_rows,
    )
    if _proxy_just_expanded is not None and _proxy_just_expanded in item_positions:
        item_line = item_positions[_proxy_just_expanded]
        viewport_lines_n = pane_height - 1
        max_scroll = max(0, total_lines - viewport_lines_n)
        clamped = min(proxy_scroll_offset, max_scroll)
        start = max(0, total_lines - viewport_lines_n - clamped)
        if item_line < start or item_line >= start + viewport_lines_n:
            proxy_scroll_offset = max(0, total_lines - viewport_lines_n - item_line)
            _proxy_copy_rows.clear()
            output, total_lines = format_proxy_block(
                proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row,
                pane_height, pane_width, proxy_scroll_offset,
                turns=_proxy_cache_turns,
                copy_feedback=_copy_feedback_until, copy_rows_out=_proxy_copy_rows,
            )
    _proxy_just_expanded = None
    return output
