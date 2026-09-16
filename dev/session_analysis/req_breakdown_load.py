# INFRASTRUCTURE
import json

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")

# FUNCTIONS

def load_proxy_entry(proxy_path, req_n):
    opus_count = 0
    with open(proxy_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'raw_payload' not in entry:
                continue
            if 'haiku' in entry.get('model', '').lower():
                continue
            opus_count += 1
            if opus_count == req_n:
                return entry
    raise ValueError(f"REQ#{req_n} not found — only {opus_count} opus raw_payload entries in proxy log")

def load_session_ground_truth(session_path, req_n):
    events = []
    pending_key = None
    pending_out = 0
    with open(session_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') != 'assistant':
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                    pending_key = None
                    pending_out = 0
                continue
            msg = d.get('message', {})
            usage = msg.get('usage', {})
            if not usage:
                continue
            cr = usage.get('cache_read_input_tokens', 0) or 0
            cc_ = usage.get('cache_creation_input_tokens', 0) or 0
            inp = usage.get('input_tokens', 0) or 0
            out = usage.get('output_tokens', 0) or 0
            key = (cr, cc_, inp)
            if key == pending_key:
                if out > pending_out:
                    pending_out = out
            else:
                if pending_key is not None:
                    events.append((*pending_key, pending_out))
                pending_key = key
                pending_out = out
    if pending_key is not None:
        events.append((*pending_key, pending_out))

    if req_n > len(events):
        raise ValueError(f"REQ#{req_n} not found — only {len(events)} deduplicated events in session JSONL")
    cr, cc_, d, out = events[req_n - 1]
    return cr, cc_, d, out

def _tokenize_system(system):
    sys_rows = []
    for i, block in enumerate(system):
        json_str = json.dumps(block, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        preview = block.get('text', '')[:60].replace('\n', ' ')
        sys_rows.append({
            'idx': i,
            'text_chars': len(block.get('text', '')),
            'json_chars': len(json_str),
            'tokens': toks,
            'cache_control': block.get('cache_control'),
            'preview': preview,
        })
    return sys_rows

def _tokenize_tools(tools):
    tools_rows = []
    for i, tool in enumerate(tools):
        json_str = json.dumps(tool, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        tools_rows.append({
            'idx': i,
            'name': tool.get('name', f'tool_{i}'),
            'json_chars': len(json_str),
            'tokens': toks,
        })
    return tools_rows

def _tokenize_messages(messages):
    msg_rows = []
    for i, msg in enumerate(messages):
        json_str = json.dumps(msg, ensure_ascii=False)
        toks = len(ENC.encode(json_str))
        content = msg.get('content', [])
        cc_blocks = []
        if isinstance(content, list):
            for j, blk in enumerate(content):
                if blk.get('cache_control'):
                    cc_blocks.append(j)
        preview = ''
        if isinstance(content, list) and content:
            preview = str(content[0].get('text', ''))[:40].replace('\n', ' ')
        elif isinstance(content, str):
            preview = content[:40].replace('\n', ' ')
        msg_rows.append({
            'idx': i,
            'role': msg.get('role', '?'),
            'json_chars': len(json_str),
            'tokens': toks,
            'cc_blocks': cc_blocks,
            'preview': preview,
        })
    return msg_rows

def tokenize_segments(entry):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    sys_rows = _tokenize_system(system)
    tools_rows = _tokenize_tools(tools)
    msg_rows = _tokenize_messages(messages)

    estimate = (
        sum(r['tokens'] for r in sys_rows)
        + sum(r['tokens'] for r in tools_rows)
        + sum(r['tokens'] for r in msg_rows)
    )
    return sys_rows, tools_rows, msg_rows, estimate
