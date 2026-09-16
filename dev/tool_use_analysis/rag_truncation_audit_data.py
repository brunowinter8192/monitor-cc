# INFRASTRUCTURE
import json
import os
import re

TRUNC_RE   = re.compile(r'\[\d+ characters? truncated\]')
TRUNC_N_RE = re.compile(r'\[(\d+) characters? truncated\]')

CC_SPLIT_LO = 0.40
CC_SPLIT_HI = 0.60

RAG_CLI_MARKERS = ('rag-cli search', 'rag-cli search_hybrid', 'rag-cli search_keyword',
                   'rag-cli search_dense', 'rag_cli search')

# FUNCTIONS

def _load_proxy(path):
    events = []
    label = _source_label(path)
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
    return base[:-len('.jsonl')] if base.endswith('.jsonl') else base


def _collect_tool_uses(events):
    out = {}
    for ev in events:
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
                    'name':    name,
                    'command': inp.get('command', inp.get('file_path', '')),
                    'source':  ev.get('_source', ''),
                }
    return out


def _collect_truncated_results(events):
    out = {}
    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_result':
                    continue
                blk_str = json.dumps(blk)
                if not TRUNC_RE.search(blk_str):
                    continue
                tid = blk.get('tool_use_id', '')
                if not tid or tid in out:
                    continue
                raw_c = blk.get('content', '')
                if isinstance(raw_c, list):
                    text = ''.join(
                        rc.get('text', '') if isinstance(rc, dict) else str(rc)
                        for rc in raw_c
                    )
                else:
                    text = str(raw_c) if raw_c else ''
                m = TRUNC_N_RE.search(text)
                trunc_bytes = int(m.group(1)) if m else 0
                trunc_pos   = m.start() if m else -1
                total_len   = len(text)
                out[tid] = {
                    'tool_use_id': tid,
                    'trunc_bytes': trunc_bytes,
                    'trunc_pos':   trunc_pos,
                    'total_len':   total_len,
                    'split_frac':  trunc_pos / total_len if total_len else 0,
                    'source':      ev.get('_source', ''),
                }
    return out


def _collect_echo_hits(events):
    hits = []
    seen = set()
    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            role    = msg.get('role', '')
            if isinstance(content, str):
                if TRUNC_RE.search(content):
                    key = ('str_content', role, ev.get('_source', ''))
                    if key not in seen:
                        seen.add(key)
                        hits.append({'location': 'message_content_str', 'role': role,
                                     'name': '', 'source': ev.get('_source', ''),
                                     'sample': content[:120]})
                continue
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                btype = blk.get('type', '')
                if btype == 'tool_result':
                    continue
                blk_str = json.dumps(blk)
                if not TRUNC_RE.search(blk_str):
                    continue
                bid   = blk.get('id', '')
                bname = blk.get('name', '')
                key   = (btype, bid or role, ev.get('_source', ''))
                if key in seen:
                    continue
                seen.add(key)
                if btype == 'tool_use':
                    inp  = blk.get('input', {})
                    cmd  = inp.get('command', inp.get('content', str(inp)[:200]))
                    hits.append({'location': 'tool_use_input', 'role': role,
                                 'name': bname, 'source': ev.get('_source', ''),
                                 'sample': str(cmd)[:200]})
                elif btype == 'text':
                    text = blk.get('text', '')
                    hits.append({'location': 'text_block', 'role': role,
                                 'name': '', 'source': ev.get('_source', ''),
                                 'sample': text[:200]})
                else:
                    hits.append({'location': btype, 'role': role,
                                 'name': bname, 'source': ev.get('_source', ''),
                                 'sample': blk_str[:200]})
    return hits


def _is_compound_bash(cmd):
    return ';' in cmd or '&&' in cmd or '||' in cmd


def _classify(trunc_results, tool_uses):
    classified = {}
    for tid, tr in trunc_results.items():
        tu     = tool_uses.get(tid, {})
        name   = tu.get('name', '?')
        cmd    = tu.get('command', '')
        frac   = tr['split_frac']

        is_rag_only = (
            name == 'Bash'
            and any(m in cmd for m in RAG_CLI_MARKERS)
            and not _is_compound_bash(cmd)
        )

        is_cc_split = (CC_SPLIT_LO <= frac <= CC_SPLIT_HI) and name == 'Bash'

        if is_rag_only:
            hyp = 'A'
        elif is_cc_split:
            hyp = 'B'
        elif not tu:
            hyp = '?'
        else:
            hyp = 'B'

        classified[tid] = {**tr, 'tool_name': name, 'command_preview': cmd[:140], 'hypothesis': hyp}
    return classified
