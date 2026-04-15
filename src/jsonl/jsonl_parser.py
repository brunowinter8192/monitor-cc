# INFRASTRUCTURE
import json
from pathlib import Path
from typing import List, Tuple, Optional

from ..constants import EXCLUDED_TOOLS
from .jsonl_extractors import (
    extract_user_media, extract_user_prompts, extract_thinking_blocks,
    extract_skill_activations, extract_usage_data, extract_system_messages,
    detect_unknown_types,
)

# ORCHESTRATOR
def parse_new_tool_calls(filepath: Path, last_position: int, tool_use_cache: dict) -> Tuple[List[dict], int, List[dict], List[dict], List[dict], List[dict], List[dict], List[dict], List[dict], List[dict]]:
    new_lines = read_new_lines(filepath, last_position)
    new_position = get_current_position(filepath)
    messages, malformed_lines = parse_jsonl_lines(new_lines)
    tool_calls = extract_tool_calls(messages, tool_use_cache)
    user_prompts = extract_user_prompts(messages)
    user_media = extract_user_media(messages)
    thinking_blocks = extract_thinking_blocks(messages)
    skill_activations = extract_skill_activations(messages)
    unknown_types = detect_unknown_types(messages)
    usage_data = extract_usage_data(messages)
    system_messages = extract_system_messages(messages)
    malformed_warnings = build_malformed_warnings(filepath, malformed_lines)
    return tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, usage_data, system_messages

# FUNCTIONS

# Build warning dictionaries from malformed line data
def build_malformed_warnings(filepath: Path, malformed_lines: List[dict]) -> List[dict]:
    warnings = []
    for malformed in malformed_lines:
        warning = {
            'file_path': filepath.name,
            'line_number': malformed['line_number'],
            'error_message': malformed['error_message'],
            'raw_line': malformed['raw_line']
        }
        warnings.append(warning)
    return warnings

# Read new lines from file since last position
def read_new_lines(filepath: Path, last_position: int) -> List[str]:
    if not filepath.exists():
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        f.seek(last_position)
        content = f.read()
        if not content:
            return []
        lines = content.split('\n')
        if lines and not lines[-1]:
            lines = lines[:-1]
        return lines

# Get current file position for next read
def get_current_position(filepath: Path) -> int:
    return filepath.stat().st_size

# Parse JSONL lines into message objects
def parse_jsonl_lines(lines: List[str]) -> Tuple[List[dict], List[dict]]:
    messages = []
    malformed_lines = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            messages.append(message)
        except json.JSONDecodeError as e:
            malformed_lines.append({
                'line_number': line_number,
                'error_message': str(e),
                'raw_line': line
            })
    return messages, malformed_lines

# Extract tool_use and tool_result pairs from messages
def extract_tool_calls(messages: List[dict], tool_use_cache: dict) -> List[dict]:
    tool_calls = []
    tool_use_count = 0
    tool_result_count = 0
    orphaned_results = 0
    total_blocks = 0
    progress_count = 0

    for message in messages:
        msg_type = message.get('type')

        if msg_type == 'progress':
            data = message.get('data', {})
            if data.get('type') != 'agent_progress':
                continue
            progress_count += 1
            agent_id = data.get('agentId')
            if not agent_id:
                continue
            inner_message = data.get('message', {})
            content_blocks = get_progress_content(inner_message)
            is_subagent = True
        else:
            content_blocks = get_message_content(message)
            is_subagent = False
            agent_id = None

        total_blocks += len(content_blocks)
        if not content_blocks:
            continue

        for block in content_blocks:
            if is_tool_use(block):
                tool_use_count += 1
                tool_data = create_tool_use_entry(block, message, is_subagent, agent_id)
                tool_use_cache[tool_data['tool_use_id']] = tool_data
            elif is_tool_result(block):
                tool_result_count += 1
                tool_use_id = block.get('tool_use_id')
                if tool_use_id in tool_use_cache:
                    tool_data = tool_use_cache[tool_use_id]
                    raw_content = extract_result_content(block)
                    tool_data['output'] = raw_content
                    tool_data['spawned_agent_id'] = extract_spawned_agent_id(message)
                    tool_data['is_error'] = block.get('is_error', False)
                    tool_calls.append(tool_data)
                    del tool_use_cache[tool_use_id]
                else:
                    orphaned_results += 1

    filtered_calls = filter_excluded_tools(tool_calls)
    sorted_calls = sort_by_timestamp(filtered_calls)
    return sorted_calls

# Get message content blocks
def get_message_content(message: dict) -> List[dict]:
    if 'message' in message and isinstance(message['message'], dict):
        content = message['message'].get('content', [])
    else:
        content = message.get('content', [])
    if isinstance(content, list):
        return content
    return []

# Get content blocks from progress message (nested structure: data.message.message.content)
def get_progress_content(inner_message: dict) -> List[dict]:
    inner_inner = inner_message.get('message', {})
    content = inner_inner.get('content', [])
    if isinstance(content, list):
        return content
    return []

# Check if content block is tool_use
def is_tool_use(block: dict) -> bool:
    return block.get('type') == 'tool_use'

# Check if content block is tool_result
def is_tool_result(block: dict) -> bool:
    return block.get('type') == 'tool_result'

# Create tool call entry from tool_use block
def create_tool_use_entry(block: dict, message: dict, is_subagent: bool = False, agent_id: str = None) -> dict:
    return {
        'tool_name': block.get('name', 'Unknown'),
        'input': block.get('input', {}),
        'output': None,
        'tool_use_id': block.get('id', ''),
        'timestamp': message.get('timestamp', ''),
        'call_number': message.get('call_number', 0),
        'is_subagent': is_subagent or message.get('isSidechain', False),
        'agent_id': agent_id or message.get('agentId', None)
    }

# Extract spawned agent ID from toolUseResult in message
def extract_spawned_agent_id(message: dict) -> Optional[str]:
    tool_use_result = message.get('toolUseResult', {})
    if isinstance(tool_use_result, dict):
        return tool_use_result.get('agentId')
    return None

# Extract result content from tool_result block
def extract_result_content(block: dict) -> str:
    content = block.get('content', '')
    if isinstance(content, list) and len(content) > 0:
        if isinstance(content[0], dict):
            return content[0].get('text', '')
        return str(content[0])
    return str(content)

# Filter out excluded tools
def filter_excluded_tools(tool_calls: List[dict]) -> List[dict]:
    return [call for call in tool_calls if call['tool_name'] not in EXCLUDED_TOOLS]

# Sort tool calls by timestamp
def sort_by_timestamp(tool_calls: List[dict]) -> List[dict]:
    return sorted(tool_calls, key=lambda x: x.get('timestamp', ''))
