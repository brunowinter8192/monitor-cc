# INFRASTRUCTURE
from ..constants import (
    RESET, RED, DIM, DIM_YELLOW_BG,
    TOOL_BLOCKLIST,
)
from .format import _format_delta, _format_k

# FUNCTIONS

# Render system blocks section for an expanded request entry, returning (lines, keys)
def render_system_blocks(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int, mods: list) -> tuple:
    lines = []
    keys = []
    wrap_width_meta = max(20, pane_width - 10)
    sys_blocks = entry.get('system_blocks', [])
    sys_total = entry.get('system_total_chars', 0)
    if sys_blocks:
        sys_key = ('sys', entry_idx)
        is_sys_expanded = expand_states.get(sys_key, False)
        sys_symbol = '\u25bc' if is_sys_expanded else '\u25b6'
        prev_sys_total = prev_entry_for_delta.get('system_total_chars', 0) if prev_entry_for_delta else 0
        sys_delta = sys_total - prev_sys_total if prev_entry_for_delta else 0
        sys_delta_str = f"  {_format_delta('sys', sys_delta)}" if sys_delta != 0 else ''
        lines.append(f"    {DIM}{sys_symbol} sys: {len(sys_blocks)} blocks ({sys_total:,}c){RESET}{sys_delta_str}")
        keys.append(sys_key)
        if is_sys_expanded:
            prev_sys_blocks = prev_entry_for_delta.get('system_blocks', []) if prev_entry_for_delta else []
            sys_unchanged = (
                prev_sys_blocks
                and len(prev_sys_blocks) == len(sys_blocks)
                and all(
                    prev_sys_blocks[i].get('chars', 0) == sys_blocks[i].get('chars', 0)
                    for i in range(len(sys_blocks))
                )
            )
            if sys_unchanged:
                lines.append(f"      {DIM}(unchanged){RESET}")
                keys.append(None)
            else:
                for sb in sys_blocks:
                    bidx = sb['idx']
                    bchars = sb.get('chars', 0)
                    is_sys_stripped = 'replaced_system_prompt' in mods and bidx == 2
                    stripped_str = f"  [STRIPPED]" if is_sys_stripped else ''
                    block_key = ('sys_block', entry_idx, bidx)
                    is_block_expanded = expand_states.get(block_key, False)
                    block_symbol = '\u25bc' if is_block_expanded else '\u25b6'
                    if is_sys_stripped:
                        lines.append(f"      {DIM_YELLOW_BG}{DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{stripped_str}{RESET}")
                    else:
                        lines.append(f"      {DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{RESET}")
                    keys.append(block_key)
                    if is_block_expanded:
                        preview = sb.get('preview', '')
                        if preview:
                            for raw_line in preview.split('\n'):
                                if not raw_line:
                                    lines.append(f"        {DIM}{RESET}")
                                    keys.append(None)
                                    continue
                                for chunk_start in range(0, len(raw_line), wrap_width_meta):
                                    lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_width_meta]}{RESET}")
                                    keys.append(None)
                        else:
                            lines.append(f"        {DIM}(no preview){RESET}")
                            keys.append(None)
                        original_text = sb.get('original_text', '')
                        if original_text:
                            for raw_line in original_text.split('\n'):
                                if not raw_line:
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{RESET}")
                                    keys.append(None)
                                    continue
                                for chunk_start in range(0, len(raw_line), wrap_width_meta):
                                    lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line[chunk_start:chunk_start + wrap_width_meta]}{RESET}")
                                    keys.append(None)
    return lines, keys

# Render tools section for an expanded request entry, returning (lines, keys)
def render_tools(entry_idx: int, entry: dict, prev_entry_for_delta, expand_states: dict, pane_width: int) -> tuple:
    lines = []
    keys = []
    wrap_w = max(20, pane_width - 12)
    tools_count = entry.get('tools_count', 0)
    tools_chars = entry.get('tools_total_chars', 0)
    tools_hash = entry.get('tools_hash', '')
    tools_names = entry.get('tools_names', [])
    if tools_count:
        tools_key = ('tools', entry_idx)
        is_tools_expanded = expand_states.get(tools_key, False)
        tools_symbol = '\u25bc' if is_tools_expanded else '\u25b6'
        hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
        prev_tools_hash = prev_entry_for_delta.get('tools_hash', '') if prev_entry_for_delta else ''
        prev_tools_names = prev_entry_for_delta.get('tools_names', []) if prev_entry_for_delta else []
        tools_changed = bool(prev_tools_hash) and prev_tools_hash != tools_hash
        added = [n for n in tools_names if n not in set(prev_tools_names)] if tools_changed else []
        removed = [n for n in prev_tools_names if n not in set(tools_names)] if tools_changed else []
        delta_parts = []
        if added:
            delta_parts.append(f"{RED}+{len(added)}{RESET}")
        if removed:
            delta_parts.append(f"{RED}-{len(removed)}{RESET}")
        tools_delta_str = f"  {'  '.join(delta_parts)}" if delta_parts else ''
        lines.append(f"    {DIM}{tools_symbol} tools: {tools_count} defs ({_format_k(tools_chars)}){hash_str}{RESET}{tools_delta_str}")
        keys.append(tools_key)
        if is_tools_expanded:
            tools_defs = entry.get('tools_defs', [])
            is_first_request = not prev_tools_hash
            added_set = set(added)
            if not is_first_request and not tools_changed:
                lines.append(f"      {DIM}(unchanged){RESET}")
                keys.append(None)
            else:
                for r_name in removed:
                    lines.append(f"      {DIM}{RED}-{r_name}{RESET}")
                    keys.append(None)
            for tool_idx, tool_def in enumerate(tools_defs):
                t_name = tool_def.get('name', '')
                if not is_first_request and (not tools_changed or t_name not in added_set):
                    continue
                is_stripped_tool = t_name in TOOL_BLOCKLIST
                tool_key = ('tool', entry_idx, tool_idx)
                is_tool_exp = expand_states.get(tool_key, False)
                t_symbol = '\u25bc' if is_tool_exp else '\u25b6'
                if is_stripped_tool:
                    lines.append(f"      {DIM_YELLOW_BG}{DIM}{t_symbol} {t_name}{RESET}")
                else:
                    lines.append(f"      {DIM}{t_symbol} {t_name}{RESET}")
                keys.append(tool_key)
                if is_tool_exp:
                    bg = DIM_YELLOW_BG if is_stripped_tool else ''
                    description = tool_def.get('description', '')
                    if description:
                        for raw_line in description.split('\n'):
                            if not raw_line:
                                lines.append(f"        {bg}{DIM}{RESET}")
                                keys.append(None)
                                continue
                            for chunk_start in range(0, len(raw_line), wrap_w):
                                lines.append(f"        {bg}{DIM}{raw_line[chunk_start:chunk_start + wrap_w]}{RESET}")
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
                                param_line += f" \u2014 {param_desc}"
                            for chunk_start in range(0, len(param_line), wrap_w):
                                lines.append(f"        {bg}{DIM}{param_line[chunk_start:chunk_start + wrap_w]}{RESET}")
                                keys.append(None)
    return lines, keys
