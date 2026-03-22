# INFRASTRUCTURE
import logging
import re

# From utils.py: Timestamp formatting
from .utils import format_timestamp
# From constants.py: Colors and config values
from .constants import GREEN, BLUE, YELLOW, CYAN, RED, PASTEL_BLUE, PASTEL_PURPLE, LIGHT_RED_BG, PASTEL_ORANGE, RESET, LONG_OUTPUT_THRESHOLD

INDENT = '  '
SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
long_output_logger = logging.getLogger('formatter.long_outputs')
long_output_handler = logging.FileHandler('src/logs/10_long_outputs.log')
long_output_handler.setFormatter(log_format)
long_output_logger.addHandler(long_output_handler)
long_output_logger.setLevel(logging.INFO)

# ORCHESTRATOR
def format_tool_call(tool_name: str, input_data: dict, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None, is_error: bool = False) -> str:
    request = format_request(tool_name, input_data, tool_use_id, timestamp, call_number, is_subagent)
    response = format_response(tool_name, output_data, tool_use_id, timestamp, call_number, is_subagent, system_reminders, is_error)
    return combine_request_response(request, response)

# FUNCTIONS

# Combine request and response sections with spacing
def combine_request_response(request: str, response: str) -> str:
    return f"{request}\n\n{response}"

# Format REQUEST header with color based on agent type
def format_request(tool_name: str, input_data: dict, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False) -> str:
    time_str = format_timestamp(timestamp)
    color = BLUE if is_subagent else GREEN
    header = f"{color}[{time_str}] REQUEST #{call_number} → {tool_name}{RESET}"

    if tool_name == 'TodoWrite' and 'todos' in input_data:
        params = format_todo_list(input_data['todos'])
    elif tool_name == 'Task' and 'subagent_type' in input_data:
        params = format_task_parameters(input_data)
    else:
        params = format_parameters(input_data)

    return f"{header}\n{params}"

# Format RESPONSE header with color based on agent type
def format_response(tool_name: str, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None, is_error: bool = False) -> str:
    time_str = format_timestamp(timestamp)

    if is_error:
        # RED imported from constants via INFRASTRUCTURE
        header = f"{RED}[{time_str}] RESPONSE #{call_number} ← {tool_name} [ERROR]{RESET}"
        content = format_error_output(output_data)
    else:
        color = BLUE if is_subagent else GREEN
        header = f"{color}[{time_str}] RESPONSE #{call_number} ← {tool_name}{RESET}"
        content = format_output(output_data)

    reminders = format_system_reminders(system_reminders)

    parts = [header, content]
    if reminders:
        parts.append(reminders)
    return '\n'.join(parts)

# Format todo list with colored status and icons
def format_todo_list(todos: list) -> str:
    if not todos:
        return f"{INDENT}(no todos)"

    lines = []
    for idx, todo in enumerate(todos, 1):
        status = todo.get('status', 'pending')
        content = todo.get('content', '(no content)')

        icon = get_status_icon(status)
        color = get_status_color(status)
        status_label = status.upper().replace('_', ' ')

        lines.append(f"\n{INDENT}TODO #{idx} - {status_label} {icon}")
        lines.append(f"{INDENT}{INDENT}{color}{content}{RESET}")

    return '\n'.join(lines)

# Format input parameters with 2-space indentation
def format_parameters(params: dict) -> str:
    lines = []
    for key, value in params.items():
        formatted_value = format_value(value)
        lines.append(f"{INDENT}{key}: {formatted_value}")
    return '\n'.join(lines)

# Format Task parameters with highlighted subagent_type
def format_task_parameters(params: dict) -> str:
    lines = []
    for key, value in params.items():
        if key == 'subagent_type':
            lines.append(f"{INDENT}{key}: {CYAN}{value}{RESET}")
        else:
            formatted_value = format_value(value)
            lines.append(f"{INDENT}{key}: {formatted_value}")
    return '\n'.join(lines)

# Format output content with 2-space indentation and red background for long outputs
def format_output(content: str) -> str:
    if not content:
        return f"{INDENT}(empty)"

    is_long = len(content) >= LONG_OUTPUT_THRESHOLD
    if is_long:
        log_long_output(content)

    lines = content.split('\n')
    formatted_lines = []
    for line in lines:
        if SCORE_PATTERN.match(line.strip()):
            formatted_lines.append(f"{INDENT}{GREEN}{line}{RESET}")
        else:
            formatted_lines.append(f"{INDENT}{line}")
    result = '\n'.join(formatted_lines)

    if is_long:
        return f"{LIGHT_RED_BG}{result}{RESET}"
    return result

# Format error output content in red
def format_error_output(content: str) -> str:
    if not content:
        return f"{INDENT}{RED}(empty){RESET}"

    lines = content.split('\n')
    formatted_lines = '\n'.join(f"{INDENT}{RED}{line}{RESET}" for line in lines)
    return formatted_lines

# Format system reminders with pastel blue color
def format_system_reminders(reminders: list) -> str:
    if not reminders:
        return ''
    lines = []
    for reminder in reminders:
        for line in reminder.split('\n'):
            if line.strip():
                lines.append(f"{INDENT}{PASTEL_BLUE}{line}{RESET}")
    return '\n'.join(lines)

# Format parameter value preserving newlines for multiline strings
def format_value(value) -> str:
    if isinstance(value, str) and '\n' in value:
        lines = value.split('\n')
        return '\n' + '\n'.join(f"{INDENT}{line}" for line in lines)
    elif isinstance(value, dict):
        return str(value)
    elif isinstance(value, list):
        return str(value)
    else:
        return str(value)

# Get status icon for todo item
def get_status_icon(status: str) -> str:
    icons = {
        'completed': '[X]',
        'in_progress': '[>]',
        'pending': '[-]'
    }
    return icons.get(status, '[-]')

# Get status color for todo item
def get_status_color(status: str) -> str:
    colors = {
        'completed': GREEN,
        'in_progress': YELLOW,
        'pending': RESET
    }
    return colors.get(status, RESET)

# Log long tool output to separate log file
def log_long_output(content: str) -> None:
    char_count = len(content)
    line_count = len(content.split('\n'))
    long_output_logger.info(f"LONG_OUTPUT detected: {char_count} chars, {line_count} lines")
    long_output_logger.info(f"Content preview (first 500 chars): {content[:500]}")
    long_output_logger.info(f"Full content:\n{content}")
    long_output_logger.info("=" * 80)

# Format USER PROMPT stamp with optional hook outputs
def format_user_prompt(timestamp: str, hook_outputs: list = None) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{PASTEL_PURPLE}[{time_str}] USER PROMPT{RESET}"

    if hook_outputs:
        lines = [header]
        for output in hook_outputs:
            if output:
                lines.append(f"{INDENT}{PASTEL_PURPLE}Hook: {output}{RESET}")
        return '\n'.join(lines)
    return header

# Format hook annotation for PreToolUse hooks
def format_hook_annotation(hook_output: str, hook_script: str) -> str:
    return f"{INDENT}{PASTEL_PURPLE}Hook [{hook_script}]: {hook_output}{RESET}"

# Format single hook event for hooks pane display
def format_hook_event(timestamp: str, hook_event: str, hook_script: str, output: str) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{PASTEL_PURPLE}[{time_str}] {hook_event} | {hook_script}{RESET}"
    if output:
        return f"{header}\n{INDENT}{PASTEL_PURPLE}{output}{RESET}"
    return header

# Format user media item (image or document)
def format_user_media(media_item: dict) -> str:
    time_str = format_timestamp(media_item.get('timestamp', ''))
    media_type = media_item.get('type', 'unknown')
    mime_type = media_item.get('media_type', 'unknown')

    if media_type == 'image':
        label = f"[IMAGE: {mime_type}]"
    elif media_type == 'document':
        label = f"[DOC: {mime_type}]"
    else:
        label = f"[MEDIA: {mime_type}]"

    return f"{PASTEL_PURPLE}[{time_str}] USER PROMPT {label}{RESET}"

# Format skill/command activation with full content
def format_skill_activation(skill_item: dict) -> str:
    time_str = format_timestamp(skill_item.get('timestamp', ''))
    skill_name = skill_item.get('skill_name', 'unknown')
    content = skill_item.get('content', '')
    header = f"{CYAN}[{time_str}] SKILL LOADED: {skill_name}{RESET}"
    body_lines = content.split('\n')
    formatted_body = '\n'.join(f"{INDENT}{line}" for line in body_lines)
    return f"{header}\n{formatted_body}"

# Format thinking block from assistant
def format_thinking(thinking_item: dict) -> str:
    time_str = format_timestamp(thinking_item.get('timestamp', ''))
    thinking_text = thinking_item.get('thinking', '')
    return f"{PASTEL_ORANGE}[{time_str}] THINKING: {thinking_text}{RESET}"

# Format unknown JSONL type warning for warnings pane
def format_unknown_type_warning(msg_type: str, count: int) -> str:
    return f"{INDENT}{YELLOW}[!] Unknown JSONL type: {msg_type} (seen {count}x){RESET}"
