# INFRASTRUCTURE
import logging
from datetime import datetime

logging.basicConfig(
    filename='src/logs/formatter.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

GREEN = '\033[38;5;35m'
BLUE = '\033[38;5;33m'
YELLOW = '\033[38;5;220m'
CYAN = '\033[38;5;51m'
RESET = '\033[0m'
INDENT = '  '

# ORCHESTRATOR
def format_tool_call(tool_name: str, input_data: dict, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False) -> str:
    request = format_request(tool_name, input_data, tool_use_id, timestamp, call_number, is_subagent)
    response = format_response(tool_name, output_data, tool_use_id, timestamp, call_number, is_subagent)
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
def format_response(tool_name: str, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False) -> str:
    time_str = format_timestamp(timestamp)
    color = BLUE if is_subagent else GREEN
    header = f"{color}[{time_str}] RESPONSE #{call_number} ← {tool_name}{RESET}"
    content = format_output(output_data)
    return f"{header}\n{content}"

# Format WARNING header with yellow color for malformed lines
def format_warning(file_path: str, line_number: int, error_message: str, raw_line: str) -> str:
    now = datetime.now().strftime('%H:%M:%S')
    header = f"{YELLOW}[{now}] [!] WARNING - Malformed JSON{RESET}"

    truncated_line = truncate_line(raw_line, 200)

    details = [
        f"{INDENT}File: {file_path}",
        f"{INDENT}Line: {line_number}",
        f"{INDENT}Error: {error_message}",
        f"{INDENT}Content: {truncated_line}"
    ]

    return f"{header}\n" + '\n'.join(details)

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

# Format output content with 2-space indentation
def format_output(content: str) -> str:
    if not content:
        return f"{INDENT}(empty)"

    lines = content.split('\n')
    return '\n'.join(f"{INDENT}{line}" for line in lines)

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

# Truncate line to max length for display
def truncate_line(line: str, max_length: int) -> str:
    if len(line) <= max_length:
        return line
    return line[:max_length] + '...'

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
