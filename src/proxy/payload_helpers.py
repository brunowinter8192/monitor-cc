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
    pat = re.compile(r'(?m)^<system-reminder>.*?' + re.escape(marker) + r'.*?</system-reminder>', re.DOTALL)
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


# Replace task-notification XML blocks with plain summary text; strips all XML wrapper
def _strip_task_notification_tags(content):
    _NOTIF_PAT = re.compile(r'(?m)^<task-notification>.*?</task-notification>\n?', re.DOTALL)
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
            elif btype == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    new_inner = _NOTIF_PAT.sub(_extract, inner)
                    result.append({**block, "content": new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub_blocks = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            new_text = _NOTIF_PAT.sub(_extract, sub.get("text", ""))
                            new_sub_blocks.append({**sub, "text": new_text})
                        else:
                            new_sub_blocks.append(sub)
                    result.append({**block, "content": new_sub_blocks})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result
    return content


# Detect CC idle-recap injection: last-msg-user, plain-string content, starts with idle marker
def _detect_idle_recap(payload: dict) -> bool:
    msgs = payload.get("messages", [])
    if not msgs:
        return False
    last = msgs[-1]
    if last.get("role") != "user":
        return False
    content = last.get("content", "")
    if not isinstance(content, str):
        return False
    return content.startswith("The user stepped away and is coming back.")


# Detect sidecar structural signature: single user-message with plain-string content and empty system
def _detect_sidecar(payload: dict) -> bool:
    if payload.get('model', '').startswith('claude-haiku'):
        return False
    msgs = payload.get("messages", [])
    if len(msgs) != 1:
        return False
    msg0 = msgs[0]
    if msg0.get("role") != "user":
        return False
    if not isinstance(msg0.get("content", ""), str):
        return False
    system = payload.get("system", "")
    if isinstance(system, str):
        return len(system.strip()) <= 10
    if isinstance(system, list):
        total = sum(
            len(b.get("text", "").strip()) if isinstance(b, dict) else len(str(b).strip())
            for b in system
        )
        return total <= 10
    return False
