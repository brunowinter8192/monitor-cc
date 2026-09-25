#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import sys

from extract_long_calls_lib import load_proxy, tool_use_blocks, pairs, filter_by
from extract_long_calls_report import build_report, build_ratio_report

RATIO_EXCLUDED_TOOLS = ['Edit', 'Write', 'worker_send']
DEFAULT_TOP_N = 30
DEFAULT_MIN_CHARS = 500


# ORCHESTRATOR

def main():
    args = parse_args()
    extract_long_calls_workflow(
        args.proxy_jsonl, args.top, args.min_chars,
        args.output, args.tool, args.ratio,
    )


# FUNCTIONS

def parse_args():
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


def write_output(content, path):
    if path:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)


if __name__ == '__main__':
    main()
