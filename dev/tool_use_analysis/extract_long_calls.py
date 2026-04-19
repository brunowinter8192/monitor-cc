#!/usr/bin/env python3
"""Extract long tool_use inputs from Proxy JSONL files and report context cost by tool."""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from datetime import datetime

CHAR_BUCKETS = [
    (500, 999, '500–999'),
    (1000, 1999, '1000–1999'),
    (2000, 4999, '2000–4999'),
    (5000, 9999, '5000–9999'),
    (10000, None, '10000+'),
]
RATIO_EXCLUDED_TOOLS = {'Edit', 'Write'}
RATIO_EXCLUDED_SUBSTR = 'worker_send'
DEFAULT_TOP_N = 30
DEFAULT_MIN_CHARS = 500
INPUT_PREVIEW_CHARS = 400
PREFIX_EXAMPLE_CHARS = 200


# ORCHESTRATOR

def extract_long_calls_workflow(proxy_paths, top_n, min_chars, output_path, tool_filter, ratio_mode):
    all_events = []
    seen_ids = {}
    for path in proxy_paths:
        events = load_events(path)
        all_events.extend(events)
        collect_tool_use_blocks(events, seen_ids, os.path.basename(path))

    measured = {bid: measure_call(c) for bid, c in seen_ids.items()}

    if ratio_mode:
        candidates = [
            m for m in measured.values()
            if (tool_filter and m['name'] == tool_filter)
            or (not tool_filter
                and m['name'] not in RATIO_EXCLUDED_TOOLS
                and RATIO_EXCLUDED_SUBSTR not in m['name'])
        ]
        tool_results = collect_tool_results(all_events)
        ratio_calls = []
        for c in candidates:
            tr = tool_results.get(c['id'])
            if tr is None:
                continue
            ratio_calls.append(compute_ratio(c, tr))
        ratio_calls.sort(key=lambda x: -x['ratio'])
        report = build_ratio_report(proxy_paths, ratio_calls, top_n, tool_filter)

    else:
        candidates = list(measured.values())
        if tool_filter:
            candidates = [c for c in candidates if c['name'] == tool_filter]
        above = [c for c in candidates if c['total_chars'] >= min_chars]
        above.sort(key=lambda x: -x['total_chars'])
        report = build_report(proxy_paths, measured, above, top_n, min_chars, tool_filter)

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


def collect_tool_results(all_events):
    """Walk all events, collect tool_result blocks by tool_use_id (first occurrence wins)."""
    seen = {}
    for event in all_events:
        messages = event.get('raw_payload', {}).get('messages', [])
        for msg in messages:
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get('type') != 'tool_result':
                    continue
                tid = block.get('tool_use_id')
                if tid and tid not in seen:
                    seen[tid] = block
    return seen


def measure_call(call):
    """Compute total_chars and per-field char counts for a tool_use call."""
    inp = call['input']
    total_chars = len(json.dumps(inp))
    field_chars = {k: len(json.dumps(v)) for k, v in inp.items()}
    return {**call, 'total_chars': total_chars, 'field_chars': field_chars}


def compute_ratio(call, tr_block):
    """Compute input/output char ratio for a matched tool_use + tool_result pair."""
    output_chars = len(json.dumps(tr_block.get('content', '')))
    ratio = call['total_chars'] / max(output_chars, 1)
    return {**call, 'output_chars': output_chars, 'ratio': ratio}


def extract_prefix(command_str):
    """Extract command prefix and tags from a Bash command string."""
    tags = []

    if '<<' in command_str:
        tags.append('[heredoc]')

    tokens = None
    for line in command_str.split('\n'):
        line = line.strip()
        if not line:
            continue
        line_tokens = line.split()
        while line_tokens and re.match(r'^[A-Z_][A-Z0-9_]*=', line_tokens[0]):
            line_tokens.pop(0)
        while line_tokens and line_tokens[0] in ('&&', '||', ';'):
            line_tokens.pop(0)
        if not line_tokens:
            continue
        if line_tokens[0].startswith('#'):
            continue
        tokens = line_tokens
        break

    if not tokens:
        return ('(empty)', tags)

    first = tokens[0]

    while first == 'cd' and len(tokens) >= 3 and tokens[2] == '&&':
        tokens = tokens[3:]
        if not tokens:
            return ('(empty)', tags)
        first = tokens[0]

    if '/' in first and re.search(r'python3?$', first):
        tags.append('[abs-venv]')
        return ('python', tags)

    if first == 'source':
        rest = ' '.join(tokens[1:])
        if '&&' in rest:
            fn_tokens = rest.split('&&', 1)[1].strip().split()
            if fn_tokens:
                tags.append('[sourced-fn]')
                return (fn_tokens[0], tags)

    if first.startswith('~') or first.startswith('/'):
        basename = first.rstrip('/').split('/')[-1]
        return (basename, tags)

    return (first, tags)


def build_prefix_cluster_table(bash_calls):
    """Aggregate Bash calls by command prefix; return sorted Markdown table."""
    clusters = {}
    for c in bash_calls:
        cmd = c['input'].get('command', '')
        prefix, tags = extract_prefix(cmd)
        tag_str = ' '.join(tags)
        key = f'{prefix} {tag_str}'.strip()
        if key not in clusters:
            clusters[key] = {
                'prefix': prefix,
                'tags': tag_str,
                'count': 0,
                'total': 0,
                'max': 0,
                'example': '',
            }
        cl = clusters[key]
        cl['count'] += 1
        cl['total'] += c['total_chars']
        cl['max'] = max(cl['max'], c['total_chars'])
        if not cl['example']:
            cl['example'] = cmd[:PREFIX_EXAMPLE_CHARS].replace('\n', ' ').replace('|', '\\|')

    rows = sorted(clusters.values(), key=lambda x: -x['total'])
    lines = [
        '| Prefix | Tags | Count | Total chars | Mean | Max | Example |',
        '|--------|------|-------|-------------|------|-----|---------|',
    ]
    for r in rows:
        mean = r['total'] // r['count']
        example = r['example']
        if len(example) > PREFIX_EXAMPLE_CHARS:
            example = example[:PREFIX_EXAMPLE_CHARS] + '…'
        lines.append(
            f"| `{r['prefix']}` | {r['tags'] or '—'} | {r['count']} |"
            f" {r['total']:,} | {mean:,} | {r['max']:,} | {example} |"
        )
    return '\n'.join(lines)


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


def build_ratio_summary_table(ratio_calls):
    """Build per-tool ratio aggregation table."""
    by_tool = {}
    for c in ratio_calls:
        name = c['name']
        if name not in by_tool:
            by_tool[name] = {
                'count': 0,
                'total_input': 0,
                'total_output': 0,
                'ratios': [],
                'max_ratio': 0.0,
            }
        s = by_tool[name]
        s['count'] += 1
        s['total_input'] += c['total_chars']
        s['total_output'] += c['output_chars']
        s['ratios'].append(c['ratio'])
        s['max_ratio'] = max(s['max_ratio'], c['ratio'])

    rows = []
    for name, s in sorted(by_tool.items(), key=lambda x: -x[1]['max_ratio']):
        mean_r = sum(s['ratios']) / len(s['ratios'])
        sorted_r = sorted(s['ratios'])
        median_r = sorted_r[len(sorted_r) // 2]
        rows.append(
            f"| {name} | {s['count']} | {s['total_input']:,} | {s['total_output']:,}"
            f" | {mean_r:.2f} | {median_r:.2f} | {s['max_ratio']:.2f} |"
        )
    header = (
        '| Tool | Count | Total input | Total output | Mean ratio | Median ratio | Max ratio |\n'
        '|------|-------|-------------|--------------|------------|--------------|----------|\n'
    )
    return header + '\n'.join(rows)


def format_call_detail(n, call):
    """Render a single top-N char-based entry section."""
    ts_local = format_timestamp_local(call['timestamp'])
    lines = []
    lines.append(
        f"### [{n}] {call['name']} — {call['total_chars']:,} chars"
        f" — {call['session_file']}:{ts_local}"
    )
    lines.append('')
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


def format_ratio_call_detail(n, call):
    """Render a single top-N ratio-based entry section."""
    ts_local = format_timestamp_local(call['timestamp'])
    lines = []
    lines.append(
        f"### [{n}] {call['name']} — ratio={call['ratio']:.2f}"
        f" — input={call['total_chars']:,} / output={call['output_chars']:,} chars"
        f" — {call['session_file']}:{ts_local}"
    )
    lines.append('')
    top_fields = sorted(call['field_chars'].items(), key=lambda x: -x[1])
    lines.append('**Top input fields:**')
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


def build_report(proxy_paths, all_calls, filtered, top_n, min_chars, tool_filter):
    """Assemble the full char-based Markdown report."""
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    title = f'Long Tool Calls Report — {now_local}'
    if tool_filter:
        title += f' — tool={tool_filter}'
    lines.append(f'# {title}')
    lines.append('')
    lines.append(f'**Sessions analyzed:** {len(proxy_paths)} files')
    lines.append(f'**Total unique tool_use blocks:** {len(all_calls)} (after dedup)')
    lines.append(f'**Calls above threshold (≥ {min_chars:,} chars):** {len(filtered)}')
    if tool_filter:
        lines.append(f'**Tool filter:** `{tool_filter}`')
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

    if tool_filter == 'Bash' and filtered:
        lines.append('## Command-Prefix Clustering')
        lines.append('')
        lines.append(build_prefix_cluster_table(filtered))
        lines.append('')

    top_slice = filtered[:top_n]
    lines.append(f'## Top {len(top_slice)} Longest Calls')
    lines.append('')
    if not top_slice:
        lines.append('*(no calls above threshold)*')
    else:
        for n, call in enumerate(top_slice, 1):
            lines.append(format_call_detail(n, call))

    return '\n'.join(lines)


def build_ratio_report(proxy_paths, ratio_calls, top_n, tool_filter):
    """Assemble the ratio-based Markdown report."""
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    title = f'Tool Call Ratio Report (input/output chars) — {now_local}'
    if tool_filter:
        title += f' — tool={tool_filter}'
    lines.append(f'# {title}')
    lines.append('')
    lines.append(f'**Sessions analyzed:** {len(proxy_paths)} files')
    lines.append(f'**Matched pairs (tool_use + tool_result):** {len(ratio_calls)}')
    if not tool_filter:
        lines.append(
            f'**Excluded tools:** Edit, Write, *worker_send (content-driven, not shortenable)*'
        )
    if tool_filter:
        lines.append(f'**Tool filter:** `{tool_filter}`')
    lines.append('')
    lines.append(
        '> **Ratio = input_chars / output_chars.** '
        'High ratio = sent much, got little back = inefficient invocation.'
    )
    lines.append('')

    lines.append('## Summary by Tool')
    lines.append('')
    if ratio_calls:
        lines.append(build_ratio_summary_table(ratio_calls))
    else:
        lines.append('*(no matched pairs found)*')
    lines.append('')

    top_slice = ratio_calls[:top_n]
    lines.append(f'## Top {len(top_slice)} Highest-Ratio Calls')
    lines.append('')
    if not top_slice:
        lines.append('*(no matched pairs found)*')
    else:
        for n, call in enumerate(top_slice, 1):
            lines.append(format_ratio_call_detail(n, call))

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
        '--tool',
        default=None,
        metavar='NAME',
        help='Filter by tool name (e.g. Bash, Read, Grep)'
    )
    parser.add_argument(
        '--ratio',
        action='store_true',
        help='Activate ratio analysis (input/output chars); excludes Edit/Write/worker_send'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=DEFAULT_TOP_N,
        metavar='N',
        help=f'Top-N entries in detail section (default: {DEFAULT_TOP_N})'
    )
    parser.add_argument(
        '--min-chars',
        type=int,
        default=DEFAULT_MIN_CHARS,
        metavar='N',
        help=f'Min input chars filter; ignored in --ratio mode (default: {DEFAULT_MIN_CHARS})'
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
    extract_long_calls_workflow(
        args.proxy_jsonl, args.top, args.min_chars,
        args.output, args.tool, args.ratio,
    )
