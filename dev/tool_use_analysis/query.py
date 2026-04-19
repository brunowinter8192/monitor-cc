#!/usr/bin/env python3
"""Thin CLI over src/proxy_forensics.py for common proxy JSONL forensic queries."""

# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path so src/ is importable when run as a script
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# From src/proxy_forensics.py: proxy loading, extraction, aggregation, utilities
from src.proxy_forensics import (
    aggregate_by_prefix,
    bucket_distribution,
    filter_by,
    format_timestamp_local,
    load_proxy,
    pairs,
    tool_use_blocks,
)


# ORCHESTRATOR

def query_workflow(args):
    events = load_proxy(args.files)
    args.func(args, events)


# FUNCTIONS

def cmd_count(args, events):
    """Count unique tool_use blocks, optionally filtered by tool name."""
    uses = tool_use_blocks(events)
    if args.tool:
        uses = filter_by(uses, tool=args.tool)
    count = sum(1 for _ in uses)
    label = args.tool if args.tool else 'all tools'
    file_count = len(args.files)
    print(f'{label}: {count} unique calls ({file_count} files)')


def cmd_ratio(args, events):
    """List highest input/output ratio pairs."""
    all_pairs = pairs(events)
    if args.tool:
        all_pairs = filter_by(all_pairs, tool=args.tool)
    if args.ratio_gt is not None:
        all_pairs = filter_by(all_pairs, ratio_gt=args.ratio_gt)
    sorted_pairs = sorted(all_pairs, key=lambda p: -p.ratio)[:args.top]
    if not sorted_pairs:
        print('No matching pairs found.')
        return
    for i, p in enumerate(sorted_pairs, 1):
        ts = format_timestamp_local(p.tu.timestamp)
        print(
            f'#{i:<3} {p.tu.name:<54} ratio={p.ratio:>7.2f}'
            f'  in={p.tu.input_chars:>6,}  out={p.tr.output_chars:>7,}'
            f'  {p.tu.session_file}:{ts}'
        )


def cmd_prefix(args, events):
    """Bash command-prefix aggregation sorted by total chars."""
    bash_uses = filter_by(tool_use_blocks(events), tool='Bash')
    buckets = aggregate_by_prefix(bash_uses)[:args.top]
    if not buckets:
        print('No Bash calls found.')
        return
    print(f'{"prefix":<30} {"tags":<22} {"count":>5} {"total_chars":>12} {"mean":>7} {"max":>7}')
    print('-' * 89)
    for b in buckets:
        print(
            f'{b.prefix:<30} {b.tags or "—":<22} {b.count:>5}'
            f' {b.total_chars:>12,} {b.mean_chars:>7,} {b.max_chars:>7,}'
        )


def cmd_bucket(args, events):
    """Input char-bucket distribution across all tool_use blocks."""
    uses = tool_use_blocks(events)
    if args.tool:
        uses = filter_by(uses, tool=args.tool)
    for label, count in bucket_distribution(uses):
        print(f'{label:<12}: {count}')


def cmd_pair(args, events):
    """Dump a single tool_use + tool_result pair as JSON by tool_use id."""
    for p in pairs(events):
        if p.tu.id == args.id:
            out = {
                'id': p.tu.id,
                'name': p.tu.name,
                'input_chars': p.tu.input_chars,
                'output_chars': p.tr.output_chars,
                'ratio': round(p.ratio, 4),
                'is_error': p.tr.is_error,
                'session_file': p.tu.session_file,
                'timestamp': p.tu.timestamp,
                'input': p.tu.input,
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return
    print(f'No pair found for id: {args.id}', file=sys.stderr)
    sys.exit(1)


def parse_args():
    """Parse command-line arguments with subcommands."""
    parser = argparse.ArgumentParser(
        description='Proxy JSONL forensic queries (thin CLI over queries.py).'
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # count
    p_count = sub.add_parser('count', help='Count unique tool_use blocks')
    p_count.add_argument('files', nargs='+', metavar='FILE')
    p_count.add_argument('--tool', default=None, metavar='NAME')
    p_count.set_defaults(func=cmd_count)

    # ratio
    p_ratio = sub.add_parser('ratio', help='List highest input/output ratio pairs')
    p_ratio.add_argument('files', nargs='+', metavar='FILE')
    p_ratio.add_argument('--top', type=int, default=10, metavar='N')
    p_ratio.add_argument('--tool', default=None, metavar='NAME')
    p_ratio.add_argument('--ratio-gt', type=float, default=None, metavar='X')
    p_ratio.set_defaults(func=cmd_ratio)

    # prefix
    p_prefix = sub.add_parser('prefix', help='Bash command-prefix aggregation')
    p_prefix.add_argument('files', nargs='+', metavar='FILE')
    p_prefix.add_argument('--top', type=int, default=20, metavar='N')
    p_prefix.set_defaults(func=cmd_prefix)

    # bucket
    p_bucket = sub.add_parser('bucket', help='Input char-bucket distribution')
    p_bucket.add_argument('files', nargs='+', metavar='FILE')
    p_bucket.add_argument('--tool', default=None, metavar='NAME')
    p_bucket.set_defaults(func=cmd_bucket)

    # pair
    p_pair = sub.add_parser('pair', help='Dump single tool_use+tool_result pair as JSON')
    p_pair.add_argument('files', nargs='+', metavar='FILE')
    p_pair.add_argument('--id', required=True, metavar='ID')
    p_pair.set_defaults(func=cmd_pair)

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    query_workflow(args)
