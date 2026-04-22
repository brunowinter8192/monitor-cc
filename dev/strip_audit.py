# INFRASTRUCTURE
import argparse
import glob
import json
import os
import sys

TAGS = ['<system-reminder>', '<persisted-output>', '<task-notification>', '<new-diagnostics>', 'SYSTEM NOTIFICATION']
FILE_TOOLS = {'Read', 'Grep', 'Bash', 'Glob'}
TRUNC = 100

# ORCHESTRATOR

def main():
    ap = argparse.ArgumentParser(description='Delta-based strip analysis for proxy JSONL logs.')
    ap.add_argument('path', nargs='?', help='Path to proxy JSONL file (default: newest opus log)')
    args = ap.parse_args()
    path = args.path or find_newest_log()
    if not path:
        print('No log file found. Pass a path or run from the project root.', file=sys.stderr)
        sys.exit(1)
    entries = load_entries(path)
    print(f'Loaded {len(entries)} entries from {path}\n')
    analyze(entries)

# FUNCTIONS

# Locate newest api_requests_opus_monitor_cc_*.jsonl by walking up from this file
def find_newest_log():
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = here
    for _ in range(6):
        candidate = os.path.dirname(candidate)
        logs_dir = os.path.join(candidate, 'src', 'logs')
        if os.path.isdir(logs_dir):
            matches = glob.glob(os.path.join(logs_dir, 'api_requests_opus_monitor_cc_*.jsonl'))
            if matches:
                return max(matches, key=os.path.getmtime)
    return None

# Parse JSONL, skipping sent_meta and schema_warning entries
def load_entries(path):
    entries = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get('type') in ('sent_meta', 'schema_warning'):
                    continue
                entries.append(d)
            except json.JSONDecodeError:
                pass
    return entries

# Flatten all text in a raw message to a single string for tag scanning
def raw_text(raw_msg):
    content = raw_msg.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if not isinstance(blk, dict):
                continue
            if blk.get('type') == 'text':
                parts.append(blk.get('text', ''))
            elif blk.get('type') == 'tool_result':
                tc = blk.get('content', '')
                if isinstance(tc, str):
                    parts.append(tc)
                elif isinstance(tc, list):
                    for sub in tc:
                        if isinstance(sub, dict):
                            parts.append(sub.get('text', ''))
        return '\n'.join(parts)
    return ''

# Scan backward through raw_msgs for a tool_use block matching the given id
def find_tool_name(raw_msgs, tool_use_id):
    for msg in reversed(raw_msgs):
        content = msg.get('content', [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if isinstance(blk, dict) and blk.get('type') == 'tool_use' and blk.get('id') == tool_use_id:
                return blk.get('name', '')
    return ''

# Build [STRIPPED] suffix with first removed chunk truncated to TRUNC chars
def fmt_removed(removed_map, msg_idx):
    chunks = removed_map.get(str(msg_idx), [])
    if not chunks or not chunks[0]:
        return '  [STRIPPED]'
    snippet = chunks[0][:TRUNC].replace('\n', ' ')
    return f"  [STRIPPED]  removed: '{snippet}' ({TRUNC}c truncated)"

# Walk entries chronologically, print delta analysis per request
def analyze(entries):
    prev = None
    for req_num, entry in enumerate(entries, 1):
        messages = entry.get('messages', [])
        prev_count = prev.get('message_count', len(prev.get('messages', []))) if prev else 0
        cur_count = entry.get('message_count', len(messages))
        delta = cur_count - prev_count

        if delta <= 0:
            prev = entry
            continue

        ts_raw = entry.get('timestamp', '')
        ts = ts_raw[11:19] if len(ts_raw) >= 19 else ts_raw
        mods = ', '.join(entry.get('modifications', []))
        print(f"REQ #{req_num}  [{ts}]  msgs: {prev_count}→{cur_count} (+{delta})  mods: {mods}")

        stripped_indices = set(entry.get('stripped_msg_indices', []))
        removed_map = entry.get('stripped_msg_removed') or {}
        raw_msgs = entry.get('raw_payload', {}).get('messages', [])

        for msg_idx in range(prev_count, cur_count):
            if msg_idx >= len(messages):
                continue
            msg = messages[msg_idx]
            role = msg.get('role', '?')[:4]
            msg_type = msg.get('type', 'text')
            chars = msg.get('chars', 0)

            # Resolve tool name for tool_result messages
            tool_name = ''
            if msg_type == 'tool_result' and msg_idx < len(raw_msgs):
                content = raw_msgs[msg_idx].get('content', [])
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get('type') == 'tool_result':
                            tid = blk.get('tool_use_id', '')
                            if tid:
                                tool_name = find_tool_name(raw_msgs, tid)
                            break

            tool_str = f'  {tool_name}' if tool_name else ''
            is_stripped = msg_idx in stripped_indices
            stripped_str = fmt_removed(removed_map, msg_idx) if is_stripped else ''

            # Tag leak scan
            leaked = []
            if msg_idx < len(raw_msgs):
                text = raw_text(raw_msgs[msg_idx])
                leaked = [t for t in TAGS if t in text]
            leaked_str = '  LEAKED: ' + ', '.join(leaked) if leaked else ''

            print(f"  NEW msg[{msg_idx}] {role:<4} {msg_type:<14}{tool_str}  {chars:,}c{stripped_str}{leaked_str}")

            if is_stripped and tool_name in FILE_TOOLS:
                print(f"    \u26a0 SUSPECT FALSE POSITIVE: {tool_name} tool_result stripped — content may be source code containing SR tags")

        prev = entry

if __name__ == '__main__':
    main()
