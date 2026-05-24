# INFRASTRUCTURE
from ..utils import format_timestamp
from ..format.strip_marker import get_stripped_data
from .warnings_parse import (
    _iso_to_float,
    _is_tool_error, _is_zero_result_block,
    _build_tool_use_id_map, _resolve_tool_call,
)

# FUNCTIONS

# Scan new proxy entries for tool errors; returns (errors_list, new_dedup_keys)
def _scan_proxy_entries_for_errors(entries: list, monitor_start_ts: float, seen_error_keys: set) -> tuple:
    errors = []
    new_keys = set()
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        if ts_raw and _iso_to_float(ts_raw) < monitor_start_ts:
            continue
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        worker_name = entry.get('_worker_name', '')
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if not _is_tool_error(msg):
                continue
            tu_id_map = _build_tool_use_id_map(messages, msg_idx)
            preceding_tu = None
            for i in range(msg_idx - 1, -1, -1):
                if messages[i].get('type') == 'tool_use':
                    preceding_tu = messages[i]
                    break
            tu_blocks_positional = [
                b for b in (preceding_tu.get('blocks', []) if preceding_tu else [])
                if b.get('type') == 'tool_use'
            ]
            for blk_idx, blk in enumerate(msg.get('blocks', [])):
                if blk.get('type') != 'tool_result' or not blk.get('is_error'):
                    continue
                full_text = blk.get('full_text', '') or blk.get('preview', '') or msg.get('content_preview', '')
                dedup_key = (worker_name, msg_idx, full_text[:200])
                if dedup_key in seen_error_keys or dedup_key in new_keys:
                    continue
                new_keys.add(dedup_key)
                tool_name, tool_call_input = _resolve_tool_call(blk, tu_id_map, tu_blocks_positional, blk_idx)
                first_line = full_text.split('\n')[0] if full_text else ''
                summary = first_line[:80] + ('…' if len(first_line) > 80 else '')
                pre_strip_text, stripped_chunks = get_stripped_data(entry, msg_idx)
                errors.append({
                    'timestamp': ts,
                    'tool_name': tool_name,
                    'summary': summary,
                    'full_text': full_text,
                    'tool_call_input': tool_call_input,
                    'worker_name': worker_name,
                    '_pre_strip_text': pre_strip_text,
                    '_stripped_chunks': stripped_chunks,
                    '_ts_raw': ts_raw,
                    '_tool_use_id': blk.get('tool_use_id', ''),
                    '_proxy_file': entry.get('_source_file', ''),
                    '_request_id': entry.get('request_id', ''),
                })
    return errors, new_keys


# Scan new proxy entries for zero-result tool calls; returns (results_list, new_dedup_keys)
def _scan_proxy_entries_for_zero_results(entries: list, monitor_start_ts: float, seen_zero_keys: set) -> tuple:
    results = []
    new_keys = set()
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        if ts_raw and _iso_to_float(ts_raw) < monitor_start_ts:
            continue
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        worker_name = entry.get('_worker_name', '')
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if msg.get('type') != 'tool_result':
                continue
            blocks = msg.get('blocks', [])
            tu_id_map = _build_tool_use_id_map(messages, msg_idx)
            preceding_tu = None
            for i in range(msg_idx - 1, -1, -1):
                if messages[i].get('type') == 'tool_use':
                    preceding_tu = messages[i]
                    break
            tu_blocks_positional = [b for b in (preceding_tu.get('blocks', []) if preceding_tu else []) if b.get('type') == 'tool_use']
            for blk_idx, blk in enumerate(blocks):
                reason = _is_zero_result_block(blk)
                if not reason:
                    continue
                text_key = blk.get('full_text', '') or blk.get('preview', '')
                dedup_key = (worker_name, msg_idx, blk_idx, text_key)
                if dedup_key in seen_zero_keys or dedup_key in new_keys:
                    continue
                new_keys.add(dedup_key)
                tool_name, tool_call_input = _resolve_tool_call(blk, tu_id_map, tu_blocks_positional, blk_idx)
                pre_strip_text, stripped_chunks = get_stripped_data(entry, msg_idx)
                results.append({
                    'timestamp': ts,
                    'tool_name': tool_name,
                    'reason': reason.capitalize(),
                    'tool_call_input': tool_call_input,
                    'worker_name': worker_name,
                    '_pre_strip_text': pre_strip_text,
                    '_stripped_chunks': stripped_chunks,
                })
    return results, new_keys
