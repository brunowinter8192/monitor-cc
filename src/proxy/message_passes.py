# INFRASTRUCTURE
from .strip_sr import (
    _strip_all_system_reminders,
    _strip_plan_mode_blocks,
    _strip_system_reminder,
    _strip_user_interrupt_sr,
    _strip_pyright_diagnostics,
    _IMP_LINE_RE,
)
from .content_strip import (
    _message_has_rejection,
    _strip_rejection_message,
)
from .payload_helpers import (
    _find_system_reminder_blocks,
    _find_all_system_reminder_blocks,
    _find_task_notification_blocks,
    _content_contains,
    _top_level_content_contains,
    _strip_task_notification_tags,
)
from .rules_config import _load_config
from .strip_po import _strip_persisted_output_previews, _PO_OPEN_TAG
from .strip_bg_completed import _strip_bg_exit_notifications, _BG_CMD_MARKER, _WAKEUP_TEXT
from .strip_hook_prefix import _strip_hook_prefix, _HOOK_PREFIX_MARKER
from .strip_git_lock import _strip_git_lock_advice, _GIT_LOCK_MARKER
from .strip_bd_noise import _strip_bd_noise, _BD_NOISE_MARKERS
from .rule_ops import _ops_from_content_change, _append_wakeup_text_to_content

# FUNCTIONS

# Role=system pass — strips entire content of every role='system' message by replacing with '.' — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_role_system_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx: dict = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "system":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not old_content or old_content == ".":
            result.append(msg)
            continue
        result.append({**msg, "content": "."})
        changed_indices.append(idx)
        pass_mods.append("stripped_role_system_msg")
        pass_removed_by_idx[idx] = [old_content if isinstance(old_content, str) else str(old_content)]
        pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, ".")
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


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


# First-pass message loop — elif-chain strips plan-mode, task-notification, task-tools-nag, deferred-tools, user-interrupt, rejection SRs — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_first_pass(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") == "user" and _content_contains(msg.get("content", ""), "Plan mode is active"):
            old_content = msg.get("content", "")
            stripped = _strip_plan_mode_blocks(old_content)
            if stripped:
                new_msg = dict(msg)
                new_msg["content"] = stripped
                result.append(new_msg)
                if stripped != old_content:
                    changed_indices.append(idx)
                    pass_mods.append("removed_plan_mode_sr")
                    pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "Plan mode")
                    pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, stripped)
            else:
                result.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
                changed_indices.append(idx)
                pass_mods.append("removed_plan_mode_sr")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "Plan mode")
                pass_injected_by_idx[idx] = ["(plan-mode reminder stripped by proxy)"]
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, "(plan-mode reminder stripped by proxy)")
        elif msg.get("role") == "user" and _top_level_content_contains(msg.get("content", ""), "<task-notification>"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_task_notification_tags(old_content)
            is_failed_bg = _content_contains(old_content, "<status>failed</status>")
            also_stripped_nag = False
            if _content_contains(new_msg["content"], "task tools haven"):
                new_msg["content"] = _strip_system_reminder(new_msg["content"], "task tools haven")
                pass_mods.append("stripped_task_tools_nag")
                also_stripped_nag = True
            new_msg["content"] = _append_wakeup_text_to_content(new_msg["content"])
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                mod_name = "replaced_task_notification" if is_failed_bg else "trimmed_task_notification"
                pass_mods.append(mod_name)
                removed = _find_task_notification_blocks(old_content)
                if also_stripped_nag:
                    removed = removed + _find_system_reminder_blocks(old_content, "task tools haven")
                pass_removed_by_idx[idx] = removed
                pass_injected_by_idx[idx] = [_WAKEUP_TEXT]
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_msg["content"])
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "task tools haven"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "task tools haven")
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_task_tools_nag")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "task tools haven")
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_msg["content"])
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "deferred tools are now available via ToolSearch"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "deferred tools are now available via ToolSearch")
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_deferred_tools_sr")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "deferred tools are now available via ToolSearch")
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_msg["content"])
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "user sent a new message while you were working"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_user_interrupt_sr(old_content, "user sent a new message while you were working")
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_user_interrupt_sr")
                _ui_blocks = _find_system_reminder_blocks(old_content, "user sent a new message while you were working")
                pass_removed_by_idx[idx] = [
                    line for block in _ui_blocks for line in _IMP_LINE_RE.findall(block)
                ] or _ui_blocks
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_msg["content"])
        elif msg.get("role") == "user" and _message_has_rejection(msg.get("content", "")):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_rejection_message(old_content)
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_rejection_message")
                pass_removed_by_idx[idx] = ["(rejection marker stripped by proxy)"]
                pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_msg["content"])
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# Cumulative second pass — strips Skills, agent-types, claudeMd, pyright, ENV-context SRs from every user message including those already touched by pass 1 — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_cumulative_sr_strips(messages: list) -> tuple:
    _SKILLS_MARKER = "The following skills are available for use with the Skill tool"
    _AGENT_TYPES_MARKER = "Available agent types for the Agent tool"
    _CLAUDEMD_MARKER = "# claudeMd"
    _PYRIGHT_ENABLED = _load_config().get("pyright_diagnostics_strip", {}).get("enabled", False)
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        content = msg.get("content", "")
        if not content:
            result.append(msg)
            continue
        original_before_pass = content
        cur_pass_mods = []
        if _content_contains(content, _SKILLS_MARKER):
            new_content = _strip_system_reminder(content, _SKILLS_MARKER)
            if new_content != content:
                content = new_content
                cur_pass_mods.append("stripped_skills_sr")
        if _content_contains(content, _AGENT_TYPES_MARKER):
            new_content = _strip_system_reminder(content, _AGENT_TYPES_MARKER)
            if new_content != content:
                content = new_content
                cur_pass_mods.append("stripped_agent_types_sr")
        if _content_contains(content, _CLAUDEMD_MARKER):
            new_content = _strip_system_reminder(content, _CLAUDEMD_MARKER)
            if new_content != content:
                content = new_content
                cur_pass_mods.append("stripped_claudemd_sr")
        if _PYRIGHT_ENABLED and _content_contains(content, "<new-diagnostics>"):
            new_content = _strip_pyright_diagnostics(content)
            if new_content != content:
                content = new_content
                cur_pass_mods.append("stripped_pyright_diagnostics")
        if content != original_before_pass:
            result.append({**msg, "content": content})
            pass_mods.extend(cur_pass_mods)
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = [
                sr for sr in _find_all_system_reminder_blocks(original_before_pass)
                if sr not in _find_all_system_reminder_blocks(content)
            ]
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(original_before_pass, content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# Final SR pass — strips all remaining system-reminder blocks from every user message — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_final_sr_pass(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        new_content = _strip_all_system_reminders(old_content)
        if new_content != old_content:
            result.append({**msg, "content": new_content})
            pass_mods.append("stripped_all_sr_msg0" if idx == 0 else "stripped_all_sr")
            changed_indices.append(idx)
            remaining = _find_all_system_reminder_blocks(new_content)
            pass_removed_by_idx[idx] = [
                sr for sr in _find_all_system_reminder_blocks(old_content) if sr not in remaining
            ]
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# PO-preview pass — strips Preview sections from persisted-output blocks in user messages — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_po_preview_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not _content_contains(old_content, _PO_OPEN_TAG):
            result.append(msg)
            continue
        new_content, po_removed = _strip_persisted_output_previews(old_content)
        if po_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("stripped_po_preview")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = po_removed
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# BG-exit-notification pass — strips "Background command "..." failed with exit code 143/137" lines from user messages — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_bg_exit_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not _top_level_content_contains(old_content, _BG_CMD_MARKER):
            result.append(msg)
            continue
        new_content, bg_removed = _strip_bg_exit_notifications(old_content)
        if bg_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("replaced_bg_completed_text")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = bg_removed
            pass_injected_by_idx[idx] = [_WAKEUP_TEXT]
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# Hook-prefix pass — strips PreToolUse:<Tool> hook error: [python3 <path>]: prefix from user message tool_result content — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_hook_prefix_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not _content_contains(old_content, _HOOK_PREFIX_MARKER):
            result.append(msg)
            continue
        new_content, hp_removed = _strip_hook_prefix(old_content)
        if hp_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("stripped_hook_error_prefix")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = hp_removed
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# Git-lock-advice pass — strips constant git index.lock advice block from user message tool_result content — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_git_lock_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not _content_contains(old_content, _GIT_LOCK_MARKER):
            result.append(msg)
            continue
        new_content, gl_removed = _strip_git_lock_advice(old_content)
        if gl_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("stripped_git_lock_advice")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = gl_removed
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# BD-noise pass — strips bd informational auto-import/export lines from user message tool_result content — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_bd_noise_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not any(_content_contains(old_content, m) for m in _BD_NOISE_MARKERS):
            result.append(msg)
            continue
        new_content, bd_removed = _strip_bd_noise(old_content)
        if bd_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("stripped_bd_noise")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = bd_removed
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk
