#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.session and args.tool:
        output = run_level4(Path(args.session), args.tool)
    elif args.session:
        output = run_level3(Path(args.session))
    elif args.project:
        output = run_level2(args.project)
    else:
        output = run_level1()
    print(output)

def run_level1():
    sessions = find_all_sessions()
    all_calls, session_summaries = collect_sessions(sessions)
    lines = ['# Session Analysis — All Projects\n']
    lines.append(format_aggregate_table(all_calls))
    lines.append('\n## Per-Session Breakdown\n')
    lines.append(format_session_breakdown(session_summaries))
    return '\n'.join(lines)

def run_level2(project_path):
    sessions = find_sessions_for_project(project_path)
    all_calls, session_summaries = collect_sessions(sessions)
    lines = [f'# Session Analysis — {project_path}\n']
    lines.append(format_aggregate_table(all_calls))
    lines.append('\n## Per-Session Breakdown\n')
    lines.append(format_session_breakdown(session_summaries))
    return '\n'.join(lines)

def run_level3(session_path):
    calls = parse_session(session_path)
    lines = [f'# Session Analysis — {session_path.name}\n']
    lines.append(format_aggregate_table(calls))
    return '\n'.join(lines)

def run_level4(session_path, tool_name):
    calls = parse_session(session_path)
    filtered = [c for c in calls if c['tool_name'] == tool_name]
    lines = [f'# Session Analysis — {session_path.name} — {tool_name}\n']
    for call in filtered:
        lines.append(format_detail_row(call))
    return '\n'.join(lines)

# FUNCTIONS

# Parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Analyze Claude Code session JSONL files')
    parser.add_argument('--project', help='Filter by project path (absolute)')
    parser.add_argument('--session', help='Path to session JSONL file')
    parser.add_argument('--tool', help='Filter by tool name (requires --session)')
    return parser.parse_args()

# Encode project path to match Claude directory naming
def encode_project_path(path):
    return path.replace('/', '-').replace('_', '-')

# Find all main session JSONL files across all projects
def find_all_sessions():
    if not PROJECTS_DIR.exists():
        return []
    sessions = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            sessions.extend(project_dir.glob('*.jsonl'))
    return sorted(sessions, key=lambda f: f.stat().st_mtime, reverse=True)

# Find main session JSONL files for a specific project path
def find_sessions_for_project(project_path):
    encoded = encode_project_path(project_path)
    project_dir = PROJECTS_DIR / encoded
    if not project_dir.exists():
        print(f'Error: Project directory not found: {project_dir}', file=sys.stderr)
        sys.exit(1)
    sessions = list(project_dir.glob('*.jsonl'))
    return sorted(sessions, key=lambda f: f.stat().st_mtime, reverse=True)

# Parse all sessions and return aggregated calls plus per-session summaries
def collect_sessions(sessions):
    all_calls = []
    session_summaries = []
    for session_path in sessions:
        calls = parse_session(session_path)
        all_calls.extend(calls)
        session_summaries.append((session_path, calls))
    return all_calls, session_summaries

# Parse one JSONL session file into list of completed tool call dicts
def parse_session(filepath):
    tool_use_cache = {}
    completed_calls = []
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
                process_message(message, tool_use_cache, completed_calls)
    except OSError as e:
        print(f'Warning: Could not read {filepath}: {e}', file=sys.stderr)
    return completed_calls

# Extract tool_use and tool_result blocks from one JSONL message
def process_message(message, tool_use_cache, completed_calls):
    msg_type = message.get('type')
    timestamp = message.get('timestamp', '')

    if msg_type == 'progress':
        data = message.get('data', {})
        if data.get('type') != 'agent_progress':
            return
        agent_id = data.get('agentId', '')
        inner = data.get('message', {}).get('message', {})
        content = inner.get('content', [])
        is_subagent = True
    else:
        msg = message.get('message', {})
        content = msg.get('content', []) if isinstance(msg, dict) else message.get('content', [])
        is_subagent = bool(message.get('isSidechain', False))
        agent_id = message.get('agentId', '')

    if not isinstance(content, list):
        return

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get('type')

        if block_type == 'tool_use':
            tool_use_id = block.get('id', '')
            tool_use_cache[tool_use_id] = {
                'tool_name': block.get('name', 'Unknown'),
                'input': block.get('input', {}),
                'timestamp': timestamp,
                'is_subagent': is_subagent,
                'agent_id': agent_id,
                'output': None,
            }

        elif block_type == 'tool_result':
            tool_use_id = block.get('tool_use_id', '')
            if tool_use_id in tool_use_cache:
                call = tool_use_cache.pop(tool_use_id)
                call['output'] = extract_result_text(block)
                completed_calls.append(call)

# Extract plain text from a tool_result content block
def extract_result_text(block):
    content = block.get('content', '')
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return first.get('text', '')
        return str(first)
    return str(content) if content else ''

# Char count of serialized input dict
def input_chars(input_dict):
    return len(json.dumps(input_dict))

# Char count of output string
def output_chars(output_str):
    return len(output_str or '')

# Format aggregate table of tool usage sorted by total chars descending
def format_aggregate_table(calls):
    stats = defaultdict(lambda: {'calls': 0, 'input': 0, 'output': 0})
    for call in calls:
        tool = call['tool_name']
        stats[tool]['calls'] += 1
        stats[tool]['input'] += input_chars(call['input'])
        stats[tool]['output'] += output_chars(call['output'])

    rows = sorted(
        [(tool, s['calls'], s['input'], s['output'], s['input'] + s['output'])
         for tool, s in stats.items()],
        key=lambda r: r[4], reverse=True
    )

    if not rows:
        return '_No tool calls found._'

    total_calls = sum(r[1] for r in rows)
    total_input = sum(r[2] for r in rows)
    total_output = sum(r[3] for r in rows)
    total_total = total_input + total_output

    w_tool = max(len('Tool'), max(len(r[0]) for r in rows), len('TOTAL'))
    w_calls = max(len('Calls'), len(f'{total_calls:,}'))
    w_input = max(len('Input (chars)'), len(f'{total_input:,}'))
    w_output = max(len('Output (chars)'), len(f'{total_output:,}'))
    w_total = max(len('Total (chars)'), len(f'{total_total:,}'))

    def row(tool, calls, inp, out, tot):
        return (f'| {tool:<{w_tool}} | {calls:>{w_calls},} | '
                f'{inp:>{w_input},} | {out:>{w_output},} | {tot:>{w_total},} |')

    sep = f'| {"-"*w_tool} | {"-"*w_calls} | {"-"*w_input} | {"-"*w_output} | {"-"*w_total} |'
    header = (f'| {"Tool":<{w_tool}} | {"Calls":>{w_calls}} | '
              f'{"Input (chars)":>{w_input}} | {"Output (chars)":>{w_output}} | '
              f'{"Total (chars)":>{w_total}} |')

    lines = [header, sep]
    for r in rows:
        lines.append(row(*r))
    lines.append(sep)
    lines.append(row('TOTAL', total_calls, total_input, total_output, total_total))
    return '\n'.join(lines)

# Format per-session breakdown table sorted by total chars descending
def format_session_breakdown(session_summaries):
    rows = []
    for session_path, calls in session_summaries:
        total = sum(input_chars(c['input']) + output_chars(c['output']) for c in calls)
        rows.append((str(session_path), len(calls), total))
    rows.sort(key=lambda r: r[2], reverse=True)

    if not rows:
        return '_No sessions found._'

    lines = ['| Session | Calls | Total (chars) |', '|---------|-------|---------------|']
    for path, call_count, total in rows:
        lines.append(f'| `{path}` | {call_count:,} | {total:,} |')
    return '\n'.join(lines)

# Extract the key identifying parameter for a tool call
def get_key_param(tool_name, input_dict):
    if tool_name in ('Read', 'Write', 'Edit'):
        return f'file_path={input_dict.get("file_path", "")}'
    if tool_name == 'Bash':
        cmd = input_dict.get('command', '')
        return f'command={cmd[:60]}{"..." if len(cmd) > 60 else ""}'
    if tool_name in ('Grep', 'Glob'):
        return f'pattern={input_dict.get("pattern", "")}'
    for k, v in input_dict.items():
        v_str = str(v)
        return f'{k}={v_str[:60]}{"..." if len(v_str) > 60 else ""}'
    return ''

# Extract HH:MM:SS from ISO timestamp string
def format_timestamp(ts):
    if not ts:
        return '??:??:??'
    match = re.search(r'T(\d{2}:\d{2}:\d{2})', ts)
    return match.group(1) if match else (ts[:8] if len(ts) >= 8 else '??:??:??')

# Format one tool call as a chronological detail line
def format_detail_row(call):
    ts = format_timestamp(call['timestamp'])
    tool = call['tool_name']
    key_param = get_key_param(tool, call['input'])
    inp = input_chars(call['input'])
    out = output_chars(call['output'])
    if call['is_subagent'] and call['agent_id']:
        attribution = f'subagent:{call["agent_id"]}'
    else:
        attribution = 'main'
    return f'[{ts}] {tool}  {key_param}  input:{inp}c  output:{out}c  ({attribution})'


if __name__ == '__main__':
    main()
