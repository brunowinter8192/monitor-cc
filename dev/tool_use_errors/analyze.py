# INFRASTRUCTURE
import argparse
import glob as _glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

INPUT_PREV  = 120   # chars for input preview
ERROR_PREV  = 200   # chars for error preview

# ---- Failure-classification markers ----
_HOOK_BLOCK_RE   = re.compile(r'PreToolUse:\w+ hook error:.*BLOCKED')
_GIT_AMBIG_RE    = re.compile(r'fatal: ambiguous argument')
_PARALLEL_TAG    = "Cancelled: parallel tool call"
_UNAVAIL_TAG     = "Error: No such tool available"
_STR_NOT_FOUND   = "String to replace not found"
_VALIDATION_TAG  = "Input validation error"
_TOOL_ERR_OPEN   = "<tool_use_error>"
_READ_BEFORE_TAG = "File has not been read yet"
_FILE_MODIFIED   = "File has been modified since read"
_OVERSIZE_RE     = re.compile(r'exceeds maximum allowed (size|tokens)')
_NOOP_EDIT_TAG   = "No changes to make: old_string and new_string"
_USER_REJECT_TAG = "The user doesn't want to proceed"
_UNKNOWN_SKILL   = "Unknown skill:"

# ---- Rule-violation signatures ----
_RULE11_DIAG_RE = re.compile(
    r'(^|&&|\|\|)\s*(grep\b[^&|]*|ls\s+[^-&|][^&|]*|wc\s+-l\s+[^&|]+'
    r'|\[\s+-[fd]\s+[^&|]+\s+\]|test\s+-[fd]\s+[^&|]+)\s*&&'
)
_KNOWN_EXT = {'.py','.md','.sh','.json','.ts','.jsonl','.txt','.yaml','.yml',
              '.toml','.cfg','.ini','.js','.go','.rs'}

# hookability buckets: pre-blockable | pre-rewritable | prompt-hook-candidate
#                     | not-statically-hookable | runtime-only | already-hooked
PATTERNS = [
    # id, title, hookability, hook, sig
    # --- Error-based signatures: require is_error=True to avoid matching RAG/log output ---
    ('parallel-cancel',    'Parallel Bash cancelled by runtime',
     'runtime-only',        None,
     lambda p: (p['is_error'] and _PARALLEL_TAG in p['err'], None)),

    ('read-before-edit',   'Edit/Write without prior Read (session state)',
     'not-statically-hookable', None,
     lambda p: (p['is_error'] and _READ_BEFORE_TAG in p['err'], None)),

    ('file-modified',      'File modified between Read and Edit',
     'not-statically-hookable', None,
     lambda p: (p['is_error'] and _FILE_MODIFIED in p['err'], None)),

    ('user-rejected',      'User explicitly rejected tool call',
     'not-statically-hookable', None,
     lambda p: (p['is_error'] and _USER_REJECT_TAG in p['err'], None)),

    ('hook-blocked',       'Blocked by a PreToolUse hook (already handled)',
     'already-hooked',      None,
     lambda p: (p['is_error'] and bool(_HOOK_BLOCK_RE.search(p['err'])), None)),

    ('git-ambiguous',      'git diff/log with bare branch name, missing "--"',
     'pre-rewritable',      None,
     lambda p: (p['is_error'] and bool(_GIT_AMBIG_RE.search(p['err'])), None)),

    ('edit-string-not-found', 'Edit: old_string not present in file',
     'prompt-hook-candidate', None,
     lambda p: (p['is_error'] and (_STR_NOT_FOUND in p['err'] or
                (_TOOL_ERR_OPEN in p['err'] and _STR_NOT_FOUND in p['err'])), None)),

    ('validation-error',   'Tool input validation error',
     'pre-blockable',       None,
     lambda p: (p['is_error'] and (_VALIDATION_TAG in p['err'] or
                (_TOOL_ERR_OPEN in p['err'] and 'validation' in p['err'].lower())), None)),

    ('tool-unavailable',   'Unknown/unregistered MCP tool or Skill',
     'pre-blockable',       None,
     lambda p: (p['is_error'] and (_UNAVAIL_TAG in p['err'] or _UNKNOWN_SKILL in p['err']), None)),

    ('read-oversize',      'Read on file > 256KB or > 25k tokens without offset/limit',
     'pre-blockable',       'block_read_oversize.py (256KB only)',
     lambda p: (p['is_error'] and bool(_OVERSIZE_RE.search(p['err'])), None)),

    ('noop-edit',          'Edit with old_string == new_string',
     'already-hooked',      'block_noop_edit.py',
     lambda p: (p['is_error'] and _NOOP_EDIT_TAG in p['err'], None)),

    ('cat-heredoc',        'Bash heredoc file creation (cat > file << EOF)',
     'pre-blockable',       None,
     lambda p: (p['tool'] == 'Bash' and
                bool(re.search(r'cat\s*(?!>)>\s*\S+\s*<<\s*[\'"]?EOF', p['cmd'])), None)),

    ('broad-grep',         'Recursive grep without --include= scope (Rule 3)',
     'already-hooked',      'block_broad_grep.py',
     lambda p: _check_broad_grep(p)),

    ('sleep-noncanonical', 'sleep N in non-canonical form (Rule 12)',
     'already-hooked',      'block_chained_sleep.py',
     lambda p: (p['tool'] == 'Bash' and
                bool(re.search(r'\bsleep\s+\d', p['cmd'])) and
                not (re.fullmatch(r'\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*', p['cmd'])
                     and p.get('run_in_bg')), None)),

    ('claire-typo',        '.claire/ typo in path (Rule 13)',
     'already-hooked',      'block_path_typo.py',
     lambda p: (('.claire/' in p['cmd'])
                if p['tool'] == 'Bash'
                else '.claire/' in p.get('fp', ''), None)),

    ('bg-trivial',         'Trivial read-only command run_in_background=true (Rule 14)',
     'already-hooked',      'block_unauthorized_background.py',
     lambda p: (p['tool'] == 'Bash' and bool(p.get('run_in_bg'))
                and bool(re.match(r'\s*(grep|cat|ls|wc|git\s+status|head|tail)\b', p['cmd'])), None)),

    ('venv-no-redirect',   './venv/bin/python script.py without redirect',
     'already-hooked',      'block_venv_no_redirect.py',
     lambda p: (p['tool'] == 'Bash'
                and bool(re.search(r'\.?\.?/?venv/bin/python\s+\S+\.py\b', p['cmd']))
                and not re.search(r'>\s*\S+', p['cmd']), None)),

    ('diag-chain-and',     'Diagnostic Bash chain using && (Rule 11)',
     'prompt-hook-candidate', None,
     lambda p: (p['tool'] == 'Bash' and '&&' in p['cmd']
                and bool(_RULE11_DIAG_RE.search(p['cmd'])), None)),
]

HOOKABILITY_ORDER = ['pre-blockable', 'pre-rewritable', 'prompt-hook-candidate',
                     'not-statically-hookable', 'runtime-only', 'already-hooked']


# ORCHESTRATOR

# Load proxy JSONLs, classify failures + rule violations, write hookability report
def analyze_tool_errors_workflow(proxy_paths: list, output_path: str | None) -> None:
    events_by_log: dict = {}
    for path in proxy_paths:
        events_by_log[path] = _load_proxy(path)

    tool_uses: dict = {}
    tool_results: dict = {}
    for path, events in events_by_log.items():
        label = _log_label(path)
        _collect_tool_uses(events, label, tool_uses)
        _collect_tool_results(events, tool_results)

    pairs = _build_pairs(tool_uses, tool_results)
    violations, uncategorized = _run_sigs(pairs)
    report = _build_report(proxy_paths, events_by_log, tool_uses, pairs, violations, uncategorized)
    _write_output(report, output_path)


# FUNCTIONS

# Load proxy JSONL — entries with raw_payload only
def _load_proxy(path: str) -> list:
    events = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except json.JSONDecodeError: continue
            if d.get('raw_payload') is None: continue
            d['_path'] = path
            events.append(d)
    return events

# Label from log filename: opus / worker:<name>
def _log_label(path: str) -> str:
    base = os.path.basename(path)
    if base.startswith('api_requests_worker_'):
        name = base.replace('api_requests_worker_', '').rsplit('_', 1)[0]
        return f'worker:{name}'
    if base.startswith('api_requests_opus_'): return 'opus'
    return base

# Collect all tool_use blocks — deduped by id, stores full input dict
def _collect_tool_uses(events: list, label: str, out: dict) -> None:
    for ev in events:
        ts = ev.get('timestamp', '')
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list): continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_use': continue
                bid = blk.get('id', '')
                if not bid or bid in out: continue
                inp = blk.get('input', {})
                out[bid] = {
                    'name': blk.get('name', ''),
                    'input_full': inp,
                    'input_preview': json.dumps(inp)[:INPUT_PREV],
                    'ts': ts, 'label': label,
                }

# Collect all tool_result blocks — deduped by tool_use_id
def _collect_tool_results(events: list, out: dict) -> None:
    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list): continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_result': continue
                tid = blk.get('tool_use_id', '')
                if not tid or tid in out: continue
                raw_c = blk.get('content', '')
                text = raw_c if isinstance(raw_c, str) else json.dumps(raw_c)
                out[tid] = {'is_error': bool(blk.get('is_error', False)), 'text': text}

# Join tool_use + tool_result into unified pair dicts
def _build_pairs(tool_uses: dict, tool_results: dict) -> list:
    pairs = []
    for bid, tu in tool_uses.items():
        tr = tool_results.get(bid, {})
        inp = tu['input_full']
        pairs.append({
            'bid': bid,
            'tool': tu['name'],
            'label': tu['label'],
            'ts': tu['ts'],
            'cmd': inp.get('command', '') or inp.get('file_path', ''),
            'fp': inp.get('file_path', ''),
            'run_in_bg': bool(inp.get('run_in_background', False)),
            'input_preview': tu['input_preview'],
            'is_error': tr.get('is_error', False),
            'err': tr.get('text', ''),
        })
    pairs.sort(key=lambda x: (x['label'], x['ts']))
    return pairs

# Run all signatures against each pair; return violations dict + unmatched error pairs
def _run_sigs(pairs: list) -> tuple:
    violations: dict = defaultdict(list)
    uncategorized: list = []
    for pair in pairs:
        matched = []
        for pat_id, _, _, _, sig in PATTERNS:
            try:
                hit, _ = sig(pair)
            except Exception:
                hit = False
            if hit:
                matched.append(pat_id)
                violations[pat_id].append(pair)
        if pair['is_error'] and not matched:
            uncategorized.append(pair)
    return violations, uncategorized

# broad_grep sig is too complex for a lambda — defined here
def _check_broad_grep(pair: dict) -> tuple:
    if pair['tool'] != 'Bash': return False, None
    cmd = pair['cmd']
    for seg in re.split(r'[;]|&&|\|\|', cmd):
        tokens = seg.split()
        if 'grep' not in tokens: continue
        gi = tokens.index('grep')
        has_r = has_include = False
        pat_idx = None
        for i, tok in enumerate(tokens[gi+1:], gi+1):
            if tok.startswith('--include='): has_include = True; continue
            if tok == '--recursive': has_r = True; continue
            if tok.startswith('-') and len(tok) > 1:
                if 'r' in tok[1:]: has_r = True
                continue
            pat_idx = i; break
        if not has_r or has_include: continue
        positionals = [t for t in tokens[(pat_idx or gi)+1:] if not t.startswith('-')]
        target = positionals[-1] if positionals else None
        if target:
            ext = os.path.splitext(target)[1].lower()
            if ext in _KNOWN_EXT or ('*' in target and '.' in target): continue
        return True, seg.strip()[:INPUT_PREV]
    return False, None

# Build the Markdown report
def _build_report(proxy_paths, events_by_log, tool_uses, pairs, violations, uncategorized) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_tu = len(tool_uses)
    total_fail = sum(1 for p in pairs if p['is_error'])
    L = [f'# Tool-Use Error Analysis — {now}', '', '## Source JSONLs', '']
    for path in proxy_paths:
        label = _log_label(path)
        tu_cnt = sum(1 for tu in tool_uses.values() if tu['label'] == label)
        L.append(f'- `{os.path.basename(path)}` ({len(events_by_log.get(path,[]))} events, {tu_cnt} tool_use) — `{label}`')
    L += ['', f'Total tool_use blocks: {total_tu}. Failures (is_error=True): {total_fail}.', '']

    # --- Hookability overview ---
    L += ['## Hookability Overview', '',
          '| Failure / Violation | Count | Hookability | Hook |',
          '|---|---|---|---|']
    for hk in HOOKABILITY_ORDER:
        for pat_id, title, hookability, hook, _ in PATTERNS:
            if hookability != hk: continue
            cnt = len(violations.get(pat_id, []))
            hook_cell = f'`{hook}`' if hook else '—'
            L.append(f'| {title} | {cnt} | {hookability} | {hook_cell} |')
    L.append('')

    # --- Coverage gaps (hookable/rewritable, no hook yet, ≥1 violation) ---
    L += ['## Coverage Gaps', '',
          'Pre-blockable or pre-rewritable patterns with violations AND no live hook:', '']
    gaps = [(pat_id, title, hookability, cnt)
            for pat_id, title, hookability, hook, _ in PATTERNS
            if hookability in ('pre-blockable', 'pre-rewritable') and not hook
            and (cnt := len(violations.get(pat_id, []))) > 0]
    if gaps:
        L += ['| Pattern | Violations | Hookability |', '|---|---|---|']
        for pat_id, title, hookability, cnt in sorted(gaps, key=lambda x: -x[3]):
            L.append(f'| {title} | {cnt} | {hookability} |')
    else:
        L.append('_No coverage gaps in this log set._')
    L.append('')

    # --- Per-pattern violations detail ---
    L += ['## Violations Detail', '']
    for pat_id, title, hookability, hook, _ in PATTERNS:
        vlist = violations.get(pat_id, [])
        if not vlist: continue
        hook_tag = f' — `{hook}`' if hook else ''
        L += [f'### `{pat_id}` — {title}',
              f'> Hookability: **{hookability}**{hook_tag}  Count: {len(vlist)}', '']
        for i, v in enumerate(vlist[:5], 1):
            ts = _fmt_ts(v['ts'])
            L += [f'**[{i}] {v["label"]} — {ts} — {v["tool"]}**', '']
            if v['input_preview']:
                L.append(f'- Input: `{v["input_preview"].replace(chr(10)," ")}`')
            if v['err']:
                L.append(f'- Error: `{v["err"][:ERROR_PREV].replace(chr(10)," ")}`')
            L.append('')
        if len(vlist) > 5:
            L.append(f'_…and {len(vlist)-5} more._')
        L += ['---', '']

    # --- Uncategorized errors ---
    L += ['## Uncategorized Failures', '']
    if uncategorized:
        L.append(f'{len(uncategorized)} failure(s) not matched by any pattern — candidates for new signatures.')
        L.append('')
        for i, p in enumerate(uncategorized[:10], 1):
            ts = _fmt_ts(p['ts'])
            L += [f'### [{i}] {p["tool"]} — {p["label"]} — {ts}', '']
            if p['input_preview']:
                L.append(f'- Input: `{p["input_preview"].replace(chr(10)," ")}`')
            L.append(f'- Error: `{p["err"][:ERROR_PREV].replace(chr(10)," ")}`')
            L.append('')
    else:
        L.append('_All failures matched at least one pattern._')

    return '\n'.join(L)

# Format UTC ISO timestamp as local HH:MM:SS
def _fmt_ts(ts_str: str) -> str:
    if not ts_str: return '?'
    try:
        return datetime.fromisoformat(ts_str.replace('Z','+00:00')).astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]

# Write report to file or stdout
def _write_output(content: str, path: str | None) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding='utf-8')
        print(f'Report written to: {path}', file=sys.stderr)
    else:
        print(content)

def _parse_args():
    p = argparse.ArgumentParser(description='Tool-use error and rule-violation analysis with hookability classification.')
    p.add_argument('proxy_jsonl', nargs='*', help='Proxy JSONL path(s) under src/logs/')
    p.add_argument('--input-glob', default=None, help='Glob pattern for log files')
    p.add_argument('--output', default=None, help='Output MD file path (default: stdout)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    paths = list(args.proxy_jsonl)
    if args.input_glob:
        paths.extend(sorted(_glob.glob(os.path.expanduser(args.input_glob))))
    paths = sorted(set(paths))
    if not paths:
        sys.exit('ERROR: no JSONL paths provided (positional or --input-glob)')
    analyze_tool_errors_workflow(paths, args.output)
