# INFRASTRUCTURE
import logging
from datetime import datetime
from typing import Dict, List

# ANSI Colors for logging
RESET_LOG = '\033[0m'
YELLOW_LOG = '\033[93m'
PURPLE_LOG = '\033[38;5;135m'
WHITE_LOG = '\033[97m'

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_ui = logging.getLogger('subagent_ui.rendering')
ui_handler = logging.FileHandler('src/logs/08_ui_rendering.log')
ui_handler.setFormatter(log_format)
logger_ui.addHandler(ui_handler)
logger_ui.setLevel(logging.INFO)

# Tagged logging helper
def log_tagged(tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET_LOG}"
    logger_ui.info(f"{colored_tag} {message}")

# From formatter.py: Color constants for terminal output
from .formatter import GREEN, BLUE, CYAN, YELLOW, RESET

subagent_states: Dict[str, bool] = {}
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
        log_tagged("RENDER_LIST", PURPLE_LOG, f"render_subagent_list: {agent_count} agents, {expanded_count} expanded")
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
    global _last_entry_count, _last_expanded_entries

    if not subagent_metadata:
        return f"{YELLOW}No subagents active yet{RESET}"

    entries = []
    expanded_entries = 0
    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        tool_calls = tool_calls_by_agent.get(agent_id, [])

        if is_expanded:
            expanded_entries += 1
            entry = build_expanded_entry(idx, metadata, tool_calls)
        else:
            entry = build_collapsed_entry(idx, metadata)

        entries.append(entry)

    if len(entries) != _last_entry_count or expanded_entries != _last_expanded_entries:
        log_tagged("ENTRIES_BUILT", PURPLE_LOG, f"Built {len(entries)} entries ({expanded_entries} expanded)")
        _last_entry_count = len(entries)
        _last_expanded_entries = expanded_entries

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
        log_tagged("NO_CALLS", YELLOW_LOG, f"Agent {metadata['agent_id']} has no tool calls yet")
        return f"{collapsed_header}\n  {YELLOW}(no tool calls yet){RESET}"

    log_tagged("EXPAND_BUILD", PURPLE_LOG, f"Building expanded entry for {metadata['agent_id']}: {len(tool_calls)} tool calls")
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

# Formats single tool call as summary line with output
def format_tool_call_summary(tool_call: dict) -> str:
    tool_name = tool_call.get('tool_name', 'Unknown')
    call_number = tool_call.get('call_number', '?')
    timestamp = format_timestamp(tool_call.get('timestamp', ''))

    input_preview = get_input_preview(tool_call.get('input', {}))

    has_output = tool_call.get('output') is not None
    direction = '↔' if has_output else '→'

    summary_line = f"{GREEN}[{timestamp}] {direction} #{call_number} {tool_name}{RESET}: {input_preview}"

    # Add output if present (FULL output, no truncating)
    if has_output:
        output = tool_call.get('output', '') or "(empty)"
        output_lines = f"\n    {CYAN}OUTPUT:{RESET} {output}"
        return summary_line + output_lines

    return summary_line

# Truncate output to first N lines
def truncate_output(output: str, max_lines: int = 5) -> str:
    if not output:
        return "(empty)"

    lines = output.split('\n')
    if len(lines) <= max_lines:
        return output

    truncated = '\n    '.join(lines[:max_lines])
    return f"{truncated}\n    ... ({len(lines) - max_lines} more lines)"

# Joins header and entries with proper spacing
def combine_sections(header: str, entries: str) -> str:
    return f"{header}\n{entries}"

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
