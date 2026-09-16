#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import sys
from pathlib import Path

from extract_patterns_collect import (
    _source_label, _load_proxy, _collect_tool_uses, _collect_tool_results,
    _build_pairs, _aggregate_waste, _aggregate_failed, _per_source_stats,
)
from extract_patterns_report import _build_report


# ORCHESTRATOR

def run(jsonl_paths, output_path):
    per_source_events = {}
    all_events = []
    for path in jsonl_paths:
        label = _source_label(path)
        evs = _load_proxy(path, label)
        per_source_events[label] = evs
        all_events.extend(evs)

    tool_uses = {}
    _collect_tool_uses(all_events, tool_uses)
    tool_results = {}
    _collect_tool_results(all_events, tool_results)

    waste_pairs, failed_pairs, ct_pairs = _build_pairs(tool_uses, tool_results)
    waste_groups  = _aggregate_waste(waste_pairs)
    failed_groups = _aggregate_failed(failed_pairs)
    source_stats  = _per_source_stats(tool_uses, waste_pairs, failed_pairs, ct_pairs, jsonl_paths)

    report = _build_report(
        jsonl_paths, per_source_events, tool_uses,
        source_stats, waste_pairs, waste_groups,
        failed_pairs, failed_groups, ct_pairs,
    )
    _write_output(report, output_path)


# FUNCTIONS

def _write_output(content, path):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)


def _parse_args():
    parser = argparse.ArgumentParser(
        description='Signature-normalized waste pattern report from Proxy JSONL files.'
    )
    parser.add_argument('proxy_jsonl', nargs='+', help='Path(s) to Proxy JSONL file(s)')
    parser.add_argument('--output', default=None, metavar='FILE',
                        help='Output markdown file path (default: stdout)')
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    run(args.proxy_jsonl, args.output)
