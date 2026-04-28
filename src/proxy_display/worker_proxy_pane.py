# INFRASTRUCTURE
from typing import Dict, List, Optional
import os
import time

from ..constants import (
    RESET, YELLOW, DIM, WHITE,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from .parser import find_worker_proxy_log, _parse_log_file
from .format import format_proxy_block
from ..panes.token_pane import build_cache_turns
from ..workers.worker_tmux import find_worker_jsonl, list_workers
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
_worker_proxy_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge

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

# Runs worker-proxy pane — reads selected worker's proxy log and shows expandable entries
def run_worker_proxy_loop() -> None:
    from ..core import monitor as _monitor
    from ..workers.worker_pane import get_selection_file_path
    from ..workers import write_selection
    global worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, worker_proxy_hover_row, worker_proxy_scroll_offset, worker_proxy_log_position
    global _worker_proxy_jsonl_position, _worker_proxy_cache_turns
    global _worker_proxy_workers, _worker_proxy_force_reload, _worker_proxy_pending_by_rid

    def _ram_state():
        return [
            ('worker_proxy_entries',          worker_proxy_entries),
            ('worker_proxy_expand_states',    worker_proxy_expand_states),
            ('worker_proxy_line_map',         worker_proxy_line_map),
            ('_worker_proxy_cache_turns',     _worker_proxy_cache_turns),
            ('_worker_proxy_workers',         _worker_proxy_workers),
            ('_worker_proxy_pending_by_rid',  _worker_proxy_pending_by_rid),
            ('worker_proxy_hover_row',        str(worker_proxy_hover_row)),
            ('worker_proxy_scroll_offset',    worker_proxy_scroll_offset),
            ('worker_proxy_log_position',     worker_proxy_log_position),
            ('_worker_proxy_jsonl_position',  _worker_proxy_jsonl_position),
            ('_worker_proxy_force_reload',    _worker_proxy_force_reload),
        ]
    register_ram_dump('worker_proxy', _ram_state)
    last_output = None
    last_data_refresh = 0.0
    last_worker_name: Optional[str] = None
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
                            key = worker_proxy_line_map.get(row)
                            if key is not None:
                                new_state = not worker_proxy_expand_states.get(key, False)
                                worker_proxy_expand_states[key] = new_state
                                if new_state:
                                    just_expanded = key
                                input_changed = True
                        elif button == 64:  # wheel up → older content
                            worker_proxy_scroll_offset = max(0, worker_proxy_scroll_offset + 3)
                            input_changed = True
                        elif button == 65:  # wheel down → newer content
                            worker_proxy_scroll_offset = max(0, worker_proxy_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            worker_proxy_hover_row = row
                            input_changed = True
                else:
                    if char == 'y':
                        key = resolve_parent_key(worker_proxy_line_map, worker_proxy_hover_row)
                        if key is not None:
                            copy_to_clipboard(_serialize_worker_proxy(key))
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None and _worker_proxy_workers:
                            if 1 <= idx <= len(_worker_proxy_workers):
                                write_selection(_monitor.active_project_filter, _worker_proxy_workers[idx - 1]['name'])
                                _worker_proxy_force_reload = True
                                input_changed = True

            now = time.time()
            if _worker_proxy_force_reload or now - last_data_refresh >= POLL_INTERVAL:
                _worker_proxy_force_reload = False
                sel_path = get_selection_file_path(_monitor.active_project_filter)
                worker_name: Optional[str] = None
                try:
                    with open(sel_path, 'r', encoding='utf-8') as f:
                        worker_name = f.read().strip() or None
                except OSError:
                    worker_name = None

                _worker_proxy_workers = list_workers(_monitor.active_project_filter) if _monitor.active_project_filter else []

                # Force worker_name to None when no workers exist or selection is stale
                if not _worker_proxy_workers:
                    worker_name = None
                elif worker_name is not None and worker_name not in {w['name'] for w in _worker_proxy_workers}:
                    worker_name = None

                if worker_name != last_worker_name:
                    worker_proxy_entries.clear()
                    worker_proxy_expand_states.clear()
                    worker_proxy_line_map.clear()
                    worker_proxy_scroll_offset = 0
                    worker_proxy_hover_row = None
                    worker_proxy_log_position = 0
                    _worker_proxy_jsonl_position = 0
                    _worker_proxy_cache_turns = []
                    _worker_proxy_pending_by_rid.clear()
                    last_worker_name = worker_name
                    input_changed = True

                if worker_name:
                    new_entries: list = []
                    log_path = find_worker_proxy_log(worker_name, _monitor.active_project_filter)
                    if log_path:
                        new_entries, worker_proxy_log_position = _parse_log_file(log_path, worker_proxy_log_position, _worker_proxy_pending_by_rid)
                        worker_proxy_entries.extend(new_entries)
                        if new_entries:
                            input_changed = True
                    worker_session = next((w.get('session', '') for w in _worker_proxy_workers if w.get('name') == worker_name), '')
                    worker_jsonl = find_worker_jsonl(worker_session) if worker_session else None
                    if worker_jsonl:
                        _worker_proxy_cache_turns, _worker_proxy_jsonl_position = build_cache_turns(worker_jsonl, _worker_proxy_jsonl_position, _worker_proxy_cache_turns)
                last_data_refresh = now
                input_changed = True

            if input_changed:
                sel_path = get_selection_file_path(_monitor.active_project_filter)
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

                header = _format_worker_proxy_header(_worker_proxy_workers, current_worker)
                header_lines = visual_line_count(header, pane_width)
                content_height = max(1, pane_height - header_lines)
                # Body starts at terminal row header_lines+1 (header may wrap to multiple rows).
                # Subtract header_lines from hover_row so format_proxy_block sees a 1-indexed body row.
                body_hover = (worker_proxy_hover_row - header_lines) if worker_proxy_hover_row and worker_proxy_hover_row > header_lines else None

                if not current_worker:
                    body = f"{DIM}Select a worker with digit keys 1-9{RESET}"
                elif not worker_proxy_entries:
                    body = f"{YELLOW}Worker: {current_worker}{RESET}\n{DIM}No proxy data yet — is worker proxy running?{RESET}"
                else:
                    worker_item_positions: dict = {}
                    body, total_lines = format_proxy_block(worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, body_hover, content_height, pane_width, worker_proxy_scroll_offset, turns=_worker_proxy_cache_turns, item_positions_out=worker_item_positions)
                    # Shift line_map by +1: body row N is at terminal row N+1 due to header
                    shifted = {r + header_lines: k for r, k in worker_proxy_line_map.items()}
                    worker_proxy_line_map.clear()
                    worker_proxy_line_map.update(shifted)
                    if just_expanded is not None and just_expanded in worker_item_positions:
                        item_line = worker_item_positions[just_expanded]
                        max_scroll = max(0, total_lines - content_height)
                        clamped = min(worker_proxy_scroll_offset, max_scroll)
                        start = max(0, total_lines - content_height - clamped)
                        if item_line < start or item_line >= start + content_height:
                            worker_proxy_scroll_offset = max(0, total_lines - content_height - item_line)
                            body, total_lines = format_proxy_block(worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, body_hover, content_height, pane_width, worker_proxy_scroll_offset, turns=_worker_proxy_cache_turns)
                            shifted = {r + header_lines: k for r, k in worker_proxy_line_map.items()}
                            worker_proxy_line_map.clear()
                            worker_proxy_line_map.update(shifted)
                output = header + '\n' + body

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
