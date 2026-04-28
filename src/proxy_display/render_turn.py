# INFRASTRUCTURE
from ..constants import (
    SOFT_RESET, RED, WHITE, YELLOW, DIM,
)
from .format import _shorten_model, _format_delta, _format_k, _is_standalone_entry, _format_latency, _fmt_thinking_budget, _fmt_effort
from .render_messages import _aggregate_entry_tags, _aggregate_req_buckets

# FUNCTIONS

# Render all per-request rows for an expanded turn group, returning (lines, keys, opus_req_num, sub_req_num)
def render_turn_expanded(group: dict, entries: list, expand_states: dict, pane_width: int, prev_entry_for_delta, opus_req_num: int, sub_req_num: int, turns=None, turn_idx: int = 0, rendered_opus_labels: list = None) -> tuple:
    from .render_sections import render_system_blocks, render_tools
    from .render_messages import render_messages
    lines = []
    keys = []

    _raw_calls = turns[turn_idx].get('api_calls', []) if turns and turn_idx < len(turns) else []
    turn_api_calls = [
        c for c in _raw_calls
        if c.get('cache_read', 0) + c.get('cache_creation', 0) > 0
        or c.get('cache_read', 0) + c.get('cache_creation', 0) + c.get('direct', 0) > 1000
    ]
    opus_call_idx = 0

    for entry_idx, entry in group['entry_pairs']:
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

        msg_count = entry.get('message_count', 0)
        cache_bp = entry.get('cache_breakpoints', [])
        bp_count = len(cache_bp)
        mods = entry.get('modifications', [])

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

        e_sys = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
        e_tools = entry.get('tools_total_chars', entry.get('tools_chars', 0))
        e_msgs = entry.get('messages_total_chars', 0)
        req_delta_str = ''
        if not is_standalone and prev_entry_for_delta is not None:
            delta_parts = []
            if e_sys > 0:
                d_req_sys = e_sys - prev_entry_for_delta.get('system_total_chars', prev_entry_for_delta.get('system_prompt_chars', 0))
                if d_req_sys != 0:
                    delta_parts.append(_format_delta('sys', d_req_sys))
            if e_tools > 0:
                d_req_tools = e_tools - prev_entry_for_delta.get('tools_total_chars', prev_entry_for_delta.get('tools_chars', 0))
                if d_req_tools != 0:
                    delta_parts.append(_format_delta('tools', d_req_tools))
            d_req_msgs = e_msgs - prev_entry_for_delta.get('messages_total_chars', 0)
            if d_req_msgs != 0:
                delta_parts.append(_format_delta('msgs', d_req_msgs))
            req_delta_str = f"  {'  '.join(delta_parts)}" if delta_parts else ''

        _curr_tools = entry.get('tools_names', [])
        _prev_tools = prev_same.get('tools_names', []) if prev_same is not None else []
        _t_added = len(set(_curr_tools) - set(_prev_tools))
        _t_removed = len(set(_prev_tools) - set(_curr_tools))
        if _t_added > 0 and _t_removed > 0:
            mods_str = f" {YELLOW}🔧+{_t_added}-{_t_removed}{SOFT_RESET}"
        elif _t_added > 0:
            mods_str = f" {YELLOW}🔧+{_t_added}{SOFT_RESET}"
        elif _t_removed > 0:
            mods_str = f" {YELLOW}🔧-{_t_removed}{SOFT_RESET}"
        else:
            mods_str = ''

        warn_str = f"  {'  '.join(warn_parts)}" if warn_parts else ''
        req_key = ('req', entry_idx)
        is_req_expanded = expand_states.get(req_key, False)
        req_symbol = '\u25bc' if is_req_expanded else '\u25b6'
        if model_short == 'haiku':
            haiku_info = f"  sys:{_format_k(e_sys)} tools:{_format_k(e_tools)} msgs:{_format_k(e_msgs)}"
        else:
            haiku_info = ''
        eff_val = entry.get('effort_value')
        eff_str = f" eff:{_fmt_effort(eff_val)}" if eff_val is not None else ''
        tc = entry.get('thinking_config') or {}
        think_str = f" think:{_fmt_thinking_budget(entry.get('thinking_budget_tokens'))}" if tc else ''
        if model_short != 'haiku':
            api_call = turn_api_calls[opus_call_idx] if opus_call_idx < len(turn_api_calls) else {}
            cr = api_call.get('cache_read', 0)
            cc = api_call.get('cache_creation', 0)
            cr_cc_str = f" CR:{_format_k(cr)} CC:{_format_k(cc)}"
            opus_call_idx += 1
        else:
            cr_cc_str = ''

        tag_labels = _aggregate_entry_tags(entry)
        tag_badge = f' {RED}⚠{",".join(tag_labels)}{SOFT_RESET}' if tag_labels else ''
        latency_str = _format_latency(entry.get('ttfb_ms'), entry.get('output_tokens_per_sec'))
        lines.append(f"  {WHITE}{req_symbol} {num_label} {model_short} {msg_count}msg BP:{bp_count}{eff_str}{think_str}{cr_cc_str}{mods_str}{warn_str}{req_delta_str}{haiku_info}{tag_badge}{latency_str}{SOFT_RESET}")
        keys.append(req_key)

        if is_req_expanded:
            _section_ref = None if is_standalone else prev_same
            buckets = _aggregate_req_buckets(entry, _section_ref)
            parts = [f'INERT:{c}' for c in buckets['inert_codes']]
            parts += [f'IDX:{i}' for i in buckets['idx_msgs']]
            parts += buckets['leak_signals']
            parts += buckets['sus_signals']
            if parts:
                lines.append(f"    {DIM}{'  '.join(parts)}{SOFT_RESET}")
                keys.append(None)
            s_lines, s_keys = render_system_blocks(entry_idx, entry, _section_ref, expand_states, pane_width, mods)
            lines.extend(s_lines)
            keys.extend(s_keys)
            t_lines, t_keys = render_tools(entry_idx, entry, _section_ref, expand_states, pane_width)
            lines.extend(t_lines)
            keys.extend(t_keys)
            m_lines, m_keys = render_messages(entry, _section_ref, entries, expand_states, pane_width)
            lines.extend(m_lines)
            keys.extend(m_keys)

        if len(entry.get('cache_breakpoints', [])) >= 1:
            prev_entry_for_delta = entry

    return lines, keys, opus_req_num, sub_req_num
