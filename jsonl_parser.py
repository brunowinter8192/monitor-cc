# INFRASTRUCTURE
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logging.basicConfig(
    filename='logs/jsonl_parser.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ORCHESTRATOR
def parse_new_tool_calls(filepath: Path, last_position: int, tool_use_cache: dict) -> Tuple[List[dict], int, List[dict]]:
    new_lines = read_new_lines(filepath, last_position)
    new_position = get_current_position(filepath)
    messages, malformed_lines = parse_jsonl_lines(new_lines)
    tool_calls = extract_tool_calls(messages, tool_use_cache)

    malformed_warnings = []
    for malformed in malformed_lines:
        warning = {
            'file_path': filepath.name,
            'line_number': malformed['line_number'],
            'error_message': malformed['error_message'],
            'raw_line': malformed['raw_line']
        }
        malformed_warnings.append(warning)

    return tool_calls, new_position, malformed_warnings

# FUNCTIONS

# Read new lines from file since last position
def read_new_lines(filepath: Path, last_position: int) -> List[str]:
    if not filepath.exists():
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        f.seek(last_position)
        content = f.read()

    return [line for line in content.split('\n') if line.strip()]

# Get current file size (position for next read)
def get_current_position(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    return filepath.stat().st_size

# Parse JSONL lines into message objects and track malformed lines
def parse_jsonl_lines(lines: List[str], start_line_number: int = 0) -> Tuple[List[dict], List[dict]]:
    messages = []
    malformed_lines = []

    for idx, line in enumerate(lines):
        line_number = start_line_number + idx + 1
        try:
            msg = json.loads(line)
            messages.append(msg)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error at line {line_number}: {str(e)}")
            malformed_entry = {
                'line_number': line_number,
                'error_message': str(e),
                'raw_line': line
            }
            malformed_lines.append(malformed_entry)

    return messages, malformed_lines

# Extract tool_use and tool_result pairs from messages
def extract_tool_calls(messages: List[dict], tool_use_cache: dict) -> List[dict]:
    tool_calls = []

    for msg in messages:
        message_content = get_message_content(msg)

        for content_block in message_content:
            if is_tool_use(content_block):
                tool_data = create_tool_use_entry(content_block, msg)
                tool_use_cache[tool_data['tool_use_id']] = tool_data

            elif is_tool_result(content_block):
                tool_use_id = content_block.get('tool_use_id')

                if tool_use_id in tool_use_cache:
                    tool_data = tool_use_cache[tool_use_id]
                    tool_data['output'] = extract_result_content(content_block)
                    tool_data['response_timestamp'] = msg.get('timestamp')

                    if tool_data['tool_name'] == 'Task':
                        tool_result_data = msg.get('toolUseResult', {})
                        spawned_agent_id = tool_result_data.get('agentId')
                        if spawned_agent_id:
                            tool_data['spawned_agent_id'] = spawned_agent_id

                    tool_calls.append(tool_data)
                    del tool_use_cache[tool_use_id]

    filtered_calls = filter_excluded_tools(tool_calls)
    sorted_calls = sort_by_timestamp(filtered_calls)
    return sorted_calls

# Get message content array from message object
def get_message_content(msg: dict) -> List[dict]:
    message = msg.get('message', {})
    content = message.get('content', [])

    if isinstance(content, list):
        return content
    return []

# Check if content block is a tool_use
def is_tool_use(content_block: dict) -> bool:
    return content_block.get('type') == 'tool_use'

# Check if content block is a tool_result
def is_tool_result(content_block: dict) -> bool:
    return content_block.get('type') == 'tool_result'

# Create tool use entry from content block
def create_tool_use_entry(content_block: dict, msg: dict) -> dict:
    return {
        'tool_name': content_block.get('name'),
        'input': content_block.get('input', {}),
        'tool_use_id': content_block.get('id'),
        'timestamp': msg.get('timestamp'),
        'output': None,
        'response_timestamp': None,
        'is_subagent': msg.get('isSidechain', False),
        'agent_id': msg.get('agentId')
    }

# Extract content from tool_result block
def extract_result_content(content_block: dict) -> str:
    content = content_block.get('content', '')

    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_parts.append(item.get('text', ''))
            else:
                text_parts.append(str(item))
        return '\n'.join(text_parts)
    else:
        return str(content)

# Filter excluded tools from tool calls list
def filter_excluded_tools(tool_calls: List[dict]) -> List[dict]:
    excluded_tools = {'Edit'}
    return [tc for tc in tool_calls if tc['tool_name'] not in excluded_tools]

# Sort tool calls by timestamp for chronological output
def sort_by_timestamp(tool_calls: List[dict]) -> List[dict]:
    return sorted(tool_calls, key=lambda tc: tc.get('timestamp') or '')
