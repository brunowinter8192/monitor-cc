# INFRASTRUCTURE
from typing import Dict, List, Optional
import os
import time

from ..colors import (
    GREEN, RED, YELLOW, WHITE, CYAN,
    DIM, PASTEL_PURPLE, SOFT_RESET,
    SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
)
from ..format.token_format import _format_k, format_cache_tracker
from ..jsonl import read_new_lines, parse_jsonl_lines, get_message_content, is_tool_use
from ..utils import append_copy_symbol
from ..search_bar import _BG_RESTORE_SENTINEL

INDENT = '  '

_WORKER_CONTEXT_WINDOW = 1000000

_STATUS_COLORS = {
    'working': GREEN,
    'idle': YELLOW,
    'exited': RED,
    'unknown': WHITE,
}

# FUNCTIONS

def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

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

def extract_worker_context_pct(jsonl_path) -> Optional[int]:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    cr = None
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        val = message.get('message', {}).get('usage', {}).get('cache_read_input_tokens')
        if val is not None:
            cr = val
    if cr is None:
        return None
    return (100 * (_WORKER_CONTEXT_WINDOW - cr)) // _WORKER_CONTEXT_WINDOW

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

def _worker_cache_copy_feedback(copy_feedback: Optional[dict], name: str) -> Optional[dict]:
    if copy_feedback is None:
        return None
    return {(k[1], k[2]): exp for k, exp in copy_feedback.items()
            if isinstance(k, tuple) and len(k) == 3 and k[0] == name}

def _scope_matches_to_worker(matches, name: str) -> set:
    scoped = set()
    for k in matches or ():
        if isinstance(k, tuple) and len(k) == 3 and k[0] == name:
            scoped.add(('turn', k[2]) if k[1] == 'turn' else (k[1], k[2]))
    return scoped

def _scope_current_key_to_worker(current_key, name: str):
    if isinstance(current_key, tuple) and len(current_key) == 3 and current_key[0] == name:
        return ('turn', current_key[2]) if current_key[1] == 'turn' else (current_key[1], current_key[2])
    return None

def _register_freeze_region(regions_out: dict, frozen: bool, pane_width: int) -> None:
    regions_out.clear()
    badge = "[FROZEN]" if frozen else "[LIVE]"
    start_col = len("Workers") + 1
    end_col = start_col + len(badge) - 1
    if end_col < pane_width:
        regions_out['freeze'] = (start_col + 1, end_col + 1)

def _build_worker_header_line(w: dict, idx: int, name: str, is_expanded: bool, selected_name: Optional[str],
                               copy_feedback: Optional[dict], pane_width: int,
                               search_match_set: Optional[set], search_current_key) -> str:
    status = w.get('status', 'unknown')
    sc = _STATUS_COLORS.get(status, WHITE)
    spawned = w.get('spawned', '')
    toggle_symbol = "[-]" if is_expanded else "[+]"
    spawned_str = f"  {WHITE}{spawned}{SOFT_RESET}" if spawned else ''
    model = w.get('model', '')
    model_str = f"  {PASTEL_PURPLE}{model}{SOFT_RESET}" if model else ''
    tokens = w.get('tokens', {})
    tok_out = tokens.get('output', 0)
    tokens_str = f"  {WHITE}{_format_k(tok_out)}out{SOFT_RESET}" if tok_out else ''
    pct = w.get('context_pct')
    if pct is None:
        pct_str = f"  {DIM}—%{SOFT_RESET}"
    else:
        pct_color = GREEN if pct >= 60 else (YELLOW if pct >= 40 else RED)
        pct_str = f"  {pct_color}{pct:3d}%{SOFT_RESET}"
    is_selected = selected_name is not None and name == selected_name
    sel_prefix = f"{GREEN}>>{SOFT_RESET} " if is_selected else "   "
    header_line = f"{sel_prefix}{toggle_symbol} {CYAN}[{idx}] {name}{SOFT_RESET}  {sc}{status.upper()}{SOFT_RESET}{pct_str}{spawned_str}{model_str}{tokens_str}"
    if search_match_set and name in search_match_set:
        marker = SEARCH_CURRENT_BG if name == search_current_key else SEARCH_MATCH_BG
        header_line = f"{marker}{header_line}{_BG_RESTORE_SENTINEL}"
    if copy_feedback is not None:
        is_flash = copy_feedback.get(name, 0) > time.time()
        header_line = append_copy_symbol(header_line, '✓' if is_flash else '⎘', pane_width)
    return header_line

def _build_worker_purpose_line(purpose: str, is_expanded: bool) -> str:
    if is_expanded:
        return f"{INDENT}{WHITE}{purpose}{SOFT_RESET}"
    truncated = purpose[:60] + ('...' if len(purpose) > 60 else '')
    return f"{INDENT}{WHITE}{truncated}{SOFT_RESET}"

def _render_worker_expanded_view(name: str, worker_turns: dict, scroll_offsets: Optional[dict],
                                  cache_expand_states: Optional[dict], copy_feedback: Optional[dict],
                                  pane_width: int, search_match_set: Optional[set], search_current_key,
                                  search_query: str) -> tuple:
    lines = []
    keys = []
    turns = worker_turns.get(name, [])
    if not turns:
        lines.append(f"{INDENT}{YELLOW}(no token data yet){SOFT_RESET}")
        keys.append(name)
        return lines, keys
    scroll_offset = (scroll_offsets or {}).get(name, 0)
    per_worker_expand = (cache_expand_states or {}).get(name, {})
    visible_lines, visible_keys, _, _, _ = format_cache_tracker(
        turns, per_worker_expand, 15, pane_width - 4, scroll_offset,
        copy_feedback=_worker_cache_copy_feedback(copy_feedback, name),
        search_match_set=_scope_matches_to_worker(search_match_set, name),
        search_current_key=_scope_current_key_to_worker(search_current_key, name),
        search_query=search_query,
    )
    for cl, ck in zip(visible_lines, visible_keys):
        lines.append(f"  {cl}")
        keys.append((name, ck[0], ck[1]) if ck is not None else None)
    return lines, keys

def _render_worker_row(w: dict, idx: int, expand_states: dict, worker_turns: dict, scroll_offsets: Optional[dict],
                        cache_expand_states: Optional[dict], selected_name: Optional[str], copy_feedback: Optional[dict],
                        pane_width: int, search_match_set: Optional[set], search_current_key, search_query: str) -> tuple:
    lines = []
    keys = []
    name = w.get('name', '?')
    purpose = w.get('purpose', '')
    is_expanded = expand_states.get(name, False)
    lines.append(_build_worker_header_line(w, idx, name, is_expanded, selected_name, copy_feedback, pane_width, search_match_set, search_current_key))
    keys.append(name)
    if purpose:
        lines.append(_build_worker_purpose_line(purpose, is_expanded))
        keys.append(name)
    if is_expanded:
        e_lines, e_keys = _render_worker_expanded_view(
            name, worker_turns, scroll_offsets, cache_expand_states, copy_feedback,
            pane_width, search_match_set, search_current_key, search_query,
        )
        lines.extend(e_lines)
        keys.extend(e_keys)
    lines.append('')
    keys.append(None)
    return lines, keys

def format_workers_block(workers: list, expand_states: dict = None, worker_turns: dict = None, scroll_offsets: dict = None, cache_expand_states: dict = None, frozen: bool = False, selected_name: Optional[str] = None, copy_feedback: Optional[dict] = None, regions_out: Optional[dict] = None, search_match_set: Optional[set] = None, search_current_key=None, search_query: str = '') -> tuple:
    freeze_indicator = f" {YELLOW}[FROZEN]{SOFT_RESET}" if frozen else f" {CYAN}[LIVE]{SOFT_RESET}"

    try:
        pane_width = os.get_terminal_size().columns
    except OSError:
        pane_width = 80

    if regions_out is not None:
        _register_freeze_region(regions_out, frozen, pane_width)

    if not workers:
        return (
            [f"{WHITE}Workers{SOFT_RESET}{freeze_indicator}", '', f"{YELLOW}No active workers{SOFT_RESET}"],
            [None, None, None],
        )

    if expand_states is None:
        expand_states = {}
    if worker_turns is None:
        worker_turns = {}

    all_lines: List[str] = [f"{WHITE}Workers{SOFT_RESET}{freeze_indicator}", '']
    line_keys: List = [None, None]

    for idx, w in enumerate(workers, 1):
        w_lines, w_keys = _render_worker_row(
            w, idx, expand_states, worker_turns, scroll_offsets, cache_expand_states,
            selected_name, copy_feedback, pane_width, search_match_set, search_current_key, search_query,
        )
        all_lines.extend(w_lines)
        line_keys.extend(w_keys)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    return all_lines, line_keys
