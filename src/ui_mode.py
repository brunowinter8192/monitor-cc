# INFRASTRUCTURE
from typing import Dict, List, Optional

# From constants.py: Colors
from .constants import RESET, PASTEL_BLUE, DIM, HOVER_BG

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

# Format active rules block for UI display with expandable invoker info
def format_rules_block(active_rules: Dict[str, set], invokers: Optional[Dict[str, List[dict]]] = None, expand_states: Optional[Dict[str, bool]] = None, line_map: Optional[Dict[int, str]] = None, hover_row: Optional[int] = None) -> str:
    if not active_rules:
        return ''
    project_rules = sorted(active_rules.get('project', set()))
    global_rules = sorted(active_rules.get('global', set()))
    if not project_rules and not global_rules:
        return ''

    if line_map is not None:
        line_map.clear()

    header = f"{PASTEL_BLUE}ACTIVE RULES ({len(project_rules)}P / {len(global_rules)}G){RESET}"
    lines = [header]
    current_line = 2
    idx = 0

    for prefix, rule_list in [('[P]', project_rules), ('[G]', global_rules)]:
        for r in rule_list:
            idx += 1
            rule_key = f'{prefix} {r}'
            is_expanded = (expand_states or {}).get(rule_key, False)
            highlight = (hover_row is not None and current_line == hover_row)
            toggle = "[-]" if is_expanded else "[+]"
            entry = f"  {PASTEL_BLUE}{toggle} {prefix} {r}{RESET}"
            if highlight:
                entry = f"{HOVER_BG}{entry}{RESET}"
            lines.append(entry)
            if line_map is not None:
                line_map[current_line] = rule_key
            current_line += 1

            if is_expanded and invokers:
                rule_invocations = invokers.get(rule_key, [])
                if rule_invocations:
                    for inv in rule_invocations:
                        ts = inv.get('timestamp', '??:??:??')
                        source = inv.get('source', 'unknown')
                        lines.append(f"      {DIM}[{ts}] {source}{RESET}")
                        current_line += 1
                else:
                    lines.append(f"      {DIM}(no invoker data){RESET}")
                    current_line += 1

    return '\n'.join(lines)

