# INFRASTRUCTURE
import re
from .strip_sn_notice import _strip_sn_notice
from .strip_bg_completed import _WAKEUP_TEXT
from .rule_ops import _ops_from_content_change

# FUNCTIONS

def _dedup_wakeup_blocks(messages: list) -> tuple:
    _wakeup_core = _WAKEUP_TEXT.rstrip('\n')
    result = []
    ops_by_msg_blk: dict = {}
    for idx, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, list):
            seen = False
            new_content = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text", "").rstrip('\n') == _wakeup_core:
                    if not seen:
                        seen = True
                        new_content.append(block)
                else:
                    new_content.append(block)
            if len(new_content) != len(content):
                result.append({**msg, "content": new_content})
                ops_by_msg_blk[idx] = _ops_from_content_change(content, new_content)
            else:
                result.append(msg)
        elif isinstance(content, str) and content.count(_wakeup_core) > 1:
            first = content.index(_wakeup_core)
            end = first + len(_wakeup_core)
            if end < len(content) and content[end] == '\n':
                end += 1
            new_content_str = content[:end]
            result.append({**msg, "content": new_content_str})
            ops_by_msg_blk[idx] = _ops_from_content_change(content, new_content_str)
        else:
            result.append(msg)
    return result, ops_by_msg_blk


_SR_FULL_WRAP_RE = re.compile(r'\A<system-reminder>\n(.*)</system-reminder>\s*\Z', re.DOTALL)


def _unwrap_full_sr_wrapper(content):
    if isinstance(content, str):
        m = _SR_FULL_WRAP_RE.match(content)
        if not m:
            return content, []
        inner, sn_removed = _strip_sn_notice(m.group(1))
        return inner, sn_removed
    if isinstance(content, list):
        result = []
        removed = []
        changed = False
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                m = _SR_FULL_WRAP_RE.match(block.get('text', ''))
                if m:
                    inner, sn_removed = _strip_sn_notice(m.group(1))
                    result.append({**block, 'text': inner})
                    removed.extend(sn_removed)
                    changed = True
                    continue
            result.append(block)
        return (result, removed) if changed else (content, [])
    return content, []
