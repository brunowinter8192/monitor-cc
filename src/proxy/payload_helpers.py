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
    pat = re.compile(r'<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>', re.DOTALL)
    if isinstance(content, str):
        return pat.findall(content)
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                result.extend(pat.findall(block.get("text", "")))
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
            if block.get("type") == "text" and substring in block.get("text", ""):
                return True
    return False


# Replace task-notification XML blocks with plain summary text; strips all XML wrapper
def _strip_task_notification_tags(content):
    _NOTIF_PAT = re.compile(r'<task-notification>.*?</task-notification>\n?', re.DOTALL)
    _SUMMARY_PAT = re.compile(r'<summary>(.*?)</summary>', re.DOTALL)

    def _extract(m):
        sm = _SUMMARY_PAT.search(m.group(0))
        return (sm.group(1).strip() + '\n') if sm else ''

    if isinstance(content, str):
        return _NOTIF_PAT.sub(_extract, content)
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get("type")
            if btype == "text":
                new_text = _NOTIF_PAT.sub(_extract, block.get("text", ""))
                if not new_text.strip():
                    new_text = "."
                result.append({**block, "text": new_text})
            else:
                result.append(block)
        return result
    return content
