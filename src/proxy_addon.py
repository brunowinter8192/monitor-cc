# INFRASTRUCTURE
import gzip
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from mitmproxy import http

ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"
DEFAULT_LOG_FILE = Path("/tmp/api_requests.jsonl")


# ORCHESTRATOR

class ProxyAddon:
    def __init__(self):
        self.log_file = _resolve_log_file()
        self.prev_messages_by_model: Dict[str, list] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        try:
            if not _is_messages_request(flow):
                return

            body = _decode_body(flow.request)
            if body is None:
                return

            payload = _parse_payload(body)
            if payload is None:
                return

            model = payload.get("model", "")
            model_family = "haiku" if "haiku" in model.lower() else "opus"
            modified_payload, modifications = apply_modification_rules(payload)
            entry = _build_entry(flow, payload, self.prev_messages_by_model.get(model_family), modifications)
            _write_entry(self.log_file, entry)
            self.prev_messages_by_model[model_family] = [_summarize_message(m) for m in payload.get("messages", [])]

            if modified_payload is not payload:
                flow.request.content = json.dumps(modified_payload).encode("utf-8")
                flow.request.headers.pop("content-encoding", None)
        except Exception as e:
            print(f"[proxy_addon] Error: {e}", file=sys.stderr)
            try:
                error_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_url": flow.request.pretty_url if flow else "unknown",
                }
                _write_entry(self.log_file, error_entry)
            except Exception:
                pass  # last resort — don't crash trying to log the error


# FUNCTIONS

# Resolve log file path from env vars — log_id gives per-proxy-start isolation
def _resolve_log_file() -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID")
    filename = f"api_requests_{log_id}.jsonl" if log_id else "api_requests.jsonl"
    if root:
        return Path(root) / "src" / "logs" / filename
    return Path("/tmp") / filename


# Check if flow is a POST to /v1/messages on api.anthropic.com
def _is_messages_request(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and flow.request.pretty_host == ANTHROPIC_API_HOST
        and flow.request.path.startswith(MESSAGES_PATH)
    )


# Decode request body, decompressing gzip if needed
def _decode_body(request: http.Request) -> Optional[bytes]:
    content = request.content
    if not content:
        return None
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            content = gzip.decompress(content)
        except OSError:
            return None
    return content


# Parse JSON payload from bytes
def _parse_payload(body: bytes) -> Optional[dict]:
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# Build full log entry dict from flow, payload, and previous request state
def _build_entry(flow: http.HTTPFlow, payload: dict, prev_messages: Optional[list], modifications: list = None) -> dict:
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
    return {
        "role": role,
        "type": msg_type,
        "chars": chars,
        "has_cache_control": _has_cache_control(msg),
        "content_preview": preview if preview else "",
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
    preview = ""
    primary_type = "text"

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "text")

        if btype == "text":
            text = block.get("text", "")
            total_chars += len(text)
            if not preview:
                classified = _classify_text(text)
                if classified != "text":
                    primary_type = classified
                preview = text

        elif btype == "tool_use":
            primary_type = "tool_use"
            name = block.get("name", "")
            input_str = json.dumps(block.get("input", {}))
            total_chars += len(name) + len(input_str)
            if not preview:
                preview = f"[tool_use:{name}]"

        elif btype == "tool_result":
            primary_type = "tool_result"
            result_content = block.get("content", "")
            if isinstance(result_content, str):
                total_chars += len(result_content)
                if not preview:
                    preview = result_content
            elif isinstance(result_content, list):
                for sub in result_content:
                    if isinstance(sub, dict):
                        t = sub.get("text", "")
                        total_chars += len(t)
                        if not preview:
                            preview = t
            if not preview:
                preview = "[tool_result]"

        elif btype == "thinking":
            if primary_type == "text":
                primary_type = "thinking"
            thinking_text = block.get("thinking", "")
            total_chars += len(thinking_text)
            if not preview:
                preview = thinking_text

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


# Remove only plan-mode blocks/sections from content, preserving everything else.
# Returns the remaining content, or None if nothing is left after stripping.
def _strip_plan_mode_blocks(content):
    if isinstance(content, list):
        kept = [b for b in content if not (isinstance(b, dict) and "Plan mode is active" in b.get("text", ""))]
        if not kept:
            return None
        for i, b in enumerate(kept):
            if isinstance(b, dict) and not b.get("text", "").strip():
                kept[i] = {**b, "text": "."}
        return kept
    if isinstance(content, str):
        # Remove the <system-reminder> block that contains plan-mode
        stripped = re.sub(
            r'<system-reminder>\s*Plan mode .*?</system-reminder>\s*',
            '', content, flags=re.DOTALL
        )
        return stripped.strip() or None
    return None


# Strip any <system-reminder> block whose text contains marker, from string or list content
def _strip_system_reminder(content, marker: str):
    pattern = re.compile(r'<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>\s*', re.DOTALL)
    if isinstance(content, str):
        return pattern.sub('', content) or "."
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                new_text = pattern.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
            else:
                result.append(block)
        return result
    return content


# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules)
def apply_modification_rules(payload: dict) -> tuple:
    modifications = []
    messages = payload.get("messages", [])
    new_messages = []
    changed = False
    for msg in messages:
        if msg.get("role") == "user" and _content_contains(msg.get("content", ""), "Plan mode is active"):
            stripped = _strip_plan_mode_blocks(msg.get("content", ""))
            if stripped:
                new_msg = dict(msg)
                new_msg["content"] = stripped
                new_messages.append(new_msg)
            else:
                new_messages.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
            modifications.append("removed_plan_mode_sr")
            changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "<task-notification>"):
            new_msg = dict(msg)
            new_msg["content"] = _strip_task_notification_tags(msg.get("content", ""))
            new_messages.append(new_msg)
            modifications.append("trimmed_task_notification")
            changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "task tools haven"):
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(msg.get("content", ""), "task tools haven")
            new_messages.append(new_msg)
            modifications.append("stripped_task_tools_nag")
            changed = True
        else:
            new_messages.append(msg)

    system = payload.get("system", [])
    new_system = system
    if isinstance(system, list) and len(system) >= 3:
        block = system[2]
        if isinstance(block, dict) and block.get("type") == "text" and len(block.get("text", "")) > 5000:
            new_block = dict(block)
            new_block["text"] = "."
            new_system = list(system)
            new_system[2] = new_block
            modifications.append("replaced_system_prompt")
            changed = True

    if not changed:
        return payload, modifications
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications


# Check if message content (str or list of blocks) contains a given substring
def _content_contains(content, substring: str) -> bool:
    if isinstance(content, str):
        return substring in content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and substring in block.get("text", ""):
                return True
    return False


# Remove output-file and tool-use-id tags from task-notification content
def _strip_task_notification_tags(content) -> str:
    _STRIP_PATTERN = re.compile(r'<(?:output-file|tool-use-id)>.*?</(?:output-file|tool-use-id)>\n?', re.DOTALL)
    if isinstance(content, str):
        return _STRIP_PATTERN.sub('', content)
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                new_text = _STRIP_PATTERN.sub('', block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
            else:
                result.append(block)
        return result
    return content


# Append log entry as a single JSONL line, creating parent dirs if needed
def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


addons = [ProxyAddon()]
