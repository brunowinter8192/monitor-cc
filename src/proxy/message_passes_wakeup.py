# INFRASTRUCTURE
import re
from .strip_sn_notice import _strip_sn_notice
from .strip_bg_completed import _WAKEUP_TEXT
from .rule_ops import _ops_from_content_change

# FUNCTIONS

# Remove duplicate _WAKEUP_TEXT injections from messages — keeps first occurrence per message.
# TN path appends {text: _WAKEUP_TEXT} with trailing \n; BGK path inlines via _strip_bg_from_text
# which calls result.strip(), producing _WAKEUP_TEXT.rstrip('\n'). Both forms count as one wake-up.
# Comparison uses rstrip('\n') so both variants are matched as duplicates of each other.
# Returns (new_messages, ops_by_msg_blk) — ops record the removal of each duplicate wakeup block.
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


# Anchored full-wrap detector — CC (2026-09+) sometimes delivers a background-task wake-up as a
# SINGLE <system-reminder> block wrapping BOTH the SN-notice paragraph AND the <task-notification>
# tag (previously always arrived as one or the other, unwrapped) — same anchored-not-substring
# rationale as strip_sn_notice.py / strip_bg_launch_ack.py (FP-nuke class, see
# process-docs/message_strip_fp_nuke/). Matches only when the ENTIRE str (or a single list[text]
# block's own text) is exactly one <system-reminder>...</system-reminder> wrap — a wrap that is
# only PART of a larger message, or a tool_result quoting this shape, never matches (list content
# is walked per-block, tool_result blocks are skipped by construction — same non-descent as
# strip_sn_notice.py).
_SR_FULL_WRAP_RE = re.compile(r'\A<system-reminder>\n(.*)</system-reminder>\s*\Z', re.DOTALL)


# Strip a top-level <system-reminder> wrapper (and any SN-notice paragraph inside it) around
# already-TN-processed content — CC's wrapped bg-task wake-up shape (2026-09+, see
# _SR_FULL_WRAP_RE above) hides the SN paragraph from strip_sn_notice.py's anchored
# lstrip().startswith() check (the wrapper, not the paragraph, sits at position 0), so
# _apply_sn_notice_strip is a no-op on it and the wrapper survives _apply_first_pass's TN-tag
# replace untouched — left in place, _apply_final_sr_pass later full-strips the ENTIRE
# <system-reminder> block (wrapper AND the just-injected wake-up text) because the paragraph-
# prefixed inner text matches the 'system-notification' SR template (strip_sr.py, mode 'full').
# Called AFTER _replace_task_notification_tags, on content that no longer carries the TN tag
# itself — only needs to detect+remove the wrapper here; _strip_sn_notice (imported above) does
# the paragraph removal. No-op for the unwrapped shape (content doesn't start with
# '<system-reminder>') or any other content, str or list[text] alike — byte-identical output for
# every case this doesn't apply to. Returns (new_content, removed_chunks).
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
