# INFRASTRUCTURE
import re

# FUNCTIONS

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
            blocks = []
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get('type', '')
                    if bt == 'thinking':
                        think_chars = len(block.get('thinking', ''))
                        blocks.append({'type': 'thinking', 'output_tokens': output_tokens, 'chars': think_chars})
                    elif bt == 'tool_use':
                        input_data = block.get('input', {})
                        blocks.append({'type': 'tool_use', 'tool_name': block.get('name', 'Unknown'), 'preview': input_data})
                    elif bt == 'text':
                        blocks.append({'type': 'text', 'preview': block.get('text', '')})

            request_id = message.get('requestId', '')
            input_key = request_id if request_id else (cache_read, cache_creation, input_tokens)
            existing_calls = current_turn['api_calls']
            if existing_calls and existing_calls[-1].get('_input_key') == input_key:
                prev = existing_calls[-1]
                prev['output_tokens'] = max(prev['output_tokens'], output_tokens)
                seen_types = set()
                for b in prev['content_blocks']:
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
                        prev['content_blocks'].append(b)
                        seen_types.add(sig)
                        if b['type'] == 'thinking':
                            current_turn['thinking_chars'] = current_turn.get('thinking_chars', 0) + b.get('chars', 0)
            else:
                current_turn['api_calls'].append({
                    'cache_read': cache_read,
                    'cache_creation': cache_creation,
                    'direct': input_tokens,
                    'output_tokens': output_tokens,
                    'content_blocks': blocks,
                    'request_id': request_id,
                    '_input_key': input_key,
                })
                current_turn['thinking_chars'] = current_turn.get('thinking_chars', 0) + sum(b.get('chars', 0) for b in blocks if b['type'] == 'thinking')

    for turn in turns:
        for call in turn.get('api_calls', []):
            call.pop('_input_key', None)

    return turns
