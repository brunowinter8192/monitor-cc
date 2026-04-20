# INFRASTRUCTURE
from datetime import datetime
from typing import Optional

from ..constants import RESET, GREEN, YELLOW, CYAN, MODE_ALL, MODE_MAIN, MODE_SUBAGENT
from ..format.formatter import format_tool_call
from ..format.formatter_events import format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_system_message

INDENT = '  '

# FUNCTIONS

# Truncate line to max length for display
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

# Display formatted warning to console
def display_warning(warning: dict) -> None:
    formatted = format_warning(
        file_path=warning['file_path'],
        line_number=warning['line_number'],
        error_message=warning['error_message'],
        raw_line=warning['raw_line']
    )

    print(formatted)
    print()

# Display formatted user media to console
def display_user_media(media_items: list) -> None:
    formatted = format_user_media(media_items)
    print(formatted)
    print()

# Display formatted skill/command activation to console
def display_skill_activation(skill_item: dict) -> None:
    formatted = format_skill_activation(skill_item)
    print(formatted)
    print()

# Display formatted thinking block to console
def display_thinking(thinking_item: dict) -> None:
    formatted = format_thinking(thinking_item)
    print(formatted)
    print()

# Display formatted tool call to console
def display_tool_call(tool_call: dict, call_number: int) -> None:
    tool_name = tool_call['tool_name']

    formatted = format_tool_call(
        tool_name=tool_name,
        input_data=tool_call['input'],
        output_data=tool_call['output'] or '',
        tool_use_id=tool_call['tool_use_id'],
        timestamp=tool_call['timestamp'],
        call_number=call_number,
        is_subagent=tool_call.get('is_subagent', False),
        system_reminders=tool_call.get('system_reminders', []),
        is_error=tool_call.get('is_error', False)
    )

    print(formatted)
    print()

# Display USER PROMPT detected from session JSONL
def display_user_prompt_from_jsonl(prompt_item: dict) -> None:
    formatted = format_user_prompt(prompt_item.get('timestamp', ''))
    print(formatted)
    print()

# Display system message detected from session JSONL
def display_system_message(sys_msg: dict) -> None:
    formatted = format_system_message(sys_msg.get('timestamp', ''), sys_msg.get('text', ''))
    print(formatted)
    print()

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
        elif mode == MODE_SUBAGENT:
            mode_label = ' (subagent only)'

        print(f"{GREEN}Monitoring {session_count} sessions{mode_label}{RESET}")
        if project_filter:
            print(f"{CYAN}Project: {project_filter}{RESET}")
        print(f"{CYAN}Waiting for new tool calls...{RESET}\n")
