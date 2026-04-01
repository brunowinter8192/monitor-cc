# INFRASTRUCTURE
from typing import Dict, List, Optional

# From utils.py: Timestamp formatting
from .utils import format_timestamp
# From constants.py: Colors and config
from .constants import RESET, GREEN, BLUE, CYAN, YELLOW, PURPLE, WHITE, HOVER_BG, EXPANDED_MAX_LINES


subagent_states: Dict[str, bool] = {}
line_to_agent_map: Dict[int, str] = {}
_last_agent_count: int = 0
_last_expanded_count: int = 0
_last_entry_count: int = 0
_last_expanded_entries: int = 0

# ORCHESTRATOR
def render_subagent_list(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]], hover_row: Optional[int] = None, scroll_offsets: Dict[str, int] = None, start_line: int = 3) -> str:
    global _last_agent_count, _last_expanded_count

    agent_count = len(subagent_metadata)
    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))

    if agent_count != _last_agent_count or expanded_count != _last_expanded_count:
        _last_agent_count = agent_count
        _last_expanded_count = expanded_count

    header = build_list_header(agent_count)
    entries = build_all_entries(subagent_metadata, tool_calls_by_agent, hover_row, scroll_offsets, start_line=start_line)
    combined = combine_sections(header, entries)

    return combined

# FUNCTIONS

# Creates header showing total subagent count
def build_list_header(count: int) -> str:
    return f"{CYAN}Active Subagents ({count}){RESET}\n"

# Builds all subagent entries based on expanded state with viewport slicing
def build_all_entries(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]], hover_row: Optional[int] = None, scroll_offsets: Optional[Dict[str, int]] = None, max_lines: int = EXPANDED_MAX_LINES, start_line: int = 3) -> str:
    global _last_entry_count, _last_expanded_entries, line_to_agent_map

    if not subagent_metadata:
        return f"{YELLOW}No subagents active yet{RESET}"

    entries = []
    expanded_entries = 0
    line_to_agent_map.clear()
    current_line = start_line

    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        tool_calls = tool_calls_by_agent.get(agent_id, [])
        highlight = (hover_row is not None and current_line == hover_row)

        if is_expanded:
            expanded_entries += 1
            entry_line_list: List[str] = []
            line_idx = 0

            header = build_collapsed_entry(idx, metadata, is_expanded=True)
            if highlight:
                first_nl = header.find('\n')
                if first_nl >= 0:
                    header = f"{HOVER_BG}{header[:first_nl]}{RESET}{header[first_nl:]}"
                else:
                    header = f"{HOVER_BG}{header}{RESET}"
            entry_line_list.append(header)
            line_to_agent_map[current_line + line_idx] = agent_id
            line_idx += 1

            if not tool_calls:
                entry_line_list.append(f"  {YELLOW}(no tool calls yet){RESET}")
                line_to_agent_map[current_line + line_idx] = agent_id
                line_idx += 1
            else:
                offset = (scroll_offsets or {}).get(agent_id, 0)
                total = len(tool_calls)

                if total > max_lines:
                    visible = tool_calls[offset:offset + max_lines]
                    if offset > 0:
                        entry_line_list.append(f"  {YELLOW}[↑ {offset} more]{RESET}")
                        line_to_agent_map[current_line + line_idx] = agent_id
                        line_idx += 1
                    for call in visible:
                        summary = format_tool_call_summary(call)
                        entry_line_list.append(f"  {summary}")
                        line_to_agent_map[current_line + line_idx] = agent_id
                        line_idx += 1
                    remaining = total - offset - len(visible)
                    if remaining > 0:
                        entry_line_list.append(f"  {YELLOW}[↓ {remaining} more]{RESET}")
                        line_to_agent_map[current_line + line_idx] = agent_id
                        line_idx += 1
                else:
                    for call in tool_calls:
                        summary = format_tool_call_summary(call)
                        entry_line_list.append(f"  {summary}")
                        line_to_agent_map[current_line + line_idx] = agent_id
                        line_idx += 1

            entry = '\n'.join(entry_line_list)
            entry_lines = len(entry_line_list)
        else:
            entry = build_collapsed_entry(idx, metadata, is_expanded=False)
            if highlight:
                entry = f"{HOVER_BG}{entry}{RESET}"
            entry_lines = 1
            line_to_agent_map[current_line] = agent_id

        entries.append(entry)
        current_line += entry_lines + 1

    if len(entries) != _last_entry_count or expanded_entries != _last_expanded_entries:
        _last_entry_count = len(entries)
        _last_expanded_entries = expanded_entries

    return '\n\n'.join(entries)

# Shows collapsed subagent entry with summary
def build_collapsed_entry(index: int, metadata: dict, is_expanded: bool) -> str:
    name = metadata['name']
    agent_id = metadata['agent_id']
    timestamp = format_timestamp(metadata['timestamp'])
    toggle_symbol = "[-]" if is_expanded else "[+]"

    return f"{toggle_symbol} {BLUE}[{index}] {name} ({agent_id}){RESET} - {timestamp}"

# Shows expanded entry with header and tool call list
def build_expanded_entry(index: int, metadata: dict, tool_calls: List[dict]) -> str:
    header = build_collapsed_entry(index, metadata, is_expanded=True)

    if not tool_calls:
        return f"{header}\n  {YELLOW}(no tool calls yet){RESET}"

    call_summaries = []
    for call in tool_calls:
        summary = format_tool_call_summary(call)
        call_summaries.append(f"  {summary}")

    return header + '\n' + '\n'.join(call_summaries)

# Generates unique display name for subagent
def format_subagent_name(agent_id: str, subagent_type: str, timestamp: str, existing_names: List[str]) -> str:
    base_name = subagent_type or agent_id

    if base_name not in existing_names:
        return base_name

    time_suffix = format_timestamp(timestamp).replace(':', '')
    return f"{base_name}-{time_suffix}"

# Formats single tool call as summary line (MCP: short name + params, non-MCP: name + char count)
def format_tool_call_summary(tool_call: dict) -> str:
    tool_name = tool_call.get('tool_name', 'Unknown')
    call_number = tool_call.get('call_number', '?')
    timestamp = format_timestamp(tool_call.get('timestamp', ''))
    input_data = tool_call.get('input', {})
    if tool_name.startswith('mcp__'):
        parts = tool_name.split('__')
        short_name = parts[-1] if len(parts) >= 3 else tool_name
        preview = get_input_preview(input_data)
        return f"{GREEN}[{timestamp}] -> #{call_number} {short_name}{RESET}: {preview}"
    else:
        char_count = format_char_count(input_data)
        return f"{GREEN}[{timestamp}] -> #{call_number} {tool_name} ({char_count}){RESET}"

# Formats input dict size as human-readable char count
def format_char_count(input_data: dict) -> str:
    total = len(str(input_data))
    if total >= 1000:
        return f"{total / 1000:.1f}k"
    return str(total)

# Joins header and entries with proper spacing
def combine_sections(header: str, entries: str) -> str:
    return f"{header}\n{entries}"

# Extracts readable name from subagent type or agent ID
def get_agent_display_name(subagent_type: str, agent_id: str) -> str:
    if subagent_type:
        return subagent_type.replace('-', ' ').title()
    return agent_id

# Returns number of tool calls for given agent
def count_calls_for_agent(tool_calls: List[dict]) -> int:
    return len(tool_calls)

# Gets preview of tool input for summary line
def get_input_preview(input_data: dict) -> str:
    if not input_data:
        return '(no input)'

    if not isinstance(input_data, dict):
        return str(input_data)[:40] + '...' if len(str(input_data)) > 40 else str(input_data)

    try:
        parts = []
        for key, value in input_data.items():
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + '...'
            parts.append(f"{key}={value_str}")

        result = ', '.join(parts)
        if len(result) > 120:
            return result[:120] + '...'
        return result
    except Exception:
        return '(parse error)'

# Toggles expanded/collapsed state for agent
def toggle_subagent_state(agent_id: str) -> bool:
    global subagent_states
    if agent_id in subagent_states:
        subagent_states[agent_id] = not subagent_states[agent_id]
        return True
    return False
