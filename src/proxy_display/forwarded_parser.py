# INFRASTRUCTURE
import hashlib
import json
import os
from collections import deque
from pathlib import Path
from typing import Optional

from ..constants import PROXY_MESSAGES_KEEP_LAST
from ..proxy.message_summary import _summarize_message
from ..proxy.logging import _compute_diff

# FUNCTIONS

# Single source — parser.py imports this; defined here so forwarded_parser.py stays a leaf (no import from parser.py)
def _proxy_session_id_for_project(project_path: str) -> str:
    return hashlib.md5(project_path.encode()).hexdigest()[:8]

# Infer model family from model name string (matches addon.py logic)
def _infer_model_family(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    return 'opus'

# Build a message summary dict with content_tail enrichment from the raw message object.
# Wraps _summarize_message (from proxy/message_summary.py) and adds content_tail for
# full-text display in the proxy pane expand view.
def _summarize_fwd_message(msg: dict) -> dict:
    s = _summarize_message(msg)
    content = msg.get('content', '')
    if isinstance(content, str):
        s['content_tail'] = content
    elif isinstance(content, list):
        s['content_tail'] = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
    else:
        s['content_tail'] = ''
    return s

# Expand {idx_str: elem} delta dict into a list of exactly count elements (None-padded gaps)
def _dict_to_list_fwd(delta_dict: dict, count: int) -> list:
    lst = [None] * count
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        if i < count:
            lst[i] = elem
    return lst

# Shallow-copy prev_list, apply delta dict overwrites, resize to count
def _apply_delta_to_list(prev_list: list, delta_dict: dict, count: int) -> list:
    lst = list(prev_list)
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        while len(lst) <= i:
            lst.append(None)
        lst[i] = elem
    if len(lst) > count:
        lst = lst[:count]
    elif len(lst) < count:
        lst.extend([None] * (count - len(lst)))
    return lst

# Build a proxy-display entry dict from a forwarded_delta header + reconstructed section data.
# message_summaries: list of summary dicts (for messages_total_chars; messages key NOT set here —
# assigned from the deque window after parse completes).
def _extract_forwarded_fields(fwd_entry: dict, system: list, tools: list, message_summaries: list) -> dict:
    entry: dict = {}
    entry['timestamp'] = fwd_entry.get('timestamp', '')
    entry['request_id'] = fwd_entry.get('request_id', '')
    entry['model'] = fwd_entry.get('model', '')
    entry['max_tokens'] = fwd_entry.get('max_tokens') or 0
    entry['output_config'] = fwd_entry.get('output_config') or {}
    entry['effort_value'] = (fwd_entry.get('output_config') or {}).get('effort')
    entry['anthropic_beta'] = fwd_entry.get('anthropic_beta') or []
    entry['context_management'] = fwd_entry.get('context_management')
    entry['diagnostics'] = fwd_entry.get('diagnostics')
    entry['is_first'] = fwd_entry.get('is_first', False)
    entry['message_count'] = fwd_entry.get('counts', {}).get('messages', 0)
    entry['messages_total_chars'] = sum(s.get('chars', 0) for s in message_summaries)

    sys_list = system if isinstance(system, list) else []
    entry['system_blocks'] = [
        {
            'idx': i,
            'chars': len(b.get('text', '')),
            'has_cc': bool(b.get('cache_control')),
            'preview': b.get('text', ''),
        }
        for i, b in enumerate(sys_list) if isinstance(b, dict)
    ]
    entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])

    tools_list = [t for t in (tools if isinstance(tools, list) else []) if isinstance(t, dict)]
    entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools_list)
    entry['tools_count'] = len(tools_list)
    entry['tools_hash'] = hashlib.md5(
        json.dumps(sorted(t.get('name', '') for t in tools_list)).encode()
    ).hexdigest()[:8]
    entry['tools_names'] = [t.get('name', '') for t in tools_list]
    entry['tools_defs'] = [
        {
            'name': t.get('name', ''),
            'description': t.get('description', ''),
            'input_schema': t.get('input_schema', {}),
            'stripped_original': None,
        }
        for t in tools_list
    ]

    # Placeholders for main-log-only fields; use_dual overlay path handles display when
    # _stripped_spans/_injected_spans are attached by the pane's accumulate_dual_log calls.
    entry['modifications'] = []
    entry['stripped_unused_tools_names'] = []
    entry['deferred_tools_names'] = []
    entry['stripped_msg_indices'] = []
    entry['cache_breakpoints'] = []   # always empty; BP:N removed from display
    entry['messages'] = None           # assigned by caller from deque window

    return entry

# Parse new forwarded_delta entries from fwd_path starting at last_pos.
# acc_by_family: persisted across calls {family: {system: [...], tools: [...], messages: [summaries]}}.
#   is_first resets the family state; subsequent entries apply deltas onto the accumulated lists.
#   Unchanged message dicts are SHARED across consecutive summary lists (shallow copy) — O(M) total
#   unique summary objects, not O(N^2).
# Deque bound: only the last PROXY_MESSAGES_KEEP_LAST entries have entry['messages'] populated;
#   earlier entries carry messages=None (lazy-loadable via _lazy_load_messages_forwarded).
# _fwd_req_idx: 0-based within this call; pane adds session-level offset for lazy-reload targeting.
def _parse_forwarded_log(fwd_path: Path, last_pos: int, acc_by_family: dict) -> tuple:
    entries: list = []
    recent_window: deque = deque()
    try:
        with open(fwd_path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            req_idx = 0
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    fwd_e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if fwd_e.get('type') != 'forwarded_delta':
                    continue
                family = _infer_model_family(fwd_e.get('model', ''))
                is_first = fwd_e.get('is_first', False)
                counts = fwd_e.get('counts', {})
                sys_cnt = counts.get('system', 0)
                tools_cnt = counts.get('tools', 0)
                msg_cnt = counts.get('messages', 0)
                # Capture prev summaries for diff_from_prev BEFORE updating accumulator.
                # is_first=True means proxy session reset → treat as first-ever request for this family.
                prev_acc = acc_by_family.get(family)
                prev_messages_for_diff = None if is_first else (prev_acc['messages'] if prev_acc else None)
                if is_first:
                    new_system = _dict_to_list_fwd(fwd_e.get('system_delta') or {}, sys_cnt)
                    new_tools = _dict_to_list_fwd(fwd_e.get('tools_delta') or {}, tools_cnt)
                    raw_msgs = _dict_to_list_fwd(fwd_e.get('messages_delta') or {}, msg_cnt)
                    new_summaries = [
                        _summarize_fwd_message(m) if isinstance(m, dict) else {}
                        for m in raw_msgs
                    ]
                else:
                    prev = prev_acc if prev_acc else {'system': [], 'tools': [], 'messages': []}
                    new_system = _apply_delta_to_list(prev['system'], fwd_e.get('system_delta') or {}, sys_cnt)
                    new_tools = _apply_delta_to_list(prev['tools'], fwd_e.get('tools_delta') or {}, tools_cnt)
                    new_summaries = list(prev['messages'])
                    for idx_str, raw_msg in (fwd_e.get('messages_delta') or {}).items():
                        i = int(idx_str)
                        while len(new_summaries) <= i:
                            new_summaries.append({})
                        new_summaries[i] = (
                            _summarize_fwd_message(raw_msg) if isinstance(raw_msg, dict) else {}
                        )
                    if len(new_summaries) > msg_cnt:
                        new_summaries = new_summaries[:msg_cnt]
                    elif len(new_summaries) < msg_cnt:
                        new_summaries.extend([{}] * (msg_cnt - len(new_summaries)))
                acc_by_family[family] = {
                    'system': new_system,
                    'tools': new_tools,
                    'messages': new_summaries,
                }
                entry = _extract_forwarded_fields(fwd_e, new_system, new_tools, new_summaries)
                entry['_fwd_req_idx'] = req_idx
                entry['flow_id'] = fwd_e.get('flow_id', '')
                entry['diff_from_prev'] = _compute_diff(prev_messages_for_diff, new_summaries)
                entries.append(entry)
                recent_window.append((entry, new_summaries))
                if len(recent_window) > PROXY_MESSAGES_KEEP_LAST:
                    recent_window.popleft()
                req_idx += 1
            new_pos = f.tell()
    except OSError:
        return [], last_pos
    for win_entry, summaries in recent_window:
        win_entry['messages'] = list(summaries)
        win_entry['messages_total_chars'] = sum(s.get('chars', 0) for s in summaries)
    return entries, new_pos

# Replay _forwarded log from byte 0 to reconstruct messages for a stripped entry.
# entry['_fwd_req_idx'] identifies the target position in the forwarded stream.
# Returns True if entry['messages'] was populated; False on any failure.
# Cost: O(fwd_file_size) — acceptable for the small delta log.
def _lazy_load_messages_forwarded(entry: dict, fwd_path: Path) -> bool:
    target_idx = entry.get('_fwd_req_idx')
    if target_idx is None or fwd_path is None or not fwd_path.exists():
        return False
    family = _infer_model_family(entry.get('model', ''))
    temp_acc: dict = {}
    try:
        with open(fwd_path, 'r', encoding='utf-8') as f:
            req_idx = 0
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    fwd_e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if fwd_e.get('type') != 'forwarded_delta':
                    continue
                e_family = _infer_model_family(fwd_e.get('model', ''))
                is_first = fwd_e.get('is_first', False)
                counts = fwd_e.get('counts', {})
                msg_cnt = counts.get('messages', 0)
                if is_first:
                    raw_msgs = _dict_to_list_fwd(fwd_e.get('messages_delta') or {}, msg_cnt)
                    summaries = [
                        _summarize_fwd_message(m) if isinstance(m, dict) else {}
                        for m in raw_msgs
                    ]
                    temp_acc[e_family] = summaries
                else:
                    prev_summaries = temp_acc.get(e_family, [])
                    summaries = list(prev_summaries)
                    for idx_str, raw_msg in (fwd_e.get('messages_delta') or {}).items():
                        i = int(idx_str)
                        while len(summaries) <= i:
                            summaries.append({})
                        summaries[i] = (
                            _summarize_fwd_message(raw_msg) if isinstance(raw_msg, dict) else {}
                        )
                    if len(summaries) > msg_cnt:
                        summaries = summaries[:msg_cnt]
                    elif len(summaries) < msg_cnt:
                        summaries.extend([{}] * (msg_cnt - len(summaries)))
                    temp_acc[e_family] = summaries
                if req_idx == target_idx:
                    reconstructed = temp_acc.get(family, [])
                    entry['messages'] = list(reconstructed)
                    entry['messages_total_chars'] = sum(s.get('chars', 0) for s in reconstructed)
                    return True
                req_idx += 1
    except OSError:
        return False
    return False

# Read new proxy-log entries for the monitored project from the _forwarded dual-log.
# acc_by_family: persisted at caller (pane) across polling cycles for delta reconstruction.
# Returns (entries, new_fwd_pos); graceful empty return if _forwarded file is absent.
def parse_proxy_log_forwarded(project_filter: Optional[str], last_pos: int, acc_by_family: dict) -> tuple:
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    if not project_filter:
        return [], last_pos
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding='utf-8').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    fwd_path = Path(root) / 'src' / 'logs' / 'dual_log' / f'api_requests_{log_id}_forwarded.jsonl'
    entries, new_pos = _parse_forwarded_log(fwd_path, last_pos, acc_by_family)
    for entry in entries:
        entry['_source_file'] = fwd_path.name
    return entries, new_pos
