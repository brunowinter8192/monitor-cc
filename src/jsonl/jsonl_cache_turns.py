# INFRASTRUCTURE
import re

# FUNCTIONS

# Parse user message content; returns (has_tool_result, text).
def _parse_user_message_text(message: dict) -> tuple:
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
    return has_tool_result, text

# Convert raw CC content blocks to simplified block dicts; output_tokens threaded into thinking blocks.
def _extract_content_blocks(content_blocks: list, output_tokens: int) -> list:
    blocks = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        bt = block.get('type', '')
        if bt == 'thinking':
            think_chars = len(block.get('thinking', ''))
            sig_chars = len(block.get('signature', ''))
            blocks.append({'type': 'thinking', 'output_tokens': output_tokens, 'chars': think_chars, 'sig_chars': sig_chars})
        elif bt == 'tool_use':
            input_data = block.get('input', {})
            blocks.append({'type': 'tool_use', 'tool_name': block.get('name', 'Unknown'), 'preview': input_data})
        elif bt == 'text':
            blocks.append({'type': 'text', 'preview': block.get('text', '')})
    return blocks

# Build a new API call dict from usage data + content blocks. _input_key set by caller.
def _build_api_call(usage: dict, blocks: list, request_id: str) -> dict:
    return {
        'cache_read':        usage.get('cache_read_input_tokens', 0),
        'cache_creation':    usage.get('cache_creation_input_tokens', 0),
        'direct':            usage.get('input_tokens', 0),
        'output_tokens':     usage.get('output_tokens', 0),
        'content_blocks':    blocks,
        'request_id':        request_id,
        'cache_creation_ttl': usage.get('cache_creation') or {},
        'server_tool_use':   usage.get('server_tool_use') or {},
        'service_tier':      usage.get('service_tier', ''),
        'speed':             usage.get('speed', ''),
        'inference_geo':     usage.get('inference_geo', ''),
        'iterations':        usage.get('iterations') or [],
    }

# Merge new blocks into prev_call (dedup path); updates prev_call output_tokens and current_turn thinking counters.
def _merge_duplicate_call(prev_call: dict, blocks: list, current_turn: dict, output_tokens: int) -> None:
    prev_call['output_tokens'] = max(prev_call['output_tokens'], output_tokens)
    seen_types = set()
    for b in prev_call['content_blocks']:
        if b['type'] == 'tool_use':
            seen_types.add(('tool_use', b.get('tool_name', '')))
        elif b['type'] == 'thinking':
            seen_types.add(('thinking',))
        elif b['type'] == 'text':
            seen_types.add(('text', b.get('preview', '')))
    for b in blocks:
        if b['type'] == 'tool_use':
            sig = ('tool_use', b.get('tool_name', ''))
        elif b['type'] == 'thinking':
            sig = ('thinking',)
        else:
            sig = ('text', b.get('preview', ''))
        if sig not in seen_types:
            prev_call['content_blocks'].append(b)
            seen_types.add(sig)
            if b['type'] == 'thinking':
                current_turn['thinking_chars'] = current_turn.get('thinking_chars', 0) + b.get('chars', 0)
                current_turn['thinking_sig_chars'] = current_turn.get('thinking_sig_chars', 0) + b.get('sig_chars', 0)

# Extract per-turn cache tracking data grouped by user prompts
def extract_cache_turns(messages: list) -> list:
    turns = []
    current_turn = None

    for message in messages:
        msg_type = message.get('type')

        if msg_type == 'user' and message.get('userType') == 'external':
            has_tool_result, text = _parse_user_message_text(message)
            stripped = text.strip()
            if not has_tool_result and stripped:
                if stripped.startswith('<command-message>') or stripped.startswith('<command-name>'):
                    m = re.search(r'<command-name>([^<]+)</command-name>', stripped)
                    skill_name = m.group(1) if m else 'unknown'
                    current_turn = {
                        'prompt': f'● skill:{skill_name}',
                        'timestamp': message.get('timestamp', ''),
                        'api_calls': [],
                        'thinking_chars': 0,
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
                    'thinking_chars': 0,
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
            blocks = _extract_content_blocks(
                content_blocks if isinstance(content_blocks, list) else [],
                output_tokens,
            )
            request_id = message.get('requestId', '')
            input_key = request_id if request_id else (cache_read, cache_creation, input_tokens)
            existing_calls = current_turn['api_calls']
            if existing_calls and existing_calls[-1].get('_input_key') == input_key:
                _merge_duplicate_call(existing_calls[-1], blocks, current_turn, output_tokens)
            else:
                new_call = _build_api_call(usage, blocks, request_id)
                new_call['_input_key'] = input_key
                existing_calls.append(new_call)
                current_turn['thinking_chars'] = current_turn.get('thinking_chars', 0) + sum(b.get('chars', 0) for b in blocks if b['type'] == 'thinking')
                current_turn['thinking_sig_chars'] = current_turn.get('thinking_sig_chars', 0) + sum(b.get('sig_chars', 0) for b in blocks if b['type'] == 'thinking')

    for turn in turns:
        for call in turn.get('api_calls', []):
            call.pop('_input_key', None)

    return turns
