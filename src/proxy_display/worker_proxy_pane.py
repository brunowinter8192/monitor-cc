# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, List, Optional, Set
import os
import time

from ..constants import (
    RESET, YELLOW, DIM, WHITE,
    POLL_INTERVAL, INPUT_POLL_INTERVAL, PROXY_MESSAGES_KEEP_LAST,
    PROXY_REPARSE_INTERVAL_SECONDS,
)
from .parser import (
    find_worker_proxy_log, _parse_forwarded_log, _lazy_load_messages_forwarded,
    accumulate_dual_log, _find_dual_log_paths, _infer_model_family,
)
from .format import format_proxy_block, _is_standalone_entry
from ..panes.token_pane import build_cache_turns
from ..workers.worker_tmux import find_worker_jsonl, list_workers
from ..workers.worker_pane import get_selection_file_path
from ..workers import write_selection
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event, parse_digit_key,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from ..utils import visual_line_count
from ..ram_audit import register_ram_dump

worker_proxy_entries: List[dict] = []
worker_proxy_expand_states: Dict[int, bool] = {}
worker_proxy_line_map: Dict[int, int] = {}
worker_proxy_hover_row: Optional[int] = None
worker_proxy_scroll_offset: int = 0
worker_proxy_log_position: int = 0

_worker_proxy_jsonl_position: int = 0
_worker_proxy_cache_turns: list = []
_worker_proxy_workers: list = []
_worker_proxy_force_reload: bool = False
_worker_proxy_fwd_pos: int = 0          # forwarded-log byte position for incremental reads
_worker_proxy_acc_fwd: dict = {}        # family accumulator for _parse_forwarded_log
_worker_proxy_log_path: Optional[Path] = None  # current log file path, updated each poll cycle for lazy-reload
_worker_proxy_pane_width: int = 80  # updated each render cycle; used by click handler for copy-button column check
_worker_proxy_copy_rows: Set[int] = set()  # phys_rows where ⎘ copy button is rendered; populated by format_proxy_block
_worker_copy_feedback_until: Dict[int, float] = {}  # entry_idx → expiry timestamp for ✓ flash
_worker_proxy_last_full_parse_ts: float = 0.0  # timestamp of last re-init to position 0 (time-triggered reset)
_wp_just_expanded = None  # line_map key set by mouse handler on expand; cleared by _build_worker_proxy_output
_worker_proxy_last_worker_name: Optional[str] = None  # tracks worker change for full state reset
_worker_proxy_stripped_pos: int = 0    # dual-log read position for _stripped.jsonl
_worker_proxy_injected_pos: int = 0    # dual-log read position for _injected.jsonl
_worker_proxy_acc_stripped: dict = {}  # family → {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
_worker_proxy_acc_injected: dict = {}  # same; entries hold Python refs so in-place updates propagate

# ORCHESTRATOR

# Runs worker-proxy pane — reads selected worker's proxy log and shows expandable entries
def run_worker_proxy_loop() -> None:
    from ..core import monitor as _monitor
    global _worker_copy_feedback_until

    register_ram_dump('worker_proxy', _worker_proxy_ram_state)
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
                        if _handle_worker_proxy_mouse(*event):
                            input_changed = True
                else:
                    if _handle_worker_proxy_key(char, _monitor):
                        input_changed = True

            now = time.time()
            input_changed, last_data_refresh = _refresh_worker_proxy_data(
                now, input_changed, last_data_refresh, _monitor
            )

            _worker_copy_feedback_until = {k: v for k, v in _worker_copy_feedback_until.items() if v > now}
            if _worker_copy_feedback_until:
                input_changed = True

            if input_changed:
                output, header = _build_worker_proxy_output(_monitor)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output, end='', flush=True)
                        print(f"\033[H{header}\033[K", end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Build header line for worker-proxy pane listing workers with current selection marked
def _format_worker_proxy_header(workers: list, current_worker: Optional[str]) -> str:
    label = f"{YELLOW}WORKER-PROXY{RESET}  "
    if not workers:
        return label + f"{DIM}no workers{RESET}"
    parts = []
    for i, w in enumerate(workers, 1):
        name = w['name']
        star = '*' if name == current_worker else ''
        if name == current_worker:
            parts.append(f"{WHITE}[{i}{star}]{name}{RESET}")
        else:
            parts.append(f"{DIM}[{i}]{name}{RESET}")
    return label + '  '.join(parts)

# Extract entry_idx from any proxy line_map key variant (shared with pane.py pattern)
def _wp_entry_idx_from_key(key) -> Optional[int]:
    if isinstance(key, int):
        return key
    if isinstance(key, tuple):
        if isinstance(key[0], str):
            return key[1]
        if isinstance(key[0], int):
            return key[0]
    return None

# Serialize a worker-proxy entry to full untruncated text for clipboard
def _serialize_worker_proxy(key) -> str:
    import json
    entry_idx = _wp_entry_idx_from_key(key)
    if entry_idx is None or entry_idx >= len(worker_proxy_entries):
        return ''
    entry = worker_proxy_entries[entry_idx]
    model = entry.get('model', '?')
    msg_count = entry.get('message_count', 0)
    parts = [f"entry_idx={entry_idx}  model={model}  msgs={msg_count}"]
    prev_same_idx = _resolve_prev_same_wp(worker_proxy_entries, entry_idx)
    start = worker_proxy_entries[prev_same_idx].get('message_count', 0) if prev_same_idx is not None else 0
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
def _resolve_prev_same_wp(entries: list, k: int) -> Optional[int]:
    for i in range(k - 1, -1, -1):
        if not _is_standalone_entry(entries[i]):
            return i
    return None

# Strip messages from all entries outside the keep-last window that are not expanded
def _strip_inactive_wp_messages(entries: list, expand_states: dict) -> None:
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
def _worker_proxy_ram_state() -> list:
    return [
        ('worker_proxy_entries',          worker_proxy_entries),
        ('worker_proxy_expand_states',    worker_proxy_expand_states),
        ('worker_proxy_line_map',         worker_proxy_line_map),
        ('_worker_proxy_cache_turns',     _worker_proxy_cache_turns),
        ('_worker_proxy_workers',         _worker_proxy_workers),
        ('_worker_proxy_fwd_pos',         _worker_proxy_fwd_pos),
        ('_worker_proxy_acc_fwd',         _worker_proxy_acc_fwd),
        ('worker_proxy_hover_row',        str(worker_proxy_hover_row)),
        ('worker_proxy_scroll_offset',    worker_proxy_scroll_offset),
        ('worker_proxy_log_position',     worker_proxy_log_position),
        ('_worker_proxy_jsonl_position',  _worker_proxy_jsonl_position),
        ('_worker_proxy_force_reload',    _worker_proxy_force_reload),
        ('_worker_proxy_stripped_pos',    _worker_proxy_stripped_pos),
        ('_worker_proxy_injected_pos',    _worker_proxy_injected_pos),
        ('_worker_proxy_acc_stripped',    _worker_proxy_acc_stripped),
        ('_worker_proxy_acc_injected',    _worker_proxy_acc_injected),
    ]

# Process one mouse event; returns True if display should refresh
def _handle_worker_proxy_mouse(button: int, col: int, row: int) -> bool:
    global worker_proxy_expand_states, worker_proxy_scroll_offset, worker_proxy_hover_row
    global _wp_just_expanded, _worker_copy_feedback_until
    if button == 0:
        key = worker_proxy_line_map.get(row)
        if key is None:
            return False
        is_req = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
        if is_req and col >= _worker_proxy_pane_width - 2 and row in _worker_proxy_copy_rows:
            entry_idx = _wp_entry_idx_from_key(key)
            if entry_idx is not None and entry_idx < len(worker_proxy_entries) and _worker_proxy_log_path:
                e = worker_proxy_entries[entry_idx]
                if e.get('messages') is None:
                    fwd_path = _worker_proxy_log_path.parent / 'dual_log' / f'{_worker_proxy_log_path.stem}_forwarded.jsonl'
                    _lazy_load_messages_forwarded(e, fwd_path)
            copy_to_clipboard(_serialize_worker_proxy(key))
            if entry_idx is not None:
                _worker_copy_feedback_until[entry_idx] = time.time() + 1.5
        else:
            new_state = not worker_proxy_expand_states.get(key, False)
            worker_proxy_expand_states[key] = new_state
            if new_state:
                entry_idx = _wp_entry_idx_from_key(key)
                if entry_idx is not None and entry_idx < len(worker_proxy_entries) and _worker_proxy_log_path:
                    e = worker_proxy_entries[entry_idx]
                    fwd_path = _worker_proxy_log_path.parent / 'dual_log' / f'{_worker_proxy_log_path.stem}_forwarded.jsonl'
                    if e.get('messages') is None:
                        _lazy_load_messages_forwarded(e, fwd_path)
                    prev_idx = _resolve_prev_same_wp(worker_proxy_entries, entry_idx)
                    if prev_idx is not None:
                        pe = worker_proxy_entries[prev_idx]
                        if pe.get('messages') is None:
                            _lazy_load_messages_forwarded(pe, fwd_path)
                _wp_just_expanded = key
        return True
    if button == 64:
        worker_proxy_scroll_offset = max(0, worker_proxy_scroll_offset + 3)
        return True
    if button == 65:
        worker_proxy_scroll_offset = max(0, worker_proxy_scroll_offset - 3)
        return True
    if button >= 32:
        worker_proxy_hover_row = row
        return True
    return False

# Process one digit-key event; writes worker selection via IPC; returns True if display should refresh
def _handle_worker_proxy_key(char: str, monitor) -> bool:
    global _worker_proxy_force_reload
    idx = parse_digit_key(char)
    if idx is not None and _worker_proxy_workers:
        if 1 <= idx <= len(_worker_proxy_workers):
            write_selection(monitor.active_project_filter, _worker_proxy_workers[idx - 1]['name'])
            _worker_proxy_force_reload = True
            return True
    return False

# Tick-boundary worker-proxy data refresh; returns (input_changed, new_last_data_refresh)
def _refresh_worker_proxy_data(now: float, input_changed: bool, last_data_refresh: float, monitor) -> tuple:
    global worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map
    global worker_proxy_scroll_offset, worker_proxy_hover_row, worker_proxy_log_position
    global _worker_proxy_jsonl_position, _worker_proxy_cache_turns
    global _worker_proxy_fwd_pos, _worker_proxy_acc_fwd
    global _worker_proxy_log_path, _worker_proxy_last_full_parse_ts
    global _worker_proxy_workers, _worker_proxy_force_reload, _worker_proxy_last_worker_name
    global _worker_proxy_stripped_pos, _worker_proxy_injected_pos
    global _worker_proxy_acc_stripped, _worker_proxy_acc_injected
    if not _worker_proxy_force_reload and now - last_data_refresh < POLL_INTERVAL:
        return input_changed, last_data_refresh
    _worker_proxy_force_reload = False
    sel_path = get_selection_file_path(monitor.active_project_filter)
    worker_name: Optional[str] = None
    try:
        with open(sel_path, 'r', encoding='utf-8') as f:
            worker_name = f.read().strip() or None
    except OSError:
        worker_name = None
    _worker_proxy_workers = list_workers(monitor.active_project_filter) if monitor.active_project_filter else []
    if not _worker_proxy_workers:
        worker_name = None
    elif worker_name is not None and worker_name not in {w['name'] for w in _worker_proxy_workers}:
        worker_name = None
    if worker_name != _worker_proxy_last_worker_name:
        worker_proxy_entries.clear()
        worker_proxy_expand_states.clear()
        worker_proxy_line_map.clear()
        worker_proxy_scroll_offset = 0
        worker_proxy_hover_row = None
        worker_proxy_log_position = 0
        _worker_proxy_jsonl_position = 0
        _worker_proxy_cache_turns = []
        _worker_proxy_fwd_pos = 0
        _worker_proxy_acc_fwd.clear()
        _worker_proxy_log_path = None
        _worker_proxy_last_full_parse_ts = now
        _worker_proxy_last_worker_name = worker_name
        _worker_proxy_stripped_pos = 0
        _worker_proxy_injected_pos = 0
        _worker_proxy_acc_stripped.clear()
        _worker_proxy_acc_injected.clear()
        input_changed = True
    if _worker_proxy_last_full_parse_ts == 0.0:
        _worker_proxy_last_full_parse_ts = now
    elif now - _worker_proxy_last_full_parse_ts >= PROXY_REPARSE_INTERVAL_SECONDS:
        worker_proxy_entries.clear()
        worker_proxy_line_map.clear()
        worker_proxy_log_position = 0
        _worker_proxy_jsonl_position = 0
        _worker_proxy_cache_turns = []
        _worker_proxy_fwd_pos = 0
        _worker_proxy_acc_fwd.clear()
        _worker_proxy_last_full_parse_ts = now
        _worker_proxy_stripped_pos = 0
        _worker_proxy_injected_pos = 0
        _worker_proxy_acc_stripped.clear()
        _worker_proxy_acc_injected.clear()
        input_changed = True
    if worker_name:
        log_path = find_worker_proxy_log(worker_name, monitor.active_project_filter)
        if log_path:
            fwd_path = log_path.parent / 'dual_log' / f'{log_path.stem}_forwarded.jsonl'
            new_entries, _worker_proxy_fwd_pos = _parse_forwarded_log(
                fwd_path, _worker_proxy_fwd_pos, _worker_proxy_acc_fwd
            )
            for entry in new_entries:
                entry['_source_file'] = fwd_path.name
            worker_proxy_entries.extend(new_entries)
            stripped_path, injected_path = _find_dual_log_paths(log_path)
            _worker_proxy_stripped_pos = accumulate_dual_log(stripped_path, _worker_proxy_stripped_pos, _worker_proxy_acc_stripped)
            _worker_proxy_injected_pos = accumulate_dual_log(injected_path, _worker_proxy_injected_pos, _worker_proxy_acc_injected)
            for entry in new_entries:
                family = _infer_model_family(entry.get('model', ''))
                if family not in _worker_proxy_acc_stripped:
                    _worker_proxy_acc_stripped[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
                    _worker_proxy_acc_injected[family] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
                entry['_stripped_spans'] = _worker_proxy_acc_stripped[family]
                entry['_injected_spans'] = _worker_proxy_acc_injected[family]
            _worker_proxy_log_path = log_path
            _strip_inactive_wp_messages(worker_proxy_entries, worker_proxy_expand_states)
            if new_entries:
                input_changed = True
        worker_session = next(
            (w.get('session', '') for w in _worker_proxy_workers if w.get('name') == worker_name), ''
        )
        worker_jsonl = find_worker_jsonl(worker_session) if worker_session else None
        if worker_jsonl:
            _worker_proxy_cache_turns, _worker_proxy_jsonl_position = build_cache_turns(
                worker_jsonl, _worker_proxy_jsonl_position, _worker_proxy_cache_turns
            )
    return True, now

# Build ANSI output for worker-proxy pane with header+body split; returns (output, header) for overdraw
def _build_worker_proxy_output(monitor) -> tuple:
    global worker_proxy_scroll_offset, _worker_proxy_pane_width, _worker_proxy_copy_rows
    global _wp_just_expanded
    sel_path = get_selection_file_path(monitor.active_project_filter)
    current_worker: Optional[str] = None
    try:
        with open(sel_path, 'r', encoding='utf-8') as f:
            current_worker = f.read().strip() or None
    except OSError:
        current_worker = None
    try:
        term = os.get_terminal_size()
        pane_height = term.lines - 1
        pane_width = term.columns
    except OSError:
        pane_height = 50
        pane_width = 80
    _worker_proxy_pane_width = pane_width
    header = _format_worker_proxy_header(_worker_proxy_workers, current_worker)
    header_lines = visual_line_count(header, pane_width)
    content_height = max(1, pane_height - header_lines)
    body_hover = (
        (worker_proxy_hover_row - header_lines)
        if worker_proxy_hover_row and worker_proxy_hover_row > header_lines
        else None
    )
    if not current_worker:
        body = f"{DIM}Select a worker with digit keys 1-9{RESET}"
    elif not worker_proxy_entries:
        body = f"{YELLOW}Worker: {current_worker}{RESET}\n{DIM}No proxy data yet — is worker proxy running?{RESET}"
    else:
        worker_item_positions: dict = {}
        _worker_proxy_copy_rows.clear()
        body, total_lines = format_proxy_block(
            worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map,
            body_hover, content_height, pane_width, worker_proxy_scroll_offset,
            turns=_worker_proxy_cache_turns, item_positions_out=worker_item_positions,
            copy_feedback=_worker_copy_feedback_until, copy_rows_out=_worker_proxy_copy_rows,
        )
        shifted = {r + header_lines: k for r, k in worker_proxy_line_map.items()}
        worker_proxy_line_map.clear()
        worker_proxy_line_map.update(shifted)
        shifted_copy = {r + header_lines for r in _worker_proxy_copy_rows}
        _worker_proxy_copy_rows.clear()
        _worker_proxy_copy_rows.update(shifted_copy)
        if _wp_just_expanded is not None and _wp_just_expanded in worker_item_positions:
            item_line = worker_item_positions[_wp_just_expanded]
            max_scroll = max(0, total_lines - content_height)
            clamped = min(worker_proxy_scroll_offset, max_scroll)
            start = max(0, total_lines - content_height - clamped)
            if item_line < start or item_line >= start + content_height:
                worker_proxy_scroll_offset = max(0, total_lines - content_height - item_line)
                _worker_proxy_copy_rows.clear()
                body, total_lines = format_proxy_block(
                    worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map,
                    body_hover, content_height, pane_width, worker_proxy_scroll_offset,
                    turns=_worker_proxy_cache_turns,
                    copy_feedback=_worker_copy_feedback_until, copy_rows_out=_worker_proxy_copy_rows,
                )
                shifted = {r + header_lines: k for r, k in worker_proxy_line_map.items()}
                worker_proxy_line_map.clear()
                worker_proxy_line_map.update(shifted)
                shifted_copy = {r + header_lines for r in _worker_proxy_copy_rows}
                _worker_proxy_copy_rows.clear()
                _worker_proxy_copy_rows.update(shifted_copy)
    _wp_just_expanded = None
    return header + '\n' + body, header
