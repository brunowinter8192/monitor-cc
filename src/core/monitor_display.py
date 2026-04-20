# INFRASTRUCTURE
from datetime import datetime
from typing import Optional

from ..constants import RESET, GREEN, YELLOW, CYAN, MODE_ALL, MODE_MAIN, MAIN_EVENT_BUFFER_CAP, ZEBRA_BG_A, ZEBRA_BG_B
from ..format.formatter import format_tool_call
from ..format.formatter_events import format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_system_message
from ..utils import truncate_visible

INDENT = '  '

main_event_buffer: list = []
main_scroll_offset: int = 0

# FUNCTIONS

# Append structured event to buffer; trim oldest if cap exceeded
def _buffer_append(event_type: str, data: dict, call_number=None) -> None:
    global main_event_buffer
    main_event_buffer.append({'type': event_type, 'data': data, 'call_number': call_number})
    if len(main_event_buffer) > MAIN_EVENT_BUFFER_CAP:
        del main_event_buffer[:len(main_event_buffer) - MAIN_EVENT_BUFFER_CAP]

# Truncate line to max length for display (legacy helper, kept for format_warning)
def truncate_line(line: str, max_length: int) -> str:
    if len(line) <= max_length:
        return line
    return line[:max_length] + '...'

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

# Buffer warning event
def display_warning(warning: dict) -> None:
    _buffer_append('warning', warning)

# Buffer user media event (items already grouped by caller)
def display_user_media(media_items: list) -> None:
    _buffer_append('user_media', {'items': media_items})

# Buffer skill/command activation event
def display_skill_activation(skill_item: dict) -> None:
    _buffer_append('skill_activation', skill_item)

# Buffer thinking block event
def display_thinking(thinking_item: dict) -> None:
    _buffer_append('thinking', thinking_item)

# Buffer tool call event
def display_tool_call(tool_call: dict, call_number: int) -> None:
    _buffer_append('tool_call', tool_call, call_number)

# Buffer user prompt event
def display_user_prompt_from_jsonl(prompt_item: dict) -> None:
    _buffer_append('user_prompt', prompt_item)

# Buffer system message event
def display_system_message(sys_msg: dict) -> None:
    _buffer_append('system_message', sys_msg)

# Format buffered event to list of display strings (split by newline)
def _format_event_to_lines(event: dict) -> list:
    t = event['type']
    d = event['data']
    if t == 'tool_call':
        formatted = format_tool_call(
            tool_name=d['tool_name'],
            input_data=d['input'],
            output_data=d['output'] or '',
            tool_use_id=d['tool_use_id'],
            timestamp=d['timestamp'],
            call_number=event['call_number'],
            is_subagent=d.get('is_subagent', False),
            system_reminders=d.get('system_reminders', []),
            is_error=d.get('is_error', False),
        )
    elif t == 'user_prompt':
        formatted = format_user_prompt(d.get('timestamp', ''))
    elif t == 'user_media':
        formatted = format_user_media(d.get('items', []))
    elif t == 'thinking':
        formatted = format_thinking(d)
    elif t == 'skill_activation':
        formatted = format_skill_activation(d)
    elif t == 'system_message':
        formatted = format_system_message(d.get('timestamp', ''), d.get('text', ''))
    elif t == 'warning':
        formatted = format_warning(d['file_path'], d['line_number'], d['error_message'], d['raw_line'])
    elif t == 'session_banner':
        formatted = f"{CYAN}--- New session detected ---{RESET}"
    else:
        return []
    return formatted.split('\n')

# Render event buffer to screen-sized string with zebra shading + truncation
def render_main_buffer(pane_height: int, pane_width: int, scroll_offset: int) -> str:
    all_lines = []
    for event in main_event_buffer:
        all_lines.extend(_format_event_to_lines(event))
        all_lines.append('')  # blank separator between events

    total = len(all_lines)
    # scroll_offset=0 → show newest (bottom); increasing offset scrolls up
    start = max(0, total - pane_height - scroll_offset)
    visible = all_lines[start:start + pane_height]

    result_lines = []
    for i, line in enumerate(visible):
        logical_idx = start + i
        zebra_bg = ZEBRA_BG_B if logical_idx % 2 else ZEBRA_BG_A
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{zebra_bg}{trunc}\033[K{RESET}")
    return '\n'.join(result_lines)

# Print session status after initialization
def print_session_status(session_count: int, project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    if session_count == 0:
        print(f"{YELLOW}No sessions found.{RESET}")
        if project_filter:
            print(f"{YELLOW}Project {project_filter} has no active Claude Code sessions.{RESET}\n")
        else:
            print(f"{YELLOW}No sessions in ~/.claude/projects{RESET}\n")
    else:
        mode_label = ''
        if mode == MODE_MAIN:
            mode_label = ' (main agent only)'
        print(f"{GREEN}Monitoring {session_count} sessions{mode_label}{RESET}")
        if project_filter:
            print(f"{CYAN}Project: {project_filter}{RESET}")
        print(f"{CYAN}Waiting for new tool calls...{RESET}\n")
