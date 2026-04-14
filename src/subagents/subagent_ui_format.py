# INFRASTRUCTURE
from typing import List

from ..utils import format_timestamp
from ..constants import RESET, BLUE, GREEN, YELLOW

# FUNCTIONS

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
