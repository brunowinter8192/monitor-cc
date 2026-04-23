#!/usr/bin/env python3
"""SR bypass audit: per-template count of bypassed vs captured SR blocks.

Scans raw_payload.messages for SR blocks still present after proxy processing
(bypassed) and stripped_msg_removed for SR blocks successfully removed (captured).
Reports bypass_rate per template per log file + aggregate summary table.

Methodology note: the proxy final-pass (stripped_all_sr_msg0) strips all
templates from msg[0] but does NOT write to stripped_msg_removed. SR blocks
captured only by the final pass show as (captured=0, bypassed=0, n/a). SR blocks
in msg[N>0] that bypass the elif chain are counted as bypassed here.

Input:  JSONL paths (positional, optional) — auto-picks newest 3
        api_requests_opus_monitor_cc_*.jsonl when not given.
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_sr_bypass_audit.md
"""

# INFRASTRUCTURE

import argparse
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

# Mirror of _SR_TEMPLATES from src/proxy/strip_sr.py
# mode 'full' → entire SR block removed; 'partial' → IMPORTANT line removed, body kept
_SR_TEMPLATES = {
    'task-tools-nag':      ("The task tools haven't been used recently",                 'full'),
    'pyright-diagnostics': ('<new-diagnostics>',                                         'full'),
    'deferred-tools':      ('The following deferred tools are now available via ToolSearch', 'full'),
    'user-interrupt':      ('The user sent a new message while you were working:',       'partial'),
    'system-notification': ('[SYSTEM NOTIFICATION - NOT USER INPUT]',                    'full'),
    'file-modified':       ('Note: ',                                                    'full'),
    'claudemd-contents':   (["As you answer the user's questions", 'Contents of '],      'full'),
    'date-changed':        ('The date has changed.',                                     'full'),
    'skills-available':    ('The following skills are available',                        'full'),
    'plan-mode':           ('Plan mode ',                                                'full'),
}

# Regex: standalone SR block (must start at line boundary)
_STANDALONE_SR_RE = re.compile(r'(?m)^<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# Resolve log directory — handles both main repo and worktree execution
_script_dir = Path(__file__).resolve().parent          # dev/tool_use_analysis/
_repo_candidate = _script_dir.parent.parent            # worktree or main root
if (_repo_candidate / 'src' / 'logs').is_dir():
    _LOGS_DIR = _repo_candidate / 'src' / 'logs'
else:
    # Worktree case: root/.claude/worktrees/<name>/ → root is 3 levels up
    _main_repo = _repo_candidate.parent.parent.parent
    _LOGS_DIR = _main_repo / 'src' / 'logs'


# ORCHESTRATOR

def sr_bypass_audit_workflow(jsonl_paths, output_path):
    all_log_data = []
    for path in jsonl_paths:
        entries = _load_entries(path)
        tpl_stats = _audit_entries(entries)
        all_log_data.append((path, len(entries), tpl_stats))
    lines = _build_report(all_log_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines))
    print(output_path)


# FUNCTIONS

# Load opus-model entries from JSONL; skip non-opus and parse errors
def _load_entries(path):
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (entry.get('model') or '').startswith('claude-opus-'):
                entries.append(entry)
    return entries


# Count bypassed and captured SR blocks per template across all entries
def _audit_entries(entries):
    bypassed = {tid: 0 for tid in _SR_TEMPLATES}
    captured = {tid: 0 for tid in _SR_TEMPLATES}

    for entry in entries:
        # Bypassed: SR blocks still present in raw_payload (reached Opus unstripped)
        messages = entry.get('raw_payload', {}).get('messages', [])
        for text in _iter_content_texts(messages):
            for inner in _find_sr_inners(text):
                tid = _match_template(inner)
                if tid:
                    bypassed[tid] += 1

        # Captured: SR blocks recorded in stripped_msg_removed (confirmed stripped)
        # Note: final-pass (stripped_all_sr_msg0) does NOT write to stripped_msg_removed,
        # so captures from msg[0] via the final pass are not counted here.
        smr = entry.get('stripped_msg_removed') or {}
        for chunks in smr.values():
            if not chunks:
                continue
            for chunk in chunks:
                if not isinstance(chunk, str):
                    continue
                for inner in _find_sr_inners(chunk):
                    tid = _match_template(inner)
                    if tid:
                        captured[tid] += 1

    return {tid: {'bypassed': bypassed[tid], 'captured': captured[tid]}
            for tid in _SR_TEMPLATES}


# Yield all raw text strings from a messages list (text blocks + tool_result layers)
def _iter_content_texts(messages):
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get('type')
                if btype == 'text':
                    yield block.get('text', '')
                elif btype == 'tool_result':
                    inner = block.get('content', '')
                    if isinstance(inner, str):
                        yield inner
                    elif isinstance(inner, list):
                        for sub in inner:
                            if isinstance(sub, dict) and sub.get('type') == 'text':
                                yield sub.get('text', '')


# Find inner texts of all standalone SR blocks in text (line-start anchored)
def _find_sr_inners(text):
    if '<system-reminder>' not in text:
        return
    for m in _STANDALONE_SR_RE.finditer(text):
        yield m.group(1).strip()


# Match inner text against templates; returns template_id or None
def _match_template(inner):
    for tid, (identifier, _mode) in _SR_TEMPLATES.items():
        identifiers = identifier if isinstance(identifier, list) else [identifier]
        for ident in identifiers:
            if inner.startswith(ident):
                return tid
    return None


# Build full report lines
def _build_report(all_log_data):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f'# SR Bypass Audit — {ts}', '']
    lines += [
        '## Methodology',
        '',
        '- **bypassed**: SR blocks found in `raw_payload.messages` content after proxy processing (text, tool_result string, nested text).',
        '- **captured**: SR blocks found in `stripped_msg_removed` entries (confirmed removed by proxy).',
        '- **bypass_rate**: `bypassed / (bypassed + captured)`. Reported as `n/a` when both are 0.',
        '- **Limitation**: `stripped_all_sr_msg0` (final pass, msg[0] only) does NOT write to `stripped_msg_removed`,',
        '  so captures from msg[0] via the final pass are not counted in `captured`. This underestimates',
        '  `captured` for templates without a dedicated elif branch. The `bypassed` column is the reliable signal.',
        '',
    ]
    for path, n_entries, tpl_stats in all_log_data:
        lines += _build_log_table(path, n_entries, tpl_stats)
    agg = {tid: {'bypassed': 0, 'captured': 0} for tid in _SR_TEMPLATES}
    for _path, _n, tpl_stats in all_log_data:
        for tid, stats in tpl_stats.items():
            agg[tid]['bypassed'] += stats['bypassed']
            agg[tid]['captured'] += stats['captured']
    lines += ['## Aggregate Summary (all logs)', '']
    lines += _build_template_table(agg)
    return lines


# Build per-log section (header + table)
def _build_log_table(path, n_entries, tpl_stats):
    lines = [
        f'## {Path(path).name}',
        f'Opus entries: {n_entries}',
        '',
    ]
    lines += _build_template_table(tpl_stats)
    return lines


# Build template table (markdown)
def _build_template_table(tpl_stats):
    lines = [
        '| template | mode | captured | bypassed | bypass_rate |',
        '|---|---|---|---|---|',
    ]
    for tid, (identifier, mode) in _SR_TEMPLATES.items():
        stats = tpl_stats[tid]
        b = stats['bypassed']
        c = stats['captured']
        total = b + c
        rate = 'n/a' if total == 0 else f'{100 * b / total:.1f}%'
        lines.append(f'| {tid} | {mode} | {c} | {b} | {rate} |')
    lines.append('')
    return lines


# Parse CLI args — accept 1+ JSONL paths or auto-pick newest 3 from logs dir
def _parse_args():
    parser = argparse.ArgumentParser(description='SR bypass audit for proxy logs')
    parser.add_argument('jsonl', nargs='*', help='JSONL paths (auto-picks newest 3 if omitted)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    args = parser.parse_args()

    if args.jsonl:
        jsonl_paths = [Path(p) for p in args.jsonl]
        for p in jsonl_paths:
            if not p.exists():
                print(f'ERROR: {p} not found', file=sys.stderr)
                sys.exit(1)
    else:
        if not _LOGS_DIR.is_dir():
            print(f'ERROR: logs dir not found: {_LOGS_DIR}', file=sys.stderr)
            sys.exit(1)
        candidates = sorted(
            _LOGS_DIR.glob('api_requests_opus_monitor_cc_*.jsonl'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]
        if not candidates:
            print(f'ERROR: no api_requests_opus_monitor_cc_*.jsonl in {_LOGS_DIR}', file=sys.stderr)
            sys.exit(1)
        jsonl_paths = candidates

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(__file__).parent / f'{ts}_sr_bypass_audit.md'

    return jsonl_paths, output_path


if __name__ == '__main__':
    jsonl_paths, output_path = _parse_args()
    sr_bypass_audit_workflow(jsonl_paths, output_path)
