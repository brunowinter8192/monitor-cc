# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
import os
import time

from .constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from .hook_parser import parse_new_hook_entries, filter_by_project, filter_by_timestamp
from .click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)
# From hooks_format.py: Hook entry formatting and block rendering
from .hooks_format import _is_noise_entry, build_hook_display_item, format_hooks_block
# From hooks_persist.py: Persisted additionalContext enrichment
from .hooks_persist import scan_persisted_hook_files, enrich_with_persisted

hooks_display_items: List[dict] = []
hooks_hover_row: Optional[int] = None
hooks_line_map: Dict[int, int] = {}
hooks_scroll_offset: int = 0
hooks_total_lines: int = 0
session_start_ts: Optional[str] = None

# FUNCTIONS

# Load historical hook entries into hooks_display_items, session-scoped
def load_historical_hooks() -> None:
    from . import monitor as _monitor
    global session_start_ts
    entries, new_pos = parse_new_hook_entries(0)
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    if session_start_ts:
        filtered = filter_by_timestamp(filtered, session_start_ts)
    items = [build_hook_display_item(e) for e in filtered if not _is_noise_entry(e)]
    extra = enrich_with_persisted(items, scan_persisted_hook_files(_monitor.active_project_filter), session_start_ts)
    for item in items + extra:
        hooks_display_items.append(item)
    _monitor.hook_log_position = new_pos

# Append new hook log entries to hooks_display_items
def process_hook_log_for_display() -> None:
    from . import monitor as _monitor
    entries, new_pos = parse_new_hook_entries(_monitor.hook_log_position)
    _monitor.hook_log_position = new_pos
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    new_items = [build_hook_display_item(e) for e in filtered if not _is_noise_entry(e)]
    if new_items:
        extra = enrich_with_persisted(new_items, scan_persisted_hook_files(_monitor.active_project_filter), session_start_ts)
        for item in new_items + extra:
            hooks_display_items.append(item)

# Runs hooks display loop with mouse scroll, click expand/collapse, hover — tokens pane pattern
def run_hooks_loop() -> None:
    from . import monitor as _monitor
    global session_start_ts, hooks_display_items, hooks_hover_row, hooks_line_map, hooks_scroll_offset, hooks_total_lines
    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    hooks_display_items.clear()
    load_historical_hooks()
    hooks_display_items.sort(key=lambda x: x.get('timestamp', ''))
    current_main_session = _monitor._get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    force_initial_render = True
    setup_keyboard_input()
    enable_mouse()
    try:
        just_expanded_idx = None
        while True:
            input_changed = False
            just_expanded_idx = None
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, _col, row = event
                        if button == 0:
                            item_idx = hooks_line_map.get(row)
                            if item_idx is not None and 0 <= item_idx < len(hooks_display_items):
                                was_expanded = hooks_display_items[item_idx].get('expanded', False)
                                hooks_display_items[item_idx]['expanded'] = not was_expanded
                                input_changed = True
                                if not was_expanded:
                                    just_expanded_idx = item_idx
                        elif button == 64:
                            hooks_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            hooks_scroll_offset = max(0, hooks_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            hooks_hover_row = row
                            input_changed = True
                else:
                    if char == 'a':
                        for item in hooks_display_items:
                            item['expanded'] = True
                        input_changed = True
                    elif char == 'A':
                        for item in hooks_display_items:
                            item['expanded'] = False
                        input_changed = True
            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    session_start_ts = _monitor._get_session_start_ts()
                    if session_start_ts is None:
                        session_start_ts = datetime.utcnow().isoformat() + 'Z'
                    hooks_display_items.clear()
                    hooks_scroll_offset = 0
                    hooks_hover_row = None
                    load_historical_hooks()
                    hooks_display_items.sort(key=lambda x: x.get('timestamp', ''))
                    input_changed = True
                else:
                    old_count = len(hooks_display_items)
                    process_hook_log_for_display()
                    if len(hooks_display_items) != old_count:
                        input_changed = True
                last_data_refresh = now
            if force_initial_render and hooks_display_items:
                input_changed = True
                force_initial_render = False
            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                item_positions: dict = {}
                output, hooks_total_lines = format_hooks_block(hooks_display_items, hooks_line_map, hooks_hover_row, hooks_scroll_offset, pane_height, pane_width, item_positions)
                if just_expanded_idx is not None and just_expanded_idx in item_positions:
                    item_line = item_positions[just_expanded_idx]
                    viewport_lines = pane_height - 1
                    max_scroll = max(0, hooks_total_lines - viewport_lines)
                    clamped = min(hooks_scroll_offset, max_scroll)
                    start = max(0, hooks_total_lines - viewport_lines - clamped)
                    if item_line < start or item_line >= start + viewport_lines:
                        hooks_scroll_offset = max(0, hooks_total_lines - viewport_lines - item_line)
                        output, hooks_total_lines = format_hooks_block(hooks_display_items, hooks_line_map, hooks_hover_row, hooks_scroll_offset, pane_height, pane_width)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
