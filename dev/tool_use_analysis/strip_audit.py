#!/usr/bin/env python3
"""Per-REQ delta audit for proxy strip verification.

Computes per-request deltas across five buckets (EFF / INERT / IDX / LEAK / SUS)
using rule-counter diffs and marker-based chunk attribution from strip_vocab.
Legend at report top; Delta-Log in compact BUCKET:RULE notation.

Input:  JSONL path (positional arg, optional — auto-picks newest
        src/logs/api_requests_opus_monitor_cc_*.jsonl when not given)
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_strip_audit.md
"""

# INFRASTRUCTURE

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Path insertion so "from proxy.strip_vocab import ..." resolves from dev/ script
_src_dir = os.path.join(
    os.environ.get('MONITOR_CC_ROOT', str(Path(__file__).parent.parent.parent)),
    'src',
)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.strip_vocab import legend_markdown

from strip_audit_classify import _load_entries
from strip_audit_report import _build_header, _build_rule_catalog, _build_delta_log, _build_summary


# ORCHESTRATOR

def strip_audit_workflow(jsonl_path, output_path):
    entries, n_haiku, n_skipped = _load_entries(jsonl_path)
    lines = []
    lines += _build_header(jsonl_path, len(entries), n_haiku, n_skipped)
    lines.append(legend_markdown())
    lines += _build_rule_catalog()
    lines += _build_delta_log(entries)
    lines += _build_summary(entries)
    output_path.write_text('\n'.join(lines))
    print(output_path)


# FUNCTIONS

# Parse CLI args; auto-pick newest log when path is omitted
def _parse_args():
    parser = argparse.ArgumentParser(description='Per-REQ strip delta audit for proxy logs')
    parser.add_argument('jsonl', nargs='?', help='JSONL log path (auto-picks newest if omitted)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    if args.jsonl:
        jsonl_path = Path(args.jsonl)
        if not jsonl_path.exists():
            print(f'ERROR: {jsonl_path} not found', file=sys.stderr)
            sys.exit(1)
    else:
        candidates = sorted(
            Path('src/logs').glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print('ERROR: no api_requests_opus_monitor_cc_*.jsonl in src/logs/', file=sys.stderr)
            sys.exit(1)
        jsonl_path = candidates[0]

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(f'dev/tool_use_analysis/{ts}_strip_audit.md')

    return jsonl_path, output_path


if __name__ == '__main__':
    jsonl_path, output_path = _parse_args()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    strip_audit_workflow(jsonl_path, output_path)
