#!/usr/bin/env python3
"""Extract failed tool calls from Proxy JSONL files and report by tool and error type.

Input:  src/logs/api_requests_*.jsonl (one or more paths, positional args)
Output: dev/tool_use_analysis/<report_name>.md (--output) or stdout
"""

# INFRASTRUCTURE
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PARALLEL_CANCEL_TAG  = "Cancelled: parallel tool call"
TOOL_UNAVAILABLE_TAG = "Error: No such tool available"
STRING_NOT_FOUND_TAG = "String to replace not found"
VALIDATION_ERROR_TAG = "Input validation error"
TOOL_USE_ERROR_OPEN  = "<tool_use_error>"

ERROR_PREVIEW_CHARS = 200
INPUT_PREVIEW_CHARS = 150


# ORCHESTRATOR

def extract_failed_workflow(proxy_paths, output_path):
    events_by_log = {}
    for path in proxy_paths:
        events_by_log[path] = _load_proxy(path)

    tool_uses  = {}
    tool_results = {}
    for path, events in events_by_log.items():
        label = _log_label(path)
        _collect_tool_uses(events, label, tool_uses)
        _collect_tool_results(events, tool_results)

    failures = _collect_failures(tool_uses, tool_results)
    report   = _build_report(proxy_paths, events_by_log, tool_uses, failures)
    _write_output(report, output_path)


# FUNCTIONS

# Load proxy JSONL — only entries with raw_payload
def _load_proxy(path):
    events = []
    with open(path, encoding='utf-8') as f:
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
            d['_path'] = path
            events.append(d)
    return events


# Build label string from log filename (opus vs worker:<name>)
def _log_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_worker_'):
        name = base.replace('api_requests_worker_', '').rsplit('_', 1)[0]
        return f'worker:{name}'
    if base.startswith('api_requests_opus_'):
        return 'opus'
    return base


# Collect all tool_use blocks across events — deduped by tool_use id
def _collect_tool_uses(events, label, out):
    for ev in events:
        ts = ev.get('timestamp', '')
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_use':
                    continue
                bid = blk.get('id', '')
                if not bid or bid in out:
                    continue
                inp = blk.get('input', {})
                out[bid] = {
                    'name': blk.get('name', ''),
                    'input_chars': len(json.dumps(inp)),
                    'input_preview': json.dumps(inp)[:INPUT_PREVIEW_CHARS],
                    'ts': ts,
                    'label': label,
                }


# Collect all tool_result blocks — deduped by tool_use_id
def _collect_tool_results(events, out):
    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_result':
                    continue
                tid = blk.get('tool_use_id', '')
                if not tid or tid in out:
                    continue
                raw_c = blk.get('content', '')
                text = raw_c if isinstance(raw_c, str) else json.dumps(raw_c)
                out[tid] = {
                    'is_error': bool(blk.get('is_error', False)),
                    'output_chars': len(text),
                    'text': text,
                }


# Classify failure type — requires is_error=True; sub-classifies by content markers
def _classify_failure(is_error, text):
    if not is_error:
        return None
    if TOOL_USE_ERROR_OPEN in text:
        if PARALLEL_CANCEL_TAG in text:
            return 'parallel-cancel'
        if TOOL_UNAVAILABLE_TAG in text:
            return 'tool-unavailable'
        if STRING_NOT_FOUND_TAG in text:
            return 'edit-string-not-found'
        if VALIDATION_ERROR_TAG in text:
            return 'validation-error'
        return 'tool-use-error'
    return 'bash-exit-nonzero'


# Match tool_use + tool_result pairs and return all failures
def _collect_failures(tool_uses, tool_results):
    failures = []
    for bid, tu in tool_uses.items():
        tr = tool_results.get(bid)
        if tr is None:
            continue
        ftype = _classify_failure(tr['is_error'], tr['text'])
        if ftype is None:
            continue
        failures.append({
            'label': tu['label'],
            'ts': tu['ts'],
            'tid': bid,
            'tool_name': tu['name'],
            'failure_type': ftype,
            'input_chars': tu['input_chars'],
            'output_chars': tr['output_chars'],
            'input_preview': tu['input_preview'],
            'error_preview': tr['text'][:ERROR_PREVIEW_CHARS].replace('\n', ' '),
        })
    failures.sort(key=lambda x: (x['label'], x['ts']))
    return failures


# Render full Markdown report
def _build_report(proxy_paths, events_by_log, tool_uses, failures):
    now_local = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []

    lines.append(f'# Failed Tool Calls Analysis — {now_local}')
    lines.append('')

    # Source block (CONVENTION.md requirement)
    lines.append('## Source JSONLs')
    lines.append('')
    total_events = 0
    total_tu = sum(1 for tu in tool_uses.values())
    for path in proxy_paths:
        events = events_by_log.get(path, [])
        label = _log_label(path)
        tu_count = sum(1 for tu in tool_uses.values() if tu['label'] == label)
        lines.append(f'- `{os.path.basename(path)}` ({len(events)} events, {tu_count} tool_use blocks)')
        total_events += len(events)
    lines.append('')
    lines.append(f'Total sessions analyzed: {len(proxy_paths)}. Total tool_use blocks: {total_tu}.')
    lines.append('')

    # Summary counts
    by_type = Counter(f['failure_type'] for f in failures)
    by_tool = Counter(f['tool_name'] for f in failures)
    by_source = Counter(f['label'] for f in failures)

    lines.append('## Summary')
    lines.append('')
    lines.append(f'**Total failures:** {len(failures)}')
    lines.append('')
    lines.append('### By Source')
    lines.append('')
    lines.append('| Source | Failures |')
    lines.append('|--------|----------|')
    for src, cnt in sorted(by_source.items()):
        lines.append(f'| `{src}` | {cnt} |')
    lines.append('')
    lines.append('### By Error Type')
    lines.append('')
    lines.append('| Error Type | Count |')
    lines.append('|------------|-------|')
    for etype, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f'| `{etype}` | {cnt} |')
    lines.append('')
    lines.append('### By Tool')
    lines.append('')
    lines.append('| Tool | Count |')
    lines.append('|------|-------|')
    for tool, cnt in sorted(by_tool.items(), key=lambda x: -x[1]):
        lines.append(f'| `{tool}` | {cnt} |')
    lines.append('')

    # Individual entries
    lines.append('## Failure Details')
    lines.append('')
    for n, f in enumerate(failures, 1):
        ts_local = _format_ts_local(f['ts'])
        lines.append(
            f"### [{n}] `{f['failure_type']}` — {f['tool_name']}"
            f" — {f['label']} — {ts_local}"
        )
        lines.append('')
        lines.append(f"**input_chars:** {f['input_chars']:,} &nbsp; **output_chars:** {f['output_chars']:,}")
        lines.append('')
        if f['input_preview']:
            lines.append('**Input preview:**')
            lines.append('```')
            lines.append(f['input_preview'])
            lines.append('```')
            lines.append('')
        lines.append('**Error content:**')
        lines.append('```')
        lines.append(f['error_preview'])
        lines.append('```')
        lines.append('')
        lines.append('---')
        lines.append('')

    return '\n'.join(lines)


# Convert UTC ISO timestamp to local HH:MM:SS
def _format_ts_local(ts_str):
    if not ts_str:
        return '?'
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]


# Write report to file or stdout
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
        description='Extract failed tool calls from Proxy JSONL files.'
    )
    parser.add_argument('proxy_jsonl', nargs='+',
                        help='Path(s) to Proxy JSONL file(s) under src/logs/')
    parser.add_argument('--output', default=None, metavar='FILE',
                        help='Output markdown file path (default: stdout)')
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    extract_failed_workflow(args.proxy_jsonl, args.output)
