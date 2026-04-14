# INFRASTRUCTURE
from typing import Dict, List, Optional

from ..constants import RESET, CYAN, YELLOW, HOVER_BG, EXPANDED_MAX_LINES
from .subagent_ui_format import build_collapsed_entry, format_tool_call_summary

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

# Joins header and entries with proper spacing
def combine_sections(header: str, entries: str) -> str:
    return f"{header}\n{entries}"

# Toggles expanded/collapsed state for agent
def toggle_subagent_state(agent_id: str) -> bool:
    global subagent_states
    subagent_states[agent_id] = not subagent_states.get(agent_id, False)
    return True
