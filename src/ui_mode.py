# INFRASTRUCTURE
import logging
import time
from typing import Dict, List

# From utils.py: ANSI colors and logging utility
from .utils import RESET, WHITE, CYAN, PURPLE, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_ui = logging.getLogger('ui_mode.loop')
ui_handler = logging.FileHandler('src/logs/08_ui_rendering.log')
ui_handler.setFormatter(log_format)
logger_ui.addHandler(ui_handler)
logger_ui.setLevel(logging.INFO)

# From click_handler.py: Keyboard input handling
from .click_handler import setup_keyboard_input, restore_terminal, read_keypress, parse_digit_key, get_agent_by_index
# From subagent_ui.py: Render subagent list and manage state
from .subagent_ui import render_subagent_list, get_agent_display_name, count_calls_for_agent, subagent_states, toggle_subagent_state

POLL_INTERVAL = 0.5
ui_loop_iteration: int = 0
last_rendered_output: str = ""
_last_agent_count: int = 0
_last_expanded_count: int = 0

# ORCHESTRATOR
def run_ui_loop(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]], agent_to_task: Dict[str, str], agent_to_type: Dict[str, str], monitor_sessions_fn) -> None:
    global ui_loop_iteration

    setup_keyboard_input()

    try:
        while True:
            ui_loop_iteration += 1
            if ui_loop_iteration % 10 == 0:
                log_tagged(logger_ui, "UI_ITER", WHITE, f"UI loop iteration #{ui_loop_iteration}")

            handle_pending_keypresses(subagent_metadata)
            monitor_sessions_fn()
            sync_ui_to_screen(subagent_metadata, tool_calls_by_agent)
            time.sleep(POLL_INTERVAL)
    finally:
        restore_terminal()

# FUNCTIONS

# Processes any pending keyboard input (digits 1-9 toggle subagents)
def handle_pending_keypresses(subagent_metadata: Dict[str, dict]) -> None:
    char = read_keypress()
    if char:
        index = parse_digit_key(char)
        if index:
            agent_id = get_agent_by_index(index, subagent_metadata)
            if agent_id:
                toggle_subagent_state(agent_id)

# Syncs UI output to terminal screen
def sync_ui_to_screen(subagent_metadata: Dict[str, dict], tool_calls_by_agent: Dict[str, List[dict]]) -> None:
    global last_rendered_output, _last_agent_count, _last_expanded_count

    agent_count = len(subagent_metadata)
    expanded_count = sum(1 for agent_id in subagent_states if subagent_states.get(agent_id, False))

    formatted_output = render_subagent_list(subagent_metadata, tool_calls_by_agent)

    if formatted_output != last_rendered_output:
        log_tagged(logger_ui, "UI_SYNC", PURPLE, f"sync_ui_to_screen: agents={agent_count}, expanded={expanded_count}")
        log_tagged(logger_ui, "UI_RENDER", PURPLE, f"Re-rendering UI: {len(formatted_output)} chars, agents={agent_count}, expanded={expanded_count}")
        print("\033[2J\033[3J\033[H", end='', flush=True)
        print(formatted_output)
        last_rendered_output = formatted_output
        _last_agent_count = agent_count
        _last_expanded_count = expanded_count

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
        log_tagged(logger_ui, "AGENT_DISC", CYAN, f"Discovered new agent: {agent_id}, type={subagent_type}, file={filepath.name}")

    tool_calls_by_agent[agent_id].append(tool_call)
    subagent_metadata[agent_id]['call_count'] = count_calls_for_agent(tool_calls_by_agent[agent_id])

