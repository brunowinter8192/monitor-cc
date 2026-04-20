# INFRASTRUCTURE
from typing import Dict, List, Optional

# From constants.py: Colors
from ..constants import RESET, PASTEL_BLUE, DIM, HOVER_BG, YELLOW, CYAN, GREEN

# From subagents/subagent_ui.py: Subagent state
from ..subagents.subagent_ui import subagent_states
# From subagents/subagent_ui_format.py: Display name helpers
from ..subagents.subagent_ui_format import get_agent_display_name, count_calls_for_agent

# FUNCTIONS

# Map source label to display color
def _source_color(source: str) -> str:
    if source == 'main':
        return CYAN
    if source.startswith('worker:'):
        return GREEN
    return DIM

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
def format_rules_block(active_rules: Dict[str, set], invokers: Optional[Dict[str, Dict[str, str]]] = None, expand_states: Optional[Dict[str, bool]] = None, line_map: Optional[Dict[int, str]] = None, hover_row: Optional[int] = None, scroll_offset: int = 0, frozen: bool = False) -> tuple:
    if not active_rules:
        return ('', 0)
    project_rules = sorted(active_rules.get('project', set()))
    global_rules = sorted(active_rules.get('global', set()))
    if not project_rules and not global_rules:
        return ('', 0)

    all_lines: List[str] = []
    rule_key_at: Dict[int, str] = {}

    freeze_indicator = f" {YELLOW}[FROZEN]{RESET}" if frozen else f" {CYAN}[LIVE]{RESET}"
    header = f"{PASTEL_BLUE}ACTIVE RULES ({len(project_rules)}P / {len(global_rules)}G){RESET}{freeze_indicator}"
    all_lines.append(header)

    for prefix, rule_list in [('[P]', project_rules), ('[G]', global_rules)]:
        for r in rule_list:
            rule_key = f'{prefix} {r}'
            is_expanded = (expand_states or {}).get(rule_key, False)
            toggle = "[-]" if is_expanded else "[+]"
            rule_line_idx = len(all_lines)
            source_map = (invokers or {}).get(rule_key, {})
            source_indicator = ''
            if source_map:
                recent_source = max(source_map.items(), key=lambda x: x[1])[0]
                source_indicator = f" {_source_color(recent_source)}●{RESET}"
            all_lines.append(f"  {PASTEL_BLUE}{toggle} {prefix} {r}{RESET}{source_indicator}")
            rule_key_at[rule_line_idx] = rule_key

            if is_expanded and invokers:
                if source_map:
                    for source, ts in sorted(source_map.items()):
                        color = _source_color(source)
                        all_lines.append(f"      {color}[{ts}] {source}{RESET}")
                else:
                    all_lines.append(f"      {DIM}(no invoker data){RESET}")

    total_lines = len(all_lines)
    visible = all_lines[scroll_offset:]

    if line_map is not None:
        line_map.clear()
        for screen_row_0, content_idx in enumerate(range(scroll_offset, total_lines)):
            screen_row = screen_row_0 + 1
            if content_idx in rule_key_at:
                line_map[screen_row] = rule_key_at[content_idx]

    output_lines = []
    for screen_row_0, line in enumerate(visible):
        screen_row = screen_row_0 + 1
        if hover_row is not None and screen_row == hover_row:
            content_idx = scroll_offset + screen_row_0
            if content_idx in rule_key_at:
                line = f"{HOVER_BG}{line}{RESET}"
        output_lines.append(line)

    return ('\n'.join(output_lines), total_lines)

