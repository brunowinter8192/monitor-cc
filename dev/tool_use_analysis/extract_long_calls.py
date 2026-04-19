#!/usr/bin/env python3
"""Extract long tool_use inputs from Proxy JSONL files and report context cost by tool."""

# INFRASTRUCTURE
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path so src/ is importable when run as a script
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# From src/proxy_forensics.py: proxy loading, extraction, aggregation, utilities
from src.proxy_forensics import (
    aggregate_by_prefix,
    aggregate_by_tool,
    bucket_distribution,
    filter_by,
    format_timestamp_local,
    load_proxy,
    pairs,
    tool_use_blocks,
)

RATIO_EXCLUDED_TOOLS = ['Edit', 'Write', 'worker_send']
DEFAULT_TOP_N = 30
DEFAULT_MIN_CHARS = 500
INPUT_PREVIEW_CHARS = 400
PREFIX_EXAMPLE_CHARS = 200


# ORCHESTRATOR

def extract_long_calls_workflow(proxy_paths, top_n, min_chars, output_path, tool_filter, ratio_mode):
    events = load_proxy(proxy_paths)

    if ratio_mode:
        all_pairs = pairs(events)
        if tool_filter:
            candidates = list(filter_by(all_pairs, tool=tool_filter))
        else:
            candidates = list(filter_by(all_pairs, exclude_tools=RATIO_EXCLUDED_TOOLS))
        candidates.sort(key=lambda p: -p.ratio)
        report = build_ratio_report(proxy_paths, candidates, top_n, tool_filter)

    else:
        all_uses_unfiltered = list(tool_use_blocks(events))
        total_unique = len(all_uses_unfiltered)
        if tool_filter:
            all_uses = [u for u in all_uses_unfiltered if u.name == tool_filter]
        else:
            all_uses = all_uses_unfiltered
        above = [u for u in all_uses if u.input_chars >= min_chars]
        above.sort(key=lambda u: -u.input_chars)
        report = build_report(proxy_paths, total_unique, above, top_n, min_chars, tool_filter)

    write_output(report, output_path)


# FUNCTIONS

def build_summary_table(uses):
    """Build per-tool Markdown table: count, total_chars, mean_chars, max_chars."""
    by_tool = {}
    for u in uses:
        if u.name not in by_tool:
            by_tool[u.name] = {'count': 0, 'total': 0, 'max': 0}
        by_tool[u.name]['count'] += 1
        by_tool[u.name]['total'] += u.input_chars
        by_tool[u.name]['max'] = max(by_tool[u.name]['max'], u.input_chars)
    rows = []
    for name, s in sorted(by_tool.items(), key=lambda x: -x[1]['total']):
        mean = s['total'] // s['count']
        rows.append(f"| {name} | {s['count']} | {s['total']:,} | {mean:,} | {s['max']:,} |")
    header = (
        '| Tool | Count ≥ threshold | Total chars | Mean chars | Max chars |\n'
        '|------|-------------------|-------------|------------|-----------|\n'
    )
    return header + '\n'.join(rows)


def build_ratio_summary_table(pair_list):
    """Build per-tool ratio aggregation table."""
    stats = aggregate_by_tool(iter(pair_list))
    rows = []
    for ts in sorted(stats.values(), key=lambda x: -x.max_ratio):
        rows.append(
            f"| {ts.name} | {ts.count} | {ts.total_input:,} | {ts.total_output:,}"
            f" | {ts.mean_ratio:.2f} | {ts.median_ratio:.2f} | {ts.max_ratio:.2f} |"
        )
    header = (
        '| Tool | Count | Total input | Total output | Mean ratio | Median ratio | Max ratio |\n'
        '|------|-------|-------------|--------------|------------|--------------|----------|\n'
    )
    return header + '\n'.join(rows)


def build_prefix_cluster_table(bash_uses):
    """Aggregate Bash uses by prefix and render Markdown table."""
    buckets = aggregate_by_prefix(iter(bash_uses))
    lines = [
        '| Prefix | Tags | Count | Total chars | Mean | Max | Example |',
        '|--------|------|-------|-------------|------|-----|---------|',
    ]
    for b in buckets:
        example = b.example
        if len(example) > PREFIX_EXAMPLE_CHARS:
            example = example[:PREFIX_EXAMPLE_CHARS] + '…'
        example = example.replace('|', '\\|')
        lines.append(
            f"| `{b.prefix}` | {b.tags or '—'} | {b.count} |"
            f" {b.total_chars:,} | {b.mean_chars:,} | {b.max_chars:,} | {example} |"
        )
    return '\n'.join(lines)


def format_call_detail(n, tu):
    """Render a single top-N char-based entry section."""
    ts_local = format_timestamp_local(tu.timestamp)
    lines = []
    lines.append(
        f"### [{n}] {tu.name} — {tu.input_chars:,} chars"
        f" — {tu.session_file}:{ts_local}"
    )
    lines.append('')
    top_fields = sorted(tu.field_chars.items(), key=lambda x: -x[1])
    lines.append('**Top fields:**')
    for field, chars in top_fields:
        lines.append(f'- `{field}`: {chars:,} chars')
    lines.append('')
    preview = json.dumps(tu.input)
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


def format_ratio_call_detail(n, p):
    """Render a single top-N ratio-based entry section."""
    ts_local = format_timestamp_local(p.tu.timestamp)
    lines = []
    lines.append(
        f"### [{n}] {p.tu.name} — ratio={p.ratio:.2f}"
        f" — input={p.tu.input_chars:,} / output={p.tr.output_chars:,} chars"
        f" — {p.tu.session_file}:{ts_local}"
    )
    lines.append('')
    top_fields = sorted(p.tu.field_chars.items(), key=lambda x: -x[1])
    lines.append('**Top input fields:**')
    for field, chars in top_fields:
        lines.append(f'- `{field}`: {chars:,} chars')
    lines.append('')
    preview = json.dumps(p.tu.input)
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


def build_report(proxy_paths, total_unique, above, top_n, min_chars, tool_filter):
    """Assemble the full char-based Markdown report."""
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    title = f'Long Tool Calls Report — {now_local}'
    if tool_filter:
        title += f' — tool={tool_filter}'
    lines.append(f'# {title}')
    lines.append('')
    lines.append(f'**Sessions analyzed:** {len(proxy_paths)} files')
    lines.append(f'**Total unique tool_use blocks:** {total_unique} (after dedup)')
    lines.append(f'**Calls above threshold (≥ {min_chars:,} chars):** {len(above)}')
    if tool_filter:
        lines.append(f'**Tool filter:** `{tool_filter}`')
    lines.append('')

    lines.append('## Summary by Tool')
    lines.append('')
    lines.append(build_summary_table(above) if above else '*(no calls above threshold)*')
    lines.append('')

    lines.append('## Char-Bucket Distribution (all calls above threshold)')
    lines.append('')
    lines.append('| Bucket | Count |')
    lines.append('|--------|-------|')
    for label, count in bucket_distribution(iter(above)):
        lines.append(f'| {label} | {count} |')
    lines.append('')

    if tool_filter == 'Bash' and above:
        lines.append('## Command-Prefix Clustering')
        lines.append('')
        lines.append(build_prefix_cluster_table(above))
        lines.append('')

    top_slice = above[:top_n]
    lines.append(f'## Top {len(top_slice)} Longest Calls')
    lines.append('')
    if not top_slice:
        lines.append('*(no calls above threshold)*')
    else:
        for n, tu in enumerate(top_slice, 1):
            lines.append(format_call_detail(n, tu))

    return '\n'.join(lines)


def build_ratio_report(proxy_paths, pair_list, top_n, tool_filter):
    """Assemble the ratio-based Markdown report."""
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    title = f'Tool Call Ratio Report (input/output chars) — {now_local}'
    if tool_filter:
        title += f' — tool={tool_filter}'
    lines.append(f'# {title}')
    lines.append('')
    lines.append(f'**Sessions analyzed:** {len(proxy_paths)} files')
    lines.append(f'**Matched pairs (tool_use + tool_result):** {len(pair_list)}')
    if not tool_filter:
        lines.append(
            '**Excluded tools:** Edit, Write, *worker_send (content-driven, not shortenable)*'
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
    lines.append(build_ratio_summary_table(pair_list) if pair_list else '*(no matched pairs found)*')
    lines.append('')

    top_slice = pair_list[:top_n]
    lines.append(f'## Top {len(top_slice)} Highest-Ratio Calls')
    lines.append('')
    if not top_slice:
        lines.append('*(no matched pairs found)*')
    else:
        for n, p in enumerate(top_slice, 1):
            lines.append(format_ratio_call_detail(n, p))

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
    parser.add_argument('proxy_jsonl', nargs='+',
                        help='Path(s) to Proxy JSONL file(s) under src/logs/')
    parser.add_argument('--tool', default=None, metavar='NAME',
                        help='Filter by tool name (e.g. Bash, Read, Grep)')
    parser.add_argument('--ratio', action='store_true',
                        help='Activate ratio analysis (input/output chars)')
    parser.add_argument('--top', type=int, default=DEFAULT_TOP_N, metavar='N',
                        help=f'Top-N entries in detail section (default: {DEFAULT_TOP_N})')
    parser.add_argument('--min-chars', type=int, default=DEFAULT_MIN_CHARS, metavar='N',
                        help=f'Min input chars filter; ignored in --ratio mode (default: {DEFAULT_MIN_CHARS})')
    parser.add_argument('--output', default=None, metavar='FILE',
                        help='Output markdown file path (default: stdout)')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    extract_long_calls_workflow(
        args.proxy_jsonl, args.top, args.min_chars,
        args.output, args.tool, args.ratio,
    )
