# INFRASTRUCTURE
import json
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST

from .content_strip import (
    _strip_plan_mode_blocks,
    _strip_system_reminder,
    _message_has_rejection,
    _strip_rejection_message,
    _strip_session_guidance,
)

_SHARED_RULES_DIR = Path.home() / ".claude" / "shared-rules"
_PROXY_RULES_CONFIG = _SHARED_RULES_DIR / "proxy_rules.json"
_file_cache: dict = {}
_config_cache: list = [None]

# FUNCTIONS

# Remove tool_reference blocks for blocked tools from tool_result content blocks
def _strip_blocked_tool_references(payload: dict) -> dict:
    messages = payload.get("messages", [])
    new_messages = []
    modified = False
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, list):
            new_messages.append(msg)
            continue
        new_content = []
        changed = False
        for block in content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue
            if block.get("type") == "tool_result":
                inner = block.get("content", [])
                if isinstance(inner, list):
                    filtered = [
                        item for item in inner
                        if not (isinstance(item, dict) and item.get("type") == "tool_reference" and item.get("tool_name") in TOOL_BLOCKLIST)
                    ]
                    if len(filtered) != len(inner):
                        block = {**block, "content": filtered}
                        changed = True
            new_content.append(block)
        if changed:
            new_messages.append({**msg, "content": new_content})
            modified = True
        else:
            new_messages.append(msg)
    if not modified:
        return payload
    result = dict(payload)
    result["messages"] = new_messages
    return result


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


# Load proxy_rules.json config, re-reading only when mtime changes
def _load_config() -> dict:
    try:
        mtime = _PROXY_RULES_CONFIG.stat().st_mtime
        cached = _config_cache[0]
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(_PROXY_RULES_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
        _config_cache[0] = (mtime, config)
        return config
    except Exception:
        return {}


# Read a rule file by path relative to shared-rules dir, caching by mtime
def _read_rule_file(rel_path: str) -> str:
    path = _SHARED_RULES_DIR / rel_path
    try:
        mtime = path.stat().st_mtime
        cached = _file_cache.get(rel_path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        content = path.read_text(encoding="utf-8")
        _file_cache[rel_path] = (mtime, content)
        return content
    except Exception:
        return ""


# Detect session type from model name in payload: sonnet/haiku → worker, opus → opus
def _get_session_type(payload: dict) -> str:
    model = payload.get("model", "").lower()
    if "sonnet" in model or "haiku" in model:
        return "worker"
    return "opus"


# Extract project working directory path from system[3] environment block
def _get_project_path(system: list) -> str:
    if not isinstance(system, list) or len(system) < 4:
        return ""
    block3 = system[3]
    if not isinstance(block3, dict) or block3.get("type") != "text":
        return ""
    text = block3.get("text", "")
    marker = "Primary working directory: "
    if marker not in text:
        return ""
    start = text.index(marker) + len(marker)
    end = text.find("\n", start)
    return text[start:end].strip() if end != -1 else text[start:].strip()


# Concatenate rule files for given session type from config
def _load_session_rules(session_type: str) -> str:
    config = _load_config()
    files = config.get("system2_rules", {}).get(session_type, {}).get("files", [])
    parts = [c for c in (_read_rule_file(f) for f in files) if c]
    return "\n\n".join(parts)


# Concatenate project-specific rule files using longest-prefix match on project_path
def _load_project_rules(project_path: str) -> str:
    if not project_path:
        return ""
    config = _load_config()
    project_rules = config.get("project_rules", {})
    best_prefix = ""
    best_files = []
    for prefix, proj_config in project_rules.items():
        if project_path.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_files = proj_config.get("files", [])
    parts = [c for c in (_read_rule_file(f) for f in best_files) if c]
    return "\n\n".join(parts)


# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals)
def apply_modification_rules(payload: dict) -> tuple:
    modifications = []
    changed = False

    session_type = _get_session_type(payload)
    system_rules = _load_session_rules(session_type)

    project_path = _get_project_path(payload.get("system", []))
    project_rules = _load_project_rules(project_path)

    messages_to_process = list(payload.get("messages", []))

    if project_rules and messages_to_process:
        msg0 = messages_to_process[0]
        if msg0.get("role") == "user":
            content = msg0.get("content", "")
            project_block = f"\n\n<system-reminder>\n{project_rules}\n</system-reminder>"
            if isinstance(content, str):
                messages_to_process[0] = {**msg0, "content": content + project_block}
            elif isinstance(content, list):
                messages_to_process[0] = {**msg0, "content": list(content) + [{"type": "text", "text": project_block}]}
            modifications.append("injected_project_rules")
            changed = True

    new_messages = []
    stripped_msg_indices = []
    stripped_msg_originals = {}
    for idx, msg in enumerate(messages_to_process):
        if msg.get("role") == "user" and _content_contains(msg.get("content", ""), "Plan mode is active"):
            stripped_msg_originals[idx] = msg.get("content", "")
            stripped = _strip_plan_mode_blocks(msg.get("content", ""))
            if stripped:
                new_msg = dict(msg)
                new_msg["content"] = stripped
                new_messages.append(new_msg)
            else:
                new_messages.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
            modifications.append("removed_plan_mode_sr")
            stripped_msg_indices.append(idx)
            changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "<task-notification>"):
            stripped_msg_originals[idx] = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_task_notification_tags(msg.get("content", ""))
            if _content_contains(new_msg["content"], "task tools haven"):
                new_msg["content"] = _strip_system_reminder(new_msg["content"], "task tools haven")
                modifications.append("stripped_task_tools_nag")
            new_messages.append(new_msg)
            modifications.append("trimmed_task_notification")
            stripped_msg_indices.append(idx)
            changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "task tools haven"):
            stripped_msg_originals[idx] = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(msg.get("content", ""), "task tools haven")
            new_messages.append(new_msg)
            modifications.append("stripped_task_tools_nag")
            stripped_msg_indices.append(idx)
            changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "deferred tools are now available via ToolSearch"):
            stripped_msg_originals[idx] = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(msg.get("content", ""), "deferred tools are now available via ToolSearch")
            new_messages.append(new_msg)
            modifications.append("stripped_deferred_tools_sr")
            stripped_msg_indices.append(idx)
            changed = True
        elif msg.get("role") == "user" and _message_has_rejection(msg.get("content", "")):
            stripped_msg_originals[idx] = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_rejection_message(msg.get("content", ""))
            new_messages.append(new_msg)
            modifications.append("stripped_rejection_message")
            stripped_msg_indices.append(idx)
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
            new_system[2] = {**block, "text": system_rules if system_rules else "."}
            modifications.append("replaced_system_prompt")
            changed = True

    if isinstance(new_system, list) and len(new_system) > 3:
        block3 = new_system[3]
        if isinstance(block3, dict) and block3.get("type") == "text":
            stripped = _strip_session_guidance(block3.get("text", ""))
            if stripped != block3.get("text", ""):
                new_system[3] = {**block3, "text": stripped}
                modifications.append("stripped_session_guidance")

    if not changed:
        return payload, modifications, None, stripped_msg_indices, stripped_msg_originals
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals
