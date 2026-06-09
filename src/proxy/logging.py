# INFRASTRUCTURE
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Union

from .message_summary import _summarize_message

# FUNCTIONS

# Compute diff between previous and current message summaries
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
    modified = 0
    first_diff = None

    for i in range(min_len):
        p, c = prev[i], curr[i]
        if p["role"] != c["role"] or p["type"] != c["type"] or p["chars"] != c["chars"]:
            modified += 1
            if first_diff is None:
                first_diff = i

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

    parts = []
    if added:
        parts.append(f"+{added} messages at end")
    if removed:
        parts.append(f"-{removed} messages")
    if modified:
        parts.append(f"{modified} msg(s) modified")
    summary = ", ".join(parts) + f" (first diff at [{first_diff}])"

    return {
        "messages_added": added,
        "messages_removed": removed,
        "messages_modified": modified,
        "first_diff_index": first_diff,
        "summary": summary,
    }


# Recursively strip cache_control keys from dicts/lists — for stable comparison hashing only
def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj


# Mirror of cache._normalize_user_content_shape — collapses single-text-block list to plain string
# for user messages after cache_control has been stripped; applied only for hash comparison, never
# to the written element. Cannot import from cache.py (circular: cache imports from logging).
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


# MD5[:10] of element with cache_control stripped and message shape normalized — stable across BP shifts
def _delta_hash(element) -> str:
    normalized = _strip_cache_control(element)
    if isinstance(normalized, dict) and "role" in normalized:
        normalized = _normalize_msg_shape_for_hash(normalized)
    return hashlib.md5(json.dumps(normalized).encode("utf-8")).hexdigest()[:10]


# Build forwarded delta entry and current hash state for _forwarded dual-log writes
def _build_forwarded_delta(payload: dict, request_id: str, prev_hashes: Optional[dict]) -> tuple:
    system = payload.get("system", []) or []
    tools = payload.get("tools", []) or []
    messages = payload.get("messages", []) or []
    system_list = system if isinstance(system, list) else []

    curr_sys_hashes = [_delta_hash(b) for b in system_list]
    curr_tool_hashes = [_delta_hash(t) for t in tools]
    curr_msg_hashes = [_delta_hash(m) for m in messages]

    curr_hashes = {
        "system": curr_sys_hashes,
        "tools": curr_tool_hashes,
        "messages": curr_msg_hashes,
    }

    is_first = prev_hashes is None

    if is_first:
        system_delta = {str(i): b for i, b in enumerate(system_list)}
        tools_delta = {str(i): t for i, t in enumerate(tools)}
        messages_delta = {str(i): m for i, m in enumerate(messages)}
    else:
        prev_sys = prev_hashes.get("system", [])
        prev_tools = prev_hashes.get("tools", [])
        prev_msgs = prev_hashes.get("messages", [])
        system_delta = {
            str(i): b for i, b in enumerate(system_list)
            if i >= len(prev_sys) or curr_sys_hashes[i] != prev_sys[i]
        }
        tools_delta = {
            str(i): t for i, t in enumerate(tools)
            if i >= len(prev_tools) or curr_tool_hashes[i] != prev_tools[i]
        }
        messages_delta = {
            str(i): m for i, m in enumerate(messages)
            if i >= len(prev_msgs) or curr_msg_hashes[i] != prev_msgs[i]
        }

    now = datetime.now(timezone.utc)
    timestamp = f"{now.strftime('%Y-%m-%dT%H:%M:%S.')}{now.microsecond // 1000:03d}Z"

    entry = {
        "type": "forwarded_delta",
        "request_id": request_id,
        "timestamp": timestamp,
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


# Extract full text from a tool_result content value — handles plain string and list-of-blocks
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


# Scan payload messages for new is_error==True tool_result blocks not yet in seen_ids.
# Returns list of error record dicts ready for _write_entry; does NOT mutate seen_ids.
# tool_name is resolved by scanning all tool_use blocks in the payload for id→name mapping.
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

    # Build tool_use_id → tool_name map from all tool_use blocks in the conversation
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
            error_full = _extract_tool_result_text(blk.get("content", ""))
            new_entries.append({
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
            })
    return new_entries
