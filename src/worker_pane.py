# INFRASTRUCTURE
from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import os
import time

from .constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from .jsonl_parser import read_new_lines, parse_jsonl_lines
from .jsonl_cache_turns import extract_cache_turns
from .click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)
# From worker_format.py: Worker data extraction and block rendering
from .worker_format import extract_worker_tokens, format_workers_block
# From worker_tmux.py: tmux session discovery and status detection
from .worker_tmux import list_workers, find_worker_jsonl

worker_expand_states: Dict[str, bool] = {}
worker_scroll_offsets: Dict[str, int] = {}
worker_line_map: Dict[int, str] = {}
worker_hover_row: Optional[int] = None
worker_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
worker_cache_line_map: Dict[int, tuple] = {}
worker_selected_name: Optional[str] = None

# FUNCTIONS

# Build path to the selection IPC file for the given project (shared with proxy/metadata panes)
def get_selection_file_path(project_filter: Optional[str]) -> str:
    if project_filter:
        normalized = os.path.normpath(os.path.expanduser(project_filter))
        project_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
    else:
        project_hash = 'global'
    return f"/tmp/monitor_cc_selected_worker_{project_hash}.txt"

# Write selected worker name to IPC selection file
def _write_selection(project_filter: Optional[str], name: Optional[str]) -> None:
    path = get_selection_file_path(project_filter)
    try:
        if name:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(name)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

# Runs workers display loop (for dedicated workers tmux pane)
def run_workers_loop() -> None:
    from . import monitor as _monitor
    global worker_expand_states, worker_scroll_offsets, worker_line_map, worker_hover_row, worker_cache_expand_states, worker_cache_line_map, worker_selected_name
    _monitor.ui_mode_active = True
    last_output = None
    workers = []
    worker_turns: Dict[str, list] = {}
    last_data_refresh = 0.0
    frozen = False
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
                        button, col, row = event
                        if button == 0:
                            cache_key = worker_cache_line_map.get(row)
                            if cache_key:
                                w_name, t_idx, c_idx = cache_key
                                states = worker_cache_expand_states.setdefault(w_name, {})
                                states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
                                input_changed = True
                            else:
                                name = worker_line_map.get(row)
                                if name:
                                    is_now_expanded = not worker_expand_states.get(name, False)
                                    worker_expand_states[name] = is_now_expanded
                                    if is_now_expanded:
                                        worker_scroll_offsets[name] = 0
                                    input_changed = True
                        elif button == 64:
                            name = worker_line_map.get(row)
                            if name:
                                worker_scroll_offsets[name] = worker_scroll_offsets.get(name, 0) + 3
                                input_changed = True
                        elif button == 65:
                            name = worker_line_map.get(row)
                            if name:
                                worker_scroll_offsets[name] = max(0, worker_scroll_offsets.get(name, 0) - 3)
                                input_changed = True
                        elif button >= 32:
                            worker_hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            if 1 <= idx <= len(workers):
                                name = workers[idx - 1]['name']
                                is_now_expanded = not worker_expand_states.get(name, False)
                                worker_expand_states[name] = is_now_expanded
                                if is_now_expanded:
                                    worker_scroll_offsets[name] = 0
                                worker_selected_name = name
                                _write_selection(_monitor.active_project_filter, name)
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                workers = list_workers(_monitor.active_project_filter) if _monitor.active_project_filter else []
                if worker_selected_name is None and workers:
                    worker_selected_name = workers[0]['name']
                    _write_selection(_monitor.active_project_filter, worker_selected_name)
                worker_turns = {}
                for w in workers:
                    name = w.get('name', '')
                    jsonl_path = find_worker_jsonl(w.get('session', ''))
                    if jsonl_path:
                        w['tokens'] = extract_worker_tokens(jsonl_path)
                        if worker_expand_states.get(name, False):
                            lines = read_new_lines(jsonl_path, 0)
                            messages, _ = parse_jsonl_lines(lines)
                            worker_turns[name] = extract_cache_turns(messages)
                last_data_refresh = now
                input_changed = True
            elif input_changed:
                for w in workers:
                    name = w.get('name', '')
                    if worker_expand_states.get(name, False) and name not in worker_turns:
                        jsonl_path = find_worker_jsonl(w.get('session', ''))
                        if jsonl_path:
                            lines = read_new_lines(jsonl_path, 0)
                            messages, _ = parse_jsonl_lines(lines)
                            worker_turns[name] = extract_cache_turns(messages)

            output = format_workers_block(workers, worker_expand_states, worker_turns, worker_line_map, worker_hover_row, worker_scroll_offsets, worker_cache_expand_states, worker_cache_line_map, frozen=frozen, selected_name=worker_selected_name)
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
