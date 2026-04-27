# INFRASTRUCTURE
from collections import Counter
from typing import List
from ..constants import WHITE, RED, DIM, SOFT_RESET
from ..format.token_format import _format_k

_prev_values: dict = {}
_worker_prev_values: dict = {}

# FUNCTIONS
# Format metadata display for latest proxy entry — public interface for main metadata pane
def _format_metadata(entry: dict) -> List[str]:
    global _prev_values
    new_values: dict = {}
    result = _format_metadata_with_state(entry, _prev_values, new_values)
    _prev_values = new_values
    return result

# Format metadata display for worker proxy entry — uses separate state from main metadata pane
def _format_worker_metadata(entry: dict) -> List[str]:
    global _worker_prev_values
    new_values: dict = {}
    result = _format_metadata_with_state(entry, _worker_prev_values, new_values)
    _worker_prev_values = new_values
    return result

# Single implementation of metadata formatting with explicit state dicts
def _format_metadata_with_state(entry: dict, prev_values: dict, new_values: dict) -> List[str]:
    lines: List[str] = []

    # SYSTEM section
    sys_blocks = entry.get('system_blocks', [])
    sys_total = entry.get('system_total_chars', 0)
    lines.append(f"{WHITE}─── SYSTEM ───{SOFT_RESET}")
    if sys_blocks:
        for sb in sys_blocks:
            idx = sb.get('idx', 0)
            chars = sb.get('chars', 0)
            key = f"sys_chars_{idx}"
            new_values[key] = chars
            prev = prev_values.get(key)
            changed = prev is not None and prev != chars
            if changed:
                lines.append(f"  {RED}[{idx}]: {_format_k(prev)} → {_format_k(chars)}{SOFT_RESET}")
            else:
                lines.append(f"  {DIM}[{idx}]: {_format_k(chars)}{SOFT_RESET}")
        new_values['sys_total'] = sys_total
        prev_total = prev_values.get('sys_total')
        total_changed = prev_total is not None and prev_total != sys_total
        if total_changed:
            lines.append(f"  {RED}total: {_format_k(prev_total)} → {_format_k(sys_total)} ({len(sys_blocks)} blocks){SOFT_RESET}")
        else:
            lines.append(f"  {DIM}total: {_format_k(sys_total)} ({len(sys_blocks)} blocks){SOFT_RESET}")
    else:
        lines.append(f"  {DIM}(no system data){SOFT_RESET}")

    # TOOLS section
    tools_count = entry.get('tools_count', 0)
    tools_chars = entry.get('tools_total_chars', 0)
    tools_hash = entry.get('tools_hash', '')
    lines.append('')
    lines.append(f"{WHITE}─── TOOLS ───{SOFT_RESET}")
    new_values['tools_count'] = tools_count
    new_values['tools_hash'] = tools_hash
    prev_hash = prev_values.get('tools_hash')
    hash_changed = prev_hash is not None and prev_hash != tools_hash
    hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
    if tools_count:
        color = RED if hash_changed else DIM
        lines.append(f"  {color}{tools_count} defs ({_format_k(tools_chars)}){hash_str}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}(no tools data){SOFT_RESET}")

    # CONFIG section
    tc = entry.get('thinking_config', {})
    oc = entry.get('output_config', {})
    effort = oc.get('effort', '?')
    budget = tc.get('budget_tokens', 0)
    think_type = tc.get('type', '?')
    lines.append('')
    lines.append(f"{WHITE}─── CONFIG ───{SOFT_RESET}")
    new_values['effort'] = effort
    new_values['budget'] = budget
    new_values['think_type'] = think_type
    prev_effort = prev_values.get('effort')
    effort_changed = prev_effort is not None and prev_effort != effort
    if effort_changed:
        lines.append(f"  {RED}effort: {prev_effort} → {effort}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}effort: {effort}{SOFT_RESET}")
    prev_budget = prev_values.get('budget')
    prev_think_type = prev_values.get('think_type')
    think_changed = (prev_budget is not None and prev_budget != budget) or (prev_think_type is not None and prev_think_type != think_type)
    budget_str = _format_k(budget) if budget else '?'
    think_str = f"{budget_str} ({think_type})"
    think_color = RED if think_changed else DIM
    lines.append(f"  {think_color}thinking: {think_str}{SOFT_RESET}")

    model = entry.get('model', '?')
    new_values['model'] = model
    prev_model = prev_values.get('model')
    model_changed = prev_model is not None and prev_model != model
    if model_changed:
        lines.append(f"  {RED}model: {prev_model} → {model}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}model: {model}{SOFT_RESET}")

    max_tokens = entry.get('max_tokens', 0)
    new_values['max_tokens'] = max_tokens
    prev_max = prev_values.get('max_tokens')
    max_changed = prev_max is not None and prev_max != max_tokens
    max_str = _format_k(max_tokens) if max_tokens else '?'
    if max_changed:
        lines.append(f"  {RED}max_tokens: {_format_k(prev_max)} → {max_str}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}max_tokens: {max_str}{SOFT_RESET}")

    temperature = entry.get('temperature', None)
    new_values['temperature'] = temperature
    prev_temp = prev_values.get('temperature')
    temp_changed = prev_temp is not None and prev_temp != temperature
    temp_str = str(temperature) if temperature is not None else 'default'
    if temp_changed:
        prev_str = str(prev_temp) if prev_temp is not None else 'default'
        lines.append(f"  {RED}temperature: {prev_str} → {temp_str}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}temperature: {temp_str}{SOFT_RESET}")

    top_p = entry.get('top_p', None)
    new_values['top_p'] = top_p
    top_p_str = str(top_p) if top_p is not None else 'default'
    lines.append(f"  {DIM}top_p: {top_p_str}{SOFT_RESET}")

    top_k = entry.get('top_k', None)
    new_values['top_k'] = top_k
    top_k_str = str(top_k) if top_k is not None else 'default'
    lines.append(f"  {DIM}top_k: {top_k_str}{SOFT_RESET}")

    tool_choice = entry.get('tool_choice', {})
    tc_type = tool_choice.get('type', '') if tool_choice else ''
    new_values['tool_choice'] = tc_type
    tc_str = tc_type if tc_type else 'auto'
    lines.append(f"  {DIM}tool_choice: {tc_str}{SOFT_RESET}")

    output_format = entry.get('output_config', {}).get('format', {})
    fmt_type = output_format.get('type', '') if output_format else ''
    new_values['output_format'] = fmt_type
    prev_fmt = prev_values.get('output_format')
    fmt_changed = prev_fmt is not None and prev_fmt != fmt_type
    fmt_str = fmt_type if fmt_type else '-'
    if fmt_changed:
        prev_fmt_str = prev_values.get('output_format', '-') or '-'
        lines.append(f"  {RED}output_format: {prev_fmt_str} → {fmt_str}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}output_format: {fmt_str}{SOFT_RESET}")

    stream = entry.get('stream', None)
    new_values['stream'] = stream
    stream_str = str(stream) if stream is not None else '-'
    lines.append(f"  {DIM}stream: {stream_str}{SOFT_RESET}")

    # CACHE MARKERS section
    cache_bps = entry.get('cache_breakpoints', [])
    msg_count = entry.get('message_count', 0)
    lines.append('')
    lines.append(f"{WHITE}─── CACHE MARKERS ───{SOFT_RESET}")
    if cache_bps:
        for bp_idx in cache_bps:
            label = '  (last msg)' if bp_idx == msg_count - 1 else ''
            lines.append(f"  {DIM}msg[{bp_idx}]{label}{SOFT_RESET}")
    else:
        lines.append(f"  {DIM}(no message breakpoints){SOFT_RESET}")

    # SESSION section
    lines.append('')
    lines.append(f"{WHITE}─── SESSION ───{SOFT_RESET}")
    request_id = entry.get('request_id', '')
    if request_id:
        lines.append(f"  {DIM}req: {request_id[:12]}{SOFT_RESET}")
    mods = entry.get('modifications', [])
    if mods:
        mod_counts = Counter(mods)
        mod_parts = []
        for mod, count in mod_counts.items():
            if count > 1:
                mod_parts.append(f"{mod} ×{count}")
            else:
                mod_parts.append(mod)
        lines.append(f"  {DIM}mods: {', '.join(mod_parts)}{SOFT_RESET}")

    return lines
