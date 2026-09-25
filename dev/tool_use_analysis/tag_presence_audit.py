#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import sys
from datetime import datetime
from pathlib import Path

from tag_presence_audit_scan import _stream_and_audit
from tag_presence_audit_report import _build_report

_script_dir = Path(__file__).resolve().parent
_repo_candidate = _script_dir.parent.parent
_LOGS_DIR = _repo_candidate / 'src' / 'logs' if (_repo_candidate / 'src' / 'logs').is_dir() else _repo_candidate.parent.parent.parent / 'src' / 'logs'


# ORCHESTRATOR

def tag_presence_audit_workflow(jsonl_path, output_path):
    (blocks, tag_counts, sr_bypassed, sr_captured, n_opus, n_reqs_with_tags, n_non_opus,
     tn_bypassed, tn_captured, nd_bypassed, nd_captured, po_bypassed, po_captured) = (
        _stream_and_audit(jsonl_path)
    )
    lines = _build_report(
        jsonl_path, blocks, tag_counts, sr_bypassed, sr_captured,
        n_opus, n_reqs_with_tags, n_non_opus,
        tn_bypassed, tn_captured, nd_bypassed, nd_captured, po_bypassed, po_captured,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines))
    print(output_path)


# FUNCTIONS

def _parse_args():
    parser = argparse.ArgumentParser(description='Tag presence audit for proxy logs')
    parser.add_argument('jsonl', nargs='?', help='JSONL log path (auto-picks newest if omitted)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    if args.jsonl:
        jsonl_path = Path(args.jsonl)
        if not jsonl_path.exists():
            print(f'ERROR: {jsonl_path} not found', file=sys.stderr)
            sys.exit(1)
    else:
        if not _LOGS_DIR.is_dir():
            print(f'ERROR: logs dir not found: {_LOGS_DIR}', file=sys.stderr)
            sys.exit(1)
        candidates = sorted(
            _LOGS_DIR.glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print(f'ERROR: no api_requests_opus_monitor_cc_*.jsonl in {_LOGS_DIR}',
                  file=sys.stderr)
            sys.exit(1)
        jsonl_path = candidates[0]

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(__file__).parent / f'{ts}_tag_presence_audit.md'

    return jsonl_path, output_path


if __name__ == '__main__':
    jsonl_path, output_path = _parse_args()
    tag_presence_audit_workflow(jsonl_path, output_path)
