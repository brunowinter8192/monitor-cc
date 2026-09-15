# INFRASTRUCTURE
import json
from datetime import datetime

from extract_long_calls_lib import (
    aggregate_by_tool, aggregate_by_prefix, bucket_distribution, format_timestamp_local,
)

INPUT_PREVIEW_CHARS = 400
PREFIX_EXAMPLE_CHARS = 200

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
