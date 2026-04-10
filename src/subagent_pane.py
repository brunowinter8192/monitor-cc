# INFRASTRUCTURE
from typing import Dict, Optional
from pathlib import Path
import io
import os
import sys
import time

from .constants import POLL_INTERVAL, INPUT_POLL_INTERVAL
from .jsonl_parser import read_new_lines, parse_jsonl_lines
from .session_finder import find_active_sessions
from .jsonl_cache_turns import extract_cache_turns
from .subagent_ui import subagent_states, toggle_subagent_state
from .subagent_render import render_subagents_with_tokens
from .click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event, get_agent_by_index,
)

agent_turns: Dict[str, list] = {}
agent_pane_line_map: Dict[int, str] = {}
agent_pane_hover_row: Optional[int] = None
agent_cache_scroll_offsets: Dict[str, int] = {}
agent_cache_expand_states: Dict[str, Dict[tuple, bool]] = {}
agent_cache_line_map: Dict[int, tuple] = {}

# FUNCTIONS

# Find agent JSONL file by agent_id across all active sessions
def find_agent_jsonl(agent_id: str) -> Optional[Path]:
    from . import monitor as _monitor
    sessions = find_active_sessions(_monitor.active_project_filter)
    target_name = f'agent-{agent_id}.jsonl'
    for session_file in sessions:
        if session_file.name == target_name:
            return session_file
    return None

# Find the nearest agent ID at or above a given row in the pane line map
def _find_agent_at_row(row: int, line_map: dict) -> Optional[str]:
    agent_id = line_map.get(row)
    if agent_id:
        return agent_id
    for r in range(row - 1, 0, -1):
        agent_id = line_map.get(r)
        if agent_id:
            return agent_id
    return None

# Runs subagents display loop (for dedicated subagents tmux pane, shows per-agent cache token view)
def run_subagents_loop() -> None:
    from . import monitor as _monitor
    global agent_turns, agent_pane_line_map, agent_pane_hover_row, agent_cache_scroll_offsets, agent_cache_expand_states, agent_cache_line_map
    _monitor.ui_mode_active = True
    _monitor.load_historical_subagents()
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
                        button, col, row = event
                        if button == 0:
                            cache_key = agent_cache_line_map.get(row)
                            if cache_key:
                                ag_id, t_idx, c_idx = cache_key
                                states = agent_cache_expand_states.setdefault(ag_id, {})
                                states[(t_idx, c_idx)] = not states.get((t_idx, c_idx), False)
                                input_changed = True
                            else:
                                agent_id = agent_pane_line_map.get(row)
                                if agent_id:
                                    toggle_subagent_state(agent_id)
                                    input_changed = True
                        elif button == 64:
                            agent_id = _find_agent_at_row(row, agent_pane_line_map)
                            if agent_id and subagent_states.get(agent_id, False):
                                agent_cache_scroll_offsets[agent_id] = agent_cache_scroll_offsets.get(agent_id, 0) + 3
                                input_changed = True
                        elif button == 65:
                            agent_id = _find_agent_at_row(row, agent_pane_line_map)
                            if agent_id and subagent_states.get(agent_id, False):
                                agent_cache_scroll_offsets[agent_id] = max(0, agent_cache_scroll_offsets.get(agent_id, 0) - 3)
                                input_changed = True
                        elif button >= 32:
                            agent_pane_hover_row = row
                            input_changed = True
                else:
                    if char == 'f':
                        frozen = not frozen
                        input_changed = True
                    else:
                        idx = parse_digit_key(char)
                        if idx is not None:
                            agent_id = get_agent_by_index(idx, _monitor.subagent_metadata)
                            if agent_id:
                                toggle_subagent_state(agent_id)
                                input_changed = True

            now = time.time()
            if not frozen and now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    _monitor.subagent_metadata.clear()
                    agent_turns.clear()
                    agent_cache_expand_states.clear()
                    agent_cache_line_map.clear()
                    agent_cache_scroll_offsets.clear()
                    subagent_states.clear()
                    _monitor.file_positions.clear()
                    _monitor.tool_use_caches.clear()
                    _monitor.load_historical_subagents()
                _stdout = sys.stdout
                sys.stdout = io.StringIO()
                _monitor.monitor_sessions()
                sys.stdout = _stdout
                agent_turns = {}
                for agent_id in _monitor.subagent_metadata:
                    jsonl_path = find_agent_jsonl(agent_id)
                    if jsonl_path:
                        agent_lines = read_new_lines(jsonl_path, 0)
                        messages, _ = parse_jsonl_lines(agent_lines)
                        agent_turns[agent_id] = extract_cache_turns(messages)
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
                output = render_subagents_with_tokens(_monitor.subagent_metadata, agent_turns, agent_pane_line_map, agent_pane_hover_row, pane_height, pane_width, agent_cache_scroll_offsets, agent_cache_expand_states, agent_cache_line_map, frozen=frozen)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
