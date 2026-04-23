# INFRASTRUCTURE
from typing import Dict, List, Optional
from pathlib import Path
import datetime
import hashlib
import os
import time
import traceback

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL, RESET, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from ..jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns
from ..input.click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard,
)
from ..utils import truncate_visible
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
worker_scroll_offset: int = 0
worker_turns: Dict[str, list] = {}

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

# Serialize a worker entry to full untruncated text for clipboard
def _serialize_workers(key) -> str:
    import json
    if isinstance(key, tuple):
        # Cache call: (worker_name, turn_idx, call_idx)
        w_name, t_idx, c_idx = key
        turns = worker_turns.get(w_name, [])
        if t_idx >= len(turns):
            return ''
        turn = turns[t_idx]
        calls = turn.get('api_calls', [])
        if c_idx >= len(calls):
            return ''
        call = calls[c_idx]
        parts = [f"Worker: {w_name}  Turn {t_idx + 1}, Call {c_idx + 1}  CR:{call.get('cache_read', 0)}  CC:{call.get('cache_creation', 0)}  D:{call.get('direct', 0)}  out:{call.get('output_tokens', 0)}"]
        for blk in call.get('content_blocks', []):
            btype = blk.get('type', '')
            if btype == 'tool_use':
                tool_name = blk.get('tool_name', 'Unknown')
                inp = blk.get('preview', {})
                parts.append(f"\n--- tool_use: {tool_name} ---")
                parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
            elif btype == 'text':
                parts.append(f"\n--- text ---")
                parts.append(blk.get('preview', ''))
        return '\n'.join(parts)
    else:
        # Worker name — serialize status info from current workers list
        # worker_turns holds the turns for this worker; we just emit identity info
        name = str(key)
        turns = worker_turns.get(name, [])
        n_turns = len(turns)
        n_calls = sum(len(t.get('api_calls', [])) for t in turns)
        return f"Worker: {name}\nTurns: {n_turns}  API calls: {n_calls}"

# Runs workers display loop (for dedicated workers tmux pane)
def run_workers_loop() -> None:
    from ..core import monitor as _monitor
    global worker_expand_states, worker_scroll_offsets, worker_line_map, worker_hover_row, worker_cache_expand_states, worker_cache_line_map, worker_selected_name, worker_scroll_offset, worker_turns
    last_output = None
    workers = []
    worker_turns.clear()
    last_data_refresh = 0.0
    frozen = False
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
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
                            elif button in (64, 65):  # wheel up / wheel down
                                w_name = None
                                cache_hit = worker_cache_line_map.get(row)
                                if cache_hit is not None:
                                    w_name = cache_hit[0]
                                else:
                                    map_hit = worker_line_map.get(row)
                                    if map_hit is not None:
                                        w_name = map_hit
                                    else:
                                        w_name = worker_selected_name
                                if w_name is not None:
                                    current = worker_scroll_offsets.get(w_name, 0)
                                    delta = 3 if button == 64 else -3
                                    worker_scroll_offsets[w_name] = max(0, current + delta)
                                    input_changed = True
                            elif button >= 32:
                                worker_hover_row = row
                                input_changed = True
                    else:
                        if char == 'y':
                            key = resolve_parent_key(worker_line_map, worker_hover_row)
                            if key is None:
                                key = resolve_parent_key(worker_cache_line_map, worker_hover_row)
                            if key is not None:
                                copy_to_clipboard(_serialize_workers(key))
                        elif char == 'f':
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
                    worker_turns.clear()
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

                all_lines, line_keys = format_workers_block(
                    workers, worker_expand_states, worker_turns,
                    worker_scroll_offsets, worker_cache_expand_states,
                    frozen=frozen, selected_name=worker_selected_name,
                )
                try:
                    term = os.get_terminal_size()
                    pane_width = term.columns
                    pane_height = term.lines
                except OSError:
                    pane_width = 80
                    pane_height = 50
                # Viewport clipping: phys_row 1..N must equal terminal row 1..N.
                # worker_scroll_offset > 0 shifts viewport toward older content.
                total_lines = len(all_lines)
                max_offset = max(0, total_lines - pane_height)
                worker_scroll_offset = min(worker_scroll_offset, max_offset)
                vp_start = max(0, total_lines - pane_height - worker_scroll_offset)
                visible_all = all_lines[vp_start:vp_start + pane_height]
                visible_keys = line_keys[vp_start:vp_start + pane_height]
                worker_line_map.clear()
                worker_cache_line_map.clear()
                result_lines = []
                phys_row = 1
                parent_count = sum(1 for k in line_keys[:vp_start] if isinstance(k, str))
                for line, key in zip(visible_all, visible_keys):
                    if isinstance(key, str):
                        zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
                        parent_count += 1
                    else:
                        zebra_bg = ZEBRA_BG_A
                    is_hovered = (key is not None and worker_hover_row is not None
                                  and phys_row == worker_hover_row)
                    if is_hovered:
                        chosen_bg = HOVER_BG
                    elif line.startswith(LIGHT_RED_BG):
                        chosen_bg = LIGHT_RED_BG
                    else:
                        chosen_bg = zebra_bg
                    trunc = truncate_visible(line, pane_width)
                    result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
                    if isinstance(key, str):
                        worker_line_map[phys_row] = key
                    elif isinstance(key, tuple):
                        worker_cache_line_map[phys_row] = key
                    phys_row += 1
                output = '\n'.join(result_lines)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
                time.sleep(INPUT_POLL_INTERVAL)
            except Exception:
                with open('/tmp/monitor_cc_error.log', 'a') as _f:
                    _f.write(f"\n[{datetime.datetime.now().isoformat()}] workers_pane error:\n")
                    traceback.print_exc(file=_f)
                time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
