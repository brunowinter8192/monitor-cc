#!/usr/bin/env python3
"""Repetition-based Bash waste analysis from a single proxy-log JSONL snapshot.

Input:  path to one proxy-log JSONL (uses the entry with the highest message_count)
Output: markdown report to stdout (redirect to file recommended)

Usage:
    ./venv/bin/python dev/tool_use_analysis/waste_repetition.py \\
        src/logs/api_requests_opus_monitor_cc_1776855140.jsonl \\
        > /tmp/waste_rep.md 2>&1
"""

# INFRASTRUCTURE
import argparse
import json
import os
import re
import sys
from collections import defaultdict

SIG_MAX_CHARS = 200
SAMPLE_DISPLAY_CHARS = 80

_SIG_SUBS = [
    (re.compile(r'/Users/[^/\s]+/'),             '<HOME>/'),
    (re.compile(r'~/'),                           '<HOME>/'),
    (re.compile(r'api_requests_[\w-]+\.jsonl'),   '<LOG>'),
    (re.compile(r"'[^']*'"),                      '<STR>'),
    (re.compile(r'"[^"]*"'),                      '<STR>'),
    (re.compile(r'\b[0-9a-f]{8,}\b'),             '<HEX>'),
    (re.compile(r'\b\d{6,}\b'),                   '<N>'),
    (re.compile(r'(worker-cli\s+\w+\s+)[\w-]+'), r'\1<WORKER>'),
]

# (pattern, context, replacement, repl_len, label) — most specific first
KNOWN_SHORTCUTS = [
    (re.compile(r'/Users/brunowinter2000/Documents/ai/Monitor_CC(?=\s|$|/)'),
     'worker_cli_arg', 'c', 1,
     '/Users/brunowinter2000/Documents/ai/Monitor_CC → c  (worker-cli/git-check/dev-sync arg)'),
    (re.compile(r'~/Documents/ai/Monitor_CC(?=\s|$|/)'),
     'worker_cli_arg', 'c', 1,
     '~/Documents/ai/Monitor_CC → c  (worker-cli/git-check/dev-sync arg)'),
    (re.compile(r'/Users/brunowinter2000/Documents/ai/Monitor_CC(?=\s|$|/)'),
     'any', '~/Documents/ai/Monitor_CC', 25,
     '/Users/brunowinter2000/Documents/ai/Monitor_CC → ~/Documents/ai/Monitor_CC  (other contexts)'),
    (re.compile(r'/Users/brunowinter2000/'),
     'any', '~/', 2,
     '/Users/brunowinter2000/ → ~/  (anywhere)'),
]


# ORCHESTRATOR

def run(path, min_count, top_k):
    snapshot = _find_snapshot(path)
    if snapshot is None:
        print('ERROR: no entry with raw_payload found in the log', file=sys.stderr)
        sys.exit(1)
    cmds = _extract_bash_cmds(snapshot)
    groups = _rank_groups(cmds, min_count)
    shortcut_hits = _count_shortcuts(cmds)
    shortcut_total = _total_shortcut_savings(cmds)
    report = _build_report(path, cmds, groups, min_count, top_k, shortcut_hits, shortcut_total)
    print(report)


# FUNCTIONS

# Find entry with highest message_count — the cumulative snapshot of the session
def _find_snapshot(path):
    best, best_count = None, -1
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
            count = len(d['raw_payload'].get('messages', []))
            if count > best_count:
                best, best_count = d, count
    return best


# Yield deduplicated Bash commands from snapshot assistant messages
def _extract_bash_cmds(snapshot):
    seen_ids = set()
    cmds = []
    for msg in snapshot['raw_payload'].get('messages', []):
        if msg.get('role') != 'assistant':
            continue
        content = msg.get('content', [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict) or blk.get('type') != 'tool_use':
                continue
            if blk.get('name') != 'Bash':
                continue
            bid = blk.get('id', '')
            if bid in seen_ids:
                continue
            seen_ids.add(bid)
            cmds.append(blk.get('input', {}).get('command', ''))
    return cmds


# Normalize a Bash command to a stable grouping signature
def _sig(cmd):
    s = cmd.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    for pat, repl in _SIG_SUBS:
        s = pat.sub(repl, s)
    return s[:SIG_MAX_CHARS]


# Return first whitespace token of signature (family grouping key), truncated
def _family_key(sig):
    tokens = sig.split()
    first = tokens[0] if tokens else '?'
    return first[:40] + ('…' if len(first) > 40 else '')


# Group commands by signature, filter by min_count, rank by count * avg_chars descending
def _rank_groups(cmds, min_count):
    raw = defaultdict(lambda: {'count': 0, 'total_chars': 0, 'sample': None})
    for cmd in cmds:
        s = _sig(cmd)
        g = raw[s]
        g['count'] += 1
        g['total_chars'] += len(cmd)
        if g['sample'] is None:
            g['sample'] = cmd
    result = []
    for sig, g in raw.items():
        if g['count'] < min_count:
            continue
        avg = g['total_chars'] // g['count']
        result.append({
            'sig': sig,
            'count': g['count'],
            'total_chars': g['total_chars'],
            'avg_chars': avg,
            'score': g['count'] * avg,
            'sample': g['sample'],
        })
    return sorted(result, key=lambda x: -x['score'])


# Return True if the cmd fragment at match_start is a worker-cli / git-check / dev-sync argument
def _ctx_worker_cli_arg(cmd, match_start):
    prefix = cmd[max(0, match_start - 80):match_start].rstrip()
    return bool(re.search(r'(worker-cli\s+\w+(\s+\S+)*|git-check|dev-sync)\s*$', prefix))


# Count per-rule occurrences and chars saved across all commands
def _count_shortcuts(cmds):
    results = []
    for pat, ctx, _repl, repl_len, label in KNOWN_SHORTCUTS:
        count = 0
        saved_per = 0
        for cmd in cmds:
            for m in pat.finditer(cmd):
                if ctx == 'worker_cli_arg' and not _ctx_worker_cli_arg(cmd, m.start()):
                    continue
                count += 1
                if saved_per == 0:
                    saved_per = len(m.group()) - repl_len
        results.append({'label': label, 'count': count,
                        'saved_per': saved_per, 'total': count * saved_per})
    return results


# Total unique shortcut savings — best rule wins per fragment, no double-counting across overlapping rules
def _total_shortcut_savings(cmds):
    total = 0
    for cmd in cmds:
        matches = []
        for pat, ctx, _repl, repl_len, _label in KNOWN_SHORTCUTS:
            for m in pat.finditer(cmd):
                if ctx == 'worker_cli_arg' and not _ctx_worker_cli_arg(cmd, m.start()):
                    continue
                matches.append((len(m.group()) - repl_len, m.start(), m.end()))
        matches.sort(key=lambda x: -x[0])
        taken = []
        for sav, start, end in matches:
            if not any(s < end and start < e for s, e in taken):
                total += sav
                taken.append((start, end))
    return total


# Assemble and return the full markdown report
def _build_report(path, cmds, groups, min_count, top_k, shortcut_hits, shortcut_total):
    total_bash = len(cmds)
    total_chars = sum(len(c) for c in cmds)
    distinct_sigs = len(set(_sig(c) for c in cmds))
    repeated_chars = sum(g['total_chars'] for g in groups)

    L = []
    L.append(f'# Bash Repetition Waste — {os.path.basename(path)}')
    L.append('')
    L.append(
        f'Total Bash calls: **{total_bash}** | '
        f'Distinct signatures: **{distinct_sigs}** | '
        f'Total chars: **{total_chars:,}** | '
        f'Repeated-sig chars (count≥{min_count}): **{repeated_chars:,}** | '
        f'Path-shortcut-saveable: **{shortcut_total:,}** chars'
    )
    L.append('')

    L.append('## Family Overview')
    L.append('')
    families = defaultdict(lambda: {'count': 0, 'total_chars': 0})
    for g in groups:
        fk = _family_key(g['sig'])
        families[fk]['count'] += g['count']
        families[fk]['total_chars'] += g['total_chars']
    if families:
        L.append('| Family (first token) | Calls | Total chars |')
        L.append('|---|---|---|')
        for fk, fs in sorted(families.items(), key=lambda x: -x[1]['total_chars']):
            L.append(f'| `{fk}` | {fs["count"]} | {fs["total_chars"]:,} |')
    else:
        L.append(f'*(no groups with count ≥ {min_count})*')
    L.append('')

    shown = groups[:top_k]
    L.append(f'## Repetition Groups (count ≥ {min_count}, top {top_k} by count×avg_chars)')
    L.append('')
    if not shown:
        L.append(f'*(no repetition groups found with count ≥ {min_count})*')
    else:
        L.append('| Rank | Count | Avg chars | Total chars | Signature (80c) | Sample (80c) |')
        L.append('|---|---|---|---|---|---|')
        for rank, g in enumerate(shown, 1):
            sig80 = g['sig'][:SAMPLE_DISPLAY_CHARS].replace('|', '\\|')
            sample80 = g['sample'].replace('\n', ' ')[:SAMPLE_DISPLAY_CHARS].replace('|', '\\|')
            L.append(
                f"| {rank} | {g['count']} | {g['avg_chars']:,} | {g['total_chars']:,} "
                f"| `{sig80}` | {sample80} |"
            )
    L.append('')

    L.append('## Replaceable Path Fragments')
    L.append('')
    L.append('| Rule | Occurrences | Chars saved / occurrence | Total saved |')
    L.append('|---|---|---|---|')
    for hit in shortcut_hits:
        L.append(
            f"| {hit['label']} | {hit['count']} "
            f"| {hit['saved_per']} | {hit['total']:,} |"
        )
    L.append('')
    L.append(f"**Total saveable via path-shortcuts: {shortcut_total:,} chars**")
    L.append('')

    if shown:
        full_count = min(10, len(shown))
        L.append(f'## Full Samples (top {full_count})')
        L.append('')
        for rank, g in enumerate(shown[:full_count], 1):
            L.append(f'### {rank}. `{g["sig"][:80]}`')
            L.append('')
            L.append('```bash')
            L.append(g['sample'])
            L.append('```')
            L.append('')

    return '\n'.join(L)


def _parse_args():
    p = argparse.ArgumentParser(
        description='Repetition-based Bash waste analysis from a proxy-log JSONL snapshot.'
    )
    p.add_argument('proxy_jsonl', help='Path to proxy-log JSONL file')
    p.add_argument('--min-count', type=int, default=2, metavar='N',
                   help='Minimum occurrence count for a group (default: 2)')
    p.add_argument('--top', type=int, default=20, metavar='K',
                   help='Show top K groups in the table (default: 20)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    run(args.proxy_jsonl, args.min_count, args.top)
