#!/usr/bin/env python3
"""Chronological tool_use / tool_result transcript from a proxy-log JSONL snapshot.

Renders WHAT calls a session made, in order — to trace the workflow and spot
redundant call sequences (10 calls where 2 would do). No waste/ratio scoring:
this is a plain timeline dump.

Input:  one or more proxy-log JSONL paths under src/logs/ (uses the entry with
        the highest message_count per file = cumulative snapshot)
Output: markdown report to stdout, or a file via --output

Usage:
    ./venv/bin/python3 dev/tool_use_analysis/extract_transcript.py \\
        src/logs/api_requests_worker_capture-gh_reference_<ts>.jsonl \\
        --output /tmp/worker_transcript.md
"""

# INFRASTRUCTURE
import argparse
import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_MAX_INPUT_CHARS = 4000
DEFAULT_MAX_RESULT_CHARS = 1500


# ORCHESTRATOR

def run(paths, max_input, max_result, with_text, out_path):
    sources = []
    body = []
    total_tool_use = 0
    for path in paths:
        snapshot, n_events = _find_snapshot(path)
        if snapshot is None:
            print(f'WARNING: no raw_payload entry in {path}', file=sys.stderr)
            sources.append((path, n_events, 0, 0))
            continue
        msgs = snapshot['raw_payload'].get('messages', [])
        tu_count = _count_tool_use(msgs)
        total_tool_use += tu_count
        sources.append((path, n_events, len(msgs), tu_count))
        body.append(f'## {os.path.basename(path)} — {len(msgs)} messages, {tu_count} tool_use blocks\n')
        body.extend(_render_transcript(msgs, max_input, max_result, with_text))
        body.append('')

    report = _build_header(sources, total_tool_use) + '\n' + '\n'.join(body)
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(out_path)
    else:
        print(report)


# FUNCTIONS

# Find entry with highest message_count (cumulative snapshot); also count raw_payload events
def _find_snapshot(path):
    best, best_count, n_events = None, -1, 0
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
            n_events += 1
            count = len(d['raw_payload'].get('messages', []))
            if count > best_count:
                best, best_count = d, count
    return best, n_events


# Count tool_use blocks across all messages of a snapshot
def _count_tool_use(msgs):
    n = 0
    for msg in msgs:
        content = msg.get('content', [])
        if isinstance(content, list):
            n += sum(1 for b in content if isinstance(b, dict) and b.get('type') == 'tool_use')
    return n


# Convert a tool_result content field (str | list[block]) to plain text
def _result_to_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(blk.get('text', '') or json.dumps(blk, ensure_ascii=False))
            else:
                parts.append(str(blk))
        return '\n'.join(parts)
    return str(content)


# Yield transcript lines for one snapshot's messages array, in order
def _render_transcript(msgs, max_input, max_result, with_text):
    lines = []
    for i, msg in enumerate(msgs):
        role = msg.get('role', '?')
        content = msg.get('content', [])
        if isinstance(content, str):
            if with_text and content.strip():
                lines.append(f'--- msg[{i}] {role} text ---')
                lines.append(content[:300])
                lines.append('')
            continue
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            btype = blk.get('type')
            if btype == 'tool_use':
                name = blk.get('name', '?')
                inp = json.dumps(blk.get('input', {}), ensure_ascii=False)
                if len(inp) > max_input:
                    inp = inp[:max_input] + f'  …[+{len(inp) - max_input}c]'
                lines.append(f'--- msg[{i}] {role} tool_use ---')
                lines.append(name)
                lines.append(inp)
                lines.append('')
            elif btype == 'tool_result':
                err = '  (ERROR)' if blk.get('is_error') else ''
                txt = _result_to_text(blk.get('content', ''))
                if len(txt) > max_result:
                    txt = txt[:max_result] + f'  …[+{len(txt) - max_result}c]'
                lines.append(f'--- msg[{i}] {role} tool_result{err} ---')
                lines.append(txt)
                lines.append('')
            elif btype == 'text' and with_text:
                t = blk.get('text', '')
                if t.strip():
                    lines.append(f'--- msg[{i}] {role} text ---')
                    lines.append(t[:300])
                    lines.append('')
    return lines


# Build the CONVENTION.md Source block header
def _build_header(sources, total_tool_use):
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    L = [f'# Tool-Use Transcript — {ts}', '', '## Source JSONLs', '']
    for path, n_events, n_msgs, tu in sources:
        L.append(f'- `{path}` ({n_events} events, {tu} tool_use blocks in snapshot of {n_msgs} msgs)')
    L.append('')
    L.append(f'Total sessions analyzed: {len(sources)}. Total tool_use blocks: {total_tool_use}.')
    L.append('')
    L.append('---')
    return '\n'.join(L)


def _parse_args():
    p = argparse.ArgumentParser(
        description='Chronological tool_use/tool_result transcript from proxy-log JSONL snapshot(s).'
    )
    p.add_argument('proxy_jsonl', nargs='+', help='One or more proxy-log JSONL paths')
    p.add_argument('--max-input-chars', type=int, default=DEFAULT_MAX_INPUT_CHARS,
                   help=f'Truncate tool_use input JSON (default {DEFAULT_MAX_INPUT_CHARS})')
    p.add_argument('--max-result-chars', type=int, default=DEFAULT_MAX_RESULT_CHARS,
                   help=f'Truncate tool_result content (default {DEFAULT_MAX_RESULT_CHARS})')
    p.add_argument('--with-text', action='store_true', default=False,
                   help='Also include assistant/user text blocks (default: tool blocks only)')
    p.add_argument('--output', default=None, help='Output markdown path (default: stdout)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    run(args.proxy_jsonl, args.max_input_chars, args.max_result_chars,
        args.with_text, args.output)
