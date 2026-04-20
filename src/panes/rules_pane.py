# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
import os
import time

from ..constants import (
    RESET, CYAN, YELLOW,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
    HOOK_INSTRUCTIONS_LOADED,
)
from ..utils import format_timestamp
from ..hooks import parse_new_hook_entries, filter_by_project, filter_by_timestamp
from ..click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

active_rules: Dict[str, set] = {'project': set(), 'global': set()}
rules_invokers: Dict[str, Dict[str, str]] = {}
rules_expand_states: Dict[str, bool] = {}
rules_line_map: Dict[int, str] = {}
rules_hover_row: Optional[int] = None
rules_scroll_offset: int = 0
rules_total_lines: int = 0
session_start_ts: Optional[str] = None

# FUNCTIONS

# Derive source label from cwd path
def derive_rule_source(cwd: str) -> str:
    if not cwd:
        return 'unknown'
    worktree_marker = '/.claude/worktrees/'
    idx = cwd.find(worktree_marker)
    if idx >= 0:
        remainder = cwd[idx + len(worktree_marker):]
        worker_name = remainder.split('/')[0]
        return f'worker:{worker_name}'
    return 'main'

# Record a rule and its invoker from a hook entry
def record_rule_invoker(entry: dict) -> None:
    output = entry.get('output', '')
    if not output:
        return
    if output.startswith('[P]'):
        active_rules['project'].add(output[4:])
        rule_key = output
    elif output.startswith('[G]'):
        active_rules['global'].add(output[4:])
        rule_key = output
    else:
        return
    cwd = entry.get('cwd', '')
    source = derive_rule_source(cwd)
    ts = format_timestamp(entry.get('timestamp', ''))
    if rule_key not in rules_invokers:
        rules_invokers[rule_key] = {}
    rules_invokers[rule_key][source] = ts

# Build sorted list of all rule keys ([P]/[G] prefixed)
def _get_sorted_rule_keys() -> List[str]:
    project_keys = [f'[P] {r}' for r in sorted(active_rules.get('project', set()))]
    global_keys = [f'[G] {r}' for r in sorted(active_rules.get('global', set()))]
    return project_keys + global_keys

# Process hook log for InstructionsLoaded entries (rules pane routing)
def process_hook_log() -> None:
    from . import monitor as _monitor
    entries, new_pos = parse_new_hook_entries(_monitor.hook_log_position)
    _monitor.hook_log_position = new_pos
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    for entry in filtered:
        if entry.get('hook_event') == HOOK_INSTRUCTIONS_LOADED:
            record_rule_invoker(entry)

# Load historical rules from hook log (with invoker data from cwd), session-scoped
def load_historical_rules() -> None:
    from . import monitor as _monitor
    global active_rules, rules_invokers
    active_rules['project'].clear()
    active_rules['global'].clear()
    rules_invokers.clear()
    entries, new_pos = parse_new_hook_entries(0)
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    if session_start_ts:
        filtered = filter_by_timestamp(filtered, session_start_ts)
    for entry in filtered:
        if entry.get('hook_event') == HOOK_INSTRUCTIONS_LOADED:
            record_rule_invoker(entry)
    _monitor.hook_log_position = new_pos

# Runs rules-only display loop (for dedicated rules tmux pane)
def run_rules_loop() -> None:
    from . import monitor as _monitor
    from .ui_mode import format_rules_block
    global rules_expand_states, rules_line_map, rules_hover_row, rules_scroll_offset, rules_total_lines, session_start_ts
    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    load_historical_rules()
    current_main_session = _monitor._get_newest_main_session()
    last_output = None
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
                        button, _col, row = event
                        if button == 0:
                            rule_key = rules_line_map.get(row)
                            if rule_key:
                                rules_expand_states[rule_key] = not rules_expand_states.get(rule_key, False)
                                input_changed = True
                        elif button == 64:
                            rules_scroll_offset = min(rules_scroll_offset + 3, max(0, rules_total_lines - 5))
                            input_changed = True
                        elif button == 65:
                            rules_scroll_offset = max(0, rules_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            rules_hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            all_keys = _get_sorted_rule_keys()
                            if 1 <= idx <= len(all_keys):
                                rule_key = all_keys[idx - 1]
                                rules_expand_states[rule_key] = not rules_expand_states.get(rule_key, False)
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    session_start_ts = _monitor._get_session_start_ts()
                    if session_start_ts is None:
                        session_start_ts = datetime.utcnow().isoformat() + 'Z'
                    load_historical_rules()
                    input_changed = True
                process_hook_log()
                last_data_refresh = now

            output, rules_total_lines = format_rules_block(active_rules, rules_invokers, rules_expand_states, rules_line_map, rules_hover_row, rules_scroll_offset, frozen)
            if output != last_output:
                print("\033[2J\033[3J\033[H", end='', flush=True)
                if output:
                    print(output)
                last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
