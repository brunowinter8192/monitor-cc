# INFRASTRUCTURE
import os
from collections import defaultdict
from datetime import datetime

from extract_patterns_collect import _source_label
from extract_patterns_wrappers import _build_wrapper_candidates

BASH_TOP_N       = 15
OTHER_MIN_COUNT  = 2
OTHER_MIN_INPUT  = 500

# FUNCTIONS

def _fmt_k(n):
    return f'{n // 1000}k' if n >= 1000 else str(n)


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


def _render_ct_breakdown(ct_pairs):
    L = ['## 2b. Content-Transfer Breakdown (large input by design — excluded from waste analysis)', '',
         '*Write, Edit, Bash(ct): bd, cat>, git-commit-long, worker-cli-send — large input expected, not wrappable.*', '',
         '| Tool | Calls | Total Input |',
         '|---|---|---|']
    by_label = defaultdict(lambda: {'count': 0, 'total_input': 0})
    for p in ct_pairs:
        if p['name'] == 'Bash':
            label = 'Bash (ct)'
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


def _render_wrapper_candidates(waste_groups, failed_groups):
    IMPL = {
        'trivial':    'A shell alias or thin argparse wrapper (≤20 LOC) eliminates the pattern.',
        'medium':     'A dedicated script or Skill with argument defaults handles all invocations (40–80 LOC).',
        'structural': 'Root fix requires a rule or config change (plugin.json / proxy_rules.json); individual wrapping will not address the root cause.',
    }
    selected = _build_wrapper_candidates(waste_groups, failed_groups)

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
