#!/usr/bin/env python3
"""Extract long tool_use inputs from Proxy JSONL files and report context cost by tool.

Input:  src/logs/api_requests_*.jsonl (one or more paths, positional args)
Output: Markdown report to stdout or --output FILE
"""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

# --- INLINED from former src/proxy_forensics.py (library removed 2026-04-19) ---

CHAR_BUCKETS = [
    (500, 999, '500–999'),
    (1000, 1999, '1000–1999'),
    (2000, 4999, '2000–4999'),
    (5000, 9999, '5000–9999'),
    (10000, None, '10000+'),
]
PREFIX_EXAMPLE_CHARS = 200


@dataclass(slots=True, frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict
    session_file: str
    timestamp: str

    @property
    def input_chars(self) -> int:
        return len(json.dumps(self.input))

    @property
    def field_chars(self) -> dict:
        return {k: len(json.dumps(v)) for k, v in self.input.items()}


@dataclass(slots=True, frozen=True)
class ToolResult:
    tool_use_id: str
    content: object
    is_error: bool

    @property
    def output_chars(self) -> int:
        return len(json.dumps(self.content))


@dataclass(slots=True, frozen=True)
class Pair:
    tu: ToolUse
    tr: ToolResult

    @property
    def ratio(self) -> float:
        return self.tu.input_chars / max(self.tr.output_chars, 1)


@dataclass(slots=True, frozen=True)
class ToolStats:
    name: str
    count: int
    total_input: int
    total_output: int
    mean_ratio: float
    median_ratio: float
    max_ratio: float


@dataclass(slots=True)
class PrefixBucket:
    prefix: str
    tags: str
    count: int
    total_chars: int
    max_chars: int
    example: str

    @property
    def mean_chars(self) -> int:
        return self.total_chars // self.count


def load_proxy(paths: list) -> list:
    events = []
    for path in paths:
        session_file = os.path.basename(path)
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
                d['_session_file'] = session_file
                events.append(d)
    return events


def tool_use_blocks(events: list) -> Iterator:
    seen: set = set()
    for event in events:
        ts = event.get('timestamp', '')
        session_file = event.get('_session_file', '')
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
                if not bid or bid in seen:
                    continue
                seen.add(bid)
                yield ToolUse(
                    id=bid,
                    name=block.get('name', ''),
                    input=block.get('input', {}),
                    session_file=session_file,
                    timestamp=ts,
                )


def tool_result_blocks(events: list) -> dict:
    seen: dict = {}
    for event in events:
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
                    seen[tid] = ToolResult(
                        tool_use_id=tid,
                        content=block.get('content', ''),
                        is_error=bool(block.get('is_error', False)),
                    )
    return seen


def pairs(events: list) -> Iterator:
    results = tool_result_blocks(events)
    for tu in tool_use_blocks(events):
        tr = results.get(tu.id)
        if tr is not None:
            yield Pair(tu=tu, tr=tr)


def filter_by(items: Iterator, tool: Optional[str] = None,
              min_input_chars: Optional[int] = None,
              max_input_chars: Optional[int] = None,
              ratio_gt: Optional[float] = None,
              ratio_lt: Optional[float] = None,
              name_contains: Optional[str] = None,
              exclude_tools: Optional[list] = None) -> Iterator:
    for item in items:
        tu = item.tu if isinstance(item, Pair) else item
        if tool is not None and tu.name != tool:
            continue
        if name_contains is not None and name_contains not in tu.name:
            continue
        if exclude_tools is not None and any(ex in tu.name for ex in exclude_tools):
            continue
        if min_input_chars is not None and tu.input_chars < min_input_chars:
            continue
        if max_input_chars is not None and tu.input_chars > max_input_chars:
            continue
        if isinstance(item, Pair):
            if ratio_gt is not None and item.ratio <= ratio_gt:
                continue
            if ratio_lt is not None and item.ratio >= ratio_lt:
                continue
        yield item


def aggregate_by_tool(pair_iter: Iterator) -> dict:
    by_tool: dict = {}
    for p in pair_iter:
        name = p.tu.name
        if name not in by_tool:
            by_tool[name] = {'count': 0, 'total_input': 0, 'total_output': 0,
                             'ratios': [], 'max_ratio': 0.0}
        s = by_tool[name]
        s['count'] += 1
        s['total_input'] += p.tu.input_chars
        s['total_output'] += p.tr.output_chars
        s['ratios'].append(p.ratio)
        s['max_ratio'] = max(s['max_ratio'], p.ratio)
    result = {}
    for name, s in by_tool.items():
        ratios = sorted(s['ratios'])
        mean_r = sum(ratios) / len(ratios)
        median_r = ratios[len(ratios) // 2]
        result[name] = ToolStats(
            name=name, count=s['count'], total_input=s['total_input'],
            total_output=s['total_output'], mean_ratio=mean_r,
            median_ratio=median_r, max_ratio=s['max_ratio'],
        )
    return result


def aggregate_by_prefix(bash_uses: Iterator) -> list:
    clusters: dict = {}
    for tu in bash_uses:
        cmd = tu.input.get('command', '')
        prefix, tags = extract_prefix(cmd)
        tag_str = ' '.join(tags)
        key = f'{prefix}\x00{tag_str}'
        if key not in clusters:
            example = cmd[:PREFIX_EXAMPLE_CHARS].replace('\n', ' ')
            clusters[key] = PrefixBucket(
                prefix=prefix, tags=tag_str, count=0,
                total_chars=0, max_chars=0, example=example,
            )
        b = clusters[key]
        b.count += 1
        b.total_chars += tu.input_chars
        b.max_chars = max(b.max_chars, tu.input_chars)
    return sorted(clusters.values(), key=lambda x: -x.total_chars)


def extract_prefix(command_str: str) -> tuple:
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


def bucket_distribution(items: Iterator) -> list:
    counts = {label: 0 for _, _, label in CHAR_BUCKETS}
    for item in items:
        ic = item.input_chars if isinstance(item, ToolUse) else item.tu.input_chars
        for lo, hi, label in CHAR_BUCKETS:
            if hi is None and ic >= lo:
                counts[label] += 1
                break
            elif hi is not None and lo <= ic <= hi:
                counts[label] += 1
                break
    return [(label, counts[label]) for _, _, label in CHAR_BUCKETS]


def format_timestamp_local(ts_str: str) -> str:
    if not ts_str:
        return '?'
    try:
        dt_utc = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt_utc.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]

# --- END INLINED from former src/proxy_forensics.py ---

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
