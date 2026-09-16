# INFRASTRUCTURE
import json
import os
import re
from collections import defaultdict

PARALLEL_CANCEL_TAG  = "Cancelled: parallel tool call"
TOOL_UNAVAILABLE_TAG = "Error: No such tool available"
STRING_NOT_FOUND_TAG = "String to replace not found"
VALIDATION_ERROR_TAG = "Input validation error"
TOOL_USE_ERROR_OPEN  = "<tool_use_error>"

WASTE_RATIO_MIN  = 3.0
WASTE_INPUT_MIN  = 50
SIG_MAX_CHARS    = 120
EXAMPLE_CHARS    = 150

CONTENT_TRANSFER_TOOLS = {'Write', 'Edit'}

_NORM_SUBS = [
    (re.compile(r'/(?:Users|tmp|var|opt)/\S+'),               '<PATH>'),
    (re.compile(r'api_requests_[a-z_-]+_\d+\.jsonl'),         '<LOG>'),
    (re.compile(r'\b(?:Monitor_CC|[A-Z]\w+)-[a-z0-9]{3}\b'), '<BEAD_ID>'),
    (re.compile(r'\b[0-9a-f]{8,}\b'),                         '<HEX>'),
    (re.compile(r'\b17\d{8}\b'),                              '<TS>'),
    (re.compile(r'"[^"]{51,}"'),                              '<TEXT>'),
    (re.compile(r"'[^']{51,}'"),                              '<TEXT>'),
]

# FUNCTIONS

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


def _source_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_'):
        base = base[len('api_requests_'):]
    if base.endswith('.jsonl'):
        base = base[:-len('.jsonl')]
    return base


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


def _normalize_sig(raw):
    s = raw.replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    for pat, repl in _NORM_SUBS:
        s = pat.sub(repl, s)
    s = re.sub(r'(worker-cli\s+\w+\s+)worker-[a-z][\w-]+', r'\1<WORKER>', s)
    return s[:SIG_MAX_CHARS]


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


def _is_content_transfer(name, inp):
    if name in CONTENT_TRANSFER_TOOLS:
        return True
    if name == 'Bash':
        cmd = inp.get('command', '')
        stripped = cmd.lstrip()
        if stripped.startswith('bd '):
            return True
        if re.match(r'cat\s+>>?', stripped):
            return True
        if re.match(r'echo\s+["\'].{100,}["\'].*>', stripped):
            return True
        if re.search(r'\bgit\s+commit\b', cmd) and len(cmd) > 200:
            return True
        if stripped.startswith('worker-cli send '):
            return True
    if 'worker_send' in name or 'worker_merge' in name:
        return True
    return False


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
