# INFRASTRUCTURE
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

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


# Build a summary dict for a single message
def _summarize_message(msg: dict) -> dict:
    role = msg.get("role", "unknown")
    content = msg.get("content", "")
    msg_type, chars, preview = _classify_content(role, content)
    blocks = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "text")
            has_cc = bool(block.get("cache_control"))
            if btype == "text":
                text = block.get("text", "")
                bchars = len(text)
                bpreview = text.split('\n')[0][:60]
            elif btype == "tool_use":
                name = block.get("name", "")
                bchars = len(name) + len(json.dumps(block.get("input", {})))
                bpreview = name
            elif btype == "tool_result":
                rc = block.get("content", "")
                if isinstance(rc, str):
                    bchars = len(rc)
                    bpreview = rc.split('\n')[0][:60]
                elif isinstance(rc, list):
                    bchars = sum(len(s.get("text", "")) for s in rc if isinstance(s, dict))
                    bpreview = next((s.get("text", "").split('\n')[0][:60] for s in rc if isinstance(s, dict) and s.get("text")), "")
                else:
                    bchars = 0
                    bpreview = ""
            elif btype == "thinking":
                thinking_text = block.get("thinking", "")
                bchars = len(thinking_text)
                bpreview = thinking_text.split('\n')[0][:60]
            else:
                bchars = len(json.dumps(block))
                bpreview = btype
            blocks.append({"type": btype, "chars": bchars, "preview": bpreview, "has_cc": has_cc})
    return {
        "role": role,
        "type": msg_type,
        "chars": chars,
        "has_cache_control": _has_cache_control(msg),
        "content_preview": preview if preview else "",
        "blocks": blocks,
    }


# Check if message or any content block has cache_control set
def _has_cache_control(msg: dict) -> bool:
    if msg.get("cache_control"):
        return True
    content = msg.get("content", "")
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("cache_control") for b in content)
    return False


# Classify message content — returns (type, total_chars, preview_text)
def _classify_content(role: str, content) -> tuple:
    if role == "system":
        if isinstance(content, str):
            return "system", len(content), content
        if isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            return "system", len(text), text
        return "system", 0, ""

    if isinstance(content, str):
        return _classify_text(content), len(content), content

    if isinstance(content, list):
        return _classify_blocks(content)

    return "text", 0, ""


# Classify plain text by checking for known special tag prefixes
def _classify_text(text: str) -> str:
    if "<system-reminder>" in text:
        return "system-reminder"
    if "<task-notification>" in text:
        return "task-notification"
    if "<command-message>" in text:
        return "command-message"
    return "text"


# Classify a list of content blocks — returns (primary_type, total_chars, preview_text)
def _classify_blocks(blocks: list) -> tuple:
    total_chars = 0
    parts = []
    primary_type = "text"

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "text")

        if btype == "text":
            text = block.get("text", "")
            total_chars += len(text)
            if not parts:
                classified = _classify_text(text)
                if classified != "text":
                    primary_type = classified
            parts.append(text)

        elif btype == "tool_use":
            primary_type = "tool_use"
            name = block.get("name", "")
            input_str = json.dumps(block.get("input", {}))
            total_chars += len(name) + len(input_str)
            parts.append(f"[tool_use:{name}]\n{input_str}")

        elif btype == "tool_result":
            primary_type = "tool_result"
            result_content = block.get("content", "")
            result_appended = False
            if isinstance(result_content, str):
                total_chars += len(result_content)
                if result_content:
                    parts.append(result_content)
                    result_appended = True
            elif isinstance(result_content, list):
                for sub in result_content:
                    if isinstance(sub, dict):
                        t = sub.get("text", "")
                        total_chars += len(t)
                        if t:
                            parts.append(t)
                            result_appended = True
            if not result_appended:
                parts.append("[tool_result]")

        elif btype == "thinking":
            if primary_type == "text":
                primary_type = "thinking"
            thinking_text = block.get("thinking", "")
            total_chars += len(thinking_text)
            parts.append(thinking_text)

    preview = "\n".join(parts)
    return primary_type, total_chars, preview


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


# Summarize raw message content for logging (str or list-of-blocks → truncated str)
def _summarize_content_for_log(content, max_chars=2000):
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
