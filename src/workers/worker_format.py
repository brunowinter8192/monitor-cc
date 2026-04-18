# INFRASTRUCTURE
from typing import Dict, List, Optional
import os

from ..constants import (
    RESET, GREEN, RED, YELLOW, WHITE, CYAN,
    PASTEL_PURPLE,
    HOVER_BG,
)
from ..token_format import _format_k, format_cache_tracker
from ..jsonl import read_new_lines, parse_jsonl_lines, get_message_content, is_tool_use
from ..utils import visual_line_count

INDENT = '  '

# FUNCTIONS

# Derive worker project name from project path (worktree-aware, matches tmux_spawn.sh logic)
def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

# Extract all tool_use entries from a worker's JSONL file
def extract_worker_tokens(jsonl_path) -> dict:
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
def extract_worker_tool_calls(jsonl_path) -> List[dict]:
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

    try:
        pane_width = os.get_terminal_size().columns
    except OSError:
        pane_width = 80

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

        spawned_str = f"  {WHITE}{spawned}{RESET}" if spawned else ''
        model = w.get('model', '')
        model_str = f"  {PASTEL_PURPLE}{model}{RESET}" if model else ''
        tokens = w.get('tokens', {})
        tok_out = tokens.get('output', 0)
        tokens_str = f"  {WHITE}{_format_k(tok_out)}out{RESET}" if tok_out else ''
        is_selected = selected_name is not None and name == selected_name
        sel_prefix = f"{GREEN}>>{RESET} " if is_selected else "   "
        header_line = f"{sel_prefix}{toggle_symbol} {CYAN}[{idx}] {name}{RESET}  {sc}{status.upper()}{RESET}{spawned_str}{model_str}{tokens_str}"
        header_span = visual_line_count(header_line, pane_width)
        if line_map is not None:
            for r in range(current_line, current_line + header_span):
                line_map[r] = name
        if hover_row is not None and current_line <= hover_row < current_line + header_span:
            lines.append(f"{HOVER_BG}{header_line}{RESET}")
        else:
            lines.append(header_line)
        current_line += header_span

        if purpose:
            if is_expanded:
                purpose_line = f"{INDENT}{WHITE}{purpose}{RESET}"
                purpose_span = visual_line_count(purpose_line, pane_width)
                if line_map is not None:
                    for r in range(current_line, current_line + purpose_span):
                        line_map[r] = name
            else:
                truncated = purpose[:60] + ('...' if len(purpose) > 60 else '')
                purpose_line = f"{INDENT}{WHITE}{truncated}{RESET}"
                purpose_span = visual_line_count(purpose_line, pane_width)
            lines.append(purpose_line)
            current_line += purpose_span

        if is_expanded:
            turns = worker_turns.get(name, [])
            if not turns:
                no_data_line = f"{INDENT}{YELLOW}(no token data yet){RESET}"
                no_data_span = visual_line_count(no_data_line, pane_width)
                if line_map is not None:
                    for r in range(current_line, current_line + no_data_span):
                        line_map[r] = name
                lines.append(no_data_line)
                current_line += no_data_span
            else:
                scroll_offset = (scroll_offsets or {}).get(name, 0)
                per_worker_expand = (cache_expand_states or {}).get(name, {})
                if cache_line_map is not None:
                    temp_clm: dict = {}
                    cache_output = format_cache_tracker(turns, per_worker_expand, temp_clm, None, 15, pane_width - 2, scroll_offset)
                    cache_start = current_line
                    for rel_row, key in temp_clm.items():
                        cache_line_map[rel_row + cache_start - 1] = (name, key[0], key[1])
                else:
                    cache_output = format_cache_tracker(turns, per_worker_expand, None, None, 15, pane_width - 2, scroll_offset)
                for cl in cache_output.split('\n'):
                    cl_full = f"  {cl}"
                    cl_span = visual_line_count(cl_full, pane_width)
                    lines.append(cl_full)
                    if line_map is not None:
                        for r in range(current_line, current_line + cl_span):
                            line_map[r] = name
                    current_line += cl_span

        lines.append('')
        current_line += 1

    if lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)
