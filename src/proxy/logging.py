# INFRASTRUCTURE
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from .message_summary import _summarize_message
from .diff_engine import _diff_system, _diff_tools, _diff_messages, _diff_top_level_fields, _get_inner_text, build_message_spans
from .strip_vocab import attribute_chunk as _attribute_chunk

# fn attribution maps for fn_map field in _build_stripped_injected_deltas
_SYS_FN: dict[int, str] = {2: '_apply_system_passes', 3: '_strip_sys3'}
_FIELD_STRIP_FN: dict[str, str] = {
    'model': '_inject_model_override', 'max_tokens': '_inject_model_override',
    'thinking': '_inject_model_override', 'output_config': '_inject_model_override',
}
_FIELD_INJECT_FN: dict[str, str] = {
    **_FIELD_STRIP_FN, 'context_management': '_inject_context_management',
}
_MSG_CODE_TO_FN: dict[str, str] = {
    'REJ': '_apply_first_pass',  'TN':  '_apply_first_pass',
    'NAG': '_apply_first_pass',  'DEF': '_apply_first_pass',
    'UI':  '_apply_first_pass',  'PM':  '_apply_first_pass',
    'SK':  '_apply_cumulative_sr_strips', 'CMD': '_apply_cumulative_sr_strips',
    'PYR': '_apply_cumulative_sr_strips',
    'ALL': '_apply_final_sr_pass', 'ENV': '_apply_final_sr_pass',
    'SN':  '_apply_final_sr_pass', 'FM':  '_apply_final_sr_pass',
    'SC':  '_check_sidecar',       'IR':  '_check_idle_recap',
    'PP':  '_apply_po_preview_strip', 'BGK': '_apply_bg_exit_strip',
    'GL':  '_apply_git_lock_strip',   'BD':  '_apply_bd_noise_strip',
    'HP':  '_apply_hook_prefix_strip',
}

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
        "max_tokens": payload.get("max_tokens"),
        "output_config": payload.get("output_config"),
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


# MD5[:10] of pipe-joined span texts — stable identity for a set of stripped texts
def _hash_spans(texts: list) -> str:
    return hashlib.md5("|".join(texts).encode("utf-8")).hexdigest()[:10]


# MD5[:10] of ordered span sequence — stable identity for equal+injected span list (new _injected format)
def _hash_span_sequence(spans: list) -> str:
    return hashlib.md5("|".join(f"{tag}:{text}" for tag, text in spans).encode("utf-8")).hexdigest()[:10]


# Build stripped_delta and injected_delta entries and updated hash states
# Both payloads are normalized (cache_control stripped) at call site before passing here.
# prev_stripped / prev_injected: flat dicts of loc_key → hash from previous request (None = first).
# Returns (stripped_entry, injected_entry, new_stripped_hashes, new_injected_hashes).
# fn_map: top-level dict (loc_key → responsible fn) attached to both entries at write time.
# Old entries without fn_map (pre-materialization) are read-side safe — field simply absent.
def _build_stripped_injected_deltas(
    orig_payload: dict,
    fwd_payload: dict,
    request_id: str,
    prev_stripped: Optional[dict],
    prev_injected: Optional[dict],
    model: str,
    stripped_msg_removed: Optional[dict] = None,
) -> tuple:
    orig_norm = _strip_cache_control(orig_payload)
    fwd_norm = _strip_cache_control(fwd_payload)

    orig_sys = [b for b in (orig_norm.get("system", []) or []) if isinstance(b, dict)]
    fwd_sys = [b for b in (fwd_norm.get("system", []) or []) if isinstance(b, dict)]
    orig_tools = orig_norm.get("tools", []) or []
    fwd_tools = fwd_norm.get("tools", []) or []
    orig_msgs = orig_norm.get("messages", []) or []
    fwd_msgs = fwd_norm.get("messages", []) or []

    sys_diffs = _diff_system(orig_sys, fwd_sys)
    tools_diff = _diff_tools(orig_tools, fwd_tools)
    orig_msgs_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_msgs_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_msgs_norm, fwd_msgs_norm)
    field_diffs = _diff_top_level_fields(orig_norm, fwd_norm)

    is_first = prev_stripped is None
    new_s: dict = {}
    new_i: dict = {}
    s_fn_map: dict = {}
    i_fn_map: dict = {}

    # system
    s_sys: dict = {}
    i_sys: dict = {}
    for d in sys_diffs:
        idx_str = str(d["idx"])
        s_texts = [t for tag, t in d["spans"] if tag == "stripped" and t]
        i_spans = [(tag, t) for tag, t in d["spans"] if tag in ("equal", "injected") and t]
        has_i = any(tag == "injected" for tag, _ in i_spans)
        if s_texts:
            lk = f"sys.{d['idx']}"
            h = _hash_spans(s_texts)
            new_s[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_sys[idx_str] = s_texts
                s_fn_map[lk] = _SYS_FN.get(d["idx"], "_apply_system_passes")
        if has_i:
            lk = f"sys.{d['idx']}"
            h = _hash_span_sequence(i_spans)
            new_i[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_sys[idx_str] = i_spans
                i_fn_map[lk] = _SYS_FN.get(d["idx"], "_apply_system_passes")

    # tools
    s_tools: dict = {}
    i_tools: dict = {}
    for name in tools_diff["stripped"]:
        lk = f"tool_w.{name}"
        h = _hash_spans([name])
        new_s[lk] = h
        if is_first or (prev_stripped or {}).get(lk) != h:
            s_tools[name] = {"whole": True}
            s_fn_map[lk] = "_strip_unused_tools"
    for name in tools_diff["injected"]:
        lk = f"tool_w.{name}"
        h = _hash_spans([name])
        new_i[lk] = h
        if is_first or (prev_injected or {}).get(lk) != h:
            i_tools[name] = {"whole": True}
            i_fn_map[lk] = "inject_mcp_tools"
    for name, _o, _f, spans in tools_diff["desc_changes"]:
        s_texts = [t for tag, t in spans if tag == "stripped" and t]
        i_spans = [(tag, t) for tag, t in spans if tag in ("equal", "injected") and t]
        has_i = any(tag == "injected" for tag, _ in i_spans)
        if s_texts:
            lk = f"tool_d.{name}"
            h = _hash_spans(s_texts)
            new_s[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_tools[name] = {"desc": s_texts}
                s_fn_map[lk] = "_strip_tool_descriptions"
        if has_i:
            lk = f"tool_d.{name}"
            h = _hash_span_sequence(i_spans)
            new_i[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_tools[name] = {"desc": i_spans}
                i_fn_map[lk] = "inject_mcp_tools"

    # messages
    s_msgs: dict = {}
    i_msgs: dict = {}
    gt_chunks = stripped_msg_removed or {}
    for md in msg_diffs:
        midx = str(md["idx"])
        s_blks: dict = {}
        i_blks: dict = {}
        msg_chunks = gt_chunks.get(md["idx"], [])
        # Raw normalized block objects for inner-text extraction (GT path)
        om_norm = orig_msgs_norm[md["idx"]] if md["idx"] < len(orig_msgs_norm) else {}
        fm_norm = fwd_msgs_norm[md["idx"]] if md["idx"] < len(fwd_msgs_norm) else {}
        o_content_raw = om_norm.get("content", "") if isinstance(om_norm, dict) else ""
        f_content_raw = fm_norm.get("content", "") if isinstance(fm_norm, dict) else ""
        for bd in md["block_diffs"]:
            bidx_int = bd["bidx"]
            bidx = str(bidx_int)
            # GT span path: only when per-block filtered chunks are non-empty (gate per block)
            spans = bd["spans"]  # default: existing _diff_text result
            if msg_chunks:
                if isinstance(o_content_raw, list) and isinstance(f_content_raw, list):
                    ob = o_content_raw[bidx_int] if bidx_int < len(o_content_raw) else None
                    fb = f_content_raw[bidx_int] if bidx_int < len(f_content_raw) else None
                else:
                    ob, fb = o_content_raw, f_content_raw
                # None-block guard: skip GT if either block is missing (index out of range)
                if ob is not None and fb is not None:
                    o_inner = _get_inner_text(ob)
                    f_inner = _get_inner_text(fb)
                    blk_chunks = [c for c in msg_chunks if c in o_inner]
                    if blk_chunks:
                        spans, _ = build_message_spans(o_inner, f_inner, blk_chunks)
            s_texts = [t for tag, t in spans if tag == "stripped" and t]
            i_spans = [(tag, t) for tag, t in spans if tag in ("equal", "injected") and t]
            has_i = any(tag == "injected" for tag, _ in i_spans)
            if s_texts:
                lk = f"msg.{md['idx']}.{bd['bidx']}"
                h = _hash_spans(s_texts)
                new_s[lk] = h
                if is_first or (prev_stripped or {}).get(lk) != h:
                    s_blks[bidx] = s_texts
                    code = _attribute_chunk("\n".join(s_texts))
                    s_fn_map[lk] = _MSG_CODE_TO_FN.get(code, "unknown") if code else "unknown"
            if has_i:
                lk = f"msg.{md['idx']}.{bd['bidx']}"
                h = _hash_span_sequence(i_spans)
                new_i[lk] = h
                if is_first or (prev_injected or {}).get(lk) != h:
                    i_blks[bidx] = i_spans
                    i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t)
                    if "background done" in i_text:
                        i_fn_map[lk] = "_apply_bg_exit_strip"
                    else:
                        code = _attribute_chunk(i_text) if i_text else None
                        i_fn_map[lk] = _MSG_CODE_TO_FN.get(code, "unknown") if code else "unknown"
        if s_blks:
            s_msgs[midx] = s_blks
        if i_blks:
            i_msgs[midx] = i_blks

    # top-level fields
    s_fields: dict = {}
    i_fields: dict = {}
    for fd in field_diffs:
        key = fd["key"]
        lk = f"field.{key}"
        if fd["tag"] in ("stripped", "replaced"):
            h = _delta_hash(fd["orig"])
            new_s[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_fields[key] = fd["orig"]
                s_fn_map[lk] = _FIELD_STRIP_FN.get(key, "_inject_model_override")
        if fd["tag"] in ("injected", "replaced"):
            h = _delta_hash(fd["fwd"])
            new_i[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_fields[key] = fd["fwd"]
                i_fn_map[lk] = _FIELD_INJECT_FN.get(key, "_inject_model_override")

    now = datetime.now(timezone.utc)
    timestamp = f"{now.strftime('%Y-%m-%dT%H:%M:%S.')}{now.microsecond // 1000:03d}Z"
    counts = {"system": len(fwd_sys), "tools": len(fwd_tools), "messages": len(fwd_msgs)}

    stripped_entry = {
        "type": "stripped_delta",
        "request_id": request_id,
        "timestamp": timestamp,
        "model": model,
        "is_first": is_first,
        "counts": counts,
        "system_delta": s_sys,
        "tools_delta": s_tools,
        "messages_delta": s_msgs,
        "fields_delta": s_fields,
        "fn_map": s_fn_map,
    }
    injected_entry = {
        "type": "injected_delta",
        "request_id": request_id,
        "timestamp": timestamp,
        "model": model,
        "is_first": is_first,
        "counts": counts,
        "system_delta": i_sys,
        "tools_delta": i_tools,
        "messages_delta": i_msgs,
        "fields_delta": i_fields,
        "fn_map": i_fn_map,
    }
    return stripped_entry, injected_entry, new_s, new_i


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
