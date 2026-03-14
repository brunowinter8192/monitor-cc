# INFRASTRUCTURE
import json
import logging
import re
from pathlib import Path
from typing import List, Tuple, Optional

# From utils.py: ANSI colors and logging utility
from .utils import RESET, RED, GREEN, YELLOW, BLUE, WHITE, log_tagged
# From constants.py: Shared constants
from .constants import EXCLUDED_TOOLS, SYSTEM_REMINDER_PATTERN

# Setup 3 loggers for different workflow phases
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_file = logging.getLogger('jsonl_parser.file')
file_handler = logging.FileHandler('src/logs/04_file_reading.log')
file_handler.setFormatter(log_format)
logger_file.addHandler(file_handler)
logger_file.setLevel(logging.INFO)

logger_parse = logging.getLogger('jsonl_parser.parse')
parse_handler = logging.FileHandler('src/logs/05_jsonl_parsing.log')
parse_handler.setFormatter(log_format)
logger_parse.addHandler(parse_handler)
logger_parse.setLevel(logging.INFO)

logger_extract = logging.getLogger('jsonl_parser.extract')
extract_handler = logging.FileHandler('src/logs/06_tool_extraction.log')
extract_handler.setFormatter(log_format)
logger_extract.addHandler(extract_handler)
logger_extract.setLevel(logging.INFO)

# ORCHESTRATOR
def parse_new_tool_calls(filepath: Path, last_position: int, tool_use_cache: dict) -> Tuple[List[dict], int, List[dict], List[dict], List[dict], List[dict]]:
    new_lines = read_new_lines(filepath, last_position)

    if len(new_lines) > 0:
        log_tagged(logger_parse, "LINES_READ", BLUE, f"Read {len(new_lines)} new lines from {filepath.name}")

    new_position = get_current_position(filepath)
    messages, malformed_lines = parse_jsonl_lines(new_lines)
    tool_calls = extract_tool_calls(messages, tool_use_cache)
    user_prompts = extract_user_prompts(messages)
    user_media = extract_user_media(messages)
    thinking_blocks = extract_thinking_blocks(messages)
    malformed_warnings = build_malformed_warnings(filepath, malformed_lines)

    if len(tool_calls) > 0 or len(malformed_warnings) > 0 or len(user_media) > 0 or len(thinking_blocks) > 0 or len(user_prompts) > 0:
        log_tagged(logger_parse, "PARSE_DONE", GREEN, f"Parsed {len(tool_calls)} tool calls, {len(user_prompts)} user prompts, {len(user_media)} user media, {len(thinking_blocks)} thinking, {len(malformed_warnings)} malformed lines")

    return tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts

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
        log_tagged(logger_file, "FILE_404", RED, f"File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        f.seek(last_position)
        content = f.read()
        bytes_read = len(content)

        if not content:
            return []

        lines = content.split('\n')
        if lines and not lines[-1]:
            lines = lines[:-1]

        if len(lines) > 0:
            log_tagged(logger_file, "FILE_READ", BLUE, f"{filepath.name}: read {bytes_read} bytes, {len(lines)} lines")

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
            log_tagged(logger_parse, "JSON_ERROR", RED, f"JSON decode error at line {line_number}: {str(e)}")
            malformed_lines.append({
                'line_number': line_number,
                'error_message': str(e),
                'raw_line': line
            })

    if len(lines) > 0:
        malformed_pct = (len(malformed_lines) / len(lines)) * 100
        log_tagged(logger_parse, "PARSE_STATS", WHITE, f"parse_jsonl_lines: valid={len(messages)}, malformed={len(malformed_lines)} ({malformed_pct:.1f}%)")

    return messages, malformed_lines

# Extract tool_use and tool_result pairs from messages
def extract_tool_calls(messages: List[dict], tool_use_cache: dict) -> List[dict]:
    if len(messages) > 0:
        log_tagged(logger_extract, "EXTRACT_START", BLUE, f"extract_tool_calls: messages={len(messages)}, cache={len(tool_use_cache)}")

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
                log_tagged(logger_extract, "TOOL_CACHED", WHITE, f"Cached tool_use: id={tool_data['tool_use_id']}, tool={tool_data['tool_name']}, subagent={is_subagent}")

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
                    log_tagged(logger_extract, "TOOL_MATCH", GREEN, f"Matched tool_result: id={tool_use_id}, tool={tool_data['tool_name']}, is_error={tool_data['is_error']}")
                    del tool_use_cache[tool_use_id]
                else:
                    orphaned_results += 1
                    log_tagged(logger_extract, "TOOL_ORPHAN", YELLOW, f"Orphaned tool_result: id={tool_use_id} (no matching tool_use in cache)")

    if len(tool_calls) > 0 or orphaned_results > 0 or progress_count > 0:
        log_tagged(logger_extract, "EXTRACT_STATS", WHITE, f"extract_tool_calls: blocks={total_blocks}, tool_use={tool_use_count}, tool_result={tool_result_count}, orphaned={orphaned_results}, progress={progress_count}, extracted={len(tool_calls)}")

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
        'agent_id': agent_id or message.get('agentId', None),
        'usage': message.get('message', {}).get('usage')
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

    if len(media_items) > 0:
        log_tagged(logger_extract, "USER_MEDIA", GREEN, f"Extracted {len(media_items)} media items from user messages")

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

    if len(prompts) > 0:
        log_tagged(logger_extract, "USER_PROMPTS", GREEN, f"Extracted {len(prompts)} user prompts")

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

    if len(thinking_items) > 0:
        log_tagged(logger_extract, "THINKING", GREEN, f"Extracted {len(thinking_items)} thinking blocks")

    return thinking_items
