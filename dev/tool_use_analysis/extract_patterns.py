#!/usr/bin/env python3
"""Signature-normalized waste pattern report from multiple Proxy JSONL files.

Input:  src/logs/api_requests_*.jsonl (one or more, positional)
Output: dev/tool_use_analysis/<date>_session_waste_patterns.md (--output) or stdout
"""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PARALLEL_CANCEL_TAG  = "Cancelled: parallel tool call"
TOOL_UNAVAILABLE_TAG = "Error: No such tool available"
STRING_NOT_FOUND_TAG = "String to replace not found"
VALIDATION_ERROR_TAG = "Input validation error"
TOOL_USE_ERROR_OPEN  = "<tool_use_error>"

WASTE_RATIO_MIN  = 3.0
WASTE_INPUT_MIN  = 50
BASH_TOP_N       = 15
OTHER_MIN_COUNT  = 2
OTHER_MIN_INPUT  = 500
EXAMPLE_CHARS    = 150
SIG_MAX_CHARS    = 120

# Tools whose large input is by design (content being written/sent) — excluded from waste analysis
CONTENT_TRANSFER_TOOLS = {'Write', 'Edit'}

# Recognizable command prefixes for Section 6 wrapper name generation (skip if absent)
# echo excluded: second token is always quoted content, never a meaningful subcommand
KNOWN_PREFIXES = frozenset({
    'worker-cli', 'git', 'bd', 'ls', 'cat', 'python3', 'python',
    'head', 'grep', 'jq', 'find',
})

# Normalization substitutions applied in order
_NORM_SUBS = [
    (re.compile(r'/(?:Users|tmp|var|opt)/\S+'),               '<PATH>'),
    (re.compile(r'api_requests_[a-z_-]+_\d+\.jsonl'),         '<LOG>'),
    (re.compile(r'\b(?:Monitor_CC|[A-Z]\w+)-[a-z0-9]{3}\b'), '<BEAD_ID>'),
    (re.compile(r'\b[0-9a-f]{8,}\b'),                         '<HEX>'),
    (re.compile(r'\b17\d{8}\b'),                              '<TS>'),
    (re.compile(r'"[^"]{51,}"'),                              '<TEXT>'),
    (re.compile(r"'[^']{51,}'"),                              '<TEXT>'),
]


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

# Load proxy JSONL — entries with raw_payload only, tagged with source label
def _load_proxy(path, label):
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
            d['_source'] = label
            events.append(d)
    return events


# Derive short label from JSONL filename (strips api_requests_ prefix and .jsonl suffix)
def _source_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_'):
        base = base[len('api_requests_'):]
    if base.endswith('.jsonl'):
        base = base[:-len('.jsonl')]
    return base


# Collect all unique tool_use blocks across events — deduped by id
def _collect_tool_uses(events, out):
    for ev in events:
        source = ev.get('_source', '')
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
                inp  = blk.get('input', {})
                name = blk.get('name', '')
                out[bid] = {
                    'name': name,
                    'input_chars': len(json.dumps(inp)),
                    'sig': _tool_sig(name, inp),
                    'raw_example': _raw_example(name, inp),
                    'source': source,
                    'ts': ts,
                    'is_ct': _is_content_transfer(name, inp),
                }


# Collect all unique tool_result blocks across events — deduped by tool_use_id
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
                raw_c  = blk.get('content', '')
                text   = raw_c if isinstance(raw_c, str) else json.dumps(raw_c)
                is_err = bool(blk.get('is_error'))
                out[tid] = {
                    'output_chars': len(text),
                    'is_error': is_err,
                    'text': text if is_err else '',
                }


# Apply normalization substitutions to produce a grouping signature
def _normalize_sig(raw):
    s = raw.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    for pat, repl in _NORM_SUBS:
        s = pat.sub(repl, s)
    s = re.sub(r'(worker-cli\s+\w+\s+)worker-[a-z][\w-]+', r'\1<WORKER>', s)
    return s[:SIG_MAX_CHARS]


# Build signature string from tool name + input fields
def _tool_sig(name, inp):
    if name == 'Bash':
        raw = inp.get('command', '')
    elif name == 'Grep':
        pat  = inp.get('pattern', '')
        path = inp.get('path', '')
        raw  = f'{pat} {path}'.strip() if path else pat
    elif name in ('Glob', 'Read', 'Write', 'Edit'):
        raw = inp.get('file_path', inp.get('path', inp.get('pattern', '')))
    else:
        vals = [v for v in inp.values() if isinstance(v, str)]
        raw  = vals[0] if vals else json.dumps(inp)[:100]
    return _normalize_sig(raw)


# Extract primary input field as display example (150 chars, newlines flattened)
def _raw_example(name, inp):
    if name == 'Bash':
        raw = inp.get('command', '')
    elif name == 'Grep':
        raw = inp.get('pattern', '') + (' ' + inp.get('path', '') if inp.get('path') else '')
    elif name in ('Glob', 'Read', 'Write', 'Edit'):
        raw = inp.get('file_path', inp.get('path', inp.get('pattern', '')))
    else:
        vals = [v for v in inp.values() if isinstance(v, str)]
        raw  = vals[0] if vals else ''
    return raw.replace('\n', ' ')[:EXAMPLE_CHARS]


# Return True for content-transfer tools whose large input is by design, not waste
def _is_content_transfer(name, inp):
    if name in CONTENT_TRANSFER_TOOLS:
        return True
    if name == 'Bash' and inp.get('command', '').lstrip().startswith('bd '):
        return True
    if 'worker_send' in name or 'worker_merge' in name:
        return True
    return False


# Classify error type from tool_result text (called only when is_error=True)
def _classify_failure(text):
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


# Build waste, failed, and content-transfer pair lists from matched tool_use + tool_result pairs
def _build_pairs(tool_uses, tool_results):
    waste, failed, ct = [], [], []
    for tid, tu in tool_uses.items():
        tr = tool_results.get(tid)
        if tr is None:
            continue
        ratio = tu['input_chars'] / max(tr['output_chars'], 1)
        if tr['is_error']:
            failed.append({**tu, 'error_type': _classify_failure(tr['text']),
                           'ratio': ratio, 'output_chars': tr['output_chars']})
        if tu['is_ct']:
            ct.append({**tu, 'ratio': ratio, 'output_chars': tr['output_chars']})
        elif ratio >= WASTE_RATIO_MIN and tu['input_chars'] >= WASTE_INPUT_MIN:
            waste.append({**tu, 'ratio': ratio, 'output_chars': tr['output_chars']})
    return waste, failed, ct


# Aggregate waste pairs by (tool_name, sig)
def _aggregate_waste(waste_pairs):
    groups = {}
    for p in waste_pairs:
        key = (p['name'], p['sig'])
        if key not in groups:
            groups[key] = {'count': 0, 'total_input': 0, 'total_ratio': 0.0,
                           'example': p['raw_example']}
        g = groups[key]
        g['count'] += 1
        g['total_input'] += p['input_chars']
        g['total_ratio'] += p['ratio']
    return groups


# Aggregate failed pairs by (tool_name, sig, error_type)
def _aggregate_failed(failed_pairs):
    groups = {}
    for p in failed_pairs:
        key = (p['name'], p['sig'], p['error_type'])
        if key not in groups:
            groups[key] = {'count': 0, 'total_input': 0, 'example': p['raw_example']}
        g = groups[key]
        g['count'] += 1
        g['total_input'] += p['input_chars']
    return groups


# Compute per-source summary stats for section 1
def _per_source_stats(tool_uses, waste_pairs, failed_pairs, ct_pairs, jsonl_paths):
    stats = {}
    for path in jsonl_paths:
        label  = _source_label(path)
        total  = sum(1 for tu in tool_uses.values()  if tu['source'] == label)
        ct     = sum(1 for p  in ct_pairs             if p['source']  == label)
        waste  = sum(1 for p  in waste_pairs          if p['source']  == label)
        failed = sum(1 for p  in failed_pairs         if p['source']  == label)
        waste_input = sum(p['input_chars'] for p in waste_pairs if p['source'] == label)
        by_sig = defaultdict(int)
        for p in waste_pairs:
            if p['source'] == label:
                by_sig[p['sig']] += p['input_chars']
        dominant = max(by_sig, key=by_sig.get) if by_sig else '—'
        stats[label] = {'total': total, 'content_transfer': ct, 'waste': waste,
                        'failed': failed, 'waste_input': waste_input, 'dominant': dominant}
    return stats


# Classify wrapper complexity from signature features
def _classify_complexity(sig, tool):
    if tool == 'Bash':
        # Heredoc / inline Python → structural (use Write+script instead)
        if '<<' in sig or "python3 << '" in sig or 'python3 -c' in sig:
            return 'structural'
        if any(op in sig for op in ('|', '&&', '||')):
            return 'medium'
        if 'bd ' in sig or '<BEAD_ID>' in sig:
            return 'medium'
    return 'trivial'


# Derive proposed wrapper name from signature tokens and tool
def _derive_wrapper_name(sig, tool):
    # Skip past shell variable assignments (VAR=... or VAR=$(...)
    s = re.sub(r'^[A-Z_][A-Z0-9_]*=\S*\s*', '', sig).strip()
    tokens = s.split()
    if not tokens:
        return f'{tool.lower()}-wrapper'
    first = tokens[0].lower().rstrip('/').split('(')[0]  # strip shell subshell openers
    # Remove placeholder markers from name
    first = re.sub(r'[<>\$"\']', '', first).strip('-').strip()
    if not first:
        return f'{tool.lower()}-wrapper'
    for alias in ('./venv/bin/python', './venv/bin/python3', 'python3', 'python'):
        if first == alias:
            first = 'python'
            break
    if first == 'worker-cli' and len(tokens) > 1:
        return f'worker-{tokens[1]}'
    # Only extract subcmd for tools with actual meaningful subcommands (not content-bearing tokens)
    if first in ('git', 'bd', 'grep', 'find', 'jq') and len(tokens) > 1:
        subcmd = re.sub(r'[<>\$"\']', '', tokens[1]).strip('-').strip()
        if subcmd and not subcmd.startswith('<'):
            return f'{first}-{subcmd}'
    return f'{first}-wrapper'


# Format char count as Nk or N
def _fmt_k(n):
    return f'{n // 1000}k' if n >= 1000 else str(n)


# Assemble the full Markdown report
def _build_report(jsonl_paths, per_source_events, tool_uses,
                  source_stats, waste_pairs, waste_groups,
                  failed_pairs, failed_groups, ct_pairs):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    L = []

    L += [f'# Session Waste Patterns — 2026-04-22', '',
          f'*Generated: {now}*', '',
          'Source: 6 proxy JSONLs (4 previous session + 2 current session).', '',
          '## Source JSONLs', '']
    for path in jsonl_paths:
        label    = _source_label(path)
        evs      = per_source_events.get(label, [])
        tu_count = sum(1 for tu in tool_uses.values() if tu['source'] == label)
        L.append(f'- `{os.path.basename(path)}` ({len(evs)} events, {tu_count} tool_use blocks)')
    total_tu = len(tool_uses)
    L += ['', f'Total sessions analyzed: {len(jsonl_paths)}. Total unique tool_use blocks: {total_tu}.', '']

    L += _render_source_summary(source_stats, jsonl_paths)
    L += _render_tool_breakdown(waste_pairs)
    L += _render_ct_breakdown(ct_pairs)
    L += _render_bash_patterns(waste_pairs)
    L += _render_other_tools(waste_pairs)
    L += _render_failed_calls(failed_pairs, failed_groups)
    L += _render_wrapper_candidates(waste_groups, failed_groups)

    return '\n'.join(L)


# Render section 1: per-source summary table (includes Content-Transfer column)
def _render_source_summary(source_stats, jsonl_paths):
    L = ['## 1. Per-Source Summary', '',
         '| Source | Total Calls | Content-Transfer | Waste Calls (ratio≥3) | Failed Calls | Total Waste Input | Dominant Offender |',
         '|---|---|---|---|---|---|---|']
    for path in jsonl_paths:
        label = _source_label(path)
        s = source_stats.get(label, {})
        dom = s.get('dominant', '—')
        if len(dom) > 50:
            dom = dom[:50] + '…'
        dom = dom.replace('|', '\\|')
        L.append(
            f"| {label} | {s.get('total', 0)} | {s.get('content_transfer', 0)} |"
            f" {s.get('waste', 0)} | {s.get('failed', 0)}"
            f" | {_fmt_k(s.get('waste_input', 0))} chars | `{dom}` |"
        )
    return L + ['']


# Render section 2: tool breakdown aggregated over all sources
def _render_tool_breakdown(waste_pairs):
    by_tool = defaultdict(lambda: {'count': 0, 'total_input': 0, 'total_ratio': 0.0})
    total_input = sum(p['input_chars'] for p in waste_pairs)
    for p in waste_pairs:
        t = by_tool[p['name']]
        t['count'] += 1
        t['total_input'] += p['input_chars']
        t['total_ratio'] += p['ratio']
    L = ['## 2. Tool Breakdown — Actionable Waste (non-content-transfer, aggregated over all 6)', '',
         '| Tool | Waste Calls | Total Waste Input | Avg Ratio | % of All Waste Input |',
         '|---|---|---|---|---|']
    for tool, s in sorted(by_tool.items(), key=lambda x: -x[1]['total_input']):
        avg_r = s['total_ratio'] / s['count'] if s['count'] else 0
        pct   = 100 * s['total_input'] / total_input if total_input else 0
        L.append(f"| {tool} | {s['count']} | {s['total_input']:,} | {avg_r:.2f} | {pct:.1f}% |")
    if not by_tool:
        L.append('*(no waste calls detected)*')
    return L + ['']


# Render section 2b: content-transfer tool breakdown (large input by design — not waste)
def _render_ct_breakdown(ct_pairs):
    L = ['## 2b. Content-Transfer Breakdown (large input by design — excluded from waste analysis)', '',
         '*Write, Edit, Bash(`bd *`), worker_send: large tool input is expected and not structurally wrappable.*', '',
         '| Tool | Calls | Total Input |',
         '|---|---|---|']
    by_label = defaultdict(lambda: {'count': 0, 'total_input': 0})
    for p in ct_pairs:
        # Label bd-Bash separately from general Bash
        if p['name'] == 'Bash':
            label = 'Bash (bd *)'
        elif 'worker_send' in p['name']:
            label = 'worker_send'
        elif 'worker_merge' in p['name']:
            label = 'worker_merge'
        else:
            label = p['name']
        g = by_label[label]
        g['count'] += 1
        g['total_input'] += p['input_chars']
    for label, g in sorted(by_label.items(), key=lambda x: -x[1]['total_input']):
        L.append(f"| {label} | {g['count']} | {g['total_input']:,} |")
    if not ct_pairs:
        L.append('*(no content-transfer calls detected)*')
    return L + ['']


# Render section 3: top Bash patterns grouped by normalized signature
def _render_bash_patterns(waste_pairs):
    bash_groups = defaultdict(lambda: {'count': 0, 'total_input': 0, 'example': ''})
    for p in waste_pairs:
        if p['name'] != 'Bash':
            continue
        g = bash_groups[p['sig']]
        g['count'] += 1
        g['total_input'] += p['input_chars']
        if not g['example']:
            g['example'] = p['raw_example']
    top = sorted(bash_groups.items(), key=lambda x: -x[1]['total_input'])[:BASH_TOP_N]
    L = ['## 3. Bash Pattern Groups (top 15 by total_input_chars)', '',
         '| # | Signature | Count | Total Input | Avg Input | Example (150c truncated) |',
         '|---|---|---|---|---|---|']
    for n, (sig, g) in enumerate(top, 1):
        avg = g['total_input'] // g['count']
        ex  = g['example'].replace('|', '\\|')
        L.append(f"| {n} | `{sig}` | {g['count']} | {g['total_input']:,} | {avg:,} | {ex} |")
    if not top:
        L.append('*(no Bash waste patterns detected)*')
    return L + ['']


# Render section 4: Grep / Glob / Read patterns above threshold
def _render_other_tools(waste_pairs):
    L = ['## 4. Other Tools (Grep / Glob / Read) — top patterns', '']
    for tool in ('Grep', 'Glob', 'Read'):
        tool_pairs = [p for p in waste_pairs if p['name'] == tool]
        if not tool_pairs:
            L += [f'### {tool}', '', 'No patterns above threshold.', '']
            continue
        by_sig = defaultdict(lambda: {'count': 0, 'total_input': 0, 'example': ''})
        for p in tool_pairs:
            g = by_sig[p['sig']]
            g['count'] += 1
            g['total_input'] += p['input_chars']
            if not g['example']:
                g['example'] = p['raw_example']
        qualifying = {s: g for s, g in by_sig.items()
                      if g['count'] >= OTHER_MIN_COUNT or g['total_input'] >= OTHER_MIN_INPUT}
        if not qualifying:
            L += [f'### {tool}', '', 'No patterns above threshold.', '']
            continue
        L += [f'### {tool}', '',
              '| # | Signature | Count | Total Input | Example |',
              '|---|---|---|---|---|']
        for n, (sig, g) in enumerate(sorted(qualifying.items(), key=lambda x: -x[1]['total_input']), 1):
            ex = g['example'].replace('|', '\\|')
            L.append(f"| {n} | `{sig}` | {g['count']} | {g['total_input']:,} | {ex} |")
        L.append('')
    return L


# Render section 5: failed calls grouped by (tool, sig, error_type)
def _render_failed_calls(failed_pairs, failed_groups):
    L = ['## 5. Failed Calls (pure waste — zero useful output)', '']
    if not failed_pairs:
        return L + ['*(no failed calls detected)*', '']
    L += ['| Tool | Error Type | Signature | Count | Example |',
          '|---|---|---|---|---|']
    for (tool, sig, etype), g in sorted(failed_groups.items(), key=lambda x: -x[1]['count']):
        ex = g['example'].replace('|', '\\|')
        L.append(f"| {tool} | `{etype}` | `{sig}` | {g['count']} | {ex} |")
    return L + ['']


# Extract first recognizable command token from a normalized signature
def _first_command_token(sig):
    s = re.sub(r'^[A-Z_][A-Z0-9_]*=\S*\s*', '', sig).strip()
    tokens = s.split()
    if not tokens:
        return ''
    first = tokens[0].lower().rstrip('/').split('(')[0]
    first = re.sub(r'[<>\$"\']', '', first).strip('-').strip()
    for alias in ('./venv/bin/python', './venv/bin/python3'):
        if first == alias:
            return 'python3'
    return first


# Render section 6: wrapper candidates sorted by savings/complexity
def _render_wrapper_candidates(waste_groups, failed_groups):
    WEIGHT = {'trivial': 1, 'medium': 2, 'structural': 4}
    IMPL = {
        'trivial':    'A shell alias or thin argparse wrapper (≤20 LOC) eliminates the pattern.',
        'medium':     'A dedicated script or Skill with argument defaults handles all invocations (40–80 LOC).',
        'structural': 'Root fix requires a rule or config change (plugin.json / proxy_rules.json); individual wrapping will not address the root cause.',
    }
    candidates = []

    # ct tools already absent from waste_groups; also skip any residual worker_send entries
    SKIP_TOOLS = {'Write', 'Edit', 'mcp__plugin_iterative-dev_iterative-dev__worker_send'}
    for (tool, sig), g in waste_groups.items():
        if g['total_input'] < 100:
            continue
        if tool in SKIP_TOOLS:
            continue
        # Skip candidates whose first command token is not in known prefixes (garbage names)
        if _first_command_token(sig) not in KNOWN_PREFIXES:
            continue
        cplx  = _classify_complexity(sig, tool)
        name  = _derive_wrapper_name(sig, tool)
        score = g['total_input'] / WEIGHT[cplx]
        candidates.append({'name': name, 'sig': sig, 'tool': tool,
                           'count': g['count'], 'total_input': g['total_input'],
                           'complexity': cplx, 'score': score, 'is_failure': False})

    for (tool, sig, etype), g in failed_groups.items():
        if _first_command_token(sig) not in KNOWN_PREFIXES:
            continue
        cplx  = 'structural' if etype in ('tool-unavailable', 'parallel-cancel') else 'medium'
        name  = _derive_wrapper_name(sig, tool) + '-fix'
        score = g['total_input'] / WEIGHT[cplx]
        candidates.append({'name': name, 'sig': sig, 'tool': tool,
                           'count': g['count'], 'total_input': g['total_input'],
                           'complexity': cplx, 'score': score, 'is_failure': True,
                           'error_type': etype})

    seen: dict = {}
    for c in candidates:
        if c['name'] not in seen or c['score'] > seen[c['name']]['score']:
            seen[c['name']] = c
    selected = sorted(seen.values(), key=lambda x: -x['score'])[:8]

    L = ['## 6. Wrapper Candidates', '',
         '*Derived from sections 3 + 5. Sorted by estimated savings / implementation complexity.*', '']
    for c in selected:
        k = _fmt_k(c['total_input'])
        if c.get('is_failure'):
            etype = c.get('error_type', '')
            prose = (f"**`{c['name']}`** — addresses `{etype}` failures on `{c['sig']}`. "
                     f"Occurred {c['count']} times totalling {k} chars total input — all producing zero "
                     f"useful output. {IMPL[c['complexity']]}")
        else:
            prose = (f"**`{c['name']}`** — wraps `{c['sig']}` ({c['tool']}). "
                     f"Observed {c['count']} calls totalling {k} chars waste input this session "
                     f"(ratio≥3). {IMPL[c['complexity']]}")
        L += [prose, '']
    if not selected:
        L += ['*(insufficient data for wrapper candidates)*', '']
    return L


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
        description='Signature-normalized waste pattern report from Proxy JSONL files.'
    )
    parser.add_argument('proxy_jsonl', nargs='+', help='Path(s) to Proxy JSONL file(s)')
    parser.add_argument('--output', default=None, metavar='FILE',
                        help='Output markdown file path (default: stdout)')
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    run(args.proxy_jsonl, args.output)
