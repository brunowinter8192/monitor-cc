# INFRASTRUCTURE
import logging
from typing import Dict, List

# From utils.py: ANSI colors and logging utility
from .utils import RESET, YELLOW, PURPLE, WHITE, log_tagged, format_timestamp
YELLOW_LOG = YELLOW
PURPLE_LOG = PURPLE
WHITE_LOG = WHITE

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_ui = logging.getLogger('subagent_ui.rendering')
ui_handler = logging.FileHandler('src/logs/08_ui_rendering.log')
ui_handler.setFormatter(log_format)
logger_ui.addHandler(ui_handler)
logger_ui.setLevel(logging.INFO)

# From formatter.py: Color constants for terminal output
from .formatter import GREEN, BLUE, CYAN, YELLOW, RESET

subagent_states: Dict[str, bool] = {}
line_to_agent_map: Dict[int, str] = {}
_last_agent_count: int = 0
_last_expanded_count: int = 0
_last_entry_count: int = 0
_last_expanded_entries: int = 0

# ORCHESTRATOR
def render_subagent_list(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]]) -> str:
    global _last_agent_count, _last_expanded_count

    agent_count = len(subagent_metadata)
    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))

    if agent_count != _last_agent_count or expanded_count != _last_expanded_count:
        log_tagged(logger_ui, "RENDER_LIST", PURPLE_LOG, f"render_subagent_list: {agent_count} agents, {expanded_count} expanded")
        _last_agent_count = agent_count
        _last_expanded_count = expanded_count

    header = build_list_header(agent_count)
    entries = build_all_entries(subagent_metadata, tool_calls_by_agent)
    combined = combine_sections(header, entries)

    return combined

# FUNCTIONS

# Creates header showing total subagent count
def build_list_header(count: int) -> str:
    return f"{CYAN}Active Subagents ({count}){RESET}\n"

# Builds all subagent entries based on expanded state
def build_all_entries(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]]) -> str:
    global _last_entry_count, _last_expanded_entries, line_to_agent_map

    if not subagent_metadata:
        return f"{YELLOW}No subagents active yet{RESET}"

    entries = []
    expanded_entries = 0
    line_to_agent_map.clear()
    current_line = 3

    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        tool_calls = tool_calls_by_agent.get(agent_id, [])

        line_to_agent_map[current_line] = agent_id

        if is_expanded:
            expanded_entries += 1
            entry = build_expanded_entry(idx, metadata, tool_calls)
            entry_lines = entry.count('\n') + 1
        else:
            entry = build_collapsed_entry(idx, metadata, is_expanded=False)
            entry_lines = 1

        entries.append(entry)
        current_line += entry_lines + 1

    if len(entries) != _last_entry_count or expanded_entries != _last_expanded_entries:
        log_tagged(logger_ui, "ENTRIES_BUILT", PURPLE_LOG, f"Built {len(entries)} entries ({expanded_entries} expanded)")
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
        log_tagged(logger_ui, "NO_CALLS", YELLOW_LOG, f"Agent {metadata['agent_id']} has no tool calls yet")
        return f"{header}\n  {YELLOW}(no tool calls yet){RESET}"

    log_tagged(logger_ui, "EXPAND_BUILD", PURPLE_LOG, f"Building expanded entry for {metadata['agent_id']}: {len(tool_calls)} tool calls")
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

# Formats single tool call as summary line with output
def format_tool_call_summary(tool_call: dict) -> str:
    tool_name = tool_call.get('tool_name', 'Unknown')
    call_number = tool_call.get('call_number', '?')
    timestamp = format_timestamp(tool_call.get('timestamp', ''))

    input_preview = get_input_preview(tool_call.get('input', {}))

    has_output = tool_call.get('output') is not None
    direction = '↔' if has_output else '→'

    summary_line = f"{GREEN}[{timestamp}] {direction} #{call_number} {tool_name}{RESET}: {input_preview}"

    if has_output:
        output = tool_call.get('output', '') or "(empty)"
        output_lines = f"\n    {CYAN}OUTPUT:{RESET} {output}"
        return summary_line + output_lines

    return summary_line

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
        new_state = "expanded" if subagent_states[agent_id] else "collapsed"
        log_tagged(logger_ui, "STATE_CHANGE", PURPLE_LOG, f"Toggled {agent_id}: {new_state}")
        return True
    return False
