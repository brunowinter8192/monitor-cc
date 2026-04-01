# INFRASTRUCTURE
from typing import Dict, List

# From constants.py: Colors
from .constants import RESET, PASTEL_BLUE

# From subagent_ui.py: Subagent state and display names
from .subagent_ui import get_agent_display_name, count_calls_for_agent, subagent_states

# FUNCTIONS

# Tracks subagent metadata from tool calls
def track_subagent_metadata(tool_call: dict, filepath, subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]], agent_to_task: Dict[str, str], agent_to_type: Dict[str, str]) -> None:
    agent_id = tool_call.get('agent_id')
    if not agent_id:
        return

    if agent_id not in subagent_metadata:
        subagent_type = agent_to_type.get(agent_id, '')
        timestamp = tool_call.get('timestamp', '')

        subagent_metadata[agent_id] = {
            'name': get_agent_display_name(subagent_type, agent_id),
            'agent_id': agent_id,
            'timestamp': timestamp,
            'file': filepath.name,
            'parent_task_id': agent_to_task.get(agent_id, ''),
            'call_count': 0
        }
        tool_calls_by_agent[agent_id] = []
        subagent_states[agent_id] = False

    tool_calls_by_agent[agent_id].append(tool_call)
    subagent_metadata[agent_id]['call_count'] = count_calls_for_agent(tool_calls_by_agent[agent_id])

# Format active rules block for UI display
def format_rules_block(active_rules: Dict[str, set]) -> str:
    if not active_rules:
        return ''
    project_rules = sorted(active_rules.get('project', set()))
    global_rules = sorted(active_rules.get('global', set()))
    if not project_rules and not global_rules:
        return ''

    header = f"{PASTEL_BLUE}ACTIVE RULES ({len(project_rules)}P / {len(global_rules)}G){RESET}"
    lines = [header]
    for r in project_rules:
        lines.append(f"  {PASTEL_BLUE}[P] {r}{RESET}")
    for r in global_rules:
        lines.append(f"  {PASTEL_BLUE}[G] {r}{RESET}")
    return '\n'.join(lines)

