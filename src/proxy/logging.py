# INFRASTRUCTURE
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Union

from .message_summary import _summarize_message

# FUNCTIONS

def _diff_modified_count(prev: list, curr: list, min_len: int) -> tuple:
    modified = 0
    first_diff = None
    for i in range(min_len):
        p, c = prev[i], curr[i]
        if p["role"] != c["role"] or p["type"] != c["type"] or p["chars"] != c["chars"]:
            modified += 1
            if first_diff is None:
                first_diff = i
    return modified, first_diff


def _build_diff_summary(added: int, removed: int, modified: int, first_diff: int) -> str:
    parts = []
    if added:
        parts.append(f"+{added} messages at end")
    if removed:
        parts.append(f"-{removed} messages")
    if modified:
        parts.append(f"{modified} msg(s) modified")
    return ", ".join(parts) + f" (first diff at [{first_diff}])"


def _compute_diff(prev: Optional[list], curr: list) -> dict:
    if prev is None:
        return {
            "messages_added": len(curr),
            "messages_removed": 0,
            "messages_modified": 0,
            "first_diff_index": 0,
            "summary": f"first request, {len(curr)} messages",
        }

    min_len = min(len(prev), len(curr))
    modified, first_diff = _diff_modified_count(prev, curr, min_len)

    added = max(0, len(curr) - len(prev))
    removed = max(0, len(prev) - len(curr))

    if first_diff is None and (added or removed):
        first_diff = min_len

    if first_diff is None:
        return {
            "messages_added": 0,
            "messages_removed": 0,
            "messages_modified": 0,
            "first_diff_index": -1,
            "summary": "no changes",
        }

    return {
        "messages_added": added,
        "messages_removed": removed,
        "messages_modified": modified,
        "first_diff_index": first_diff,
        "summary": _build_diff_summary(added, removed, modified, first_diff),
    }


def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj


def _normalize_msg_shape_for_hash(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


def _delta_hash(element) -> str:
    normalized = _strip_cache_control(element)
    if isinstance(normalized, dict) and "role" in normalized:
        normalized = _normalize_msg_shape_for_hash(normalized)
    return hashlib.md5(json.dumps(normalized).encode("utf-8")).hexdigest()[:10]


def _compute_delta_hashes(system_list: list, tools: list, messages: list) -> dict:
    return {
        "system": [_delta_hash(b) for b in system_list],
        "tools": [_delta_hash(t) for t in tools],
        "messages": [_delta_hash(m) for m in messages],
    }


def _build_section_deltas(system_list: list, tools: list, messages: list, curr_hashes: dict, prev_hashes: Optional[dict]) -> tuple:
    if prev_hashes is None:
        return (
            {str(i): b for i, b in enumerate(system_list)},
            {str(i): t for i, t in enumerate(tools)},
            {str(i): m for i, m in enumerate(messages)},
        )
    prev_sys = prev_hashes.get("system", [])
    prev_tools = prev_hashes.get("tools", [])
    prev_msgs = prev_hashes.get("messages", [])
    system_delta = {
        str(i): b for i, b in enumerate(system_list)
        if i >= len(prev_sys) or curr_hashes["system"][i] != prev_sys[i]
    }
    tools_delta = {
        str(i): t for i, t in enumerate(tools)
        if i >= len(prev_tools) or curr_hashes["tools"][i] != prev_tools[i]
    }
    messages_delta = {
        str(i): m for i, m in enumerate(messages)
        if i >= len(prev_msgs) or curr_hashes["messages"][i] != prev_msgs[i]
    }
    return system_delta, tools_delta, messages_delta


def _forwarded_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S.')}{now.microsecond // 1000:03d}Z"


def _build_forwarded_delta(payload: dict, request_id: str, prev_hashes: Optional[dict]) -> tuple:
    system = payload.get("system", []) or []
    tools = payload.get("tools", []) or []
    messages = payload.get("messages", []) or []
    system_list = system if isinstance(system, list) else []

    curr_hashes = _compute_delta_hashes(system_list, tools, messages)
    is_first = prev_hashes is None
    system_delta, tools_delta, messages_delta = _build_section_deltas(system_list, tools, messages, curr_hashes, prev_hashes)

    entry = {
        "type": "forwarded_delta",
        "request_id": request_id,
        "timestamp": _forwarded_timestamp(),
        "model": payload.get("model", ""),
        "max_tokens": payload.get("max_tokens"),
        "output_config": payload.get("output_config"),
        "context_management": payload.get("context_management"),
        "diagnostics": payload.get("diagnostics"),
        "is_first": is_first,
        "counts": {
            "system": len(system_list),
            "tools": len(tools),
            "messages": len(messages),
        },
        "system_delta": system_delta,
        "tools_delta": tools_delta,
        "messages_delta": messages_delta,
    }

    return entry, curr_hashes


def _extract_tool_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return str(content) if content is not None else ""


def _build_tool_use_name_map(messages: list) -> dict:
    tu_name_map: dict = {}
    for msg in messages:
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if blk.get("type") == "tool_use":
                bid = blk.get("id", "")
                if bid:
                    tu_name_map[bid] = blk.get("name", "")
    return tu_name_map


def _build_error_entry(blk: dict, tid: str, tu_name_map: dict, request_id: str, timestamp: str,
                        worker_context: str, session_id: str, proxy_file: str) -> dict:
    error_full = _extract_tool_result_text(blk.get("content", ""))
    return {
        "type": "tool_error",
        "request_id": request_id,
        "timestamp": timestamp,
        "ts": timestamp,
        "session_id": session_id,
        "worker": worker_context,
        "tool_name": tu_name_map.get(tid, ""),
        "tool_use_id": tid,
        "error_full": error_full,
        "proxy_file": proxy_file,
    }


def _build_errors_entries(
    payload: dict,
    request_id: str,
    timestamp: str,
    seen_ids: set,
    worker_context: str,
    session_id: str,
    proxy_file: str,
) -> list:
    messages = payload.get("messages", []) or []
    tu_name_map = _build_tool_use_name_map(messages)

    new_entries = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if blk.get("type") != "tool_result":
                continue
            if blk.get("is_error") is not True:
                continue
            tid = blk.get("tool_use_id", "")
            if tid in seen_ids:
                continue
            new_entries.append(_build_error_entry(blk, tid, tu_name_map, request_id, timestamp, worker_context, session_id, proxy_file))
    return new_entries
