# INFRASTRUCTURE
import json
from pathlib import Path
from typing import Optional

from .forwarded_parser import _infer_model_family
from .proxy_badge import _is_total_tokens_nuke, _msgs_delta_is_substantial

# FUNCTIONS

def accumulate_original_tools(path: Optional[Path], last_pos: int, acc_by_family: dict) -> int:
    if path is None or not path.exists():
        return last_pos
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tools = (entry.get('payload') or {}).get('tools')
                if not tools:
                    continue
                family = _infer_model_family(entry.get('model', ''))
                fam_map = acc_by_family.setdefault(family, {})
                fam_map.clear()
                for t in tools:
                    if isinstance(t, dict) and t.get('name'):
                        fam_map[t['name']] = t
            return f.tell()
    except OSError:
        return last_pos

def _reset_family_acc_if_first(acc: dict, entry: dict) -> None:
    if not entry.get('is_first', False):
        return
    for section in ('system', 'tools', 'messages', 'fields'):
        acc[section].clear()
    acc.setdefault('_has_content_by_flow_id', {}).clear()
    acc.setdefault('_msg_idx_by_flow_id', {}).clear()
    acc.setdefault('_sys_idx_by_flow_id', {}).clear()
    acc.setdefault('_tool_name_by_flow_id', {}).clear()
    acc.setdefault('_lag_msg_idx_by_flow_id', {}).clear()
    acc['_last_line_meta'] = None

def _merge_dual_log_entry(acc: dict, entry: dict) -> dict:
    acc['system'].update(entry.get('system_delta') or {})
    for name, val in (entry.get('tools_delta') or {}).items():
        acc['tools'][name] = val
    msgs_delta = entry.get('messages_delta') or {}
    for midx, blks in msgs_delta.items():
        if midx not in acc['messages']:
            acc['messages'][midx] = {}
        acc['messages'][midx].update(blks)
    acc['fields'].update(entry.get('fields_delta') or {})
    return msgs_delta

def _record_flow_lookups(acc: dict, entry: dict, msgs_delta: dict) -> None:
    fid = entry.get('flow_id', '')
    has_content = bool(
        entry.get('system_delta') or entry.get('tools_delta')
        or _msgs_delta_is_substantial(msgs_delta, entry.get('type', ''))
    )
    acc.setdefault('_has_content_by_flow_id', {})[fid] = has_content
    acc.setdefault('_msg_idx_by_flow_id', {})[fid] = set(msgs_delta.keys())
    acc.setdefault('_sys_idx_by_flow_id', {})[fid] = set((entry.get('system_delta') or {}).keys())
    acc.setdefault('_tool_name_by_flow_id', {})[fid] = set((entry.get('tools_delta') or {}).keys())

def _apply_lag_correction(acc: dict, entry: dict, msgs_delta: dict) -> None:
    fid = entry.get('flow_id', '')
    count = (entry.get('counts') or {}).get('messages', 0)
    prev_meta = acc.get('_last_line_meta')
    if prev_meta is not None:
        prev_fid, prev_count = prev_meta
        trailing = str(prev_count - 1)
        if (count >= prev_count and prev_count > 0
                and _is_total_tokens_nuke(msgs_delta.get(trailing))):
            acc.setdefault('_lag_msg_idx_by_flow_id', {}).setdefault(
                prev_fid, set()).add(trailing)
    acc['_last_line_meta'] = (fid, count)

def accumulate_dual_log(path: Optional[Path], last_pos: int, acc_by_family: dict) -> int:
    if path is None or not path.exists():
        return last_pos
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                family = _infer_model_family(entry.get('model', ''))
                acc = acc_by_family.setdefault(
                    family,
                    {
                        'system': {}, 'tools': {}, 'messages': {}, 'fields': {},
                        '_has_content_by_flow_id': {}, '_msg_idx_by_flow_id': {},
                    }
                )
                _reset_family_acc_if_first(acc, entry)
                msgs_delta = _merge_dual_log_entry(acc, entry)
                _record_flow_lookups(acc, entry, msgs_delta)
                _apply_lag_correction(acc, entry, msgs_delta)
            return f.tell()
    except OSError:
        return last_pos
