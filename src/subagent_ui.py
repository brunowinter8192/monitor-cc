# INFRASTRUCTURE
import logging
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    filename='src/logs/subagent_ui.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# From formatter.py: Color constants for terminal output
from .formatter import GREEN, BLUE, CYAN, YELLOW, RESET

subagent_states: Dict[str, bool] = {}

# ORCHESTRATOR
def render_subagent_list(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]]) -> str:
    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))
    logging.debug(f"render_subagent_list: rendering {len(subagent_metadata)} agents ({expanded_count} expanded)")

    header = build_list_header(len(subagent_metadata))
    entries = build_all_entries(subagent_metadata, tool_calls_by_agent)
    footer = build_keybinding_footer()
    return combine_sections(header, entries, footer)

# FUNCTIONS

# Creates header showing total subagent count
def build_list_header(count: int) -> str:
    return f"{CYAN}Active Subagents ({count}){RESET}\n"

# Builds all subagent entries based on expanded state
def build_all_entries(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]]) -> str:
    if not subagent_metadata:
        return f"{YELLOW}No subagents active yet{RESET}"

    entries = []
    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        tool_calls = tool_calls_by_agent.get(agent_id, [])

        if is_expanded:
            entry = build_expanded_entry(idx, metadata, tool_calls)
        else:
            entry = build_collapsed_entry(idx, metadata)

        entries.append(entry)

    return '\n\n'.join(entries)

# Shows collapsed subagent entry with summary
def build_collapsed_entry(index: int, metadata: dict) -> str:
    name = metadata['name']
    agent_id = metadata['agent_id']
    timestamp = format_timestamp(metadata['timestamp'])

    return f"{BLUE}[{index}] [+] {name} ({agent_id}){RESET} - {timestamp}"

# Shows expanded entry with header and tool call list
def build_expanded_entry(index: int, metadata: dict, tool_calls: List[dict]) -> str:
    collapsed_header = build_collapsed_entry(index, metadata)
    collapsed_header = collapsed_header.replace('[+]', '[-]')

    if not tool_calls:
        return f"{collapsed_header}\n  {YELLOW}(no tool calls yet){RESET}"

    call_summaries = []
    for call in tool_calls:
        summary = format_tool_call_summary(call)
        call_summaries.append(f"  {summary}")

    return collapsed_header + '\n' + '\n'.join(call_summaries)

# Generates unique display name for subagent
def format_subagent_name(agent_id: str, subagent_type: str, timestamp: str, existing_names: List[str]) -> str:
    base_name = subagent_type or agent_id

    if base_name not in existing_names:
        return base_name

    time_suffix = format_timestamp(timestamp).replace(':', '')
    return f"{base_name}-{time_suffix}"

# Formats single tool call as summary line
def format_tool_call_summary(tool_call: dict) -> str:
    tool_name = tool_call.get('tool_name', 'Unknown')
    call_number = tool_call.get('call_number', '?')
    timestamp = format_timestamp(tool_call.get('timestamp', ''))

    input_preview = get_input_preview(tool_call.get('input', {}))

    has_output = tool_call.get('output') is not None
    direction = '↔' if has_output else '→'

    return f"{GREEN}[{timestamp}] {direction} #{call_number} {tool_name}{RESET}: {input_preview}"

# Shows keybinding help footer
def build_keybinding_footer() -> str:
    return f"\n{CYAN}Click on agent to expand/collapse{RESET}"

# Joins header entries and footer with proper spacing
def combine_sections(header: str, entries: str, footer: str) -> str:
    return f"{header}\n{entries}{footer}"

# Toggles expanded state for specific subagent
def toggle_subagent(agent_id: str) -> None:
    current_state = subagent_states.get(agent_id, False)
    subagent_states[agent_id] = not current_state
    new_state = 'expanded' if not current_state else 'collapsed'
    expanded_total = sum(1 for aid in subagent_states if subagent_states.get(aid, False))
    logging.info(f"Toggled {agent_id} to {new_state} (total expanded: {expanded_total}/{len(subagent_states)})")

# Collapses all subagents
def collapse_all() -> None:
    for agent_id in subagent_states:
        subagent_states[agent_id] = False
    logging.info("Collapsed all subagents")

# Extracts readable name from subagent type or agent ID
def get_agent_display_name(subagent_type: str, agent_id: str) -> str:
    if subagent_type:
        return subagent_type.replace('-', ' ').title()
    return agent_id

# Extracts creation timestamp from agent metadata
def extract_timestamp_from_agent(tool_calls: List[dict]) -> str:
    if not tool_calls:
        return datetime.now().isoformat()
    return tool_calls[0].get('timestamp', datetime.now().isoformat())

# Returns number of tool calls for given agent
def count_calls_for_agent(tool_calls: List[dict]) -> int:
    return len(tool_calls)

# Converts ISO timestamp to HH:MM:SS format
def format_timestamp(iso_timestamp: str) -> str:
    if not iso_timestamp:
        return '00:00:00'
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except ValueError:
        return '00:00:00'

# Gets preview of tool input for summary line
def get_input_preview(input_data: dict) -> str:
    if not input_data:
        return '(no input)'

    if 'command' in input_data:
        cmd = input_data['command']
        return cmd[:50] + '...' if len(cmd) > 50 else cmd

    if 'file_path' in input_data:
        return input_data['file_path']

    if 'pattern' in input_data:
        return f"pattern: {input_data['pattern']}"

    first_key = next(iter(input_data))
    first_value = str(input_data[first_key])
    return first_value[:40] + '...' if len(first_value) > 40 else first_value
