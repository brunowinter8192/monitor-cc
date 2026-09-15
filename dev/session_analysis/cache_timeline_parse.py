# INFRASTRUCTURE
import json
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# FUNCTIONS

def encode_project_path(path):
    return path.replace('/', '-').replace('_', '-')

def find_project_sessions(project_path, include_workers=False):
    encoded = encode_project_path(project_path)
    if include_workers:
        sessions = []
        if PROJECTS_DIR.exists():
            for d in PROJECTS_DIR.iterdir():
                if d.is_dir() and d.name.startswith(encoded):
                    sessions.extend(d.glob('*.jsonl'))
    else:
        project_dir = PROJECTS_DIR / encoded
        if not project_dir.exists():
            print(f'Error: Project directory not found: {project_dir}', file=sys.stderr)
            sys.exit(1)
        sessions = list(project_dir.glob('*.jsonl'))
    return sorted(sessions, key=lambda f: f.stat().st_mtime, reverse=True)

def parse_session_turns(filepath):
    turns = []
    last_user_timestamp = None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get('type') == 'user':
                    ts = message.get('timestamp', '')
                    if ts and ts == last_user_timestamp:
                        continue
                    last_user_timestamp = ts
                turn = extract_turn(message)
                if turn:
                    turns.append(turn)
    except OSError as e:
        print(f'Warning: Could not read {filepath}: {e}', file=sys.stderr)
    return turns

def extract_turn(message):
    if message.get('type') != 'assistant':
        return None
    msg = message.get('message', {})
    usage = msg.get('usage', {})
    input_tokens = usage.get('input_tokens', 0)
    cache_creation = usage.get('cache_creation_input_tokens', 0)
    cache_read = usage.get('cache_read_input_tokens', 0)
    output_tokens = usage.get('output_tokens', 0)
    if input_tokens == 0 and cache_creation == 0 and output_tokens == 0:
        return None
    cc_obj = usage.get('cache_creation') or {}
    ephemeral_1h = cc_obj.get('ephemeral_1h_input_tokens', 0)
    ephemeral_5m = cc_obj.get('ephemeral_5m_input_tokens', 0)
    content = msg.get('content', [])
    block_type, tool_name = classify_content(content)
    return {
        'timestamp': message.get('timestamp', ''),
        'input_tokens': input_tokens,
        'cache_creation': cache_creation,
        'cache_read': cache_read,
        'output_tokens': output_tokens,
        'ephemeral_1h': ephemeral_1h,
        'ephemeral_5m': ephemeral_5m,
        'block_type': block_type,
        'tool_name': tool_name,
    }

def classify_content(content):
    if not isinstance(content, list):
        return 'text', None
    for block in content:
        if not isinstance(block, dict):
            continue
        bt = block.get('type', '')
        if bt == 'thinking':
            return 'thinking', None
        elif bt == 'tool_use':
            return 'tool_use', block.get('name', 'Unknown')
    return 'text', None

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
