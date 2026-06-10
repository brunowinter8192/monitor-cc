# INFRASTRUCTURE
import time
from ..constants import (
    SOFT_RESET, RED, GREEN, WHITE, YELLOW, DIM,
)
from ..utils import _ANSI_ESCAPE_RE, _cell_width
from .format import _shorten_model, _format_delta, _format_k, _is_standalone_entry, _fmt_thinking_budget, _fmt_effort
from .render_messages import _aggregate_req_buckets

# FUNCTIONS

# Compute cross-group delta string for a request (e.g. "  Δsys:+1k  Δmsgs:+500"), or ''
def _compute_req_delta_str(entry: dict, is_standalone: bool, prev_entry_for_delta) -> str:
    if is_standalone or prev_entry_for_delta is None:
        return ''
    e_sys = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    e_tools = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    e_msgs = entry.get('messages_total_chars', 0)
    delta_parts = []
    if e_sys > 0:
        d = e_sys - prev_entry_for_delta.get('system_total_chars', prev_entry_for_delta.get('system_prompt_chars', 0))
        if d != 0:
            delta_parts.append(_format_delta('sys', d))
    if e_tools > 0:
        d = e_tools - prev_entry_for_delta.get('tools_total_chars', prev_entry_for_delta.get('tools_chars', 0))
        if d != 0:
            delta_parts.append(_format_delta('tools', d))
    d = e_msgs - prev_entry_for_delta.get('messages_total_chars', 0)
    if d != 0:
        delta_parts.append(_format_delta('msgs', d))
    return f"  {'  '.join(delta_parts)}" if delta_parts else ''

# Compute tool-mod string (🔧+N / -N / ±N) comparing entry tools to prev_same, or ''
def _compute_req_mods_str(entry: dict, prev_same) -> str:
    _curr = entry.get('tools_names', [])
    _prev = prev_same.get('tools_names', []) if prev_same is not None else []
    added = len(set(_curr) - set(_prev))
    removed = len(set(_prev) - set(_curr))
    if added > 0 and removed > 0:
        return f" {YELLOW}🔧+{added}-{removed}{SOFT_RESET}"
    if added > 0:
        return f" {YELLOW}🔧+{added}{SOFT_RESET}"
    if removed > 0:
        return f" {YELLOW}🔧-{removed}{SOFT_RESET}"
    return ''

# Build the request header line string with haiku_info, eff/think, tag_badge, copy ⎘/✓ right-pad
def _build_req_header_line(entry: dict, entry_idx: int, num_label: str, req_symbol: str, model_short: str, msg_count: int, req_delta_str: str, mods_str: str, warn_str: str, pane_width: int, copy_feedback) -> str:
    e_sys = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    e_tools = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    e_msgs = entry.get('messages_total_chars', 0)
    haiku_info = f"  sys:{_format_k(e_sys)} tools:{_format_k(e_tools)} msgs:{_format_k(e_msgs)}" if model_short == 'haiku' else ''
    eff_val = entry.get('effort_value')
    eff_str = f" eff:{_fmt_effort(eff_val)}" if eff_val is not None else ''
    mt = entry.get('max_tokens') or 0
    think_str = f" think:{_fmt_thinking_budget(mt)}" if (mt and model_short != 'haiku') else ''
    _fid = entry.get('flow_id', '')
    _n_strip = len(entry.get('_strip_fns_lookup', {}).get(_fid, set()))
    _n_inj   = len(entry.get('_inject_fns_lookup', {}).get(_fid, set()))
    _badge_parts = []
    if _n_strip: _badge_parts.append(f'{YELLOW}{_n_strip}strip{SOFT_RESET}')
    if _n_inj:   _badge_parts.append(f'{GREEN}{_n_inj}inj{SOFT_RESET}')
    tag_badge = (' ' + ' '.join(_badge_parts)) if _badge_parts else ''
    header_raw = f"  {WHITE}{req_symbol} {num_label} {model_short} {msg_count}msg{eff_str}{think_str}{mods_str}{warn_str}{req_delta_str}{haiku_info}{tag_badge}{SOFT_RESET}"
    if copy_feedback is not None:
        _stripped_h = _ANSI_ESCAPE_RE.sub('', header_raw)
        visible_len = sum(_cell_width(ch) for ch in _stripped_h)
        is_flash = copy_feedback.get(entry_idx, 0) > time.time()
        copy_sym = '✓' if is_flash else '⎘'
        sym_cells = _cell_width(copy_sym)
        pad = pane_width - 1 - sym_cells - visible_len  # 1 space + sym_cells
        if pad >= 0:
            return header_raw + ' ' * pad + ' ' + copy_sym
    return header_raw

# Render expanded section for one request entry (buckets, fields, beta, directives, sys, tools, messages)
def _render_req_expanded(entry_idx: int, entry: dict, entries: list, is_standalone: bool, prev_same, expand_states: dict, pane_width: int) -> tuple:
    from .render_sections import render_system_blocks, render_tools, render_fields_delta, render_beta, render_directives
    from .render_messages import render_messages
    lines = []
    keys = []
    mods = entry.get('modifications', [])
    _section_ref = None if is_standalone else prev_same
    buckets = _aggregate_req_buckets(entry, _section_ref)
    parts = [f'INERT:{c}' for c in buckets['inert_codes']]
    parts += [f'IDX:{i}' for i in buckets['idx_msgs']]
    parts += buckets['leak_signals']
    parts += buckets['sus_signals']
    if parts:
        lines.append(f"    {DIM}{'  '.join(parts)}{SOFT_RESET}")
        keys.append(None)
    f_lines, f_keys = render_fields_delta(entry_idx, entry, expand_states, pane_width)
    lines.extend(f_lines)
    keys.extend(f_keys)
    b_lines, b_keys = render_beta(entry_idx, entry, expand_states)
    lines.extend(b_lines)
    keys.extend(b_keys)
    d_lines, d_keys = render_directives(entry_idx, entry, expand_states)
    lines.extend(d_lines)
    keys.extend(d_keys)
    s_lines, s_keys = render_system_blocks(entry_idx, entry, _section_ref, expand_states, pane_width, mods)
    lines.extend(s_lines)
    keys.extend(s_keys)
    t_lines, t_keys = render_tools(entry_idx, entry, _section_ref, expand_states, pane_width)
    lines.extend(t_lines)
    keys.extend(t_keys)
    m_lines, m_keys = render_messages(entry, _section_ref, entries, expand_states, pane_width)
    lines.extend(m_lines)
    keys.extend(m_keys)
    return lines, keys

# Render all per-request rows for an expanded turn group, returning (lines, keys, opus_req_num, sub_req_num)
def render_turn_expanded(group: dict, entries: list, expand_states: dict, pane_width: int, prev_entry_for_delta, opus_req_num: int, sub_req_num: int, turns=None, turn_idx: int = 0, rendered_opus_labels: list = None, copy_feedback=None, copy_rows_out=None) -> tuple:
    lines = []
    keys = []
    for entry_idx, entry in group['entry_pairs']:
        model_short = _shorten_model(entry.get('model', '?'))
        if _is_standalone_entry(entry):
            num_label = 'H' if model_short == 'haiku' else 'S'
        else:
            if (entry.get('diff_from_prev') or {}).get('messages_added', 1) > 0:
                opus_req_num += 1
                sub_req_num = 0
                num_label = f'#{opus_req_num}'
            else:
                sub_req_num += 1
                num_label = f'#{opus_req_num}.{sub_req_num}'
        msg_count = entry.get('message_count', 0)
        warn_parts = []
        prev_same = None
        is_standalone = _is_standalone_entry(entry)
        if model_short != 'haiku' and not is_standalone and rendered_opus_labels is not None:
            rendered_opus_labels.append((entry_idx, num_label))
        if not is_standalone:
            _ef = 'haiku' if 'haiku' in entry.get('model', '').lower() else 'opus'
            for _i in range(entry_idx - 1, -1, -1):
                _pf = 'haiku' if 'haiku' in entries[_i].get('model', '').lower() else 'opus'
                if _pf == _ef and not _is_standalone_entry(entries[_i]):
                    prev_same = entries[_i]
                    break
        if prev_same is not None:
            if entry.get('tools_hash') and prev_same.get('tools_hash') and entry.get('tools_hash') != prev_same.get('tools_hash'):
                warn_parts.append(f"{RED}⚠T{SOFT_RESET}")
            if entry.get('system_total_chars') is not None and prev_same.get('system_total_chars') is not None and entry.get('system_total_chars') != prev_same.get('system_total_chars'):
                warn_parts.append(f"{RED}⚠S{SOFT_RESET}")
        warn_str = f"  {'  '.join(warn_parts)}" if warn_parts else ''
        req_key = ('req', entry_idx)
        is_req_expanded = expand_states.get(req_key, False)
        req_symbol = '▼' if is_req_expanded else '▶'
        req_delta_str = _compute_req_delta_str(entry, is_standalone, prev_entry_for_delta)
        mods_str = _compute_req_mods_str(entry, prev_same)
        lines.append(_build_req_header_line(entry, entry_idx, num_label, req_symbol, model_short, msg_count, req_delta_str, mods_str, warn_str, pane_width, copy_feedback))
        keys.append(req_key)
        if is_req_expanded:
            e_lines, e_keys = _render_req_expanded(entry_idx, entry, entries, is_standalone, prev_same, expand_states, pane_width)
            lines.extend(e_lines)
            keys.extend(e_keys)
        if len(entry.get('cache_breakpoints', [])) >= 1:
            prev_entry_for_delta = entry
    return lines, keys, opus_req_num, sub_req_num
