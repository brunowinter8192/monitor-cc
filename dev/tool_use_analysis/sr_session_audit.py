#!/usr/bin/env python3
"""SR Session-JSONL longitudinal audit across all CC project sessions.

Scans ~/.claude/projects/*/*.jsonl for <system-reminder> blocks in user-role messages.
Classifies each block against the current strip template catalog from
src/proxy/strip_sr._SR_TEMPLATES. Reports known/preserved/unknown buckets with
per-bucket timeline and CC-version attribution across all projects and sessions.

Noise filters applied before classification:
  - code-heuristic: inner text starts with regex syntax (.*?, \\s*) or contains
    Python code markers (re.compile, _SR_TEMPLATES, def ...).
  - data-file-noise (Option A): UNKNOWN bucket only — drops SR when the 120-char
    context before <system-reminder> contains \\d+\\t (Read-tool line-number prefix),
    indicating the SR was read from a data file rather than injected by CC.

Input:  ~/.claude/projects/*/*.jsonl  (CC session files, filtered by --since date)
Output: dev/tool_use_analysis/<YYYYMMDDHHMM>_sr_session_audit.md
"""

# INFRASTRUCTURE

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

_src_dir = os.path.join(
    os.environ.get('MONITOR_CC_ROOT', str(Path(__file__).parent.parent.parent)),
    'src',
)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.strip_sr import _SR_TEMPLATES, _PRESERVE_PREAMBLE

_CC_PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# Line-start anchored SR block regex (same anchor as src/proxy/strip_sr._STANDALONE_SR_RE)
_SR_RE = re.compile(r'(?m)^<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# Read-tool output format: 'NNN\t content' — used to detect data-file-noise context
_READ_TOOL_LINE_RE = re.compile(r'\d+\t')
_LINE_NUM_PREFIX_RE = re.compile(r'^\d+\t')

# Code-noise heuristic: inner text that starts with these is a regex/code artefact
_NOISE_STARTS = ('.*?', r'\s*', r'\n', '(.*', '(.*?)', '...', r'\d+\t')
_NOISE_CONTAINS = (
    're.compile', 're.escape', 're.findall',
    ' def ', '\ndef ', '_TAG_', '_STRIP_', '_SR_TEMPLATES',
)


# ORCHESTRATOR

def sr_session_audit_workflow(project_filter, since_date, output_path, top_n):
    scan = {
        'n_files': 0, 'n_entries': 0, 'n_parse_errors': 0,
        'n_total_srs': 0, 'n_code_noise': 0, 'n_data_noise': 0,
        'since': since_date, 'project_filter': project_filter or 'none', 'top': top_n,
    }
    known = {tid: _empty_stat() for tid in _SR_TEMPLATES}
    preserved = _empty_stat()
    unknown = {}  # normalized_prefix → stat dict with extra 'sample' + 'projects' keys

    for proj_name, session_path in _iter_sessions(project_filter):
        scan['n_files'] += 1
        for entry_date, version, content in _iter_user_messages(session_path, since_date, scan):
            scan['n_entries'] += 1
            for inner, layer, ctx_before in _extract_sr_hits(content):
                scan['n_total_srs'] += 1
                bucket, noise = _classify(inner, ctx_before)
                if noise == 'code-noise':
                    scan['n_code_noise'] += 1
                elif noise == 'data-file-noise':
                    scan['n_data_noise'] += 1
                elif bucket == 'preserved':
                    _add(preserved, layer, version, entry_date)
                elif bucket is not None:
                    _add(known[bucket[len('known:'):]], layer, version, entry_date)
                else:
                    key = ' '.join(inner[:100].split())
                    if key not in unknown:
                        unknown[key] = _empty_stat()
                        unknown[key]['sample'] = inner
                        unknown[key]['projects'] = set()
                    _add(unknown[key], layer, version, entry_date)
                    unknown[key]['projects'].add(proj_name)

    scan['n_classified'] = (
        sum(s['total'] for s in known.values()) + preserved['total']
        + sum(s['total'] for s in unknown.values())
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(_build_report(known, preserved, unknown, scan)), encoding='utf-8')
    print(output_path)


# FUNCTIONS

# Yield (proj_name, session_path) for all session JSONLs matching optional project filter
def _iter_sessions(project_filter):
    if not _CC_PROJECTS_DIR.is_dir():
        return
    for proj_dir in sorted(_CC_PROJECTS_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        if project_filter and project_filter not in proj_dir.name:
            continue
        for jsonl in sorted(proj_dir.glob('*.jsonl')):
            yield proj_dir.name, jsonl


# Yield (entry_date, version, content) for user messages with date >= since_date
def _iter_user_messages(session_path, since_date, scan):
    try:
        with open(session_path, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    scan['n_parse_errors'] += 1
                    continue
                if ev.get('type') != 'user':
                    continue
                entry_date = _parse_date(ev.get('timestamp', ''))
                if entry_date is None or entry_date < since_date:
                    continue
                yield entry_date, ev.get('version', 'unknown'), ev.get('message', {}).get('content', '')
    except OSError:
        pass


# Yield (inner, layer, ctx_before) for all line-start SR blocks in user message content
def _extract_sr_hits(content):
    texts = []  # (layer, full_text)
    if isinstance(content, str):
        texts.append(('text', content))
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get('type')
            if btype == 'text':
                texts.append(('text', block.get('text', '')))
            elif btype == 'tool_result':
                ic = block.get('content', '')
                if isinstance(ic, str):
                    texts.append(('tool_result', ic))
                elif isinstance(ic, list):
                    for sub in ic:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            texts.append(('tool_result', sub.get('text', '')))
    for layer, text in texts:
        if '<system-reminder>' not in text:
            continue
        for m in _SR_RE.finditer(text):
            inner = m.group(1).strip()
            yield inner, layer, text[max(0, m.start() - 120):m.start()]


# Classify inner text → (bucket_or_None, noise_type_or_None)
def _classify(inner, ctx_before):
    if _is_code_noise(inner):
        return None, 'code-noise'
    if inner.startswith(_PRESERVE_PREAMBLE):
        return 'preserved', None
    for tid, spec in _SR_TEMPLATES.items():
        ids = spec[0] if isinstance(spec[0], list) else [spec[0]]
        for ident in ids:
            if inner.startswith(ident):
                return f'known:{tid}', None
    # Option A: unknown + Read-tool line-number prefix in context → data-file artefact
    if _READ_TOOL_LINE_RE.search(ctx_before):
        return None, 'data-file-noise'
    return None, None  # genuine unknown


# True if inner text looks like regex/code rather than a real SR injection
def _is_code_noise(inner):
    if not inner or inner == '.':
        return True
    if _LINE_NUM_PREFIX_RE.match(inner):
        return True
    head = inner[:120]
    for p in _NOISE_STARTS:
        if inner.startswith(p):
            return True
    for p in _NOISE_CONTAINS:
        if p in head:
            return True
    return False


# Add one SR observation to a stat bucket
def _add(stat, layer, version, entry_date):
    stat['total'] += 1
    stat[layer] = stat.get(layer, 0) + 1
    if stat['first'] is None or entry_date < stat['first']:
        stat['first'] = entry_date
    if stat['last'] is None or entry_date > stat['last']:
        stat['last'] = entry_date
    stat['versions'].add(version)


# Return a fresh stat bucket
def _empty_stat():
    return {'total': 0, 'text': 0, 'tool_result': 0, 'first': None, 'last': None, 'versions': set()}


# Parse ISO-8601 timestamp string to date; returns None on failure
def _parse_date(ts_raw):
    if not ts_raw:
        return None
    try:
        return datetime.fromisoformat(ts_raw.replace('Z', '+00:00')).date()
    except (ValueError, AttributeError):
        return None


# Format one Known/Preserved table row
def _row(label, s):
    return (
        f"| {label} | {s['total']} | {s['text']} | {s['tool_result']} "
        f"| {s['first'] or '—'} | {s['last'] or '—'} "
        f"| {', '.join(sorted(s['versions']))[:40]} |"
    )


# Build the full report as a list of lines
def _build_report(known, preserved, unknown, scan):
    ts_run = datetime.now().strftime('%Y-%m-%d %H:%M')
    n_noise = scan['n_code_noise'] + scan['n_data_noise']
    top_n = scan['top']

    L = [
        '# SR Session-JSONL Audit',
        (f"Run: {ts_run}  since={scan['since']}  files_scanned={scan['n_files']}  "
         f"srs_total={scan['n_total_srs']}  srs_filtered_noise={n_noise}  "
         f"classified={scan['n_classified']}"),
        '',
        '## Scan Parameters',
        f"- since: {scan['since']}",
        f"- project_filter: {scan['project_filter']}",
        f"- top: {top_n}",
        f"- entries_processed: {scan['n_entries']}  parse_errors: {scan['n_parse_errors']}",
        '- noise_filters:',
        ('  - **code-heuristic**: inner starts with `.*?` / `\\s*` / `(.*` / `...` / `\\n` '
         'or contains `re.compile` / `re.escape` / `_SR_TEMPLATES` / `\\ndef` / `_TAG_` / `_STRIP_`'),
        ('  - **data-file-noise (Option A)**: UNKNOWN-bucket only — drops SR when the '
         '120-char context before `<system-reminder>` matches `\\d+\\t` (Read-tool '
         'line-number prefix). Likely artefact from reading old session data or proxy logs. '
         'KNOWN/PRESERVED templates are never filtered by this rule.'),
        f"- noise_breakdown: code_noise={scan['n_code_noise']}  data_file_noise={scan['n_data_noise']}",
        '',
        '## Known Templates (would be stripped today)',
        '| template_id | total | text | tool_result | first | last | cc_versions |',
        '|---|---|---|---|---|---|---|',
    ]
    for tid in _SR_TEMPLATES:
        L.append(_row(tid, known[tid]))
    L += [
        '',
        '## Preserved',
        '| bucket | total | text | tool_result | first | last | cc_versions |',
        '|---|---|---|---|---|---|---|',
        _row('claudemd-preamble', preserved),
        '',
    ]

    sorted_unknown = sorted(unknown.items(), key=lambda x: -x[1]['total'])[:top_n]
    L += [
        f'## Unknown / Gap Candidates (NOT stripped — top {top_n} by count)',
        '| total | text | tool_result | first | last | cc_versions | identifier prefix |',
        '|---|---|---|---|---|---|---|',
    ]
    for key, s in sorted_unknown:
        key_cell = key[:60].replace('|', '\\|')
        L.append(
            f"| {s['total']} | {s['text']} | {s['tool_result']} "
            f"| {s['first'] or '?'} | {s['last'] or '?'} "
            f"| {', '.join(sorted(s['versions']))[:40]} | {key_cell} |"
        )
    L.append('')

    if sorted_unknown:
        L.append(f'## Top-{min(top_n, len(sorted_unknown))} Unknown — Sample text')
        for key, s in sorted_unknown:
            versions_str = ', '.join(sorted(s['versions']))
            proj_str = ', '.join(sorted(s.get('projects', set()))[:5])
            sample = s.get('sample', '')[:600]
            L += [
                '',
                (f'### "{key[:80]}"  '
                 f'(count={s["total"]}, {s["first"] or "?"} → {s["last"] or "?"}, '
                 f'cc_versions: {versions_str})'),
                f'Projects: {proj_str}',
                '```',
                sample,
                '```',
            ]
        L.append('')

    return L


def main():
    parser = argparse.ArgumentParser(description='SR Session-JSONL longitudinal audit')
    parser.add_argument('project_filter', nargs='?', default='',
                        help='Substring filter on project directory name (empty = all)')
    parser.add_argument('--since', default='2026-04-16', metavar='YYYY-MM-DD',
                        help='Include only messages with timestamp >= this date (default: 2026-04-16)')
    parser.add_argument('--output', help='Output MD path (auto-generated if omitted)')
    parser.add_argument('--top', type=int, default=30, metavar='N',
                        help='Top-N Unknown gap candidates to show (default: 30)')
    args = parser.parse_args()
    try:
        since_date = date.fromisoformat(args.since)
    except ValueError:
        print(f'ERROR: invalid --since date: {args.since}', file=sys.stderr)
        sys.exit(1)
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime('%Y%m%d%H%M')
        output_path = Path(__file__).parent / f'{ts}_sr_session_audit.md'
    sr_session_audit_workflow(args.project_filter or '', since_date, output_path, args.top)


if __name__ == '__main__':
    main()
