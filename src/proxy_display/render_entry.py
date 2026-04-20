# INFRASTRUCTURE
import json
from typing import Optional

from ..constants import (
    SOFT_RESET, GREEN, RED, YELLOW, WHITE, DIM, DIM_YELLOW_BG,
)
from .format import _shorten_model, _format_delta, _format_k

# FUNCTIONS

# Render a single proxy entry into (lines, line_keys). indent sets the nesting level.
def _render_entry_lines(entry_idx: int, entry: dict, entries: list, expand_states: dict, pane_width: int, indent: str = '', num_label: str = '#0') -> tuple:
    L1 = indent
    L2 = indent + '  '
    L3 = indent + '    '
    L4 = indent + '      '
    lines = []
    keys = []

    model = _shorten_model(entry.get('model', '?'))
    msg_count = entry.get('message_count', 0)
    cache_bp = entry.get('cache_breakpoints', [])

    bp_count = len(cache_bp)
    is_expanded = expand_states.get(entry_idx, False)
    symbol = '\u25bc' if is_expanded else '\u25b6'

    is_standalone = (
        'haiku' in entry.get('model', '').lower()
        or (entry.get('system_total_chars', entry.get('system_prompt_chars', 0)) == 0
            and entry.get('tools_total_chars', entry.get('tools_chars', 0)) == 0
            and len(entry.get('cache_breakpoints', [])) == 0)
    )
    model_family = "haiku" if "haiku" in entry.get('model', '').lower() else "opus"
    prev_entry = None
    if not is_standalone:
        for _i in range(entry_idx - 1, -1, -1):
            _prev_model = entries[_i].get('model', '')
            _prev_family = "haiku" if "haiku" in _prev_model.lower() else "opus"
            if _prev_family == model_family:
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
    lines.append(f"{WHITE}{L1}{symbol} {num_label}  {model}  {msg_count}msg  BP:{bp_count}{mods_str}  {status_str}{haiku_info}{SOFT_RESET}")
    keys.append(entry_idx)
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

        messages = entry.get('messages', [])
        stripped_indices = set(entry.get('stripped_msg_indices', []))

        new_start = prev_entry.get('message_count', 0) if prev_entry is not None else 0
        for msg_idx, msg in enumerate(messages):
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars = msg.get('chars', 0)
            chars_fmt = f"{chars:,}c"
            blocks = msg.get('blocks', [])
            msg_key = (entry_idx, 'msg', msg_idx)
            is_msg_expanded = expand_states.get(msg_key, False)
            msg_symbol = '\u25bc' if is_msg_expanded else '\u25b6'
            is_stripped = msg_idx in stripped_indices
            is_old = msg_idx < new_start
            type_label = f"{len(blocks)} blocks" if len(blocks) > 1 else msg_type
            if is_stripped:
                lines.append(f"{L2}{DIM_YELLOW_BG}{DIM}{msg_symbol} [{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}  [STRIPPED]{SOFT_RESET}")
            elif is_old:
                lines.append(f"{L2}{DIM}{msg_symbol} [{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            else:
                lines.append(f"{L2}{WHITE}{msg_symbol} [{msg_idx:3d}] {role:<8} {type_label:<20} {chars_fmt:>8}{SOFT_RESET}")
            keys.append(msg_key)

            if is_msg_expanded:
                bg = DIM_YELLOW_BG if is_stripped else ''
                if blocks:
                    for bidx, blk in enumerate(blocks):
                        btype = blk.get('type', 'text')
                        bchars = blk.get('chars', 0)
                        bcc = ' [CC]' if blk.get('has_cc') else ''
                        lines.append(f"{L3}{bg}{DIM}[{bidx}] {btype:<12} {bchars:>6,}c{bcc}{SOFT_RESET}")
                        keys.append(None)
                        full_text = blk.get('full_text', blk.get('preview', ''))
                        if full_text:
                            for raw_line in full_text.split('\n'):
                                if not raw_line:
                                    lines.append(f"{L4}{bg}{DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                lines.append(f"{L4}{bg}{DIM}{raw_line}{SOFT_RESET}")
                                keys.append(None)
                else:
                    preview = msg.get('content_preview', '')
                    if preview:
                        for raw_line in preview.split('\n'):
                            if not raw_line:
                                lines.append(f"{L4}{bg}{DIM}{SOFT_RESET}")
                                keys.append(None)
                                continue
                            lines.append(f"{L4}{bg}{DIM}{raw_line}{SOFT_RESET}")
                            keys.append(None)
                    else:
                        lines.append(f"{L4}{bg}{DIM}(no preview){SOFT_RESET}")
                        keys.append(None)

    return lines, keys
