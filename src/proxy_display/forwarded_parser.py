# INFRASTRUCTURE
import hashlib
import json
import os
from collections import deque
from pathlib import Path
from typing import Optional

from ..constants import PROXY_MESSAGES_KEEP_LAST
from ..pane_error_log import log_pane_error
from ..proxy.message_summary import _infer_model_family, _summarize_message
from ..proxy.logging import _compute_diff

# FUNCTIONS

def _proxy_session_id_for_project(project_path: str) -> str:
    normalized_path = os.path.normpath(os.path.expanduser(project_path))
    return hashlib.md5(normalized_path.encode()).hexdigest()[:8]

def _resolve_log_id(root: str, session_id: str) -> str:
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding='utf-8').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    return log_id

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

def _build_system_blocks(system) -> list:
    sys_list = system if isinstance(system, list) else []
    return [
        {
            'idx': i,
            'chars': len(b.get('text', '')),
            'has_cc': bool(b.get('cache_control')),
            'preview': b.get('text', ''),
        }
        for i, b in enumerate(sys_list) if isinstance(b, dict)
    ]

def _build_tools_fields(tools) -> dict:
    tools_list = [t for t in (tools if isinstance(tools, list) else []) if isinstance(t, dict)]
    return {
        'tools_total_chars': sum(len(json.dumps(t)) for t in tools_list),
        'tools_count': len(tools_list),
        'tools_hash': hashlib.md5(
            json.dumps(sorted(t.get('name', '') for t in tools_list)).encode()
        ).hexdigest()[:8],
        'tools_names': [t.get('name', '') for t in tools_list],
        'tools_defs': [
            {
                'name': t.get('name', ''),
                'description': t.get('description', ''),
                'input_schema': t.get('input_schema', {}),
                'stripped_original': None,
            }
            for t in tools_list
        ],
    }

def _dict_to_list_fwd(delta_dict: dict, count: int) -> list:
    lst = [None] * count
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        if i < count:
            lst[i] = elem
    return lst

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

def _build_first_summaries(messages_delta: dict, msg_cnt: int) -> list:
    raw_msgs = _dict_to_list_fwd(messages_delta or {}, msg_cnt)
    return [
        _summarize_fwd_message(m) if isinstance(m, dict) else {}
        for m in raw_msgs
    ]

def _apply_messages_delta(prev_summaries: list, messages_delta: dict, msg_cnt: int) -> tuple:
    new_summaries = list(prev_summaries)
    delta_summaries = []
    for idx_str, raw_msg in (messages_delta or {}).items():
        i = int(idx_str)
        while len(new_summaries) <= i:
            new_summaries.append({})
        new_summaries[i] = _summarize_fwd_message(raw_msg) if isinstance(raw_msg, dict) else {}
        delta_summaries.append(new_summaries[i])
    if len(new_summaries) > msg_cnt:
        new_summaries = new_summaries[:msg_cnt]
    elif len(new_summaries) < msg_cnt:
        new_summaries.extend([{}] * (msg_cnt - len(new_summaries)))
    return new_summaries, delta_summaries

def _reconstruct_first_request(fwd_e: dict, sys_cnt: int, tools_cnt: int, msg_cnt: int) -> tuple:
    new_system = _dict_to_list_fwd(fwd_e.get('system_delta') or {}, sys_cnt)
    new_tools = _dict_to_list_fwd(fwd_e.get('tools_delta') or {}, tools_cnt)
    new_summaries = _build_first_summaries(fwd_e.get('messages_delta'), msg_cnt)
    return new_system, new_tools, new_summaries, new_summaries

def _reconstruct_delta_request(prev_acc: Optional[dict], fwd_e: dict, sys_cnt: int, tools_cnt: int, msg_cnt: int) -> tuple:
    prev = prev_acc if prev_acc else {'system': [], 'tools': [], 'messages': []}
    new_system = _apply_delta_to_list(prev['system'], fwd_e.get('system_delta') or {}, sys_cnt)
    new_tools = _apply_delta_to_list(prev['tools'], fwd_e.get('tools_delta') or {}, tools_cnt)
    new_summaries, delta_summaries = _apply_messages_delta(prev['messages'], fwd_e.get('messages_delta') or {}, msg_cnt)
    return new_system, new_tools, new_summaries, delta_summaries

def _extract_forwarded_fields(fwd_entry: dict, system: list, tools: list, message_summaries: list, delta_messages: list) -> dict:
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
    entry['has_thinking_delta'] = any(
        any(b.get('type') == 'thinking' for b in s.get('blocks', []))
        for s in delta_messages if isinstance(s, dict)
    )

    entry['system_blocks'] = _build_system_blocks(system)
    entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])
    entry.update(_build_tools_fields(tools))

    entry['modifications'] = []
    entry['stripped_unused_tools_names'] = []
    entry['deferred_tools_names'] = []
    entry['stripped_msg_indices'] = []
    entry['cache_breakpoints'] = []
    entry['messages'] = None

    return entry

def _process_forwarded_entry(fwd_e: dict, req_idx: int, acc_by_family: dict) -> tuple:
    family = _infer_model_family(fwd_e.get('model', ''))
    is_first = fwd_e.get('is_first', False)
    counts = fwd_e.get('counts', {})
    sys_cnt = counts.get('system', 0)
    tools_cnt = counts.get('tools', 0)
    msg_cnt = counts.get('messages', 0)
    prev_acc = acc_by_family.get(family)
    prev_messages_for_diff = None if is_first else (prev_acc['messages'] if prev_acc else None)
    if is_first:
        new_system, new_tools, new_summaries, delta_summaries = _reconstruct_first_request(fwd_e, sys_cnt, tools_cnt, msg_cnt)
    else:
        new_system, new_tools, new_summaries, delta_summaries = _reconstruct_delta_request(prev_acc, fwd_e, sys_cnt, tools_cnt, msg_cnt)
    acc_by_family[family] = {
        'system': new_system,
        'tools': new_tools,
        'messages': new_summaries,
    }
    entry = _extract_forwarded_fields(fwd_e, new_system, new_tools, new_summaries, delta_summaries)
    entry['_fwd_req_idx'] = req_idx
    entry['flow_id'] = fwd_e.get('flow_id', '')
    entry['diff_from_prev'] = _compute_diff(prev_messages_for_diff, new_summaries)
    return entry, new_summaries

def _parse_forwarded_log(fwd_path: Path, last_pos: int, acc_by_family: dict, keep_last: int = PROXY_MESSAGES_KEEP_LAST) -> tuple:
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
                entry, new_summaries = _process_forwarded_entry(fwd_e, req_idx, acc_by_family)
                entries.append(entry)
                recent_window.append((entry, new_summaries))
                if keep_last is not None and len(recent_window) > keep_last:
                    recent_window.popleft()
                req_idx += 1
            new_pos = f.tell()
    except OSError:
        log_pane_error('forwarded_parser')
        return [], last_pos
    for win_entry, summaries in recent_window:
        win_entry['messages'] = list(summaries)
        win_entry['messages_total_chars'] = sum(s.get('chars', 0) for s in summaries)
    return entries, new_pos

def _lazy_load_messages_forwarded(entry: dict, fwd_path: Path) -> bool:
    target_flow_id = entry.get('flow_id')
    if not target_flow_id or fwd_path is None or not fwd_path.exists():
        return False
    family = _infer_model_family(entry.get('model', ''))
    temp_acc: dict = {}
    try:
        with open(fwd_path, 'r', encoding='utf-8') as f:
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
                    summaries = _build_first_summaries(fwd_e.get('messages_delta'), msg_cnt)
                else:
                    prev_summaries = temp_acc.get(e_family, [])
                    summaries, _ = _apply_messages_delta(prev_summaries, fwd_e.get('messages_delta') or {}, msg_cnt)
                temp_acc[e_family] = summaries
                if fwd_e.get('flow_id') == target_flow_id:
                    reconstructed = temp_acc.get(family, [])
                    entry['messages'] = list(reconstructed)
                    entry['messages_total_chars'] = sum(s.get('chars', 0) for s in reconstructed)
                    return True
    except OSError:
        log_pane_error('forwarded_parser')
        return False
    return False

def reconstruct_all_messages(fwd_path: Path) -> dict:
    entries, _ = _parse_forwarded_log(fwd_path, 0, {}, keep_last=None)
    return {e['flow_id']: e['messages'] for e in entries if e.get('flow_id')}

def parse_proxy_log_forwarded(project_filter: Optional[str], last_pos: int, acc_by_family: dict) -> tuple:
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    if not project_filter:
        return [], last_pos
    session_id = _proxy_session_id_for_project(project_filter)
    log_id = _resolve_log_id(root, session_id)
    fwd_path = Path(root) / 'src' / 'logs' / 'dual_log' / f'api_requests_{log_id}_forwarded.jsonl'
    entries, new_pos = _parse_forwarded_log(fwd_path, last_pos, acc_by_family)
    for entry in entries:
        entry['_source_file'] = fwd_path.name
    return entries, new_pos
