# INFRASTRUCTURE
from typing import Dict, List, Optional
import os

from ..constants import (
    GREEN, RED, YELLOW, WHITE, CYAN,
    PASTEL_PURPLE, SOFT_RESET,
)
from ..format.token_format import _format_k, format_cache_tracker
from ..jsonl import read_new_lines, parse_jsonl_lines, get_message_content, is_tool_use

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

# Build flat (all_lines, line_keys) for workers pane; keys: str=worker name, 3-tuple=cache entry, None=non-clickable
def format_workers_block(workers: list, expand_states: dict = None, worker_turns: dict = None, scroll_offsets: dict = None, cache_expand_states: dict = None, frozen: bool = False, selected_name: Optional[str] = None) -> tuple:
    freeze_indicator = f" {YELLOW}[FROZEN]{SOFT_RESET}" if frozen else f" {CYAN}[LIVE]{SOFT_RESET}"

    all_lines: List[str] = []
    line_keys: List = []

    if not workers:
        all_lines.append(f"{WHITE}Workers{SOFT_RESET}{freeze_indicator}")
        line_keys.append(None)
        all_lines.append('')
        line_keys.append(None)
        all_lines.append(f"{YELLOW}No active workers{SOFT_RESET}")
        line_keys.append(None)
        return all_lines, line_keys

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

    all_lines.append(f"{WHITE}Workers{SOFT_RESET}{freeze_indicator}")
    line_keys.append(None)
    all_lines.append('')
    line_keys.append(None)

    for idx, w in enumerate(workers, 1):
        status = w.get('status', 'unknown')
        sc = status_colors.get(status, WHITE)
        name = w.get('name', '?')
        spawned = w.get('spawned', '')
        purpose = w.get('purpose', '')
        is_expanded = expand_states.get(name, False)
        toggle_symbol = "[-]" if is_expanded else "[+]"

        spawned_str = f"  {WHITE}{spawned}{SOFT_RESET}" if spawned else ''
        model = w.get('model', '')
        model_str = f"  {PASTEL_PURPLE}{model}{SOFT_RESET}" if model else ''
        tokens = w.get('tokens', {})
        tok_out = tokens.get('output', 0)
        tokens_str = f"  {WHITE}{_format_k(tok_out)}out{SOFT_RESET}" if tok_out else ''
        is_selected = selected_name is not None and name == selected_name
        sel_prefix = f"{GREEN}>>{SOFT_RESET} " if is_selected else "   "
        header_line = f"{sel_prefix}{toggle_symbol} {CYAN}[{idx}] {name}{SOFT_RESET}  {sc}{status.upper()}{SOFT_RESET}{spawned_str}{model_str}{tokens_str}"
        all_lines.append(header_line)
        line_keys.append(name)

        if purpose:
            if is_expanded:
                purpose_line = f"{INDENT}{WHITE}{purpose}{SOFT_RESET}"
            else:
                truncated = purpose[:60] + ('...' if len(purpose) > 60 else '')
                purpose_line = f"{INDENT}{WHITE}{truncated}{SOFT_RESET}"
            all_lines.append(purpose_line)
            line_keys.append(name)

        if is_expanded:
            turns = worker_turns.get(name, [])
            if not turns:
                all_lines.append(f"{INDENT}{YELLOW}(no token data yet){SOFT_RESET}")
                line_keys.append(name)
            else:
                scroll_offset = (scroll_offsets or {}).get(name, 0)
                per_worker_expand = (cache_expand_states or {}).get(name, {})
                visible_lines, visible_keys, _, _, _ = format_cache_tracker(
                    turns, per_worker_expand, 15, pane_width - 4, scroll_offset
                )
                for cl, ck in zip(visible_lines, visible_keys):
                    all_lines.append(f"  {cl}")
                    if ck is not None:
                        line_keys.append((name, ck[0], ck[1]))
                    else:
                        line_keys.append(None)

        all_lines.append('')
        line_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    return all_lines, line_keys
