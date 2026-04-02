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
BAR_WIDTH = 40
LARGE_CACHE_THRESHOLD = 10000
TIME_GAP_MINUTES = 5
TIME_GAP_SECONDS_SMALL = 5
TTL_MAX_MINUTES = 60

# ORCHESTRATOR

def main():
    args = parse_args()
    if args.session:
        session_path = Path(args.session)
        turns = parse_session_turns(session_path)
        if args.aggregate:
            output = run_aggregate_view(session_path, turns)
        else:
            output = run_timeline_view(session_path, turns, anomalies_only=args.anomalies_only)
    elif args.project:
        output = run_project_view(args.project, include_workers=args.workers)
    else:
        print('Error: --session or --project required', file=sys.stderr)
        sys.exit(1)
    print(output)

def run_timeline_view(session_path, turns, anomalies_only=False):
    flags, anomaly_details = detect_anomalies(turns)
    lines = [f'# Cache Timeline — {session_path.name}\n']
    lines.append(format_turn_table(turns, flags=flags, anomalies_only=anomalies_only))
    lines.append('')
    lines.append(format_summary(turns, anomaly_details=anomaly_details))
    return '\n'.join(lines)

def run_aggregate_view(session_path, turns):
    _, anomaly_details = detect_anomalies(turns)
    lines = [f'# Cache Timeline (per-minute) — {session_path.name}\n']
    lines.append(format_minute_chart(turns))
    lines.append('')
    lines.append(format_summary(turns, anomaly_details=anomaly_details))
    return '\n'.join(lines)

def run_project_view(project_path, include_workers=False):
    sessions = find_project_sessions(project_path, include_workers)
    if not sessions:
        return f'No sessions found for project: {project_path}'
    lines = [f'# Cache Timeline — {project_path}\n']
    lines.append(format_project_summary(sessions))
    return '\n'.join(lines)

# FUNCTIONS

# Parse CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Analyze cache/token behavior over time in Claude Code sessions')
    parser.add_argument('--session', help='Path to session JSONL file')
    parser.add_argument('--project', help='Project path (absolute) — summary per session')
    parser.add_argument('--aggregate', action='store_true', help='Per-minute aggregation view (requires --session)')
    parser.add_argument('--workers', action='store_true', help='Include worker sessions (requires --project)')
    parser.add_argument('--anomalies-only', action='store_true', dest='anomalies_only', help='Only show turns with anomalies (requires --session)')
    return parser.parse_args()

# Encode project path to match Claude directory naming
def encode_project_path(path):
    return path.replace('/', '-').replace('_', '-')

# Find JSONL session files for a given project path
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

# Parse all assistant turns from a JSONL session file
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

# Extract token usage and content type from one assistant message
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

# Determine primary content block type and tool name from content list
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

# Compute cache status string for one turn
def cache_status(turn):
    cr = turn['cache_read']
    cc = turn['cache_creation']
    total_cache = cr + cc
    if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
        return f'MISS ({format_k(cc)} new)'
    elif cc > LARGE_CACHE_THRESHOLD and cc > cr:
        hit_pct = int(cr / total_cache * 100) if total_cache else 0
        return f'PARTIAL ({hit_pct}% hit)'
    elif total_cache > 0:
        hit_pct = int(cr / total_cache * 100) if total_cache else 0
        return f'HIT ({hit_pct}%)'
    return 'NO CACHE'

# Classify cache event as MISS / PARTIAL / HIT for counting
def classify_cache_event(turn):
    cr = turn['cache_read']
    cc = turn['cache_creation']
    if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
        return 'MISS'
    elif cc > LARGE_CACHE_THRESHOLD and cc > cr:
        return 'PARTIAL'
    return 'HIT'

# Format large token count as compact k string
def format_k(n):
    if n >= 1000:
        return f'{n/1000:.1f}k'
    return str(n)

# Build display label for tool/content type column
def type_label(turn):
    if turn['block_type'] == 'tool_use':
        name = turn['tool_name'] or 'Unknown'
        if '__' in name:
            name = name.split('__')[-1]
        return name[:22]
    elif turn['block_type'] == 'thinking':
        return 'Thinking'
    return 'Text'

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

# Detect STUCK_CACHE, FAILED_RESUME, PREMATURE_TTL anomalies across all turns
def detect_anomalies(turns):
    flags = defaultdict(list)
    details = []

    for i in range(4, len(turns)):
        cr_n = turns[i]['cache_read']
        cr_n2 = turns[i - 2]['cache_read']
        cr_n4 = turns[i - 4]['cache_read']
        cc_n = turns[i]['cache_creation']
        if cr_n == cr_n2 == cr_n4 and cc_n > cr_n:
            flags[i].append('STUCK_CACHE')

    stuck_indices = sorted(i for i, f in flags.items() if 'STUCK_CACHE' in f)
    if stuck_indices:
        ranges = []
        start = prev = stuck_indices[0]
        for idx in stuck_indices[1:]:
            if idx == prev + 1:
                prev = idx
            else:
                ranges.append((start, prev))
                start = prev = idx
        ranges.append((start, prev))
        for s, e in ranges:
            cr_stuck = turns[s]['cache_read']
            cc_s = turns[s]['cache_creation']
            cc_e = turns[e]['cache_creation']
            details.append({
                'type': 'STUCK_CACHE',
                'turns': (s + 1, e + 1),
                'description': (
                    f'cache_read stuck at {cr_stuck:,} for {e - s + 1} turns '
                    f'while cache_creation grew from {format_k(cc_s)} to {format_k(cc_e)}'
                ),
            })

    for i in range(1, len(turns) - 1):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if not (t_prev and t_curr):
            continue
        gap_seconds = (t_curr - t_prev).total_seconds()
        if gap_seconds <= TIME_GAP_SECONDS_SMALL:
            continue
        if turns[i]['cache_read'] != 0:
            continue
        cr_next = turns[i + 1]['cache_read']
        cc_next = turns[i + 1]['cache_creation']
        if cc_next > 0 and cr_next < cc_next * 0.5:
            flags[i + 1].append('FAILED_RESUME')
            details.append({
                'type': 'FAILED_RESUME',
                'turns': (i + 1, i + 2),
                'description': (
                    f'Resume at {format_time(turns[i]["timestamp"])} after '
                    f'{gap_seconds / 60:.0f}m gap, cache_read did not recover by turn {i + 2}'
                ),
            })

    for i in range(1, len(turns)):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if not (t_prev and t_curr):
            continue
        gap_minutes = (t_curr - t_prev).total_seconds() / 60
        if not (TIME_GAP_MINUTES < gap_minutes < TTL_MAX_MINUTES):
            continue
        cr = turns[i]['cache_read']
        cc = turns[i]['cache_creation']
        if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
            flags[i].append('PREMATURE_TTL')
            details.append({
                'type': 'PREMATURE_TTL',
                'turns': (i + 1, i + 1),
                'description': (
                    f'Full cache rebuild ({format_k(cc)} new) after {gap_minutes:.0f}m gap '
                    f'at turn {i + 1} ({format_time(turns[i]["timestamp"])})'
                ),
            })

    return dict(flags), details

# Format per-turn timeline table, with optional anomaly flags and anomalies-only filter
def format_turn_table(turns, flags=None, anomalies_only=False):
    if not turns:
        return '_No assistant turns found._'
    flags = flags or {}
    header = (
        f'{"Turn":>5}  {"Time":8}  {"Direct":>8}  {"CacheNew":>10}  '
        f'{"CacheHit":>10}  {"Output":>8}  {"Tool/Type":<22}  {"Cache Status":<24}  Anomalies'
    )
    sep = '-' * len(header)
    rows = [header, sep]
    for i, turn in enumerate(turns, 1):
        turn_flags = flags.get(i - 1, [])
        if anomalies_only and not turn_flags:
            continue
        tl = type_label(turn)
        status = cache_status(turn)
        flag_str = '  '.join(turn_flags)
        rows.append(
            f'{i:>5}  {format_time(turn["timestamp"]):8}  '
            f'{turn["input_tokens"]:>8,}  '
            f'{turn["cache_creation"]:>10,}  '
            f'{turn["cache_read"]:>10,}  '
            f'{turn["output_tokens"]:>8,}  '
            f'{tl:<22}  {status:<24}  {flag_str}'
        )
    return '\n'.join(rows)

# Format anomalies summary section
def format_anomalies_section(anomaly_details):
    counts = {'STUCK_CACHE': [], 'FAILED_RESUME': [], 'PREMATURE_TTL': []}
    for d in anomaly_details:
        counts[d['type']].append(d)
    lines = ['## Anomalies\n']
    for atype, items in counts.items():
        if not items:
            lines.append(f'{atype}: 0 occurrences')
        else:
            turn_ranges = ', '.join(
                f'turns {d["turns"][0]}-{d["turns"][1]}' if d["turns"][0] != d["turns"][1]
                else f'turn {d["turns"][0]}'
                for d in items
            )
            lines.append(f'{atype}: {len(items)} occurrence{"s" if len(items) > 1 else ""} ({turn_ranges})')
            for d in items:
                lines.append(f'  {d["description"]}')
    return '\n'.join(lines)

# Find time gaps larger than min_gap_minutes between consecutive turns
def find_time_gaps(turns, min_gap_minutes):
    gaps = []
    for i in range(1, len(turns)):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if t_prev and t_curr:
            diff = (t_curr - t_prev).total_seconds() / 60
            if diff >= min_gap_minutes:
                gaps.append({
                    'before_time': format_time(turns[i - 1]['timestamp']),
                    'after_time': format_time(turns[i]['timestamp']),
                    'minutes': diff,
                    'turn_before': i,
                    'turn_after': i + 1,
                })
    return gaps

# Format summary section with totals, hit rate, spikes, time gaps, and anomalies
def format_summary(turns, anomaly_details=None):
    if not turns:
        return ''
    total_turns = len(turns)
    total_input = sum(t['input_tokens'] for t in turns)
    total_cc = sum(t['cache_creation'] for t in turns)
    total_cr = sum(t['cache_read'] for t in turns)
    total_output = sum(t['output_tokens'] for t in turns)
    total_tokens = total_input + total_cc + total_output
    total_cache = total_cr + total_cc
    hit_rate = int(total_cr / total_cache * 100) if total_cache else 0
    miss_count = sum(1 for t in turns if classify_cache_event(t) == 'MISS')
    partial_count = sum(1 for t in turns if classify_cache_event(t) == 'PARTIAL')
    spike_turn = max(turns, key=lambda t: t['cache_creation'] + t['input_tokens'])
    spike_idx = turns.index(spike_turn) + 1
    spike_label = type_label(spike_turn)
    spike_tokens = spike_turn['cache_creation'] + spike_turn['input_tokens']
    gaps = find_time_gaps(turns, TIME_GAP_MINUTES)
    lines = ['## Summary']
    lines.append(f'- Turns: {total_turns}')
    lines.append(f'- Total tokens: {total_tokens:,}  (input: {total_input + total_cc:,} | output: {total_output:,})')
    lines.append(f'- Cache hit rate: {hit_rate}%  (read: {total_cr:,} | new: {total_cc:,})')
    lines.append(f'- MISS events: {miss_count}  |  PARTIAL events: {partial_count}')
    lines.append(f'- Biggest spike: Turn {spike_idx} ({spike_label}) — {spike_tokens:,} tokens')
    if gaps:
        gap_strs = [f'{g["before_time"]}→{g["after_time"]} ({g["minutes"]:.0f}m)' for g in gaps]
        lines.append(f'- Gaps >{TIME_GAP_MINUTES}m: {", ".join(gap_strs)}')
    else:
        lines.append(f'- Gaps >{TIME_GAP_MINUTES}m: none')
    result = '\n'.join(lines)
    if anomaly_details is not None:
        result += '\n\n' + format_anomalies_section(anomaly_details)
    return result

# Format per-minute token bar chart
def format_minute_chart(turns):
    if not turns:
        return '_No assistant turns found._'
    buckets = defaultdict(lambda: {'input': 0, 'cache_creation': 0, 'cache_read': 0, 'output': 0, 'turns': 0})
    for turn in turns:
        ts = parse_timestamp(turn['timestamp'])
        if not ts:
            continue
        key = ts.strftime('%H:%M')
        buckets[key]['input'] += turn['input_tokens']
        buckets[key]['cache_creation'] += turn['cache_creation']
        buckets[key]['cache_read'] += turn['cache_read']
        buckets[key]['output'] += turn['output_tokens']
        buckets[key]['turns'] += 1
    if not buckets:
        return '_No timestamps found._'
    sorted_keys = sorted(buckets.keys())
    max_tokens = max(
        b['input'] + b['cache_creation'] + b['output']
        for b in buckets.values()
    )
    lines = [f'{"Time":5}  {"Turns":>5}  {"Total Tokens":>14}  Bar']
    lines.append('-' * 60)
    for key in sorted_keys:
        b = buckets[key]
        total = b['input'] + b['cache_creation'] + b['output']
        bar_len = int(total / max_tokens * BAR_WIDTH) if max_tokens else 0
        lines.append(f'{key:5}  {b["turns"]:>5}  {total:>14,}  {"#" * bar_len}')
    return '\n'.join(lines)

# Format per-session summary table for a project
def format_project_summary(sessions):
    rows = []
    for session_path in sessions:
        turns = parse_session_turns(session_path)
        if not turns:
            continue
        total_input = sum(t['input_tokens'] + t['cache_creation'] for t in turns)
        total_output = sum(t['output_tokens'] for t in turns)
        total_cr = sum(t['cache_read'] for t in turns)
        total_cc = sum(t['cache_creation'] for t in turns)
        total_cache = total_cr + total_cc
        hit_rate = int(total_cr / total_cache * 100) if total_cache else 0
        miss_count = sum(1 for t in turns if classify_cache_event(t) == 'MISS')
        first_ts = format_time(turns[0]['timestamp']) if turns else '?'
        last_ts = format_time(turns[-1]['timestamp']) if turns else '?'
        rows.append({
            'name': session_path.name[:36],
            'turns': len(turns),
            'input': total_input,
            'output': total_output,
            'hit_rate': hit_rate,
            'miss': miss_count,
            'first': first_ts,
            'last': last_ts,
        })
    if not rows:
        return '_No sessions with data found._'
    header = f'{"Session":<38}  {"Turns":>5}  {"Input":>10}  {"Output":>8}  {"Hit%":>5}  {"MISS":>4}  Time Range'
    sep = '-' * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f'{r["name"]:<38}  {r["turns"]:>5}  {r["input"]:>10,}  '
            f'{r["output"]:>8,}  {r["hit_rate"]:>4}%  {r["miss"]:>4}  '
            f'{r["first"]}–{r["last"]}'
        )
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
