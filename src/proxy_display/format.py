# INFRASTRUCTURE
from collections import Counter
from typing import Optional

from ..constants import (
    RESET, SOFT_RESET, GREEN, RED, DIM, YELLOW, PASTEL_PURPLE, HOVER_BG,
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

# Format TTFB + gen-rate + stall badge for REQ header (color-coded by Opus thresholds)
# TTFB thresholds: green<2s yellow<10s red≥10s  |  gen-rate: green≥25 yellow≥10 red<10 tok/s
# stalls: yellow 1-2, red ≥3  |  n_stalls=0 → no stall badge
def _format_latency(ttfb_ms: Optional[float], output_tokens_per_sec: Optional[float],
                    n_stalls: int = 0, max_stall_ms: Optional[float] = None) -> str:
    if ttfb_ms is None and output_tokens_per_sec is None and not n_stalls:
        return ''
    parts = []
    if ttfb_ms is not None:
        ttfb_s = ttfb_ms / 1000.0
        col = GREEN if ttfb_s < 2.0 else (YELLOW if ttfb_s < 10.0 else RED)
        parts.append(f"{col}TTFB:{ttfb_s:.1f}s{SOFT_RESET}")
    else:
        parts.append(f"{DIM}TTFB:?{SOFT_RESET}")
    if output_tokens_per_sec is not None:
        tps = output_tokens_per_sec
        col = GREEN if tps >= 25.0 else (YELLOW if tps >= 10.0 else RED)
        parts.append(f"{col}gen:{tps:.0f}tok/s{SOFT_RESET}")
    if n_stalls > 0:
        col = RED if n_stalls >= 3 else YELLOW
        max_s = f"{max_stall_ms / 1000:.0f}s" if max_stall_ms is not None else "?s"
        parts.append(f"{col}{n_stalls}-stalls(max {max_s}){SOFT_RESET}")
    return '  ' + ' '.join(parts)


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

# True when entry is a structural sidecar (haiku, zero-context, or mc=1 title/summary)
# mc=1+no-BP catches CC title/summary generation; bp=[0] guard preserves real first-REQ
def _is_standalone_entry(entry: dict) -> bool:
    return (
        'haiku' in entry.get('model', '').lower()
        or (entry.get('system_total_chars', entry.get('system_prompt_chars', 0)) == 0
            and entry.get('tools_total_chars', entry.get('tools_chars', 0)) == 0
            and len(entry.get('cache_breakpoints', [])) == 0)
        or (entry.get('message_count', 0) == 1
            and len(entry.get('cache_breakpoints', [])) == 0)
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
def format_proxy_block(entries: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, turns: list = None, item_positions_out: Optional[dict] = None) -> tuple:
    from ..utils import format_timestamp
    from .render_entry import _render_entry_lines
    from .render_turn import render_turn_expanded
    if not entries:
        return (f"{YELLOW}No API requests logged yet{SOFT_RESET}", 0)

    if expand_states is None:
        expand_states = {}

    all_lines = []
    line_keys = []

    groups = _assign_turns_to_entries(entries, turns) if turns else None
    opus_req_num = 0
    sub_req_num = 0
    rendered_opus_labels = []

    if groups:
        prev_group_last_entry = None
        prev_effort = None
        prev_budget = None
        for group in groups:
            turn_idx = group['turn_idx']
            opus_req_num = sum(len(t.get('api_calls', [])) for t in turns[:turn_idx])
            sub_req_num = 0

            _opus_pairs = [(idx, e) for idx, e in group['entry_pairs'] if 'haiku' not in e.get('model', '').lower()]
            last_e = _opus_pairs[-1][1] if _opus_pairs else group['entry_pairs'][-1][1]
            last_sys = last_e.get('system_total_chars', last_e.get('system_prompt_chars', 0))
            last_tools = last_e.get('tools_total_chars', last_e.get('tools_chars', 0))
            last_msgs = last_e.get('messages_total_chars', 0)

            # Aggregate effort: highest-priority value across all opus entries in turn
            _effort_priority = {'high': 3, 'medium': 2, 'low': 1}
            _eff_vals = [e.get('effort_value') for _, e in _opus_pairs if e.get('effort_value') is not None]
            effort = max(_eff_vals, key=lambda x: _effort_priority.get(x, 0)) if _eff_vals else None
            # Aggregate thinking budget: max non-None across all opus entries in turn
            _bgt_vals = [e.get('thinking_budget_tokens') for _, e in _opus_pairs
                         if e.get('thinking_budget_tokens') is not None]
            budget = max(_bgt_vals) if _bgt_vals else None
            effort_changed = prev_effort is not None and effort is not None and prev_effort != effort
            budget_changed = prev_budget is not None and budget is not None and budget != prev_budget
            effort_color = RED if effort_changed else ''
            budget_color = RED if budget_changed else ''
            config_str = f"  {effort_color}effort:{_fmt_effort(effort)}{SOFT_RESET if effort_color else ''}  {budget_color}think:{_fmt_thinking_budget(budget)}{SOFT_RESET if budget_color else ''}"

            if prev_group_last_entry is not None:
                ple = prev_group_last_entry
                d_msgs = last_msgs - ple.get('messages_total_chars', 0)
                delta_str = f"  {_format_delta('msgs', d_msgs)}"
            else:
                delta_str = f"  {DIM}(first turn){SOFT_RESET}"

            turn_ts = format_timestamp(group['timestamp'])[:5]

            all_lines.append(f"{PASTEL_PURPLE}Turn {turn_idx + 1} [{turn_ts}]{config_str}{delta_str}{SOFT_RESET}")
            line_keys.append(None)

            if prev_group_last_entry is not None:
                ple = prev_group_last_entry
                prev_sys = ple.get('system_total_chars', ple.get('system_prompt_chars', 0))
                prev_tools = ple.get('tools_total_chars', ple.get('tools_chars', 0))
                prev_msgs = ple.get('messages_total_chars', 0)
                all_lines.append(f"  {DIM}total: tools:{_format_k(prev_tools)}  msgs:{_format_k(prev_msgs)}{SOFT_RESET}")
            else:
                all_lines.append(f"  {DIM}total: (first turn){SOFT_RESET}")
            line_keys.append(None)

            prev_entry_for_delta = prev_group_last_entry
            t_lines, t_keys, opus_req_num, sub_req_num = render_turn_expanded(
                group, entries, expand_states, pane_width,
                prev_entry_for_delta, opus_req_num, sub_req_num,
                turns=turns, turn_idx=turn_idx,
                rendered_opus_labels=rendered_opus_labels,
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
            prev_effort = effort
            prev_budget = budget
            all_lines.append('')
            line_keys.append(None)
    else:
        for entry_idx, entry in enumerate(entries):
            model_short = _shorten_model(entry.get('model', '?'))
            if model_short == 'haiku':
                num_label = 'H'
            else:
                bp_len = len(entry.get('cache_breakpoints', []))
                if entry_idx == 0 or bp_len >= 1:
                    opus_req_num += 1
                    sub_req_num = 0
                    num_label = f'#{opus_req_num}'
                else:
                    sub_req_num += 1
                    num_label = f'#{opus_req_num}.{sub_req_num}'
            e_lines, e_keys = _render_entry_lines(entry_idx, entry, entries, expand_states, pane_width, indent='', num_label=num_label, rendered_opus_labels=rendered_opus_labels)
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
