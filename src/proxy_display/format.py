# INFRASTRUCTURE
from collections import Counter
from typing import Optional

from ..constants import (
    RESET, SOFT_RESET, GREEN, RED, DIM, YELLOW, HOVER_BG,
    DIM_YELLOW_BG, ZEBRA_BG_A, ZEBRA_BG_B, COLLISION_BG,
)
from ..format.token_format import _format_k
from ..utils import truncate_visible
from .parser import _chars_to_tokens

# FUNCTIONS

# Format token estimate as compact string with ~ prefix
def _format_tok_est(chars: int) -> str:
    return f"~{_format_k(_chars_to_tokens(chars))}tok"

# Format a signed char-count delta with token estimate (GREEN=positive, RED=negative, DIM=zero)
def _format_delta(label: str, delta: int) -> str:
    if delta == 0:
        return f"{DIM}Δ{label}:0{SOFT_RESET}"
    sign = '+' if delta > 0 else '-'
    color = GREEN if delta > 0 else RED
    abs_chars = abs(delta)
    tok_est = _chars_to_tokens(abs_chars)
    return f"{color}Δ{label}:{sign}{_format_k(abs_chars)}(~{_format_k(tok_est)}tok){SOFT_RESET}"

# Format effort string as compact label: 'high'→'hig', 'medium'→'med', 'low'→'lo', None→'-'
def _fmt_effort(s: Optional[str]) -> str:
    if s is None:
        return '-'
    return {'high': 'hig', 'medium': 'med', 'low': 'lo'}.get(s, s[:3])


# Format thinking budget as compact string: None→'-', <1000→str(n), ≥1000→'Nk'
def _fmt_thinking_budget(n: Optional[int]) -> str:
    if n is None:
        return '-'
    if n < 1000:
        return str(n)
    return f'{n // 1000}k'


# Shorten full model name to family label
def _shorten_model(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    if 'opus' in m:
        return 'opus'
    return model[:8] if model else '?'

# True when entry is a structural sidecar (haiku or zero-context: no system AND no tools).
# cache_breakpoints is always [] for forwarded entries, so the old bp-guard logic is replaced
# by system/tools presence: a real main-session request always carries a full system prompt
# and tool list (sys_chars>0, tools_chars>0); CC title/summary and haiku sidecars have neither.
# Backward-compatible: old main-log entries with bp=[0] had sys_chars>0 too, so they still pass.
def _is_standalone_entry(entry: dict) -> bool:
    sys_chars = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    tools_chars = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    return (
        'haiku' in entry.get('model', '').lower()
        or (sys_chars == 0 and tools_chars == 0)
    )


# Assign each proxy entry to the matching turn based on timestamp comparison
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

# Format proxy pane with API request entries grouped by turn, expand/collapse, scroll, hover
def format_proxy_block(entries: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, turns: list = None, item_positions_out: Optional[dict] = None, copy_feedback: Optional[dict] = None, copy_rows_out: Optional[set] = None) -> tuple:
    from .render_entry import _render_entry_lines
    from .render_turn import render_turn_expanded
    if not entries:
        return (f"{YELLOW}No API requests logged yet{SOFT_RESET}", 0)

    if expand_states is None:
        expand_states = {}

    all_lines = []
    line_keys = []

    if turns:
        groups = _assign_turns_to_entries(entries, turns)
    else:
        groups = [{'turn_idx': 0, 'timestamp': '', 'entry_pairs': list(enumerate(entries))}]
    opus_req_num = 0
    sub_req_num = 0
    rendered_opus_labels = []

    if groups:
        prev_group_last_entry = None
        for group in groups:
            turn_idx = group['turn_idx']
            sub_req_num = 0

            prev_entry_for_delta = prev_group_last_entry
            t_lines, t_keys, opus_req_num, sub_req_num = render_turn_expanded(
                group, entries, expand_states, pane_width,
                prev_entry_for_delta, opus_req_num, sub_req_num,
                turns=turns, turn_idx=turn_idx,
                rendered_opus_labels=rendered_opus_labels,
                copy_feedback=copy_feedback,
                copy_rows_out=copy_rows_out,
            )
            all_lines.extend(t_lines)
            line_keys.extend(t_keys)
            if item_positions_out is not None:
                base = len(all_lines) - len(t_lines)
                for i, key in enumerate(t_keys):
                    if key is not None:
                        item_positions_out[key] = base + i

            main_entries = [e for _, e in group['entry_pairs'] if 'haiku' not in e.get('model', '').lower()]
            if main_entries:
                prev_group_last_entry = main_entries[-1]
            all_lines.append('')
            line_keys.append(None)
    else:
        for entry_idx, entry in enumerate(entries):
            model_short = _shorten_model(entry.get('model', '?'))
            if _is_standalone_entry(entry):
                num_label = 'H' if model_short == 'haiku' else 'S'
            else:
                diff = entry.get('diff_from_prev', {})
                if diff.get('messages_added', 1) > 0:
                    opus_req_num += 1
                    sub_req_num = 0
                    num_label = f'#{opus_req_num}'
                else:
                    sub_req_num += 1
                    num_label = f'#{opus_req_num}.{sub_req_num}'
            e_lines, e_keys = _render_entry_lines(entry_idx, entry, entries, expand_states, pane_width, indent='', num_label=num_label, rendered_opus_labels=rendered_opus_labels, copy_feedback=copy_feedback, copy_rows_out=copy_rows_out)
            all_lines.extend(e_lines)
            line_keys.extend(e_keys)
            if item_positions_out is not None:
                base = len(all_lines) - len(e_lines)
                for i, key in enumerate(e_keys):
                    if key is not None:
                        item_positions_out[key] = base + i
            all_lines.append('')
            line_keys.append(None)

    _label_counts = Counter(lbl for _, lbl in rendered_opus_labels)
    collision_entry_idxs = {idx for idx, lbl in rendered_opus_labels if _label_counts[lbl] >= 2}

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

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

    initial_offset = sum(1 for k in line_keys[:start] if k is not None)
    parent_count = initial_offset
    result_lines = []
    for row_offset, line in enumerate(visible_lines):
        row = row_offset + 1
        key = visible_keys[row_offset]
        if copy_rows_out is not None:
            is_req_line = (isinstance(key, tuple) and key[0] == 'req') or isinstance(key, int)
            if is_req_line and ('⎘' in line or '✓' in line):
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
        elif is_collision:
            chosen_bg = COLLISION_BG
        else:
            chosen_bg = zebra_bg
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")

    return '\n'.join(result_lines), total_lines
