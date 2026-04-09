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

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent)), "src")
sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST, AGENT_TRIMMED_DESCRIPTION


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
            modified_payload, modifications, original_system2 = apply_modification_rules(payload)

            # Log MODIFIED payload (after rule application, before tool strip + cache breakpoints)
            entry = _build_entry(flow, modified_payload, self.prev_messages_by_model.get(model_family), modifications)
            if original_system2 is not None:
                entry['original_system2_text'] = original_system2
            _write_entry(self.log_file, entry)

            # Strip unused tools from the modified payload before sending to API
            modified_payload, stripped_count = _strip_unused_tools(modified_payload)
            if stripped_count > 0:
                modifications.append(f"stripped_{stripped_count}_unused_tools")

            # Cache-control: strip CC's markers, set our own on the modified payload
            prev_mod_msgs = self.prev_messages_by_model.get(model_family)
            modified_payload = _strip_all_cache_control(modified_payload)
            modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)

            # Store MODIFIED message summaries for next request's diff (BP3 stability)
            self.prev_messages_by_model[model_family] = [
                _summarize_message(m) for m in modified_payload.get("messages", [])
            ]

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


_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"


# Check if user message content contains a tool_result block with the rejection text
def _message_has_rejection(content) -> bool:
    if isinstance(content, str):
        return _REJECTION_MARKER in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tool_content = block.get("content", "")
            if isinstance(tool_content, str) and _REJECTION_MARKER in tool_content:
                return True
            if isinstance(tool_content, list) and any(
                _REJECTION_MARKER in sub.get("text", "")
                for sub in tool_content if isinstance(sub, dict)
            ):
                return True
    return False


# Replace rejection tool_result block content with '.'
def _strip_rejection_message(content):
    if isinstance(content, str):
        return "."
    if isinstance(content, list):
        result = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_content = block.get("content", "")
                has_rejection = (isinstance(tool_content, str) and _REJECTION_MARKER in tool_content) or (
                    isinstance(tool_content, list) and any(
                        _REJECTION_MARKER in sub.get("text", "")
                        for sub in tool_content if isinstance(sub, dict)
                    )
                )
                result.append({**block, "content": "."} if has_rejection else block)
            else:
                result.append(block)
        return result
    return content


# Extract SessionStart system-reminder block from MSG[0] content. Returns (modified_content, extracted_text_or_None).
def _extract_session_start_block(content):
    _RULES_MARKER = "SessionStart hook additional context:"
    _TAG_OPEN = "<system-reminder>"
    _TAG_CLOSE = "</system-reminder>"

    def _extract_from_text(text: str):
        if _RULES_MARKER not in text:
            return text, None
        marker_idx = text.index(_RULES_MARKER)
        open_idx = text.rfind(_TAG_OPEN, 0, marker_idx)
        if open_idx == -1:
            return text, None
        close_idx = text.find(_TAG_CLOSE, marker_idx)
        if close_idx == -1:
            return text, None
        close_end = close_idx + len(_TAG_CLOSE)
        extracted = text[open_idx:close_end]
        remaining = (text[:open_idx] + text[close_end:]).strip() or "."
        return remaining, extracted

    if isinstance(content, str):
        return _extract_from_text(content)
    if isinstance(content, list):
        for i, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            new_text, extracted = _extract_from_text(block.get("text", ""))
            if extracted:
                new_blocks = list(content)
                new_blocks[i] = {**block, "text": new_text}
                return new_blocks, extracted
    return content, None


# Remove '# Session-specific guidance' section from text, keeping '# Environment' onward.
def _strip_session_guidance(text: str) -> str:
    marker = "# Session-specific guidance"
    env_marker = "# Environment"
    if marker not in text:
        return text
    start = text.index(marker)
    env_idx = text.find(env_marker, start)
    if env_idx == -1:
        return text[:start].strip() or "."
    return (text[:start] + text[env_idx:]).strip()


# Remove ALL cache_control markers from payload (system, tools, messages)
def _strip_all_cache_control(payload: dict) -> dict:
    result = dict(payload)

    # Strip from system blocks
    system = result.get("system", [])
    if isinstance(system, list):
        new_system = []
        for block in system:
            if isinstance(block, dict) and "cache_control" in block:
                block = {k: v for k, v in block.items() if k != "cache_control"}
            new_system.append(block)
        result["system"] = new_system

    # Strip from tools
    tools = result.get("tools", [])
    if tools:
        new_tools = []
        for tool in tools:
            if isinstance(tool, dict) and "cache_control" in tool:
                tool = {k: v for k, v in tool.items() if k != "cache_control"}
            new_tools.append(tool)
        result["tools"] = new_tools

    # Strip from messages (top-level and content blocks)
    messages = result.get("messages", [])
    new_messages = []
    for msg in messages:
        new_msg = {k: v for k, v in msg.items() if k != "cache_control"}
        content = new_msg.get("content", "")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and "cache_control" in block:
                    block = {k: v for k, v in block.items() if k != "cache_control"}
                new_blocks.append(block)
            new_msg["content"] = new_blocks
        new_messages.append(new_msg)
    result["messages"] = new_messages

    return result


# Set our own cache_control breakpoints (max 4) on the already-modified, stripped payload.
# prev_mod_messages: summaries from the PREVIOUS request's modified payload (for BP3).
def _set_cache_breakpoints(payload: dict, prev_mod_messages: list = None) -> dict:
    result = dict(payload)
    bp_count = 0
    cc_marker = {"type": "ephemeral", "ttl": "1h"}
    cc_marker_global = {"type": "ephemeral", "ttl": "1h", "scope": "global"}

    # BP1: rules block (SessionStart system-reminder), fallback to last system block
    system = result.get("system", [])
    if isinstance(system, list) and system:
        new_system = list(system)
        rules_prefix = "<system-reminder>\nSessionStart hook additional context:"
        rules_idx = next(
            (i for i, b in enumerate(new_system) if isinstance(b, dict) and b.get("text", "").startswith(rules_prefix)),
            None,
        )
        target_idx = rules_idx if rules_idx is not None else len(new_system) - 1
        target = new_system[target_idx]
        if isinstance(target, dict):
            new_system[target_idx] = {**target, "cache_control": cc_marker_global}
            result["system"] = new_system
            bp_count += 1

    # BP2: last tool WITHOUT defer_loading (defer_loading + cache_control = API error)
    tools = result.get("tools", [])
    if tools:
        new_tools = list(tools)
        for ti in range(len(new_tools) - 1, -1, -1):
            tool = new_tools[ti]
            if isinstance(tool, dict) and not tool.get("defer_loading"):
                new_tools[ti] = {**tool, "cache_control": cc_marker}
                bp_count += 1
                break
        result["tools"] = new_tools

    # BP3: last message that is UNCHANGED from previous request
    messages = result.get("messages", [])
    if messages and prev_mod_messages is not None:
        curr_summaries = [_summarize_message(m) for m in messages]
        diff = _compute_diff(prev_mod_messages, curr_summaries)
        first_diff = diff.get("first_diff_index", -1)

        # Place BP3 at the message just before the first difference
        if first_diff > 0:
            bp3_idx = first_diff - 1
            messages = list(messages)
            messages[bp3_idx] = _add_cache_control_to_message(messages[bp3_idx], cc_marker)
            bp_count += 1

    # BP4: last message (for next request's cache)
    if messages:
        last_idx = len(messages) - 1
        # Don't double-set if BP3 already set on last message
        if not _has_cache_control(messages[last_idx]):
            messages = list(messages) if not isinstance(messages, list) else messages
            messages[last_idx] = _add_cache_control_to_message(messages[last_idx], cc_marker)
            bp_count += 1

    result["messages"] = messages
    return result


# Add cache_control to the last content block of a message
def _add_cache_control_to_message(msg: dict, cc_marker: dict) -> dict:
    new_msg = dict(msg)
    content = new_msg.get("content", "")
    if isinstance(content, list) and content:
        new_blocks = list(content)
        last_block = new_blocks[-1]
        if isinstance(last_block, dict):
            new_blocks[-1] = {**last_block, "cache_control": cc_marker}
        new_msg["content"] = new_blocks
    elif isinstance(content, str):
        # String content → wrap in block to attach cache_control
        new_msg["content"] = [{"type": "text", "text": content, "cache_control": cc_marker}]
    return new_msg


# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules)
def apply_modification_rules(payload: dict) -> tuple:
    modifications = []
    changed = False

    # Pre-process MSG[0]: extract SessionStart rules block → will be inserted into system array
    extracted_rules_text = None
    messages_to_process = list(payload.get("messages", []))
    if messages_to_process:
        msg0 = messages_to_process[0]
        if msg0.get("role") == "user" and _content_contains(msg0.get("content", ""), "SessionStart hook additional context:"):
            modified_content, extracted_rules_text = _extract_session_start_block(msg0.get("content", ""))
            if extracted_rules_text:
                messages_to_process[0] = {**msg0, "content": modified_content}
                modifications.append("extracted_rules_to_system")
                changed = True

    new_messages = []
    for msg in messages_to_process:
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
        elif msg.get("role") == "user" and _message_has_rejection(msg.get("content", "")):
            new_msg = dict(msg)
            new_msg["content"] = _strip_rejection_message(msg.get("content", ""))
            new_messages.append(new_msg)
            modifications.append("stripped_rejection_message")
            changed = True
        else:
            new_messages.append(msg)

    system = payload.get("system", [])
    new_system = list(system) if isinstance(system, list) else system

    original_system2_text = None
    if isinstance(new_system, list) and len(new_system) >= 3:
        block = new_system[2]
        if isinstance(block, dict) and block.get("type") == "text":
            original_system2_text = block.get("text", "")
            if extracted_rules_text:
                new_system[2] = {**block, "text": extracted_rules_text}
            else:
                new_system[2] = {**block, "text": "."}
            modifications.append("replaced_system_prompt")
            changed = True

    if extracted_rules_text and isinstance(new_system, list):
        # Strip session guidance from system[3] (rules now live in system[2], no extra block inserted)
        if len(new_system) > 3:
            block3 = new_system[3]
            if isinstance(block3, dict) and block3.get("type") == "text":
                stripped = _strip_session_guidance(block3.get("text", ""))
                if stripped != block3.get("text", ""):
                    new_system[3] = {**block3, "text": stripped}
                    modifications.append("stripped_session_guidance")

    if not changed:
        return payload, modifications, None
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications, original_system2_text


# Remove blocklisted tools from payload and trim Agent description. Returns (modified_payload, count_removed).
def _strip_unused_tools(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0
    kept = [t for t in tools if t.get("name") not in TOOL_BLOCKLIST]
    removed = len(tools) - len(kept)
    trimmed = [
        {**t, "description": AGENT_TRIMMED_DESCRIPTION} if t.get("name") == "Agent" else t
        for t in kept
    ]
    if removed == 0 and trimmed == kept:
        return payload, 0
    modified = dict(payload)
    modified["tools"] = trimmed
    return modified, removed


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
