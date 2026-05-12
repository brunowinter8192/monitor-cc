#!/usr/bin/env python3
"""Match tool_use/tool_result pairs from Proxy JSONL files against Hard-Rules in tool-use.md.
Reports per-rule compliance with violations and an uncategorized-failures bucket.

Input:  src/logs/api_requests_*.jsonl (one or more paths, positional args)
Output: rule compliance report (--output FILE or stdout)
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

RULES_DEFAULT = Path.home() / '.claude/shared-rules/global/tool-use.md'
TOTAL_RULES = 16
SIGNATURE_RULES = {2, 3, 6, 9, 10, 12, 13, 14}
INPUT_PREVIEW_CHARS = 120
ERROR_PREVIEW_CHARS = 300

# Rule 3 — extensions indicating explicit file targets (not broad-scope directory scan)
_FILE_EXTENSIONS = {'.py', '.md', '.sh', '.json', '.ts', '.jsonl', '.txt',
                    '.yaml', '.yml', '.toml', '.cfg', '.ini', '.js', '.go', '.rs'}
# Rule 14 — trivial read-only commands that must not run in background
_BG_TRIVIAL_RE = re.compile(r'^(grep|cat|ls|wc|git\s+status|head|tail)\b')


# ORCHESTRATOR

def rule_compliance_workflow(proxy_paths, rules_path, output_path):
    rules = _parse_rules(rules_path)

    events_by_log = {}
    for path in proxy_paths:
        events_by_log[path] = _load_proxy(path)

    tool_uses = {}
    tool_results = {}
    for path, events in events_by_log.items():
        label = _log_label(path)
        _collect_tool_uses(events, label, tool_uses)
        _collect_tool_results(events, tool_results)

    pairs = _build_pairs(tool_uses, tool_results)
    violations, uncategorized = _run_signatures(pairs)
    report = _build_report(proxy_paths, events_by_log, tool_uses, pairs,
                           violations, uncategorized, rules)
    _write_output(report, output_path)


# FUNCTIONS

# Parse Hard-Rules section from tool-use.md → dict[int, {num, title, summary}]
def _parse_rules(rules_path):
    rules = {}
    try:
        lines = Path(rules_path).expanduser().read_text(encoding='utf-8').splitlines()
    except (OSError, IOError) as e:
        print(f'Warning: cannot read rules file: {e}', file=sys.stderr)
        return rules

    in_hr = False
    cur = None
    para = []
    collecting = False
    in_fence = False

    def save():
        if cur and cur['num'] not in rules:
            rules[cur['num']] = {**cur, 'summary': ' '.join(para)[:400]}

    for line in lines:
        if not in_hr:
            if line.startswith('## Hard Rules'):
                in_hr = True
            continue
        if line.startswith('## Soft Rules') or line.rstrip() == '---':
            save()
            break
        m = re.match(r'^### (\d+)\. (.+)$', line)
        if m:
            save()
            cur = {'num': int(m.group(1)), 'title': m.group(2).strip()}
            para = []
            collecting = True
            in_fence = False
            continue
        if not collecting or cur is None:
            continue
        if line.startswith('```'):
            in_fence = not in_fence
            if in_fence:
                collecting = False
            continue
        if in_fence:
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('|'):
            para.append(stripped)
        elif not stripped and para:
            collecting = False
    else:
        save()
    return rules


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


# Build session label from log filename (opus / worker:<name>)
def _log_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_worker_'):
        name = base.replace('api_requests_worker_', '').rsplit('_', 1)[0]
        return f'worker:{name}'
    if base.startswith('api_requests_opus_'):
        return 'opus'
    return base


# Collect all tool_use blocks — deduped by id, stores full input dict
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
                inp_str = json.dumps(inp)
                out[bid] = {
                    'name': blk.get('name', ''),
                    'input_full': inp,
                    'input_preview': inp_str[:INPUT_PREVIEW_CHARS],
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
                out[tid] = {'is_error': bool(blk.get('is_error', False)), 'text': text}


# Join tool_use + tool_result into unified pair dicts — ALL tool_uses included
def _build_pairs(tool_uses, tool_results):
    pairs = []
    for bid, tu in tool_uses.items():
        tr = tool_results.get(bid, {})
        pairs.append({
            'bid': bid,
            'tool_name': tu['name'],
            'label': tu['label'],
            'ts': tu['ts'],
            'input_full': tu['input_full'],
            'input_preview': tu['input_preview'],
            'is_error': tr.get('is_error', False),
            'error_text': tr.get('text', ''),
        })
    pairs.sort(key=lambda x: (x['label'], x['ts']))
    return pairs


# Rule 2 — No Bash heredoc file creation (cat > file << EOF; not >> which is append)
def _sig_rule2(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if re.search(r'cat\s*(?!>)>\s*\S+\s*<<\s*[\'"]?EOF', cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 3 — Recursive grep without --include= on directory target (broad-scope)
def _sig_rule3(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if not re.search(r'\bgrep\b[^|&\n]*-[a-zA-Z]*r', cmd):
        return False, None
    if '--include=' in cmd:
        return False, None
    # Guard: last non-flag token with known file extension → explicit file target, skip
    for tok in reversed(cmd.split()):
        if not tok.startswith('-'):
            if os.path.splitext(tok)[1].lower() in _FILE_EXTENSIONS:
                return False, None
            break
    return True, cmd[:INPUT_PREVIEW_CHARS]


# Rule 6 — Parallel Bash cancelled by runtime
def _sig_rule6(pair):
    if not pair['is_error']:
        return False, None
    if 'Cancelled: parallel tool call' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 9 — Read before Edit/Write
def _sig_rule9(pair):
    if not pair['is_error']:
        return False, None
    if 'File has not been read yet' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 10 — Branch-name ambiguity (git fatal: ambiguous argument)
def _sig_rule10(pair):
    if pair['tool_name'] != 'Bash' or not pair['is_error']:
        return False, None
    if 'fatal: ambiguous argument' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 12 — sleep forbidden (canonical form sleep N && echo done + bg=True is allowed)
def _sig_rule12(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    cmd = pair['input_full'].get('command', '')
    if not re.search(r'\bsleep\s+\d', cmd):
        return False, None
    if (re.fullmatch(r'sleep\s+\d+\s*&&\s*echo done', cmd.strip())
            and pair['input_full'].get('run_in_background')):
        return False, None
    return True, cmd[:INPUT_PREVIEW_CHARS]


# Rule 13 — .claire/ typo in path (requires is_error; checks error_text + file_path only)
def _sig_rule13(pair):
    if not pair['is_error']:
        return False, None
    if '.claire/' in pair['error_text']:
        return True, pair['error_text'][:INPUT_PREVIEW_CHARS]
    if pair['tool_name'] in ('Read', 'Write', 'Edit'):
        fp = pair['input_full'].get('file_path', '')
        if '.claire/' in fp:
            return True, fp[:INPUT_PREVIEW_CHARS]
    return False, None


# Rule 14 — Trivial read-only command run in background unnecessarily
def _sig_rule14(pair):
    if pair['tool_name'] != 'Bash':
        return False, None
    if not pair['input_full'].get('run_in_background'):
        return False, None
    cmd = pair['input_full'].get('command', '').strip()
    if _BG_TRIVIAL_RE.match(cmd):
        return True, cmd[:INPUT_PREVIEW_CHARS]
    return False, None


# Run all signatures against each pair — violations by rule_id + uncategorized failures
def _run_signatures(pairs):
    violations = defaultdict(list)
    uncategorized = []
    sigs = [(2, _sig_rule2), (3, _sig_rule3), (6, _sig_rule6), (9, _sig_rule9),
            (10, _sig_rule10), (12, _sig_rule12), (13, _sig_rule13), (14, _sig_rule14)]
    for pair in pairs:
        matched = []
        for rule_id, fn in sigs:
            hit, evidence = fn(pair)
            if hit:
                matched.append(rule_id)
                violations[rule_id].append({
                    'rule_id': rule_id,
                    'tool_name': pair['tool_name'],
                    'label': pair['label'],
                    'ts': pair['ts'],
                    'input_preview': pair['input_preview'],
                    'error_text': pair['error_text'],
                    'evidence': evidence or '',
                })
        if pair['is_error'] and not matched:
            uncategorized.append(pair)
    return violations, uncategorized


# Render full Markdown compliance report
def _build_report(proxy_paths, events_by_log, tool_uses, pairs, violations, uncategorized, rules):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    L = [f'# Rule Compliance Analysis — {now}', '', '## Source JSONLs', '']
    total_tu = len(tool_uses)
    for path in proxy_paths:
        label = _log_label(path)
        tu_count = sum(1 for tu in tool_uses.values() if tu['label'] == label)
        L.append(f'- `{os.path.basename(path)}` ({len(events_by_log.get(path, []))} events, '
                 f'{tu_count} tool_use) — `{label}`')
    total_fail = sum(1 for p in pairs if p['is_error'])
    rules_viol = sum(1 for r in SIGNATURE_RULES if violations.get(r))
    L += ['', '## Summary', '',
          f'- Total tool_use blocks: {total_tu}',
          f'- Failures (is_error=True): {total_fail}',
          f'- Rules with violations: {rules_viol} / {TOTAL_RULES}',
          f'- Uncategorized failures: {len(uncategorized)}', '']

    L += ['## Per-Rule Compliance', '',
          '| Rule | Title | Status | Violations | Sample |',
          '|------|-------|--------|------------|--------|']
    for num in range(1, TOTAL_RULES + 1):
        rule = rules.get(num, {'title': f'Rule {num}', 'summary': ''})
        title = rule['title'][:50]
        if num not in SIGNATURE_RULES:
            L.append(f'| {num} | {title} | — | — | *(no signature in v1)* |')
        else:
            vlist = violations.get(num, [])
            if vlist:
                v0 = vlist[0]
                sample = f'`{v0["tool_name"]}` {v0["evidence"][:35].replace(chr(10)," ").replace("|","｜")}'
                L.append(f'| {num} | {title} | ⚠ violated | {len(vlist)} | {sample} |')
            else:
                L.append(f'| {num} | {title} | ✅ clean | 0 | — |')
    L.append('')

    L += ['## Violations Detail', '']
    any_v = False
    for num in range(1, TOTAL_RULES + 1):
        vlist = violations.get(num, [])
        if not vlist:
            continue
        any_v = True
        rule = rules.get(num, {'title': f'Rule {num}', 'summary': ''})
        L += [f'### Rule {num} — {rule["title"]}', '']
        if rule.get('summary'):
            L += [f'> {rule["summary"][:300]}', '']
        L += [f'**Violations ({len(vlist)}):**', '']
        for i, v in enumerate(vlist, 1):
            ts = _format_ts_local(v['ts'])
            L += [f'#### [{i}] {v["label"]} — {ts} — {v["tool_name"]}', '']
            if v['input_preview']:
                L.append(f'- **Input:** `{v["input_preview"]}`')
            if v['evidence'] and v['evidence'] != v['input_preview']:
                L.append(f'- **Evidence:** `{v["evidence"][:120]}`')
            if v['error_text']:
                err = v['error_text'][:ERROR_PREVIEW_CHARS].replace('\n', ' ')
                L.append(f'- **Error:** `{err}`')
            else:
                L.append('- **Error:** *(call succeeded — input-based violation)*')
            L.append('')
        L += ['---', '']
    if not any_v:
        L += ['*No violations detected.*', '', '---', '']

    L += ['## Uncategorized Failures', '']
    if uncategorized:
        L.append(f'{len(uncategorized)} failure(s) not matched by any rule — '
                 f'candidates for new or sharpened signatures.')
        L.append('')
        for i, p in enumerate(uncategorized, 1):
            ts = _format_ts_local(p['ts'])
            L += [f'### [{i}] {p["tool_name"]} — {p["label"]} — {ts}', '']
            if p['input_preview']:
                L.append(f'- **Input:** `{p["input_preview"]}`')
            L.append(f'- **Error:** `{p["error_text"][:ERROR_PREVIEW_CHARS].replace(chr(10), " ")}`')
            L.append('')
    else:
        L += ['*All failures matched at least one rule.*', '']

    L += ['## Recommendations', '']
    recs = []
    for num in range(1, TOTAL_RULES + 1):
        vlist = violations.get(num, [])
        if not vlist:
            continue
        rule = rules.get(num, {'title': f'Rule {num}'})
        labels = [v['label'] for v in vlist]
        dominant = max(set(labels), key=labels.count)
        recs.append(f'- **Rule {num} ({rule["title"][:40]}):** {len(vlist)} violation(s), '
                    f'mostly `{dominant}`. Review all flagged calls.')
    L += recs if recs else ['*No violations — no recommendations.*']
    L.append('')
    return '\n'.join(L)


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
    p = argparse.ArgumentParser(
        description='Match proxy JSONL tool calls against tool-use.md Hard-Rules.'
    )
    p.add_argument('proxy_jsonl', nargs='+',
                   help='Path(s) to Proxy JSONL file(s) under src/logs/')
    p.add_argument('--rules', default=str(RULES_DEFAULT), metavar='PATH',
                   help=f'Path to tool-use.md (default: {RULES_DEFAULT})')
    p.add_argument('--output', default=None, metavar='FILE',
                   help='Output markdown file path (default: stdout)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    rule_compliance_workflow(args.proxy_jsonl, args.rules, args.output)
