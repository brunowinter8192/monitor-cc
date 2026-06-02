# INFRASTRUCTURE
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from .message_summary import _summarize_message

# FUNCTIONS

# Build full log entry dict from flow, payload, and previous request state
def _build_entry(flow, payload: dict, prev_messages: Optional[list], modifications: list = None) -> dict:
    messages = payload.get("messages", [])
    system = payload.get("system", "")
    system_chars = _count_system_chars(system)

    message_summaries = [_summarize_message(m) for m in messages]
    cache_breakpoints = [i for i, s in enumerate(message_summaries) if s["has_cache_control"]]
    total_input_chars = sum(s["chars"] for s in message_summaries) + system_chars

    request_id = flow.request.headers.get("x-request-id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    timestamp = f"{now.strftime('%Y-%m-%dT%H:%M:%S.')}{now.microsecond // 1000:03d}Z"

    tools = payload.get("tools", [])
    return {
        "timestamp": timestamp,
        "request_id": request_id,
        "model": payload.get("model", ""),
        "message_count": len(messages),
        "total_input_chars": total_input_chars,
        "system_prompt_chars": system_chars,
        "system_content": system,
        "has_cache_control": bool(cache_breakpoints),
        "cache_breakpoints": cache_breakpoints,
        "tools_count": len(tools),
        "tools_chars": sum(len(json.dumps(t)) for t in tools),
        "tools_names": [t.get("name", "") for t in tools],
        "tools": tools,
        "max_tokens": payload.get("max_tokens"),
        "temperature": payload.get("temperature"),
        "top_p": payload.get("top_p"),
        "top_k": payload.get("top_k"),
        "metadata": payload.get("metadata"),
        "tool_choice": payload.get("tool_choice"),
        "stream": payload.get("stream"),
        "raw_payload_keys": list(payload.keys()),
        "messages": message_summaries,
        "diff_from_prev": _compute_diff(prev_messages, message_summaries),
        "modifications": modifications or [],
        "raw_payload": payload,
        "request_headers": {k: v for k, v in flow.request.headers.items()},
    }


# Count characters in system field — supports string or list of blocks
def _count_system_chars(system) -> int:
    if isinstance(system, str):
        return len(system)
    if isinstance(system, list):
        return sum(len(b.get("text", "")) for b in system if isinstance(b, dict))
    return 0


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


# Build latency update record written by response hook (linked to main entry via request_id)
def _build_latency_update(request_id: str,
                          ttfb_ms: Optional[float],
                          stream_duration_ms: Optional[float],
                          output_tokens: Optional[int],
                          output_tokens_per_sec: Optional[float],
                          n_stalls: int = 0,
                          max_stall_ms: Optional[float] = None,
                          total_stall_ms: Optional[float] = None) -> dict:
    return {
        "type": "latency_update",
        "request_id": request_id,
        "ttfb_ms": ttfb_ms,
        "stream_duration_ms": stream_duration_ms,
        "output_tokens": output_tokens,
        "output_tokens_per_sec": output_tokens_per_sec,
        "n_stalls": n_stalls,
        "max_stall_ms": max_stall_ms,
        "total_stall_ms": total_stall_ms,
    }


# Summarize raw message content for logging (str or list-of-blocks → truncated str)
def _summarize_content_for_log(content, max_chars=50000):
    if isinstance(content, str):
        return content[:max_chars]
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    parts.append(text)
                elif block.get("type") == "tool_result":
                    tc = block.get("content", "")
                    if isinstance(tc, str):
                        parts.append(tc)
        return "\n".join(parts)[:max_chars]
    return str(content)[:max_chars]


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
