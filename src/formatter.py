# INFRASTRUCTURE
from datetime import datetime
import logging

GREEN = '\033[38;5;35m'
BLUE = '\033[38;5;33m'
YELLOW = '\033[38;5;220m'
CYAN = '\033[38;5;51m'
PASTEL_BLUE = '\033[38;5;117m'
PASTEL_PURPLE = '\033[38;5;183m'
LIGHT_RED_BG = '\033[48;5;203m'
RESET = '\033[0m'
INDENT = '  '
LONG_OUTPUT_THRESHOLD = 10000

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
long_output_logger = logging.getLogger('formatter.long_outputs')
long_output_handler = logging.FileHandler('src/logs/10_long_outputs.log')
long_output_handler.setFormatter(log_format)
long_output_logger.addHandler(long_output_handler)
long_output_logger.setLevel(logging.INFO)

# ORCHESTRATOR
def format_tool_call(tool_name: str, input_data: dict, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None) -> str:
    request = format_request(tool_name, input_data, tool_use_id, timestamp, call_number, is_subagent)
    response = format_response(tool_name, output_data, tool_use_id, timestamp, call_number, is_subagent, system_reminders)
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
def format_response(tool_name: str, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None) -> str:
    time_str = format_timestamp(timestamp)
    color = BLUE if is_subagent else GREEN
    header = f"{color}[{time_str}] RESPONSE #{call_number} ← {tool_name}{RESET}"
    content = format_output(output_data)
    reminders = format_system_reminders(system_reminders)
    if reminders:
        return f"{header}\n{content}\n{reminders}"
    return f"{header}\n{content}"

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

# Convert ISO timestamp to HH:MM:SS format
def format_timestamp(iso_timestamp: str) -> str:
    dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
    return dt.astimezone().strftime('%H:%M:%S')

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
    formatted_lines = '\n'.join(f"{INDENT}{line}" for line in lines)

    if is_long:
        return f"{LIGHT_RED_BG}{formatted_lines}{RESET}"
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
