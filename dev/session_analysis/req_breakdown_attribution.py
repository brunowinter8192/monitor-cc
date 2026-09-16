# INFRASTRUCTURE
import json
import re

from req_breakdown_load import ENC

CONTEXT_CHARS = 500
KPI_THRESHOLD = 0.10

# FUNCTIONS

def load_last_opus_entry(prev_proxy_path):
    last_entry = None
    with open(prev_proxy_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = entry.get('model', '').lower()
            if 'haiku' in model:
                continue
            if 'raw_payload' in entry:
                last_entry = entry
    return last_entry

def serialize_prefix(entry):
    rp = entry.get('raw_payload', {})
    parts = [
        json.dumps(rp.get('system', []), ensure_ascii=False),
        json.dumps(rp.get('tools', []), ensure_ascii=False),
        json.dumps(rp.get('messages', []), ensure_ascii=False),
    ]
    return "\n".join(parts)

def find_last_bp_message_index(messages):
    last_idx = -1
    for i, msg in enumerate(messages):
        content = msg.get('content', [])
        if isinstance(content, list):
            for block in content:
                if block.get('cache_control'):
                    last_idx = i
                    break
        elif isinstance(content, dict) and content.get('cache_control'):
            last_idx = i
    return last_idx

def compute_last_bp_end_char(entry, full_prefix):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    last_bp_idx = find_last_bp_message_index(messages)

    system_json = json.dumps(system, ensure_ascii=False)
    tools_json = json.dumps(tools, ensure_ascii=False)
    msgs_offset_char = len(system_json) + 1 + len(tools_json) + 1

    if last_bp_idx < 0:
        return len(full_prefix)

    partial_msgs_json = json.dumps(messages[:last_bp_idx + 1], ensure_ascii=False)
    last_bp_end_in_msgs = len(partial_msgs_json) - 1
    return msgs_offset_char + last_bp_end_in_msgs

def identify_segment_by_char(drift_char, entry):
    rp = entry.get('raw_payload', {})
    system = rp.get('system', []) or []
    tools = rp.get('tools', []) or []
    messages = rp.get('messages', []) or []

    system_json = json.dumps(system, ensure_ascii=False)
    tools_json = json.dumps(tools, ensure_ascii=False)

    sys_end = len(system_json)
    tools_start = sys_end + 1
    tools_end = tools_start + len(tools_json)
    msgs_start = tools_end + 1

    if drift_char <= sys_end:
        offset_in_section = drift_char
        cumulative = 1
        for i, block in enumerate(system):
            block_json = json.dumps(block, ensure_ascii=False)
            block_end = cumulative + len(block_json)
            if offset_in_section <= block_end:
                return {'block_type': 'system', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = block_end + 2
        return {'block_type': 'system', 'block_idx': len(system) - 1, 'char_offset': offset_in_section}

    elif drift_char <= tools_end:
        offset_in_section = drift_char - tools_start
        cumulative = 1
        for i, tool in enumerate(tools):
            tool_json = json.dumps(tool, ensure_ascii=False)
            tool_end = cumulative + len(tool_json)
            if offset_in_section <= tool_end:
                return {'block_type': 'tools', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = tool_end + 2
        return {'block_type': 'tools', 'block_idx': len(tools) - 1, 'char_offset': offset_in_section}

    else:
        offset_in_section = drift_char - msgs_start
        cumulative = 1
        for i, msg in enumerate(messages):
            msg_json = json.dumps(msg, ensure_ascii=False)
            msg_end = cumulative + len(msg_json)
            if offset_in_section <= msg_end:
                return {'block_type': 'messages', 'block_idx': i, 'char_offset': offset_in_section - cumulative}
            cumulative = msg_end + 2
        return {'block_type': 'messages', 'block_idx': len(messages) - 1, 'char_offset': offset_in_section}

def find_nearest_heading(prefix_text, drift_char):
    text_before = prefix_text[:drift_char]
    matches = list(re.finditer(r'^#{1,3} .+', text_before, re.MULTILINE))
    if matches:
        return matches[-1].group(0)[:120]
    return None

def _find_byte_drift(old_bytes, new_bytes):
    min_len = min(len(old_bytes), len(new_bytes))
    drift_byte = min_len
    for i in range(min_len):
        if old_bytes[i] != new_bytes[i]:
            drift_byte = i
            break
    return drift_byte

def _build_drift_context(old_prefix, new_prefix, old_bytes, new_bytes, drift_byte, drift_char):
    ctx_start = max(0, drift_char - CONTEXT_CHARS)
    ctx_end = min(len(new_prefix), drift_char + CONTEXT_CHARS)
    old_drift_char = len(old_bytes[:drift_byte].decode('utf-8', errors='replace'))
    old_ctx_start = max(0, old_drift_char - CONTEXT_CHARS)
    old_ctx_end = min(len(old_prefix), old_drift_char + CONTEXT_CHARS)

    return {
        'old': old_prefix[old_ctx_start:old_ctx_end],
        'new': new_prefix[ctx_start:ctx_end],
        'old_bytes_at_drift': repr(old_bytes[drift_byte:drift_byte + 20]) if drift_byte < len(old_bytes) else '(end of old)',
        'new_bytes_at_drift': repr(new_bytes[drift_byte:drift_byte + 20]) if drift_byte < len(new_bytes) else '(end of new)',
    }

def _tokens_around_drift(current_entry, new_prefix, drift_char):
    tokens_before_drift = len(ENC.encode(new_prefix[:drift_char]))
    last_bp_end_char = compute_last_bp_end_char(current_entry, new_prefix)
    tokens_after_drift_to_last_bp = len(ENC.encode(new_prefix[drift_char:last_bp_end_char]))
    return tokens_before_drift, last_bp_end_char, tokens_after_drift_to_last_bp

def _locate_segment_and_heading(current_entry, new_prefix, drift_char):
    segment = identify_segment_by_char(drift_char, current_entry)
    nearest_heading = None
    if segment.get('block_type') == 'system' and segment.get('block_idx') == 2:
        nearest_heading = find_nearest_heading(new_prefix, drift_char)
    return segment, nearest_heading

def compute_prefix_attribution(current_entry, prev_proxy_path, actual_cr, actual_cc):
    prev_entry = load_last_opus_entry(prev_proxy_path)
    if prev_entry is None:
        return {'error': 'No opus entry with raw_payload found in prev proxy log'}

    old_prefix = serialize_prefix(prev_entry)
    new_prefix = serialize_prefix(current_entry)

    old_bytes = old_prefix.encode('utf-8')
    new_bytes = new_prefix.encode('utf-8')
    drift_byte = _find_byte_drift(old_bytes, new_bytes)

    drift_char = len(new_bytes[:drift_byte].decode('utf-8', errors='replace'))

    tokens_before_drift, last_bp_end_char, tokens_after_drift_to_last_bp = _tokens_around_drift(
        current_entry, new_prefix, drift_char,
    )

    context = _build_drift_context(old_prefix, new_prefix, old_bytes, new_bytes, drift_byte, drift_char)

    segment, nearest_heading = _locate_segment_and_heading(current_entry, new_prefix, drift_char)

    cr_delta = abs(tokens_before_drift - actual_cr) / actual_cr if actual_cr > 0 else None
    cc_delta = abs(tokens_after_drift_to_last_bp - actual_cc) / actual_cc if actual_cc > 0 else None

    return {
        'drift_byte': drift_byte,
        'drift_char': drift_char,
        'common_prefix_bytes': drift_byte,
        'total_new_bytes': len(new_bytes),
        'total_old_bytes': len(old_bytes),
        'tokens_before_drift': tokens_before_drift,
        'tokens_after_drift_to_last_bp': tokens_after_drift_to_last_bp,
        'last_bp_end_char': last_bp_end_char,
        'segment': segment,
        'context': context,
        'nearest_heading': nearest_heading,
        'cr_kpi_pct': cr_delta,
        'cc_kpi_pct': cc_delta,
        'cr_kpi_pass': cr_delta is not None and cr_delta < KPI_THRESHOLD,
        'cc_kpi_pass': cc_delta is not None and cc_delta < KPI_THRESHOLD,
    }
