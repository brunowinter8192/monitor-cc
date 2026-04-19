#!/usr/bin/env python3
"""Extract long tool_use inputs from Proxy JSONL files and report context cost by tool."""

# INFRASTRUCTURE
import argparse
import json
import os
import sys
from datetime import datetime

CHAR_BUCKETS = [
    (500, 999, '500–999'),
    (1000, 1999, '1000–1999'),
    (2000, 4999, '2000–4999'),
    (5000, 9999, '5000–9999'),
    (10000, None, '10000+'),
]
DEFAULT_TOP_N = 30
DEFAULT_MIN_CHARS = 500
INPUT_PREVIEW_CHARS = 400


# ORCHESTRATOR

def extract_long_calls_workflow(proxy_paths, top_n, min_chars, output_path):
    seen_ids = {}
    for path in proxy_paths:
        events = load_events(path)
        collect_tool_use_blocks(events, seen_ids, os.path.basename(path))
    measured = [measure_call(c) for c in seen_ids.values()]
    filtered = [m for m in measured if m['total_chars'] >= min_chars]
    filtered.sort(key=lambda x: x['total_chars'], reverse=True)
    report = build_report(proxy_paths, seen_ids, filtered, top_n, min_chars)
    write_output(report, output_path)


# FUNCTIONS

def load_events(path):
    """Load proxy JSONL lines; skip entries with raw_payload == null."""
    events = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('raw_payload') is None:
                continue
            events.append(d)
    return events


def collect_tool_use_blocks(events, seen_ids, session_file):
    """Walk messages[].content[], collect tool_use blocks; dedup by id (first occurrence wins)."""
    for event in events:
        ts = event.get('timestamp', '')
        messages = event.get('raw_payload', {}).get('messages', [])
        for msg in messages:
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get('type') != 'tool_use':
                    continue
                bid = block.get('id')
                if not bid or bid in seen_ids:
                    continue
                seen_ids[bid] = {
                    'id': bid,
                    'name': block.get('name', ''),
                    'input': block.get('input', {}),
                    'session_file': session_file,
                    'timestamp': ts,
                }


def measure_call(call):
    """Compute total_chars and per-field char counts for a tool_use call."""
    inp = call['input']
    total_chars = len(json.dumps(inp))
    field_chars = {k: len(json.dumps(v)) for k, v in inp.items()}
    return {**call, 'total_chars': total_chars, 'field_chars': field_chars}


def bucket_distribution(calls):
    """Count calls per char-bucket range; returns list of (label, count) in bucket order."""
    counts = {label: 0 for _, _, label in CHAR_BUCKETS}
    for call in calls:
        tc = call['total_chars']
        for lo, hi, label in CHAR_BUCKETS:
            if hi is None and tc >= lo:
                counts[label] += 1
                break
            elif hi is not None and lo <= tc <= hi:
                counts[label] += 1
                break
    return [(label, counts[label]) for _, _, label in CHAR_BUCKETS]


def build_summary_table(calls):
    """Build per-tool Markdown table: count, total_chars, mean_chars, max_chars."""
    by_tool = {}
    for c in calls:
        name = c['name']
        if name not in by_tool:
            by_tool[name] = {'count': 0, 'total': 0, 'max': 0}
        by_tool[name]['count'] += 1
        by_tool[name]['total'] += c['total_chars']
        by_tool[name]['max'] = max(by_tool[name]['max'], c['total_chars'])
    rows = []
    for name, s in sorted(by_tool.items(), key=lambda x: -x[1]['total']):
        mean = s['total'] // s['count']
        rows.append(
            f"| {name} | {s['count']} | {s['total']:,} | {mean:,} | {s['max']:,} |"
        )
    header = (
        '| Tool | Count ≥ threshold | Total chars | Mean chars | Max chars |\n'
        '|------|-------------------|-------------|------------|-----------|\n'
    )
    return header + '\n'.join(rows)


def format_call_detail(n, call):
    """Render a single top-N entry section."""
    ts_local = format_timestamp_local(call['timestamp'])
    lines = []
    lines.append(
        f"### [{n}] {call['name']} — {call['total_chars']:,} chars"
        f" — {call['session_file']}:{ts_local}"
    )
    lines.append('')
    # Top fields sorted by char count descending
    top_fields = sorted(call['field_chars'].items(), key=lambda x: -x[1])
    lines.append('**Top fields:**')
    for field, chars in top_fields:
        lines.append(f'- `{field}`: {chars:,} chars')
    lines.append('')
    preview = json.dumps(call['input'])
    if len(preview) > INPUT_PREVIEW_CHARS:
        preview = preview[:INPUT_PREVIEW_CHARS] + '…'
    lines.append('**Input preview (first 400 chars of json.dumps):**')
    lines.append('```')
    lines.append(preview)
    lines.append('```')
    lines.append('')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)


def format_timestamp_local(ts_str):
    """Convert UTC ISO timestamp string to local HH:MM:SS."""
    if not ts_str:
        return '?'
    try:
        dt_utc = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt_utc.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]


def build_report(proxy_paths, all_calls, filtered, top_n, min_chars):
    """Assemble the full Markdown report."""
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    lines.append(f'# Long Tool Calls Report — {now_local}')
    lines.append('')
    lines.append(f'**Sessions analyzed:** {len(proxy_paths)} files')
    lines.append(f'**Total unique tool_use blocks:** {len(all_calls)} (after dedup)')
    lines.append(f'**Calls above threshold (≥ {min_chars:,} chars):** {len(filtered)}')
    lines.append('')

    lines.append('## Summary by Tool')
    lines.append('')
    if filtered:
        lines.append(build_summary_table(filtered))
    else:
        lines.append('*(no calls above threshold)*')
    lines.append('')

    lines.append('## Char-Bucket Distribution (all calls above threshold)')
    lines.append('')
    lines.append('| Bucket | Count |')
    lines.append('|--------|-------|')
    for label, count in bucket_distribution(filtered):
        lines.append(f'| {label} | {count} |')
    lines.append('')

    top_slice = filtered[:top_n]
    lines.append(f'## Top {min(top_n, len(top_slice))} Longest Calls')
    lines.append('')
    if not top_slice:
        lines.append('*(no calls above threshold)*')
    else:
        for n, call in enumerate(top_slice, 1):
            lines.append(format_call_detail(n, call))

    return '\n'.join(lines)


def write_output(content, path):
    """Write report to file or stdout."""
    if path:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract long tool_use inputs from Proxy JSONL files.'
    )
    parser.add_argument(
        'proxy_jsonl',
        nargs='+',
        help='Path(s) to Proxy JSONL file(s) under src/logs/'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=DEFAULT_TOP_N,
        metavar='N',
        help=f'Top-N longest calls in detail section (default: {DEFAULT_TOP_N})'
    )
    parser.add_argument(
        '--min-chars',
        type=int,
        default=DEFAULT_MIN_CHARS,
        metavar='N',
        help=f'Only include calls with total input chars >= N (default: {DEFAULT_MIN_CHARS})'
    )
    parser.add_argument(
        '--output',
        default=None,
        metavar='FILE',
        help='Output markdown file path (default: stdout)'
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    extract_long_calls_workflow(args.proxy_jsonl, args.top, args.min_chars, args.output)
