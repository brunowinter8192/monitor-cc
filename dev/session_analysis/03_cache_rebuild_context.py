#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECTS_DIR = Path.home() / '.claude' / 'projects'
DEFAULT_CONTEXT = 5
REBUILD_THRESHOLD = 0.2
TIME_GAP_THRESHOLD_SECONDS = 300

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.all:
        output = run_all(args.context)
    elif args.session:
        output = run_session(Path(args.session), args.context, args.summary_only)
    else:
        print('Error: --session or --all required', file=sys.stderr)
        sys.exit(1)
    print(output)

def run_session(session_path, context_window, summary_only):
    messages = parse_all_messages(session_path)
    rebuilds = detect_rebuilds(messages)
    lines = [f'# Cache Rebuild Context — {session_path.name}\n']
    if not rebuilds:
        lines.append('_No cache rebuilds detected._')
        return '\n'.join(lines)
    if not summary_only:
        for i, rebuild in enumerate(rebuilds, 1):
            lines.append(format_rebuild_block(rebuild, messages, i, context_window))
            lines.append('')
    lines.append(format_pattern_summary(rebuilds))
    return '\n'.join(lines)

def run_all(context_window):
    sessions = find_all_sessions()
    lines = ['# Cache Rebuild Context — All Projects\n']
    all_rebuilds = []
    session_rows = []
    for session_path in sessions:
        messages = parse_all_messages(session_path)
        rebuilds = detect_rebuilds(messages)
        if rebuilds:
            all_rebuilds.extend(rebuilds)
            session_rows.append((session_path, len(rebuilds)))
    lines.append(format_session_rebuild_table(session_rows))
    lines.append('')
    lines.append(format_pattern_summary(all_rebuilds))
    return '\n'.join(lines)

# FUNCTIONS

# Parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Analyze cache rebuilds in Claude Code sessions')
    parser.add_argument('--session', help='Path to session JSONL file')
    parser.add_argument('--context', type=int, default=DEFAULT_CONTEXT,
                        help=f'Messages before/after rebuild (default: {DEFAULT_CONTEXT})')
    parser.add_argument('--summary-only', action='store_true', dest='summary_only',
                        help='Show only pattern summary, no context blocks')
    parser.add_argument('--all', action='store_true',
                        help='Scan all session JSONLs across all projects')
    return parser.parse_args()

# Find all main session JSONL files across all projects
def find_all_sessions():
    if not PROJECTS_DIR.exists():
        return []
    sessions = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            sessions.extend(project_dir.glob('*.jsonl'))
    return sorted(sessions, key=lambda f: f.stat().st_mtime, reverse=True)

# Parse all messages from a JSONL session file into normalized dicts
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

# Extract normalized message dict from raw JSONL entry
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

# Classify assistant message content into display label
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

# Classify user message into display label
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

# Return known tag category from text, or None
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

# Parse ISO timestamp string to datetime object
def parse_timestamp(ts):
    if not ts:
        return None
    try:
        ts_clean = re.sub(r'\.\d+', '', ts)
        ts_clean = re.sub(r'[+-]\d{2}:\d{2}$', '', ts_clean)
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None

# Extract HH:MM:SS from ISO timestamp string
def format_time(ts):
    if not ts:
        return '??:??:??'
    m = re.search(r'T(\d{2}:\d{2}:\d{2})', ts)
    return m.group(1) if m else '??:??:??'

# Format seconds as human-readable gap string
def format_gap(seconds):
    if seconds < 60:
        return f'{int(seconds)}s'
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f'{minutes}m{secs}s'

# Map a message label to a categorical pattern bucket for the summary table
def preceding_event_category(msg, gap_seconds):
    if gap_seconds is not None and gap_seconds > TIME_GAP_THRESHOLD_SECONDS:
        return 'time gap >5min'
    label = msg['label']
    if label in ('task-notification', 'skill-activation', 'system-reminder', 'tool_result'):
        return label
    if msg['type'] == 'user' and label.startswith('text:'):
        return 'user prompt (text)'
    if msg['type'] == 'assistant':
        return f'assistant ({label})'
    return label

# Detect cache rebuilds across all messages, return list of rebuild dicts
def detect_rebuilds(messages):
    rebuilds = []
    prev_max_cr = 0
    first_assistant = True

    for i, msg in enumerate(messages):
        if msg['type'] != 'assistant':
            continue
        cr = msg['cache_read']
        cc = msg['cache_creation']

        if first_assistant:
            first_assistant = False
            prev_max_cr = max(prev_max_cr, cr)
            continue

        if prev_max_cr > 0 and cc > cr and cr < prev_max_cr * REBUILD_THRESHOLD:
            gap_seconds = compute_gap_from_prev_assistant(messages, i)
            preceding_label, preceding_category = compute_preceding_event(messages, i, gap_seconds)
            rebuilds.append({
                'msg_index': i,
                'timestamp': msg['timestamp'],
                'cache_read': cr,
                'cache_creation': cc,
                'prev_max_cr': prev_max_cr,
                'gap_seconds': gap_seconds,
                'preceding_label': preceding_label,
                'preceding_category': preceding_category,
            })

        prev_max_cr = max(prev_max_cr, cr)

    return rebuilds

# Compute time gap in seconds from previous assistant message to index i
def compute_gap_from_prev_assistant(messages, i):
    rebuild_ts = messages[i]['timestamp']
    for j in range(i - 1, -1, -1):
        if messages[j]['type'] == 'assistant' and messages[j]['timestamp']:
            t_prev = parse_timestamp(messages[j]['timestamp'])
            t_curr = parse_timestamp(rebuild_ts)
            if t_prev and t_curr:
                return (t_curr - t_prev).total_seconds()
            break
    return None

# Return (display label, category) for the message immediately before rebuild index
def compute_preceding_event(messages, rebuild_idx, gap_seconds):
    if rebuild_idx == 0:
        return 'unknown', 'unknown'
    prev_msg = messages[rebuild_idx - 1]
    category = preceding_event_category(prev_msg, gap_seconds)
    return prev_msg['label'], category

# Format one rebuild context block with surrounding messages
def format_rebuild_block(rebuild, messages, rebuild_num, context_window):
    idx = rebuild['msg_index']
    time_str = format_time(rebuild['timestamp'])
    cr = rebuild['cache_read']
    cc = rebuild['cache_creation']
    prev_max = rebuild['prev_max_cr']
    gap = rebuild['gap_seconds']

    lines = [f'=== REBUILD #{rebuild_num} at {time_str} ===']
    lines.append(f'  CR: {cr:,}  CC: {cc:,}  (prev max CR was {prev_max:,})')
    if gap is not None:
        lines.append(f'  Gap from previous API call: {format_gap(gap)}')

    lines.append('')
    lines.append(f'  Context ({context_window} before → rebuild → {context_window} after):')

    start = max(0, idx - context_window)
    end = min(len(messages) - 1, idx + context_window)

    for j in range(start, end + 1):
        msg = messages[j]
        offset = j - idx
        ts = format_time(msg['timestamp'])

        if offset == 0:
            offset_str = '*0'
        elif offset > 0:
            offset_str = f'+{offset}'
        else:
            offset_str = str(offset)

        type_col = msg['type'][:10]
        suffix = '  ← REBUILD' if offset == 0 else ''

        if msg['type'] == 'assistant':
            mcr = msg['cache_read']
            mcc = msg['cache_creation']
            cache_part = f'CR: {mcr:,} CC: {mcc:,}'
            lines.append(f'  [{offset_str:>3}] [{ts}] {type_col:<10}  {cache_part}  {msg["label"]}{suffix}')
        else:
            lines.append(f'  [{offset_str:>3}] [{ts}] {type_col:<10}  {msg["label"]}{suffix}')

    return '\n'.join(lines)

# Format pattern summary table of preceding event categories
def format_pattern_summary(rebuilds):
    if not rebuilds:
        return '_No rebuilds to summarize._'
    counts = defaultdict(int)
    total = len(rebuilds)
    for r in rebuilds:
        counts[r['preceding_category']] += 1
    rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    w = max(len('Event before rebuild'), max(len(label) for label, _ in rows))
    lines = [f'\n## Preceding Event Patterns (event immediately before rebuild)']
    lines.append(f'| {"Event before rebuild":<{w}} | {"Count":>5} | {"Percentage":>10} |')
    lines.append(f'|{"-"*(w+2)}|{"-"*7}|{"-"*12}|')
    for label, count in rows:
        pct = int(count / total * 100)
        lines.append(f'| {label:<{w}} | {count:>5} | {pct:>9}% |')
    return '\n'.join(lines)

# Format per-session rebuild count table for --all mode
def format_session_rebuild_table(session_rows):
    if not session_rows:
        return '_No sessions with cache rebuilds found._'
    lines = [f'| {"Session":<52} | {"Rebuilds":>8} |']
    lines.append(f'|{"-"*54}|{"-"*10}|')
    for session_path, count in session_rows:
        name = session_path.name[:50]
        lines.append(f'| {name:<52} | {count:>8} |')
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
