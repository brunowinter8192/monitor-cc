# INFRASTRUCTURE
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional

# From constants.py: Colors
from .constants import RESET, RED, GREEN, YELLOW, BLUE, WHITE
# From constants.py: Shared constants
from .constants import EXCLUDED_TOOLS, SYSTEM_REMINDER_PATTERN, KNOWN_MESSAGE_TYPES, KNOWN_IGNORED_TYPES

# ORCHESTRATOR
def parse_new_tool_calls(filepath: Path, last_position: int, tool_use_cache: dict) -> Tuple[List[dict], int, List[dict], List[dict], List[dict], List[dict], List[dict], List[dict], List[dict]]:
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
    malformed_warnings = build_malformed_warnings(filepath, malformed_lines)

    return tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, unknown_types, usage_data

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
                    tool_data['output'] = strip_system_reminders(raw_content)
                    tool_data['system_reminders'] = extract_system_reminders(raw_content)
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

# Extract system-reminder tags from content string
def extract_system_reminders(content: str) -> List[str]:
    pattern = r'<system-reminder>(.*?)</system-reminder>'
    matches = re.findall(pattern, content, re.DOTALL)
    return [m.strip() for m in matches]

# Remove system-reminder tags from content string
def strip_system_reminders(content: str) -> str:
    return re.sub(SYSTEM_REMINDER_PATTERN, '', content, flags=re.DOTALL).strip()

# Filter out excluded tools
def filter_excluded_tools(tool_calls: List[dict]) -> List[dict]:
    return [call for call in tool_calls if call['tool_name'] not in EXCLUDED_TOOLS]

# Sort tool calls by timestamp
def sort_by_timestamp(tool_calls: List[dict]) -> List[dict]:
    return sorted(tool_calls, key=lambda x: x.get('timestamp', ''))

# Extract non-text media from user messages (images, documents)
def extract_user_media(messages: List[dict]) -> List[dict]:
    media_items = []

    for message in messages:
        if message.get('type') != 'user':
            continue

        timestamp = message.get('timestamp', '')
        content = message.get('message', {}).get('content', [])

        if not isinstance(content, list):
            continue

        for block in content:
            block_type = block.get('type')
            if block_type in ('image', 'document'):
                source = block.get('source', {})
                media_type = source.get('media_type', 'unknown')
                media_items.append({
                    'type': block_type,
                    'media_type': media_type,
                    'timestamp': timestamp
                })

    return media_items

# Extract user prompts from external user messages
def extract_user_prompts(messages: List[dict]) -> List[dict]:
    prompts = []

    for message in messages:
        if message.get('type') != 'user':
            continue
        if message.get('userType') != 'external':
            continue

        timestamp = message.get('timestamp', '')
        content = message.get('message', {}).get('content', '')

        if isinstance(content, list):
            has_tool_result = any(
                isinstance(b, dict) and b.get('type') == 'tool_result'
                for b in content
            )
            if has_tool_result:
                continue
            text_parts = [
                b.get('text', '') for b in content
                if isinstance(b, dict) and b.get('type') == 'text'
            ]
            text = '\n'.join(text_parts)
        elif isinstance(content, str):
            text = content
        else:
            continue

        stripped = text.strip()
        if not stripped:
            continue
        if stripped.startswith('<command-message>') or stripped.startswith('<command-name>'):
            continue
        if stripped.startswith('Base directory for this skill:'):
            continue

        prompts.append({
            'timestamp': timestamp,
            'text': text
        })

    return prompts

# Extract thinking blocks from assistant messages
def extract_thinking_blocks(messages: List[dict]) -> List[dict]:
    thinking_items = []

    for message in messages:
        if message.get('type') != 'assistant':
            continue

        timestamp = message.get('timestamp', '')
        content = message.get('message', {}).get('content', [])

        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'thinking':
                thinking_text = block.get('thinking', '')
                if thinking_text:
                    thinking_items.append({
                        'thinking': thinking_text,
                        'timestamp': timestamp
                    })

    return thinking_items

# Extract skill/command activations from user messages
# JSONL structure: Tags-Message (command-name) followed by Content-Message (isMeta=true)
# Tags-Message has the name, Content-Message has the full skill/command body
def extract_skill_activations(messages: List[dict]) -> List[dict]:
    activations = []
    pending_skill_name = ''

    for message in messages:
        if message.get('type') != 'user':
            continue

        timestamp = message.get('timestamp', '')
        content = message.get('message', {}).get('content', '')

        if isinstance(content, list):
            text_parts = [
                b.get('text', '') for b in content
                if isinstance(b, dict) and b.get('type') == 'text'
            ]
            text = '\n'.join(text_parts)
        elif isinstance(content, str):
            text = content
        else:
            continue

        stripped = text.strip()

        # Tags-Message: extract skill/command name, wait for Content-Message
        if stripped.startswith('<command-message>') or stripped.startswith('<command-name>'):
            name_match = re.search(r'<command-name>/?(.*?)</command-name>', text)
            if name_match:
                pending_skill_name = name_match.group(1)
            continue

        # Content-Message: isMeta=true following a Tags-Message
        if message.get('isMeta') and pending_skill_name:
            activations.append({
                'skill_name': pending_skill_name,
                'content': text,
                'timestamp': timestamp
            })
            pending_skill_name = ''

    return activations

# Extract output token usage data from assistant messages with content block type breakdown
def extract_usage_data(messages: List[dict]) -> List[dict]:
    usage_items = []

    for message in messages:
        if message.get('type') != 'assistant':
            continue

        usage = message.get('message', {}).get('usage', {})
        output_tokens = usage.get('output_tokens', 0)
        input_tokens = usage.get('input_tokens', 0)
        cache_creation_input_tokens = usage.get('cache_creation_input_tokens', 0)
        cache_read_input_tokens = usage.get('cache_read_input_tokens', 0)

        if output_tokens == 0 and input_tokens == 0:
            continue

        request_id = message.get('requestId', '')
        content_blocks = message.get('message', {}).get('content', [])

        block_type = 'text'
        tool_name = None

        if isinstance(content_blocks, list):
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                bt = block.get('type', '')
                if bt == 'thinking':
                    block_type = 'thinking'
                    break
                elif bt == 'tool_use':
                    block_type = 'tool_use'
                    tool_name = block.get('name', 'Unknown')
                    break

        usage_items.append({
            'type': block_type,
            'tool_name': tool_name,
            'output_tokens': output_tokens,
            'input_tokens': input_tokens,
            'cache_creation_input_tokens': cache_creation_input_tokens,
            'cache_read_input_tokens': cache_read_input_tokens,
            'request_id': request_id,
        })

    return usage_items

# Extract per-turn cache tracking data grouped by user prompts
def extract_cache_turns(messages: list) -> list:
    turns = []
    current_turn = None

    for message in messages:
        msg_type = message.get('type')

        if msg_type == 'user' and message.get('userType') == 'external':
            content = message.get('message', {}).get('content', '')
            has_tool_result = False
            text = ''
            if isinstance(content, list):
                has_tool_result = any(
                    isinstance(b, dict) and b.get('type') == 'tool_result'
                    for b in content
                )
                text_parts = [
                    b.get('text', '') for b in content
                    if isinstance(b, dict) and b.get('type') == 'text'
                ]
                text = '\n'.join(text_parts)
            elif isinstance(content, str):
                text = content

            stripped = text.strip()
            if not has_tool_result and stripped:
                if stripped.startswith('<command-message>') or stripped.startswith('<command-name>'):
                    m = re.search(r'<command-name>([^<]+)</command-name>', stripped)
                    skill_name = m.group(1) if m else 'unknown'
                    current_turn = {
                        'prompt': f'\u25cf skill:{skill_name}',
                        'timestamp': message.get('timestamp', ''),
                        'api_calls': [],
                    }
                    turns.append(current_turn)
                    continue
                if stripped.startswith('Base directory for this skill:'):
                    continue
                if current_turn and current_turn.get('timestamp') == message.get('timestamp', ''):
                    continue
                current_turn = {
                    'prompt': stripped,
                    'timestamp': message.get('timestamp', ''),
                    'api_calls': [],
                }
                turns.append(current_turn)
            continue

        if msg_type == 'assistant' and current_turn is not None:
            usage = message.get('message', {}).get('usage', {})
            cache_read = usage.get('cache_read_input_tokens', 0)
            cache_creation = usage.get('cache_creation_input_tokens', 0)
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)

            if cache_read == 0 and cache_creation == 0 and input_tokens == 0:
                continue

            content_blocks = message.get('message', {}).get('content', [])
            blocks = []
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get('type', '')
                    if bt == 'thinking':
                        blocks.append({'type': 'thinking'})
                    elif bt == 'tool_use':
                        input_data = block.get('input', {})
                        blocks.append({'type': 'tool_use', 'tool_name': block.get('name', 'Unknown'), 'preview': input_data})
                    elif bt == 'text':
                        blocks.append({'type': 'text', 'preview': block.get('text', '')[:30]})

            current_turn['api_calls'].append({
                'cache_read': cache_read,
                'cache_creation': cache_creation,
                'direct': input_tokens,
                'output_tokens': output_tokens,
                'content_blocks': blocks,
            })

    return turns

# Detect unknown message types not in KNOWN or KNOWN_IGNORED sets
def detect_unknown_types(messages: List[dict]) -> List[dict]:
    all_known = KNOWN_MESSAGE_TYPES | KNOWN_IGNORED_TYPES
    unknown = {}

    for message in messages:
        msg_type = message.get('type', '')
        if msg_type and msg_type not in all_known:
            if msg_type not in unknown:
                unknown[msg_type] = {'type': msg_type, 'count': 0, 'example': str(message)[:200]}
            unknown[msg_type]['count'] += 1

    return list(unknown.values())
