# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
import os
import time

from ..constants import (
    RESET, YELLOW, DIM,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from .parser import parse_proxy_log, find_worker_proxy_log, _parse_log_file
from .format import format_proxy_block
from ..token_pane import build_cache_turns
from ..click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

proxy_entries: List[dict] = []
proxy_expand_states: Dict[int, bool] = {}
proxy_line_map: Dict[int, int] = {}
proxy_hover_row: Optional[int] = None
proxy_scroll_offset: int = 0
proxy_log_position: int = 0

_proxy_jsonl_position: int = 0
_proxy_cache_turns: list = []

worker_proxy_entries: List[dict] = []
worker_proxy_expand_states: Dict[int, bool] = {}
worker_proxy_line_map: Dict[int, int] = {}
worker_proxy_hover_row: Optional[int] = None
worker_proxy_scroll_offset: int = 0
worker_proxy_log_position: int = 0

# FUNCTIONS

# Runs proxy pane display loop — reads api_requests.jsonl, shows expandable entries
def run_proxy_loop() -> None:
    from .. import monitor as _monitor
    global proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, proxy_scroll_offset, proxy_log_position
    global _proxy_jsonl_position, _proxy_cache_turns
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
                                proxy_expand_states[key] = not proxy_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            proxy_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
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
                    input_changed = True
                new_entries, proxy_log_position = parse_proxy_log(_monitor.active_project_filter, proxy_log_position)
                filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
                proxy_entries.extend(filtered)
                main_sessions = _monitor.get_main_session_files()
                if main_sessions:
                    filepath = main_sessions[0]
                    _proxy_cache_turns, _proxy_jsonl_position = build_cache_turns(filepath, _proxy_jsonl_position, _proxy_cache_turns)
                if filtered and _proxy_cache_turns:
                    latest_turn_key = ('turn', len(_proxy_cache_turns) - 1)
                    if latest_turn_key not in proxy_expand_states:
                        proxy_expand_states[latest_turn_key] = True
                last_data_refresh = now
                input_changed = True

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                output = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, pane_height, pane_width, proxy_scroll_offset, turns=_proxy_cache_turns)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# Runs worker-proxy pane — reads selected worker's proxy log and shows expandable entries
def run_worker_proxy_loop() -> None:
    from .. import monitor as _monitor
    from ..worker_pane import get_selection_file_path
    global worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, worker_proxy_hover_row, worker_proxy_scroll_offset, worker_proxy_log_position
    last_output = None
    last_data_refresh = 0.0
    last_worker_name: Optional[str] = None
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
                            key = worker_proxy_line_map.get(row)
                            if key is not None:
                                worker_proxy_expand_states[key] = not worker_proxy_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            worker_proxy_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            worker_proxy_scroll_offset = max(0, worker_proxy_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            worker_proxy_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                sel_path = get_selection_file_path(_monitor.active_project_filter)
                worker_name: Optional[str] = None
                try:
                    with open(sel_path, 'r', encoding='utf-8') as f:
                        worker_name = f.read().strip() or None
                except OSError:
                    worker_name = None

                if worker_name != last_worker_name:
                    worker_proxy_entries.clear()
                    worker_proxy_expand_states.clear()
                    worker_proxy_line_map.clear()
                    worker_proxy_scroll_offset = 0
                    worker_proxy_hover_row = None
                    worker_proxy_log_position = 0
                    last_worker_name = worker_name
                    input_changed = True

                if worker_name:
                    log_path = find_worker_proxy_log(worker_name)
                    if log_path:
                        new_entries, worker_proxy_log_position = _parse_log_file(log_path, worker_proxy_log_position)
                        worker_proxy_entries.extend(new_entries)
                        if new_entries:
                            input_changed = True

                last_data_refresh = now

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

                if not current_worker:
                    output = f"{YELLOW}Select a worker in the Workers pane{RESET}"
                elif not worker_proxy_entries:
                    output = f"{YELLOW}Worker: {current_worker}{RESET}\n{DIM}No proxy data yet — is worker proxy running?{RESET}"
                else:
                    output = format_proxy_block(worker_proxy_entries, worker_proxy_expand_states, worker_proxy_line_map, worker_proxy_hover_row, pane_height, pane_width, worker_proxy_scroll_offset, turns=None)

                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
