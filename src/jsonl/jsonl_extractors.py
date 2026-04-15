# INFRASTRUCTURE
import re
from typing import List

from ..constants import KNOWN_MESSAGE_TYPES, KNOWN_IGNORED_TYPES

# FUNCTIONS

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
        prompts.append({'timestamp': timestamp, 'text': text})
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
                    thinking_items.append({'thinking': thinking_text, 'timestamp': timestamp})
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

# Extract system messages (type=system) and their text content
def extract_system_messages(messages: List[dict]) -> List[dict]:
    items = []
    for message in messages:
        if message.get('type') != 'system':
            continue
        timestamp = message.get('timestamp', '')
        content = message.get('content', '') or message.get('message', {}).get('content', '')
        if isinstance(content, list):
            text_parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
            text = '\n'.join(text_parts)
        elif isinstance(content, str):
            text = content
        else:
            continue
        text = text.strip()
        if text:
            items.append({'timestamp': timestamp, 'text': text})
    return items

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
