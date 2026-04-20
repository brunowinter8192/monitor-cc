# INFRASTRUCTURE
from ..constants import RESET, YELLOW, CYAN, HOVER_BG
from ..format.token_format import format_cache_tracker
from ..utils import visual_line_count
from .subagent_ui import subagent_states
from .subagent_ui_format import build_collapsed_entry

# FUNCTIONS

# Render subagent list with cache-tracker turns for expanded agents
def render_subagents_with_tokens(subagent_metadata_map, turns_by_agent, pane_line_map, pane_hover_row, pane_height, pane_width, scroll_offsets, cache_expand_states=None, cache_line_map=None, frozen: bool = False) -> str:
    agent_count = len(subagent_metadata_map)
    all_lines = []
    all_keys = []

    freeze_indicator = f" {YELLOW}[FROZEN]{RESET}" if frozen else f" {CYAN}[LIVE]{RESET}"
    header = f"{CYAN}Active Subagents ({agent_count}){RESET}{freeze_indicator}"
    all_lines.append(header)
    all_keys.append(None)
    all_lines.append('')
    all_keys.append(None)

    if not subagent_metadata_map:
        all_lines.append(f"{YELLOW}No subagents active yet{RESET}")
        all_keys.append(None)
        if pane_line_map is not None:
            pane_line_map.clear()
        return '\n'.join(all_lines)

    for idx, (agent_id, metadata) in enumerate(sorted(subagent_metadata_map.items(), key=lambda x: x[1]['timestamp']), 1):
        is_expanded = subagent_states.get(agent_id, False)
        entry_header = build_collapsed_entry(idx, metadata, is_expanded=is_expanded)
        all_lines.append(entry_header)
        all_keys.append(agent_id)

        if is_expanded:
            turns = turns_by_agent.get(agent_id, [])
            scroll_offset = scroll_offsets.get(agent_id, 0)
            if not turns:
                all_lines.append(f"  {YELLOW}(no token data yet){RESET}")
                all_keys.append(None)
            else:
                per_agent_expand = (cache_expand_states or {}).get(agent_id, {})
                if cache_line_map is not None:
                    temp_clm: dict = {}
                    cache_output = format_cache_tracker(turns, per_agent_expand, temp_clm, None, 15, pane_width - 2, scroll_offset)
                    cache_start = len(all_lines) + 1
                    for rel_row, key in temp_clm.items():
                        cache_line_map[rel_row + cache_start - 1] = (agent_id, key[0], key[1])
                else:
                    cache_output = format_cache_tracker(turns, per_agent_expand, None, None, 15, pane_width - 2, scroll_offset)
                for cl in cache_output.split('\n'):
                    all_lines.append(f"  {cl}")
                    all_keys.append(None)

        all_lines.append('')
        all_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        all_keys.pop()

    if pane_line_map is not None:
        pane_line_map.clear()
        phys_row = 1
        for line, key in zip(all_lines, all_keys):
            span = visual_line_count(line, pane_width)
            if key is not None:
                for r in range(phys_row, phys_row + span):
                    pane_line_map[r] = key
            phys_row += span

    result_lines = []
    phys_row = 1
    for row_offset, line in enumerate(all_lines):
        key = all_keys[row_offset]
        span = visual_line_count(line, pane_width)
        hover_active = (key is not None and pane_hover_row is not None and
                        phys_row <= pane_hover_row < phys_row + span)
        result_lines.append(f"{HOVER_BG}{line}{RESET}" if hover_active else line)
        phys_row += span

    return '\n'.join(result_lines)
