# INFRASTRUCTURE
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST

_REJECTION_MARKER = "The user doesn't want to proceed with this tool use"

# FUNCTIONS

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


# Check if user message content contains a tool_result block with the rejection marker
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


# Remove tool_reference blocks for blocked tools from tool_result content blocks
def _strip_blocked_tool_references(payload: dict) -> dict:
    messages = payload.get("messages", [])
    if not messages:
        return payload
    modified = False
    new_messages = []
    for msg in messages:
        content = msg.get("content", [])
        if not isinstance(content, list):
            new_messages.append(msg)
            continue
        new_content = []
        changed = False
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
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
