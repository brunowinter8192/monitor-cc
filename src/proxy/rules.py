# INFRASTRUCTURE
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
    _extract_session_start_block,
    _strip_session_guidance,
)

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


# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals)
def apply_modification_rules(payload: dict) -> tuple:
    modifications = []
    changed = False

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
            if extracted_rules_text:
                new_system[2] = {**block, "text": extracted_rules_text}
            else:
                new_system[2] = {**block, "text": "."}
            modifications.append("replaced_system_prompt")
            changed = True

    if extracted_rules_text and isinstance(new_system, list):
        if len(new_system) > 3:
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
