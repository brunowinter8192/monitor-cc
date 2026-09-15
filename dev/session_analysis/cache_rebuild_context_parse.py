# INFRASTRUCTURE
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# FUNCTIONS

def find_all_sessions():
    if not PROJECTS_DIR.exists():
        return []
    sessions = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            sessions.extend(project_dir.glob('*.jsonl'))
    return sorted(sessions, key=lambda f: f.stat().st_mtime, reverse=True)

def parse_all_messages(filepath):
    messages = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = extract_message(raw)
                if msg:
                    messages.append(msg)
    except OSError as e:
        print(f'Warning: Could not read {filepath}: {e}', file=sys.stderr)
    return messages

def extract_message(raw):
    msg_type = raw.get('type', '')
    if not msg_type:
        return None
    result = {
        'type': msg_type,
        'timestamp': raw.get('timestamp', ''),
        'cache_read': 0,
        'cache_creation': 0,
        'label': '',
        'raw': raw,
    }
    if msg_type == 'assistant':
        msg = raw.get('message', {})
        usage = msg.get('usage', {})
        result['cache_read'] = usage.get('cache_read_input_tokens', 0)
        result['cache_creation'] = usage.get('cache_creation_input_tokens', 0)
        result['input_tokens'] = usage.get('input_tokens', 0)
        result['label'] = classify_assistant_content(msg.get('content', []))
    elif msg_type == 'user':
        result['label'] = classify_user_message(raw)
    elif msg_type == 'system':
        subtype = raw.get('subtype', '')
        result['label'] = subtype if subtype else 'system'
    elif msg_type == 'progress':
        data = raw.get('data', {})
        agent_id = data.get('agentId', '')
        result['label'] = f'progress agent:{agent_id}' if agent_id else 'progress'
    else:
        result['label'] = msg_type
    return result

def classify_assistant_content(content):
    if not isinstance(content, list):
        return 'text'
    for block in content:
        if not isinstance(block, dict):
            continue
        bt = block.get('type', '')
        if bt == 'thinking':
            return 'thinking'
        if bt == 'tool_use':
            name = block.get('name', 'Unknown')
            if '__' in name:
                name = name.split('__')[-1]
            return f'tool_use: {name}'
    return 'text'

def classify_user_message(raw):
    msg = raw.get('message', {})
    content = msg.get('content', []) if isinstance(msg, dict) else []
    if not content:
        content = raw.get('content', [])
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content):
            return 'tool_result'
        for block in content:
            text = block.get('text', '') if isinstance(block, dict) else str(block)
            tag = classify_text_by_tags(text)
            if tag:
                return tag
        first_text = next(
            (b.get('text', '') if isinstance(b, dict) else str(b) for b in content if b),
            ''
        )
        return f'text: {first_text[:60]}'
    if isinstance(content, str):
        tag = classify_text_by_tags(content)
        return tag if tag else f'text: {content[:60]}'
    return 'text'

def classify_text_by_tags(text):
    if not text:
        return None
    if '<task-notification>' in text or '<task-id>' in text:
        return 'task-notification'
    if '<command-message>' in text or '<command-name>' in text:
        return 'skill-activation'
    if '<system-reminder>' in text:
        return 'system-reminder'
    return None

def parse_timestamp(ts):
    if not ts:
        return None
    try:
        ts_clean = re.sub(r'\.\d+', '', ts)
        ts_clean = re.sub(r'[+-]\d{2}:\d{2}$', '', ts_clean)
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None

def format_time(ts):
    if not ts:
        return '??:??:??'
    m = re.search(r'T(\d{2}:\d{2}:\d{2})', ts)
    return m.group(1) if m else '??:??:??'

def format_gap(seconds):
    if seconds < 60:
        return f'{int(seconds)}s'
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f'{minutes}m{secs}s'
