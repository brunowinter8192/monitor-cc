# INFRASTRUCTURE
from collections import Counter
from typing import Optional

from ..colors import (
    RESET, SOFT_RESET, DIM, YELLOW, HOVER_BG,
    DIM_YELLOW_BG, DIM_GREEN_BG, ZEBRA_BG_A, ZEBRA_BG_B, COLLISION_BG,
)
from ..format.token_format import _format_k
from ..utils import truncate_visible
from .proxy_badge import _chars_to_tokens
from src.proxy_display.turn_cache import TurnCache
from ..search_bar import _BG_RESTORE_SENTINEL, resolve_bg_restore

# FUNCTIONS

def _format_tok_est(chars: int) -> str:
    return f"~{_format_k(_chars_to_tokens(chars))}tok"

def _fmt_effort(s: Optional[str]) -> str:
    if s is None:
        return '-'
    return {'high': 'hig', 'medium': 'med', 'low': 'lo'}.get(s, s[:3])


def _fmt_thinking_budget(n: Optional[int]) -> str:
    if n is None:
        return '-'
    if n < 1000:
        return str(n)
    return f'{n // 1000}k'


def _shorten_model(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    if 'opus' in m:
        return 'opus'
    return model[:8] if model else '?'

def _is_standalone_entry(entry: dict) -> bool:
    if entry.get('is_continue'):
        return False
    sys_chars = entry.get('system_total_chars', 0)
    tools_chars = entry.get('tools_total_chars', 0)
    return (
        'haiku' in entry.get('model', '').lower()
        or (sys_chars == 0 and tools_chars == 0)
    )


def _assign_turns_to_entries(entries: list, turns: list) -> list:
    if not turns or not entries:
        return []
    groups = [{'turn_idx': i, 'timestamp': t.get('timestamp', ''), 'entry_pairs': []} for i, t in enumerate(turns)]
    for entry_idx, entry in enumerate(entries):
        entry_ts = entry.get('timestamp', '')
        assigned = False
        for i in range(len(turns) - 1, -1, -1):
            if entry_ts >= turns[i].get('timestamp', ''):
                groups[i]['entry_pairs'].append((entry_idx, entry))
                assigned = True
                break
        if not assigned:
            groups[0]['entry_pairs'].append((entry_idx, entry))
    return [g for g in groups if g['entry_pairs']]

def _apply_row_backgrounds(visible_lines: list, visible_keys: list, collision_entry_idxs: set, hover_row, copy_rows_out, pane_width: int, initial_parent_count: int) -> list:
    parent_count = initial_parent_count
    result_lines = []
    for row_offset, line in enumerate(visible_lines):
        row = row_offset + 1
        key = visible_keys[row_offset]
        if copy_rows_out is not None:
            is_req_line = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
            is_msg_line = isinstance(key, tuple) and key[0] == 'msg'
            is_think_line = isinstance(key, tuple) and key[0] == 'think'
            is_block_line = isinstance(key, tuple) and key[0] == 'block'
            if (is_req_line or is_msg_line or is_think_line or is_block_line) and ('⎘' in line or '✓' in line):
                copy_rows_out.add(row)
        if key is not None:
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = key is not None and hover_row is not None and row == hover_row
        is_collision = bool(collision_entry_idxs and (
            (isinstance(key, tuple) and key[0] == 'req' and key[1] in collision_entry_idxs) or
            (isinstance(key, int) and key in collision_entry_idxs)
        ))
        if is_hovered:
            chosen_bg = HOVER_BG
        elif DIM_YELLOW_BG in line:
            chosen_bg = DIM_YELLOW_BG
        elif DIM_GREEN_BG in line:
            chosen_bg = DIM_GREEN_BG
        elif is_collision:
            chosen_bg = COLLISION_BG
        else:
            chosen_bg = zebra_bg
        line = resolve_bg_restore(line, chosen_bg)
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
    return result_lines

def _compute_collision_idxs(rendered_opus_labels: list) -> set:
    label_counts = Counter(lbl for _, lbl in rendered_opus_labels)
    return {idx for idx, lbl in rendered_opus_labels if label_counts[lbl] >= 2}

def _slice_viewport(all_lines: list, line_keys: list, parent_prefix: list, pane_height: int, scroll_offset: int, line_map: Optional[dict]) -> tuple:
    total_lines = len(all_lines)
    viewport_lines = max(1, pane_height - 1)
    max_scroll = max(0, len(all_lines) - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, len(all_lines) - viewport_lines - clamped_offset)
    end = start + viewport_lines
    visible_lines = all_lines[start:end]
    visible_keys = line_keys[start:end]
    if line_map is not None:
        line_map.clear()
        for row_idx, key in enumerate(visible_keys):
            if key is not None:
                line_map[row_idx + 1] = key
    initial_parent_count = parent_prefix[start]
    return visible_lines, visible_keys, initial_parent_count, total_lines

def format_proxy_block(entries: list, expand_states: dict, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, turns: list = None, item_positions_out: Optional[dict] = None, copy_feedback: Optional[dict] = None, copy_rows_out: Optional[set] = None, search_match_set: Optional[set] = None, search_current_entry_idx: Optional[int] = None, search_query: str = '', request_id_by_flow: Optional[dict] = None, *, turn_cache: TurnCache) -> tuple:
    if not entries:
        return (f"{YELLOW}No API requests logged yet{SOFT_RESET}", 0)
    from src.proxy_display.frozen_turns import assign_groups, render_frozen
    groups = assign_groups(entries, turns, turn_cache)
    flat = render_frozen(
        entries, groups, expand_states, pane_width, turns,
        copy_feedback, search_match_set, search_current_entry_idx, search_query, request_id_by_flow, turn_cache,
    )
    if item_positions_out is not None:
        item_positions_out.update(flat['positions'])
    visible_lines, visible_keys, initial_parent_count, total_lines = _slice_viewport(
        flat['lines'], flat['keys'], flat['parent_prefix'], pane_height, scroll_offset, line_map
    )
    result_lines = _apply_row_backgrounds(visible_lines, visible_keys, flat['collision'], hover_row, copy_rows_out, pane_width, initial_parent_count)
    return '\n'.join(result_lines), total_lines
