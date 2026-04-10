# INFRASTRUCTURE
from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import os
import subprocess
import time

from .constants import (
    RESET, GREEN, RED, YELLOW, WHITE, CYAN,
    PASTEL_PURPLE,
    HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from .token_pane import _format_k, format_cache_tracker
from .jsonl_parser import read_new_lines, parse_jsonl_lines, extract_cache_turns, get_message_content, is_tool_use
from .session_finder import encode_project_path
from .click_handler import (
    read_keypress, parse_digit_key, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

INDENT = '  '

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

# Derive worker project name from project path (worktree-aware, matches tmux_spawn.sh logic)
def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

# Read a single env var from a tmux session
def get_tmux_env(session: str, var: str) -> str:
    result = subprocess.run(
        ["tmux", "show-environment", "-t", session, var],
        capture_output=True, text=True
    )
    if result.returncode == 0 and '=' in result.stdout:
        return result.stdout.strip().split('=', 1)[1]
    return ''

# Detect worker status: working, idle, exited, or unknown
def detect_worker_status(session: str) -> str:
    dead = subprocess.run(
        ["tmux", "display-message", "-t", f"{session}:^", "-p", "#{pane_dead}"],
        capture_output=True, text=True
    ).stdout.strip()

    if dead == "1":
        return "exited"
    if dead != "0":
        return "unknown"

    now = int(time.time())
    last_activity = subprocess.run(
        ["tmux", "list-panes", "-t", session, "-F", "#{window_activity}"],
        capture_output=True, text=True
    ).stdout.strip().split('\n')[0]
    delta = now - int(last_activity or "0")

    if delta > 10:
        return "idle"
    return "working"

# List all workers for the current project
def list_workers(project_path: str) -> List[dict]:
    project = get_worker_project_name(project_path)
    prefix = f"worker-{project}-"

    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []

    sessions = [s for s in result.stdout.strip().split('\n') if s.startswith(prefix)]
    workers = []
    for session in sessions:
        if not session:
            continue
        name = session[len(prefix):]
        workers.append({
            'name': name,
            'session': session,
            'status': detect_worker_status(session),
            'spawned': get_tmux_env(session, 'WORKER_SPAWNED'),
            'purpose': get_tmux_env(session, 'WORKER_PURPOSE'),
            'model': get_tmux_env(session, 'WORKER_MODEL') or 'sonnet',
        })
    return workers

# Find the most recent JSONL file for a worker's Claude Code session
def find_worker_jsonl(session_name: str) -> Optional[Path]:
    result = subprocess.run(
        ["tmux", "display-message", "-t", f"{session_name}:^", "-p", "#{pane_current_path}"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    working_dir = result.stdout.strip()
    encoded = encode_project_path(working_dir)
    project_dir = Path.home() / '.claude' / 'projects' / encoded

    if not project_dir.exists():
        return None

    jsonl_files = [f for f in project_dir.glob('*.jsonl') if not f.name.startswith('agent-')]
    if not jsonl_files:
        return None

    return max(jsonl_files, key=lambda f: f.stat().st_mtime)

# Extract all tool_use entries from a worker's JSONL file
def extract_worker_tokens(jsonl_path: Path) -> dict:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    total_output = 0
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        usage = message.get('message', {}).get('usage', {})
        total_output += usage.get('output_tokens', 0)
    return {'output': total_output}

# Extract tool call list from a worker's JSONL file
def extract_worker_tool_calls(jsonl_path: Path) -> List[dict]:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    calls = []
    call_number = 0
    for message in messages:
        content_blocks = get_message_content(message)
        timestamp = message.get('timestamp', '')
        for block in content_blocks:
            if is_tool_use(block):
                call_number += 1
                calls.append({
                    'tool_name': block.get('name', 'Unknown'),
                    'input': block.get('input', {}),
                    'timestamp': timestamp,
                    'call_number': call_number,
                })
    return calls

# Format workers pane with optional expand/collapse showing cache tracker per worker
def format_workers_block(workers: list, expand_states: dict = None, worker_turns: dict = None, line_map: dict = None, hover_row: Optional[int] = None, scroll_offsets: dict = None, cache_expand_states: dict = None, cache_line_map: dict = None, frozen: bool = False, selected_name: Optional[str] = None) -> str:
    freeze_indicator = f" {YELLOW}[FROZEN]{RESET}" if frozen else f" {CYAN}[LIVE]{RESET}"

    if not workers:
        return f"{WHITE}Workers{RESET}{freeze_indicator}\n\n{YELLOW}No active workers{RESET}"

    if expand_states is None:
        expand_states = {}
    if worker_turns is None:
        worker_turns = {}

    status_colors = {
        'working': GREEN,
        'idle': YELLOW,
        'exited': RED,
        'unknown': WHITE,
    }

    lines = []
    current_line = 1

    lines.append(f"{WHITE}Workers{RESET}{freeze_indicator}")
    lines.append('')
    current_line += 2

    if line_map is not None:
        line_map.clear()
    if cache_line_map is not None:
        cache_line_map.clear()

    for idx, w in enumerate(workers, 1):
        status = w.get('status', 'unknown')
        sc = status_colors.get(status, WHITE)
        name = w.get('name', '?')
        spawned = w.get('spawned', '')
        purpose = w.get('purpose', '')
        is_expanded = expand_states.get(name, False)
        toggle_symbol = "[-]" if is_expanded else "[+]"

        if line_map is not None:
            line_map[current_line] = name

        spawned_str = f"  {WHITE}{spawned}{RESET}" if spawned else ''
        model = w.get('model', '')
        model_str = f"  {PASTEL_PURPLE}{model}{RESET}" if model else ''
        tokens = w.get('tokens', {})
        tok_out = tokens.get('output', 0)
        tokens_str = f"  {WHITE}{_format_k(tok_out)}out{RESET}" if tok_out else ''
        is_selected = selected_name is not None and name == selected_name
        sel_prefix = f"{GREEN}>>{RESET} " if is_selected else "   "
        header_line = f"{sel_prefix}{toggle_symbol} {CYAN}[{idx}] {name}{RESET}  {sc}{status.upper()}{RESET}{spawned_str}{model_str}{tokens_str}"
        if hover_row is not None and current_line == hover_row:
            header_line = f"{HOVER_BG}{header_line}{RESET}"
        lines.append(header_line)
        current_line += 1

        if purpose:
            if is_expanded:
                purpose_line = f"{INDENT}{WHITE}{purpose}{RESET}"
                if line_map is not None:
                    line_map[current_line] = name
            else:
                truncated = purpose[:60] + ('...' if len(purpose) > 60 else '')
                purpose_line = f"{INDENT}{WHITE}{truncated}{RESET}"
            lines.append(purpose_line)
            current_line += 1

        if is_expanded:
            turns = worker_turns.get(name, [])
            if not turns:
                if line_map is not None:
                    line_map[current_line] = name
                lines.append(f"{INDENT}{YELLOW}(no token data yet){RESET}")
                current_line += 1
            else:
                scroll_offset = (scroll_offsets or {}).get(name, 0)
                per_worker_expand = (cache_expand_states or {}).get(name, {})
                try:
                    pane_width = os.get_terminal_size().columns
                except OSError:
                    pane_width = 80
                if cache_line_map is not None:
                    temp_clm: dict = {}
                    cache_output = format_cache_tracker(turns, per_worker_expand, temp_clm, None, 15, pane_width - 2, scroll_offset)
                    cache_start = current_line
                    for rel_row, key in temp_clm.items():
                        cache_line_map[rel_row + cache_start - 1] = (name, key[0], key[1])
                else:
                    cache_output = format_cache_tracker(turns, per_worker_expand, None, None, 15, pane_width - 2, scroll_offset)
                for cl in cache_output.split('\n'):
                    lines.append(f"  {cl}")
                    if line_map is not None:
                        line_map[current_line] = name
                    current_line += 1

        lines.append('')
        current_line += 1

    if lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)

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
