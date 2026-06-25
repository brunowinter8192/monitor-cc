# INFRASTRUCTURE
import re
import sys
import os
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST

# FUNCTIONS

# Extract <system-reminder> blocks containing marker from str or list content (incl. tool_result)
def _find_system_reminder_blocks(content, marker: str) -> list:
    pat = re.compile(r'(?m)^<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>\n?', re.DOTALL)
    if isinstance(content, str):
        return pat.findall(content)
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                result.extend(pat.findall(block.get("text", "")))
            elif block.get("type") == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    result.extend(pat.findall(inner))
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            result.extend(pat.findall(sub.get("text", "")))
        return result
    return []


# Extract ALL <system-reminder>...</system-reminder> blocks from str or list content (incl. tool_result)
def _find_all_system_reminder_blocks(content) -> list:
    pat = re.compile(r'(?m)^<system-reminder>.*?</system-reminder>\n?', re.DOTALL)
    if isinstance(content, str):
        return pat.findall(content)
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                result.extend(pat.findall(block.get("text", "")))
            elif block.get("type") == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    result.extend(pat.findall(inner))
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            result.extend(pat.findall(sub.get("text", "")))
        return result
    return []


# Extract <task-notification>...</task-notification> blocks from str or list content (incl. tool_result)
def _find_task_notification_blocks(content) -> list:
    pat = re.compile(r'(?m)^<task-notification>.*?</task-notification>', re.DOTALL)
    if isinstance(content, str):
        return pat.findall(content)
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                result.extend(pat.findall(block.get("text", "")))
            elif block.get("type") == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    result.extend(pat.findall(inner))
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            result.extend(pat.findall(sub.get("text", "")))
        return result
    return []


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


# Check if message content (str or list of blocks incl. tool_result) contains a given substring
def _content_contains(content, substring: str) -> bool:
    if isinstance(content, str):
        return substring in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if substring in block.get("text", ""):
                return True
            if block.get("type") == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str) and substring in inner:
                    return True
                if isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and substring in sub.get("text", ""):
                            return True
    return False


# Extract <output-file> path from the first <task-notification> block in content (str or list); returns '' if absent
def _extract_task_notification_output_file(content) -> str:
    _OUTPUT_FILE_PAT = re.compile(r'<output-file>(.*?)</output-file>', re.DOTALL)
    for block_text in _find_task_notification_blocks(content):
        m = _OUTPUT_FILE_PAT.search(block_text)
        if m:
            return m.group(1).strip()
    return ''


# Replace <task-notification>...</task-notification> blocks inline with replacement_text (no separate append)
# Uses lambda form of re.sub to avoid backslash-sequence interpretation in replacement_text.
def _replace_task_notification_tags(content, replacement_text: str):
    _NOTIF_PAT = re.compile(r'(?m)^<task-notification>.*?</task-notification>\n?', re.DOTALL)
    _repl = lambda m: replacement_text  # noqa: E731
    if isinstance(content, str):
        return _NOTIF_PAT.sub(_repl, content) or '.'
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get("type")
            if btype == "text":
                new_text = _NOTIF_PAT.sub(_repl, block.get("text", ""))
                result.append({**block, "text": new_text or '.'})
            else:
                result.append(block)
        return result
    return content


# Check if content (str or top-level text blocks only — does NOT descend into tool_result) contains substring
def _top_level_content_contains(content, substring: str) -> bool:
    if isinstance(content, str):
        return substring in content
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and substring in block.get("text", ""):
                return True
    return False

