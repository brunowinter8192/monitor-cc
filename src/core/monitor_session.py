# INFRASTRUCTURE
from pathlib import Path

# From constants.py: Mode constants and tool name
from ..constants import MODE_WARNINGS, MODE_TOKENS, MODE_MAIN, TOOL_TASK
# From jsonl/: Parse JSONL and extract tool calls
from ..jsonl import parse_new_tool_calls_isolated
# From monitor_display.py: Console output for tool calls and session status
from .monitor_display import display_warning, display_user_media, display_skill_activation, display_thinking, display_tool_call, display_user_prompt_from_jsonl, display_system_message

# FUNCTIONS

# Get end position of file (for initializing at EOF)
def get_file_end_position(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    return filepath.stat().st_size

# Get initial position for new session file
def get_initial_position(filepath: Path) -> int:
    from . import monitor as _monitor
    if _monitor.is_agent_file(filepath):
        return 0
    return get_file_end_position(filepath)

# Process single session file for new tool calls and warnings
def process_session_file(filepath: Path) -> None:
    from . import monitor as _monitor

    if filepath not in _monitor.tool_use_caches:
        _monitor.tool_use_caches[filepath] = {}

    last_position = _monitor.file_positions[filepath]
    cache = _monitor.tool_use_caches[filepath]

    tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, usage_data, system_messages = parse_new_tool_calls_isolated(filepath, last_position, cache)

    _monitor.file_positions[filepath] = new_position

    if _monitor.active_mode in (MODE_WARNINGS, MODE_TOKENS):
        return

    for warning in malformed_warnings:
        display_warning(warning)

    for prompt_item in user_prompts:
        display_user_prompt_from_jsonl(prompt_item)

    for sys_msg in system_messages:
        display_system_message(sys_msg)

    for skill_item in skill_activations:
        display_skill_activation(skill_item)

    media_groups: dict = {}
    for media_item in user_media:
        ts = media_item.get('timestamp', '')
        media_groups.setdefault(ts, []).append(media_item)
    for ts_group in media_groups.values():
        display_user_media(ts_group)

    for thinking_item in thinking_blocks:
        display_thinking(thinking_item)

    for tool_call in tool_calls:
        if is_task_request(tool_call):
            handle_task_request(tool_call)
        elif is_task_response(tool_call):
            handle_task_response(tool_call)
        elif is_subagent_call(tool_call):
            handle_subagent_call(tool_call)
        else:
            _monitor.call_counter += 1
            display_tool_call(tool_call, _monitor.call_counter)

# Check if tool call is a Task REQUEST
def is_task_request(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == TOOL_TASK and tool_call.get('output') is None

# Check if tool call is a Task RESPONSE
def is_task_response(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == TOOL_TASK and tool_call.get('output') is not None

# Check if tool call is from a Subagent
def is_subagent_call(tool_call: dict) -> bool:
    return tool_call.get('is_subagent', False)

# Handle Task tool REQUEST (no output yet)
def handle_task_request(tool_call: dict) -> int:
    from . import monitor as _monitor
    _monitor.call_counter += 1
    _monitor.task_requests_seen.add(tool_call['tool_use_id'])
    display_tool_call(tool_call, _monitor.call_counter)
    return 1

# Handle Task tool RESPONSE (has output, may spawn agent)
def handle_task_response(tool_call: dict) -> int:
    from . import monitor as _monitor

    spawned_agent_id = tool_call.get('spawned_agent_id')
    if spawned_agent_id:
        _monitor.agent_to_task[spawned_agent_id] = tool_call['tool_use_id']
        subagent_type = tool_call.get('input', {}).get('subagent_type', '')
        _monitor.agent_to_type[spawned_agent_id] = subagent_type

        if spawned_agent_id in _monitor.buffered_subagent_calls:
            for buffered_call in _monitor.buffered_subagent_calls[spawned_agent_id]:
                _monitor.call_counter += 1
                display_tool_call(buffered_call, _monitor.call_counter)
            del _monitor.buffered_subagent_calls[spawned_agent_id]

    _monitor.call_counter += 1
    display_tool_call(tool_call, _monitor.call_counter)
    return 1

# Handle tool call from subagent
def handle_subagent_call(tool_call: dict) -> None:
    from . import monitor as _monitor

    agent_id = tool_call.get('agent_id')

    if _monitor.active_mode == MODE_MAIN:
        return

    if agent_id and agent_id in _monitor.agent_to_task:
        _monitor.call_counter += 1
        display_tool_call(tool_call, _monitor.call_counter)
    elif agent_id:
        if agent_id not in _monitor.buffered_subagent_calls:
            _monitor.buffered_subagent_calls[agent_id] = []
        _monitor.buffered_subagent_calls[agent_id].append(tool_call)

# Load historical data from newest main session for initial display
def load_historical_main() -> None:
    from . import monitor as _monitor
    main_sessions = _monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _monitor.file_positions[filepath] = 0
        _monitor.tool_use_caches[filepath] = {}

