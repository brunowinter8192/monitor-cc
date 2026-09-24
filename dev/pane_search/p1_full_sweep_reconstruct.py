# INFRASTRUCTURE
import gc
import json
import time
import tracemalloc
from collections import deque
from pathlib import Path

_SKIPPED_LINES = 0

# FUNCTIONS

def skipped_line_count() -> int:
    return _SKIPPED_LINES

def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1

def _infer_model_family(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    return 'opus'

def _dict_to_list(delta: dict, count: int) -> list:
    lst = [None] * count
    for idx_str, elem in delta.items():
        i = int(idx_str)
        if i < count:
            lst[i] = elem
    return lst

def _apply_delta_to_list(prev_list: list, delta: dict, count: int) -> list:
    lst = list(prev_list)
    for idx_str, elem in delta.items():
        i = int(idx_str)
        while len(lst) <= i:
            lst.append(None)
        lst[i] = elem
    if len(lst) > count:
        lst = lst[:count]
    elif len(lst) < count:
        lst.extend([None] * (count - len(lst)))
    return lst

def _summarize(msg) -> dict:
    if not isinstance(msg, dict):
        return {'chars': 0}
    content = msg.get('content', '')
    if isinstance(content, str):
        chars = len(content)
    elif isinstance(content, list):
        chars = sum(len(json.dumps(b)) for b in content if isinstance(b, dict))
    else:
        chars = 0
    return {'role': msg.get('role', ''), 'chars': chars}

def _next_forwarded_delta(f):
    while True:
        raw = f.readline()
        if not raw:
            return None
        line = raw.strip()
        if not line:
            continue
        try:
            fwd_e = json.loads(line)
        except json.JSONDecodeError:
            _note_skipped_line()
            continue
        if fwd_e.get('type') != 'forwarded_delta':
            continue
        return fwd_e

def _merge_messages_delta(base_summaries: list, messages_delta: dict, msg_cnt: int) -> list:
    summaries = list(base_summaries)
    for idx_str, raw_msg in (messages_delta or {}).items():
        i = int(idx_str)
        while len(summaries) <= i:
            summaries.append({})
        summaries[i] = _summarize(raw_msg)
    if len(summaries) > msg_cnt:
        summaries = summaries[:msg_cnt]
    elif len(summaries) < msg_cnt:
        summaries.extend([{}] * (msg_cnt - len(summaries)))
    return summaries

def _sweep_parse(fwd_path: Path, keep_last) -> tuple:
    acc_by_family: dict = {}
    entries: list = []
    recent_window: deque = deque()
    t0 = time.perf_counter()
    with open(fwd_path, 'r', encoding='utf-8') as f:
        req_idx = 0
        while True:
            fwd_e = _next_forwarded_delta(f)
            if fwd_e is None:
                break
            family = _infer_model_family(fwd_e.get('model', ''))
            is_first = fwd_e.get('is_first', False)
            counts = fwd_e.get('counts', {})
            sys_cnt, tools_cnt, msg_cnt = counts.get('system', 0), counts.get('tools', 0), counts.get('messages', 0)
            prev = acc_by_family.get(family) if not is_first else None
            if is_first:
                new_system = _dict_to_list(fwd_e.get('system_delta') or {}, sys_cnt)
                new_tools = _dict_to_list(fwd_e.get('tools_delta') or {}, tools_cnt)
                raw_msgs = _dict_to_list(fwd_e.get('messages_delta') or {}, msg_cnt)
                new_summaries = [_summarize(m) for m in raw_msgs]
            else:
                base = prev if prev else {'system': [], 'tools': [], 'messages': []}
                new_system = _apply_delta_to_list(base['system'], fwd_e.get('system_delta') or {}, sys_cnt)
                new_tools = _apply_delta_to_list(base['tools'], fwd_e.get('tools_delta') or {}, tools_cnt)
                new_summaries = _merge_messages_delta(base['messages'], fwd_e.get('messages_delta') or {}, msg_cnt)
            acc_by_family[family] = {'system': new_system, 'tools': new_tools, 'messages': new_summaries}
            entry = {
                'model': fwd_e.get('model', ''),
                'message_count': msg_cnt,
                'messages_total_chars': sum(s.get('chars', 0) for s in new_summaries),
                '_fwd_req_idx': req_idx,
                'messages': None,
            }
            entries.append(entry)
            recent_window.append((entry, new_summaries))
            if keep_last is not None and len(recent_window) > keep_last:
                recent_window.popleft()
            req_idx += 1
    for win_entry, summaries in recent_window:
        win_entry['messages'] = list(summaries)
    elapsed = time.perf_counter() - t0
    return entries, elapsed

def _lazy_load_one(fwd_path: Path, target_idx: int, target_family: str) -> list:
    temp_acc: dict = {}
    with open(fwd_path, 'r', encoding='utf-8') as f:
        req_idx = 0
        while True:
            fwd_e = _next_forwarded_delta(f)
            if fwd_e is None:
                break
            family = _infer_model_family(fwd_e.get('model', ''))
            is_first = fwd_e.get('is_first', False)
            msg_cnt = fwd_e.get('counts', {}).get('messages', 0)
            if is_first:
                raw_msgs = _dict_to_list(fwd_e.get('messages_delta') or {}, msg_cnt)
                summaries = [_summarize(m) for m in raw_msgs]
            else:
                summaries = _merge_messages_delta(temp_acc.get(family, []), fwd_e.get('messages_delta') or {}, msg_cnt)
            temp_acc[family] = summaries
            if req_idx == target_idx:
                return list(temp_acc.get(target_family, []))
            req_idx += 1
    return []

def _traced_sweep(fwd_path: Path, keep_last) -> tuple:
    gc.collect()
    tracemalloc.clear_traces()
    entries, elapsed = _sweep_parse(fwd_path, keep_last)
    current, peak = tracemalloc.get_traced_memory()
    return entries, elapsed, current, peak

def _measure_lazy_load_all(entries: list, fwd_path: Path) -> list:
    times = []
    for entry in entries:
        family = _infer_model_family(entry['model'])
        t0 = time.perf_counter()
        _lazy_load_one(fwd_path, entry['_fwd_req_idx'], family)
        times.append(time.perf_counter() - t0)
    return times
