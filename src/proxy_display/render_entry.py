# INFRASTRUCTURE
import json
import time
from typing import Optional

from ..constants import (
    SOFT_RESET, GREEN, RED, YELLOW, WHITE, DIM, DIM_YELLOW_BG,
)
from ..utils import _ANSI_ESCAPE_RE, _cell_width
from .format import _shorten_model, _format_delta, _format_k, _is_standalone_entry
from .render_messages import _aggregate_entry_tags, _aggregate_req_buckets
from .render_sections import render_fields_delta

# FUNCTIONS

# Render a single proxy entry into (lines, line_keys). indent sets the nesting level.
def _render_entry_lines(entry_idx: int, entry: dict, entries: list, expand_states: dict, pane_width: int, indent: str = '', num_label: str = '#0', rendered_opus_labels: list = None, copy_feedback=None, copy_rows_out=None) -> tuple:
    L1 = indent
    L2 = indent + '  '
    L3 = indent + '    '
    lines = []
    keys = []

    model = _shorten_model(entry.get('model', '?'))
    msg_count = entry.get('message_count', 0)
    is_expanded = expand_states.get(entry_idx, False)
    symbol = '\u25bc' if is_expanded else '\u25b6'

    is_standalone = _is_standalone_entry(entry)
    if model != 'haiku' and not is_standalone and rendered_opus_labels is not None:
        rendered_opus_labels.append((entry_idx, num_label))
    model_family = "haiku" if "haiku" in entry.get('model', '').lower() else "opus"
    prev_entry = None
    if not is_standalone:
        for _i in range(entry_idx - 1, -1, -1):
            _prev_model = entries[_i].get('model', '')
            _prev_family = "haiku" if "haiku" in _prev_model.lower() else "opus"
            if _prev_family == model_family and not _is_standalone_entry(entries[_i]):
                prev_entry = entries[_i]
                break

    warn_symbols = []
    warn_details = []
    if prev_entry is not None:
        if entry.get('tools_hash') and prev_entry.get('tools_hash') and entry.get('tools_hash') != prev_entry.get('tools_hash'):
            warn_symbols.append(f"{RED}⚠T{SOFT_RESET}")
            curr_names = set(entry.get('tools_names', []))
            prev_names = set(prev_entry.get('tools_names', []))
            added = sorted(curr_names - prev_names)
            removed = sorted(prev_names - curr_names)
            warn_details.append([f"{L3}{GREEN}+{n}{SOFT_RESET}" for n in added] + [f"{L3}{RED}-{n}{SOFT_RESET}" for n in removed])
        if entry.get('system_total_chars') is not None and prev_entry.get('system_total_chars') is not None and entry.get('system_total_chars') != prev_entry.get('system_total_chars'):
            warn_symbols.append(f"{RED}⚠S{SOFT_RESET}")
            old_c = prev_entry['system_total_chars']
            new_c = entry['system_total_chars']
            delta = new_c - old_c
            warn_details.append([f"{L3}{DIM}sys: {_format_k(old_c)} → {_format_k(new_c)} ({delta:+,}){SOFT_RESET}"])
    all_status = warn_symbols[:]
    status_str = '  '.join(all_status)
    _curr_tools = entry.get('tools_names', [])
    _prev_tools = prev_entry.get('tools_names', []) if prev_entry is not None else []
    _t_added = len(set(_curr_tools) - set(_prev_tools))
    _t_removed = len(set(_prev_tools) - set(_curr_tools))
    if _t_added > 0 and _t_removed > 0:
        mods_str = f"  {YELLOW}🔧+{_t_added}-{_t_removed}{SOFT_RESET}"
    elif _t_added > 0:
        mods_str = f"  {YELLOW}🔧+{_t_added}{SOFT_RESET}"
    elif _t_removed > 0:
        mods_str = f"  {YELLOW}🔧-{_t_removed}{SOFT_RESET}"
    else:
        mods_str = ''

    sys_chars = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    tools_chars = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    msgs_chars = entry.get('messages_total_chars', 0)
    if is_standalone:
        haiku_info = f"  sys:{_format_k(sys_chars)} tools:{_format_k(tools_chars)} msgs:{_format_k(msgs_chars)}"
    else:
        haiku_info = ''
    tag_labels = _aggregate_entry_tags(entry)
    tag_badge = f'  {RED}⚠{",".join(tag_labels)}{SOFT_RESET}' if tag_labels else ''
    header_raw_e = f"{WHITE}{L1}{symbol} {num_label}  {model}  {msg_count}msg{mods_str}  {status_str}{haiku_info}{tag_badge}{SOFT_RESET}"
    if copy_feedback is not None:
        _stripped_he = _ANSI_ESCAPE_RE.sub('', header_raw_e)
        visible_len = sum(_cell_width(ch) for ch in _stripped_he)
        is_flash = copy_feedback.get(entry_idx, 0) > time.time()
        copy_sym = '✓' if is_flash else '⎘'
        sym_cells = _cell_width(copy_sym)
        pad = pane_width - 1 - sym_cells - visible_len  # 1 space + sym_cells
        if pad >= 0:
            lines.append(header_raw_e + ' ' * pad + ' ' + copy_sym)
        else:
            lines.append(header_raw_e)
    else:
        lines.append(header_raw_e)
    keys.append(entry_idx)
    if is_expanded:
        buckets = _aggregate_req_buckets(entry, prev_entry)
        parts = [f'INERT:{c}' for c in buckets['inert_codes']]
        parts += [f'IDX:{i}' for i in buckets['idx_msgs']]
        parts += buckets['leak_signals']
        parts += buckets['sus_signals']
        if parts:
            lines.append(f"{L2}{DIM}{'  '.join(parts)}{SOFT_RESET}")
            keys.append(None)
    if prev_entry is None:
        lines.append(f"{L2}{DIM}(first request){SOFT_RESET}")
        keys.append(None)
    else:
        d_sys = sys_chars - prev_entry.get('system_total_chars', prev_entry.get('system_prompt_chars', 0))
        d_tools = tools_chars - prev_entry.get('tools_total_chars', prev_entry.get('tools_chars', 0))
        d_msgs = msgs_chars - prev_entry.get('messages_total_chars', 0)
        if d_sys == 0 and d_tools == 0 and d_msgs == 0:
            lines.append(f"{L2}{DIM}Δ: (no change){SOFT_RESET}")
            keys.append(None)
        else:
            neg_key = (entry_idx, 'neg_delta')
            is_neg_exp = expand_states.get(neg_key, False)
            neg_sym = '\u25bc' if is_neg_exp else '\u25b6'
            lines.append(f"{L2}{neg_sym} {_format_delta('sys', d_sys)}  {_format_delta('tools', d_tools)}  {_format_delta('msgs', d_msgs)}")
            keys.append(neg_key)
            if is_neg_exp:
                if d_tools < 0:
                    curr_names = set(entry.get('tools_names', []))
                    prev_names = prev_entry.get('tools_names', [])
                    prev_defs = {d.get('name', ''): d for d in prev_entry.get('tools_defs', [])}
                    removed_tools = [n for n in prev_names if n not in curr_names]
                    for t_name in removed_tools:
                        t_chars = len(json.dumps(prev_defs.get(t_name, {})))
                        lines.append(f"{L3}{RED}removed:{SOFT_RESET} {DIM}{t_name} ({_format_k(t_chars)}c){SOFT_RESET}")
                        keys.append(None)
                elif d_tools > 0:
                    curr_names = entry.get('tools_names', [])
                    prev_names = set(prev_entry.get('tools_names', []))
                    curr_defs = {d.get('name', ''): d for d in entry.get('tools_defs', [])}
                    added_tools = [n for n in curr_names if n not in prev_names]
                    for t_name in added_tools:
                        t_chars = len(json.dumps(curr_defs.get(t_name, {})))
                        lines.append(f"{L3}{GREEN}added:{SOFT_RESET} {DIM}{t_name} ({_format_k(t_chars)}c){SOFT_RESET}")
                        keys.append(None)
                if d_msgs < 0:
                    curr_msgs = entry.get('messages', [])
                    prev_msgs = prev_entry.get('messages', [])
                    removed_msgs = prev_msgs[len(curr_msgs):]
                    for m_offset, msg in enumerate(removed_msgs):
                        m_idx = len(curr_msgs) + m_offset
                        role = msg.get('role', '?')[:4]
                        m_type = msg.get('type', 'text')
                        m_chars = msg.get('chars', 0)
                        lines.append(f"{L3}{RED}removed:{SOFT_RESET} {DIM}[{m_idx:3d}] {role:<8} {m_type:<20} {m_chars:,}c{SOFT_RESET}")
                        keys.append(None)
                elif d_msgs > 0:
                    curr_msgs = entry.get('messages', [])
                    prev_msgs = prev_entry.get('messages', []) if prev_entry else []
                    added_msgs = curr_msgs[len(prev_msgs):]
                    for m_offset, msg in enumerate(added_msgs):
                        m_idx = len(prev_msgs) + m_offset
                        role = msg.get('role', '?')[:4]
                        m_type = msg.get('type', 'text')
                        m_chars = msg.get('chars', 0)
                        lines.append(f"{L3}{GREEN}added:{SOFT_RESET} {DIM}[{m_idx:3d}] {role:<8} {m_type:<20} {m_chars:,}c{SOFT_RESET}")
                        keys.append(None)

    if warn_symbols:
        warn_key = (entry_idx, 'warnings')
        is_warn_expanded = expand_states.get(warn_key, False)
        warn_sym = '\u25bc' if is_warn_expanded else '\u25b6'
        lines.append(f"{L2}{warn_sym} {'  '.join(warn_symbols)}")
        keys.append(warn_key)
        if is_warn_expanded:
            for detail_lines in warn_details:
                for dl in detail_lines:
                    lines.append(dl)
                    keys.append(None)

    schema_warnings = entry.get('schema_warnings', [])
    if schema_warnings:
        schema_key = (entry_idx, 'schema')
        is_schema_expanded = expand_states.get(schema_key, False)
        schema_sym = '\u25bc' if is_schema_expanded else '\u25b6'
        lines.append(f"{L2}{schema_sym} {RED}⚠ SCHEMA DRIFT ({len(schema_warnings)}){SOFT_RESET}")
        keys.append(schema_key)
        if is_schema_expanded:
            for sw in schema_warnings:
                lines.append(f"{L3}{DIM}{sw}{SOFT_RESET}")
                keys.append(None)

    if is_expanded:
        lines.append(f"{L2}{DIM}{'─' * min(40, pane_width - len(L2) - 2)}{SOFT_RESET}")
        keys.append(None)
        f_lines, f_keys = render_fields_delta(entry_idx, entry, expand_states, pane_width)
        lines.extend(f_lines)
        keys.extend(f_keys)

        messages = entry.get('messages', [])
        stripped_indices = set(entry.get('stripped_msg_indices', []))

        new_start = prev_entry.get('message_count', 0) if prev_entry is not None else 0
        for msg_idx, msg in enumerate(messages):
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars = msg.get('chars', 0)
            chars_fmt = f"{chars:,}c"
            blocks = msg.get('blocks', [])
            is_stripped = msg_idx in stripped_indices
            is_old = msg_idx < new_start
            type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
            if is_stripped:
                lines.append(f"{L2}{DIM_YELLOW_BG}{DIM}[{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}  [STRIPPED]{SOFT_RESET}")
            elif is_old:
                lines.append(f"{L2}{DIM}[{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            else:
                lines.append(f"{L2}{WHITE}[{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            keys.append(None)

    return lines, keys
