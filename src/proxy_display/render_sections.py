# INFRASTRUCTURE
from ..constants import (
    SOFT_RESET, RED, DIM, DIM_YELLOW_BG, DIM_GREEN_BG,
)
from .format import _format_delta, _format_k

# FUNCTIONS

# Render system blocks section for an expanded request entry, returning (lines, keys)
def render_system_blocks(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int, mods: list) -> tuple:
    lines = []
    keys = []
    sys_blocks = entry.get('system_blocks', [])
    sys_total = entry.get('system_total_chars', 0)
    if sys_blocks:
        sys_key = ('sys', entry_idx)
        is_sys_expanded = expand_states.get(sys_key, False)
        sys_symbol = '▼' if is_sys_expanded else '▶'
        prev_sys_total = prev_entry_for_delta.get('system_total_chars', 0) if prev_entry_for_delta else 0
        sys_delta = sys_total - prev_sys_total if prev_entry_for_delta else 0
        sys_delta_str = f"  {_format_delta('sys', sys_delta)}" if sys_delta != 0 else ''
        lines.append(f"    {DIM}{sys_symbol} sys: {len(sys_blocks)} blocks ({sys_total:,}c){SOFT_RESET}{sys_delta_str}")
        keys.append(sys_key)
        if is_sys_expanded:
            prev_sys_blocks = prev_entry_for_delta.get('system_blocks', []) if prev_entry_for_delta else []
            use_dual = '_stripped_spans' in entry
            is_first_sys = not prev_sys_blocks
            prev_block_by_idx = {b['idx']: b for b in prev_sys_blocks}
            for sb in sys_blocks:
                if not is_first_sys and prev_block_by_idx.get(sb['idx'], {}).get('preview', '') == sb.get('preview', ''):
                    continue
                bidx = sb['idx']
                bchars = sb.get('chars', 0)
                block_key = ('sys_block', entry_idx, bidx)
                is_block_expanded = expand_states.get(block_key, False)
                block_symbol = '▼' if is_block_expanded else '▶'
                if use_dual:
                    s_spans = entry['_stripped_spans']['system'].get(str(bidx))
                    i_spans = entry['_injected_spans']['system'].get(str(bidx))
                else:
                    is_old_stripped = ('replaced_system_prompt' in mods and bidx == 2) or ('stripped_sys3' in mods and bidx == 3)
                    s_spans = True if is_old_stripped else None  # marker only; content from original_text
                    i_spans = None
                if s_spans:
                    hdr_bg = DIM_YELLOW_BG
                elif i_spans:
                    hdr_bg = DIM_GREEN_BG
                else:
                    hdr_bg = ''
                if hdr_bg:
                    lines.append(f"      {hdr_bg}{DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{SOFT_RESET}")
                else:
                    lines.append(f"      {DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{SOFT_RESET}")
                keys.append(block_key)
                if is_block_expanded:
                    if use_dual and i_spans and isinstance(i_spans[0], (list, tuple)):
                        # New format: inline render — equal=DIM, injected=DIM_GREEN_BG, no gray preview
                        for tag, span_text in i_spans:
                            bg = DIM_GREEN_BG if tag == "injected" else ""
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                lines.append(f"        {bg}{DIM}{raw_line or ''}{SOFT_RESET}")
                                keys.append(None)
                        for span_text in (s_spans or []):
                            for raw_line in span_text.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                keys.append(None)
                    else:
                        preview = sb.get('preview', '')
                        if preview:
                            for raw_line in preview.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                lines.append(f"        {DIM}{raw_line or ''}{SOFT_RESET}")
                                keys.append(None)
                        else:
                            lines.append(f"        {DIM}(no preview){SOFT_RESET}")
                            keys.append(None)
                        if use_dual:
                            for span_text in (s_spans or []):
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in (i_spans or []):
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_GREEN_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                        else:
                            original_text = sb.get('original_text', '')
                            if original_text:
                                for raw_line in original_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
    return lines, keys

# Render tools section for an expanded request entry, returning (lines, keys)
def render_tools(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    tools_count = entry.get('tools_count', 0)
    tools_chars = entry.get('tools_total_chars', 0)
    tools_hash = entry.get('tools_hash', '')
    tools_names = entry.get('tools_names', [])
    if tools_count:
        tools_key = ('tools', entry_idx)
        is_tools_expanded = expand_states.get(tools_key, False)
        tools_symbol = '▼' if is_tools_expanded else '▶'
        hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
        prev_tools_hash = prev_entry_for_delta.get('tools_hash', '') if prev_entry_for_delta else ''
        prev_tools_names = prev_entry_for_delta.get('tools_names', []) if prev_entry_for_delta else []
        tools_changed = bool(prev_tools_hash) and prev_tools_hash != tools_hash
        is_first_request = not prev_tools_hash
        if not is_first_request and not tools_changed:
            return lines, keys
        added = [n for n in tools_names if n not in set(prev_tools_names)] if tools_changed else []
        removed = [n for n in prev_tools_names if n not in set(tools_names)] if tools_changed else []
        delta_parts = []
        if added:
            delta_parts.append(f"{RED}+{len(added)}{SOFT_RESET}")
        if removed:
            delta_parts.append(f"{RED}-{len(removed)}{SOFT_RESET}")
        tools_delta_str = f"  {'  '.join(delta_parts)}" if delta_parts else ''
        lines.append(f"    {DIM}{tools_symbol} tools: {tools_count} defs ({_format_k(tools_chars)}){hash_str}{SOFT_RESET}{tools_delta_str}")
        keys.append(tools_key)
        if is_tools_expanded:
            tools_defs = entry.get('tools_defs', [])
            use_dual = '_stripped_spans' in entry
            added_set = set(added)
            for r_name in removed:
                lines.append(f"      {DIM}{RED}-{r_name}{SOFT_RESET}")
                keys.append(None)
            for tool_idx, tool_def in enumerate(tools_defs):
                t_name = tool_def.get('name', '')
                if not is_first_request and (not tools_changed or t_name not in added_set):
                    continue
                tool_key = ('tool', entry_idx, tool_idx)
                is_tool_exp = expand_states.get(tool_key, False)
                t_symbol = '▼' if is_tool_exp else '▶'
                if use_dual:
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
                        if i_desc and isinstance(i_desc[0], (list, tuple)):
                            # New format: inline render for desc_changes — equal=DIM, injected=DIM_GREEN_BG
                            for tag, span_text in i_desc:
                                span_bg = DIM_GREEN_BG if tag == "injected" else ""
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    if not raw_line:
                                        lines.append(f"        {span_bg}{DIM}{SOFT_RESET}")
                                        keys.append(None)
                                        continue
                                    lines.append(f"        {span_bg}{DIM}{raw_line}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in (s_desc or []):
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                        else:
                            # Old format or whole_injected: forwarded description + stacked yellow/green
                            description = tool_def.get('description', '')
                            if description:
                                for raw_line in description.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    if not raw_line:
                                        lines.append(f"        {bg}{DIM}{SOFT_RESET}")
                                        keys.append(None)
                                        continue
                                    lines.append(f"        {bg}{DIM}{raw_line}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in (s_desc or []):
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                            for span_text in (i_desc or []):
                                for raw_line in span_text.split('\n'):
                                    raw_line = raw_line.expandtabs(8)
                                    lines.append(f"        {DIM_GREEN_BG}{DIM}{raw_line or ''}{SOFT_RESET}")
                                    keys.append(None)
                        input_schema = tool_def.get('input_schema', {})
                        props = input_schema.get('properties', {}) if isinstance(input_schema, dict) else {}
                        required_props = input_schema.get('required', []) if isinstance(input_schema, dict) else []
                        for param_name, param_info in props.items():
                            if isinstance(param_info, dict):
                                param_type = param_info.get('type', '?')
                                param_desc = param_info.get('description', '')
                                req_marker = '*' if param_name in required_props else ''
                                param_line = f"{param_name}{req_marker}: {param_type}"
                                if param_desc:
                                    param_line += f" — {param_desc}"
                                lines.append(f"        {bg}{DIM}{param_line}{SOFT_RESET}")
                                keys.append(None)
                else:
                    stripped_original = tool_def.get('stripped_original')
                    lines.append(f"      {DIM}{t_symbol} {t_name}{SOFT_RESET}")
                    keys.append(tool_key)
                    if is_tool_exp:
                        bg = ''
                        description = tool_def.get('description', '')
                        if description:
                            for raw_line in description.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {bg}{DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                lines.append(f"        {bg}{DIM}{raw_line}{SOFT_RESET}")
                                keys.append(None)
                        orig_desc = (stripped_original or {}).get('description', '')
                        if orig_desc:
                            for raw_line in orig_desc.split('\n'):
                                raw_line = raw_line.expandtabs(8)
                                if not raw_line:
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{SOFT_RESET}")
                                    keys.append(None)
                                    continue
                                lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line}{SOFT_RESET}")
                                keys.append(None)
                        input_schema = tool_def.get('input_schema', {})
                        props = input_schema.get('properties', {}) if isinstance(input_schema, dict) else {}
                        required_props = input_schema.get('required', []) if isinstance(input_schema, dict) else []
                        for param_name, param_info in props.items():
                            if isinstance(param_info, dict):
                                param_type = param_info.get('type', '?')
                                param_desc = param_info.get('description', '')
                                orig_param_desc = ''
                                if not param_desc and stripped_original:
                                    orig_param_desc = stripped_original.get('params', {}).get(param_name, '')
                                req_marker = '*' if param_name in required_props else ''
                                param_line = f"{param_name}{req_marker}: {param_type}"
                                if orig_param_desc:
                                    param_line += f" — {orig_param_desc}"
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{param_line}{SOFT_RESET}")
                                else:
                                    if param_desc:
                                        param_line += f" — {param_desc}"
                                    lines.append(f"        {bg}{DIM}{param_line}{SOFT_RESET}")
                                keys.append(None)
            deferred = entry.get('deferred_tools_names', [])
            if use_dual:
                forwarded_names = set(tools_names)
                for name, val in entry['_stripped_spans'].get('tools', {}).items():
                    if val.get('whole') and name not in forwarded_names:
                        lines.append(f"      {DIM_YELLOW_BG}{DIM}▶ {name}{SOFT_RESET}")
                        keys.append(None)
            else:
                stripped_unused = entry.get('stripped_unused_tools_names', [])
                if stripped_unused:
                    for s_name in stripped_unused:
                        lines.append(f"      {DIM_YELLOW_BG}{DIM}▶ {s_name}{SOFT_RESET}")
                        keys.append(None)
            if deferred:
                for d_name in deferred:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}▶ {d_name}{SOFT_RESET}")
                    keys.append(None)
    return lines, keys

# Render fields delta section for an expanded request entry, returning (lines, keys)
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
