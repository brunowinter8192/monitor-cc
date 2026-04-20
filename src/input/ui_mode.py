# INFRASTRUCTURE
from typing import Dict, List, Optional

# From constants.py: Colors
from ..constants import PASTEL_BLUE, DIM, YELLOW, CYAN, GREEN, SOFT_RESET

# FUNCTIONS

# Map source label to display color
def _source_color(source: str) -> str:
    if source == 'main':
        return CYAN
    if source.startswith('worker:'):
        return GREEN
    return DIM

# Build (visible_lines, visible_keys, None, scroll_offset) for rules pane; keys: str=rule_key, None=non-clickable
def format_rules_block(active_rules: Dict[str, set], invokers: Optional[Dict[str, Dict[str, str]]] = None, expand_states: Optional[Dict[str, bool]] = None, line_map: Optional[Dict[int, str]] = None, hover_row: Optional[int] = None, scroll_offset: int = 0, frozen: bool = False) -> tuple:
    if not active_rules:
        return ([], [], None, 0, 0)
    project_rules = sorted(active_rules.get('project', set()))
    global_rules = sorted(active_rules.get('global', set()))
    if not project_rules and not global_rules:
        return ([], [], None, 0, 0)

    all_lines: List[str] = []
    all_keys: List = []
    rule_key_at: Dict[int, str] = {}

    freeze_indicator = f" {YELLOW}[FROZEN]{SOFT_RESET}" if frozen else f" {CYAN}[LIVE]{SOFT_RESET}"
    header = f"{PASTEL_BLUE}ACTIVE RULES ({len(project_rules)}P / {len(global_rules)}G){SOFT_RESET}{freeze_indicator}"
    all_lines.append(header)
    all_keys.append(None)

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
                source_indicator = f" {_source_color(recent_source)}●{SOFT_RESET}"
            all_lines.append(f"  {PASTEL_BLUE}{toggle} {prefix} {r}{SOFT_RESET}{source_indicator}")
            all_keys.append(rule_key)
            rule_key_at[rule_line_idx] = rule_key

            if is_expanded and invokers:
                if source_map:
                    for source, ts in sorted(source_map.items()):
                        color = _source_color(source)
                        all_lines.append(f"      {color}[{ts}] {source}{SOFT_RESET}")
                        all_keys.append(None)
                else:
                    all_lines.append(f"      {DIM}(no invoker data){SOFT_RESET}")
                    all_keys.append(None)

    total_lines = len(all_lines)
    visible_lines = all_lines[scroll_offset:]
    visible_keys = all_keys[scroll_offset:]

    return (visible_lines, visible_keys, None, scroll_offset, total_lines)
