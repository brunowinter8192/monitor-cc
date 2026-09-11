# INFRASTRUCTURE
from typing import Optional

from ..colors import (
    SOFT_RESET, RED, DIM, DIM_YELLOW_BG, DIM_GREEN_BG,
)
from .format import _format_k
from .render_line_helpers import _emit_text_lines, _emit_span_lines, _emit_inline_spans

# FUNCTIONS

def _extract_schema_props(input_schema) -> tuple:
    props = input_schema.get('properties', {}) if isinstance(input_schema, dict) else {}
    required_props = input_schema.get('required', []) if isinstance(input_schema, dict) else []
    return props, required_props

def _render_tool_params(props: dict, required_props: list, indent: str, bg: str) -> tuple:
    lines = []
    keys = []
    for param_name, param_info in props.items():
        if isinstance(param_info, dict):
            param_type = param_info.get('type', '?')
            param_desc = param_info.get('description', '')
            req_marker = '*' if param_name in required_props else ''
            param_line = f"{param_name}{req_marker}: {param_type}"
            if param_desc:
                param_line += f" — {param_desc}"
            lines.append(f"{indent}{bg}{DIM}{param_line}{SOFT_RESET}")
            keys.append(None)
    return lines, keys

def _render_tool_desc(tool_def: dict, s_desc: list, i_desc: list, bg: str) -> tuple:
    lines = []
    keys = []
    if i_desc and isinstance(i_desc[0], (list, tuple)):
        n_lines, n_keys = _emit_inline_spans(i_desc, "        ", DIM_GREEN_BG)
        lines.extend(n_lines)
        keys.extend(n_keys)
        s_lines, s_keys = _emit_span_lines(s_desc or [], "        ", DIM_YELLOW_BG)
        lines.extend(s_lines)
        keys.extend(s_keys)
        return lines, keys
    description = tool_def.get('description', '')
    if description:
        d_lines, d_keys = _emit_text_lines(description, "        ", bg)
        lines.extend(d_lines)
        keys.extend(d_keys)
    s_lines, s_keys = _emit_span_lines(s_desc or [], "        ", DIM_YELLOW_BG)
    lines.extend(s_lines)
    keys.extend(s_keys)
    i_lines, i_keys = _emit_span_lines(i_desc or [], "        ", DIM_GREEN_BG)
    lines.extend(i_lines)
    keys.extend(i_keys)
    return lines, keys

def _render_tool_dual(tool_idx: int, t_name: str, tool_def: dict, entry: dict, expand_states: dict, entry_idx: int) -> tuple:
    lines = []
    keys = []
    tool_key = ('tool', entry_idx, tool_idx)
    is_tool_exp = expand_states.get(tool_key, False)
    t_symbol = '▼' if is_tool_exp else '▶'
    s_tool = entry['_stripped_spans']['tools'].get(t_name, {})
    i_tool = entry['_injected_spans']['tools'].get(t_name, {})
    whole_injected = bool(i_tool.get('whole'))
    s_desc = s_tool.get('desc', [])
    i_desc = i_tool.get('desc', [])
    hdr_bg = DIM_GREEN_BG if whole_injected else ''
    lines.append(f"      {hdr_bg}{DIM}{t_symbol} {t_name}{SOFT_RESET}")
    keys.append(tool_key)
    if is_tool_exp:
        bg = DIM_GREEN_BG if whole_injected else ''
        d_lines, d_keys = _render_tool_desc(tool_def, s_desc, i_desc, bg)
        lines.extend(d_lines)
        keys.extend(d_keys)
        props, required_props = _extract_schema_props(tool_def.get('input_schema', {}))
        p_lines, p_keys = _render_tool_params(props, required_props, "        ", bg)
        lines.extend(p_lines)
        keys.extend(p_keys)
    return lines, keys

def _render_whole_stripped_tool(entry_idx: int, name: str, tool_def: Optional[dict], expand_states: dict) -> tuple:
    lines = []
    keys = []
    tool_key = ('stripped_tool', entry_idx, name)
    is_tool_exp = expand_states.get(tool_key, False)
    t_symbol = '▼' if is_tool_exp else '▶'
    lines.append(f"      {DIM_YELLOW_BG}{DIM}{t_symbol} {name}{SOFT_RESET}")
    keys.append(tool_key)
    if is_tool_exp:
        if tool_def is None:
            lines.append(f"        {DIM_YELLOW_BG}{DIM}(original definition unavailable){SOFT_RESET}")
            keys.append(None)
            return lines, keys
        description = tool_def.get('description', '')
        if description:
            d_lines, d_keys = _emit_text_lines(description, "        ", DIM_YELLOW_BG)
            lines.extend(d_lines)
            keys.extend(d_keys)
        props, required_props = _extract_schema_props(tool_def.get('input_schema', {}))
        p_lines, p_keys = _render_tool_params(props, required_props, "        ", DIM_YELLOW_BG)
        lines.extend(p_lines)
        keys.extend(p_keys)
    return lines, keys

def _compute_tools_delta(tools_hash: str, tools_names: list, prev_entry_for_delta) -> dict:
    prev_tools_hash = prev_entry_for_delta.get('tools_hash', '') if prev_entry_for_delta else ''
    prev_tools_names = prev_entry_for_delta.get('tools_names', []) if prev_entry_for_delta else []
    tools_changed = bool(prev_tools_hash) and prev_tools_hash != tools_hash
    is_first_request = not prev_tools_hash
    added = [n for n in tools_names if n not in set(prev_tools_names)] if tools_changed else []
    removed = [n for n in prev_tools_names if n not in set(tools_names)] if tools_changed else []
    return {
        'tools_changed': tools_changed,
        'is_first_request': is_first_request,
        'added': added,
        'removed': removed,
    }

def _render_tool_defs_list(tools_defs: list, entry: dict, expand_states: dict, entry_idx: int, delta: dict) -> tuple:
    lines = []
    keys = []
    added_set = set(delta['added'])
    for tool_idx, tool_def in enumerate(tools_defs):
        t_name = tool_def.get('name', '')
        if not delta['is_first_request'] and (not delta['tools_changed'] or t_name not in added_set):
            continue
        t_lines, t_keys = _render_tool_dual(tool_idx, t_name, tool_def, entry, expand_states, entry_idx)
        lines.extend(t_lines)
        keys.extend(t_keys)
    return lines, keys

def _render_whole_stripped_extras(entry: dict, tools_names: list, expand_states: dict, entry_idx: int) -> tuple:
    lines = []
    keys = []
    forwarded_names = set(tools_names)
    original_tools = entry.get('_original_tools_by_name') or {}
    for name, val in entry['_stripped_spans'].get('tools', {}).items():
        if val.get('whole') and name not in forwarded_names:
            t_lines, t_keys = _render_whole_stripped_tool(entry_idx, name, original_tools.get(name), expand_states)
            lines.extend(t_lines)
            keys.extend(t_keys)
    return lines, keys

def _render_tools_body(entry_idx: int, entry: dict, expand_states: dict, tools_names: list, delta: dict) -> tuple:
    lines = []
    keys = []
    tools_defs = entry.get('tools_defs', [])
    for r_name in delta['removed']:
        lines.append(f"      {DIM}{RED}-{r_name}{SOFT_RESET}")
        keys.append(None)
    d_lines, d_keys = _render_tool_defs_list(tools_defs, entry, expand_states, entry_idx, delta)
    lines.extend(d_lines)
    keys.extend(d_keys)
    w_lines, w_keys = _render_whole_stripped_extras(entry, tools_names, expand_states, entry_idx)
    lines.extend(w_lines)
    keys.extend(w_keys)
    for d_name in entry.get('deferred_tools_names', []):
        lines.append(f"      {DIM_YELLOW_BG}{DIM}▶ {d_name}{SOFT_RESET}")
        keys.append(None)
    return lines, keys

def render_tools(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    tools_count = entry.get('tools_count', 0)
    if not tools_count:
        return lines, keys
    tools_chars = entry.get('tools_total_chars', 0)
    tools_hash = entry.get('tools_hash', '')
    tools_names = entry.get('tools_names', [])
    tools_key = ('tools', entry_idx)
    is_tools_expanded = expand_states.get(tools_key, False)
    tools_symbol = '▼' if is_tools_expanded else '▶'
    hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
    delta = _compute_tools_delta(tools_hash, tools_names, prev_entry_for_delta)
    if not delta['is_first_request'] and not delta['tools_changed']:
        return lines, keys
    lines.append(f"    {DIM}{tools_symbol} tools: {tools_count} defs ({_format_k(tools_chars)}){hash_str}{SOFT_RESET}")
    keys.append(tools_key)
    if is_tools_expanded:
        b_lines, b_keys = _render_tools_body(entry_idx, entry, expand_states, tools_names, delta)
        lines.extend(b_lines)
        keys.extend(b_keys)
    return lines, keys

def render_beta(entry_idx: int, entry: dict, expand_states: dict) -> tuple:
    lines = []
    keys = []
    flags = entry.get('anthropic_beta') or []
    if not flags:
        return lines, keys
    beta_key = ('beta', entry_idx)
    is_beta_expanded = expand_states.get(beta_key, False)
    beta_symbol = '▼' if is_beta_expanded else '▶'
    lines.append(f"    {DIM}{beta_symbol} beta: {len(flags)} flags{SOFT_RESET}")
    keys.append(beta_key)
    if is_beta_expanded:
        for flag in flags:
            lines.append(f"      {DIM}{flag}{SOFT_RESET}")
            keys.append(None)
    return lines, keys


def render_directives(entry_idx: int, entry: dict, expand_states: dict) -> tuple:
    lines = []
    keys = []
    cm = entry.get('context_management')
    edits = (cm or {}).get('edits') or []
    if edits:
        ctx_key = ('ctx', entry_idx)
        is_ctx_expanded = expand_states.get(ctx_key, False)
        ctx_symbol = '▼' if is_ctx_expanded else '▶'
        lines.append(f"    {DIM}{ctx_symbol} ctx: {len(edits)} edits{SOFT_RESET}")
        keys.append(ctx_key)
        if is_ctx_expanded:
            for edit in edits:
                lines.append(f"      {DIM}{edit.get('type', '')}{SOFT_RESET}")
                keys.append(None)
    diag = entry.get('diagnostics') or {}
    pmid = diag.get('previous_message_id')
    if pmid:
        lines.append(f"    {DIM}diag: {pmid[:14]}{SOFT_RESET}")
        keys.append(None)
    return lines, keys


def render_fields_delta(entry_idx: int, entry: dict, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    if '_stripped_spans' not in entry:
        return lines, keys
    s_fields = entry['_stripped_spans'].get('fields', {})
    i_fields = entry['_injected_spans'].get('fields', {})
    if not s_fields and not i_fields:
        return lines, keys
    all_field_keys = sorted(set(s_fields) | set(i_fields))
    fields_key = ('fields', entry_idx)
    is_fields_expanded = expand_states.get(fields_key, False)
    fields_symbol = '▼' if is_fields_expanded else '▶'
    lines.append(f"    {DIM}{fields_symbol} fields: {len(all_field_keys)} changed{SOFT_RESET}")
    keys.append(fields_key)
    if is_fields_expanded:
        for k in all_field_keys:
            old_val = s_fields.get(k)
            new_val = i_fields.get(k)
            if old_val is not None and new_val is not None:
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{k}: {old_val}{SOFT_RESET}")
                keys.append(None)
                lines.append(f"      {DIM_GREEN_BG}{DIM}{k}: {new_val}{SOFT_RESET}")
                keys.append(None)
            elif old_val is not None:
                lines.append(f"      {DIM_YELLOW_BG}{DIM}{k}: {old_val}{SOFT_RESET}")
                keys.append(None)
            else:
                lines.append(f"      {DIM_GREEN_BG}{DIM}{k}: {new_val}{SOFT_RESET}")
                keys.append(None)
    return lines, keys
