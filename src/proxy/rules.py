# INFRASTRUCTURE
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)

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
    _strip_session_guidance,
    _strip_git_status,
    _strip_tool_descriptions,
    _strip_sys3,
)
from .payload_helpers import (
    _find_system_reminder_blocks,
    _find_all_system_reminder_blocks,
    _find_task_notification_blocks,
    _strip_blocked_tool_references,
    _content_contains,
    _strip_task_notification_tags,
    _detect_sidecar,
    _detect_idle_recap,
)
from .rules_config import _load_config, _load_system2_rules
from .strip_po import _strip_persisted_output_previews, _PO_OPEN_TAG
from .strip_bg_completed import _strip_bg_exit_notifications, _BG_CMD_MARKER, _WAKEUP_SR

_WORKTREE_PATH_PATTERN = re.compile(r'(/[^\s]+)/\.claude/worktrees/[^/\s]+')

# ORCHESTRATOR

# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)
def apply_modification_rules(payload: dict, model_family: str = "opus", project_path: str = "") -> tuple:
    system_rules = _load_system2_rules(model_family, project_path)

    result = _check_idle_recap(payload)
    if result is not None:
        return result

    result = _check_sidecar(payload)
    if result is not None:
        return result

    messages_to_process = list(payload.get("messages", []))
    modifications = []
    changed = False
    stripped_msg_indices = []
    stripped_msg_originals = {}
    stripped_msg_removed = {}

    new_messages, pass_mods, pass_removed, c_idxs = _apply_first_pass(messages_to_process)
    modifications.extend(pass_mods)
    for idx in c_idxs:
        if idx not in stripped_msg_indices:
            stripped_msg_indices.append(idx)
            stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
        stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
    if c_idxs:
        changed = True

    new_messages, pass_mods, pass_removed, c_idxs = _apply_cumulative_sr_strips(new_messages)
    modifications.extend(pass_mods)
    for idx in c_idxs:
        if idx not in stripped_msg_indices:
            stripped_msg_indices.append(idx)
            stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
        stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
    if c_idxs:
        changed = True

    new_messages, pass_mods, pass_removed, c_idxs = _apply_final_sr_pass(new_messages)
    modifications.extend(pass_mods)
    for idx in c_idxs:
        if idx not in stripped_msg_indices:
            stripped_msg_indices.append(idx)
            stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
        stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
    if c_idxs:
        changed = True

    new_messages, pass_mods, pass_removed, c_idxs = _apply_po_preview_strip(new_messages)
    modifications.extend(pass_mods)
    for idx in c_idxs:
        if idx not in stripped_msg_indices:
            stripped_msg_indices.append(idx)
            stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
        stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
    if c_idxs:
        changed = True

    new_messages, pass_mods, pass_removed, c_idxs = _apply_bg_exit_strip(new_messages)
    modifications.extend(pass_mods)
    for idx in c_idxs:
        if idx not in stripped_msg_indices:
            stripped_msg_indices.append(idx)
            stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
        stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
    if c_idxs:
        changed = True

    new_system, original_system2_text, sys_mods, sys_changed = _apply_system_passes(
        payload.get("system", []), system_rules
    )
    modifications.extend(sys_mods)
    if sys_changed:
        changed = True

    if not changed:
        return payload, modifications, None, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed


# FUNCTIONS

# Short-circuit for CC idle-recap injected message — returns full 6-tuple if detected, None otherwise
def _check_idle_recap(payload: dict) -> tuple:
    if not _detect_idle_recap(payload):
        return None
    msgs = payload["messages"]
    idx = len(msgs) - 1
    orig_content = msgs[idx]["content"]
    marker = f"[IDLE_RECAP_STRIPPED_{len(orig_content)}_BYTES]"
    modified = dict(payload)
    modified["messages"] = list(msgs)
    modified["messages"][idx] = {**msgs[idx], "content": marker}
    return (
        modified,
        ["stripped_idle_recap"],
        None,
        [idx],
        {idx: orig_content},
        {idx: [orig_content]},
    )


# Short-circuit for sidecar single-message requests — returns full 6-tuple if detected, None otherwise
def _check_sidecar(payload: dict) -> tuple:
    if not _detect_sidecar(payload):
        return None
    orig_content = payload["messages"][0]["content"]
    orig_len = len(orig_content)
    marker = f"[SIDECAR_STRIPPED_{orig_len}_BYTES]"
    modified = dict(payload)
    modified["messages"] = [{**payload["messages"][0], "content": marker}]
    return (
        modified,
        ["stripped_sidecar_content"],
        None,
        [0],
        {0: orig_content},
        {0: [orig_content]},
    )


# Append _WAKEUP_SR to content (str or list) as wake-up reminder for failed bg-task signals
def _append_wakeup_sr_to_content(content):
    if isinstance(content, str):
        sep = '' if not content or content.endswith('\n') else '\n'
        return content + sep + _WAKEUP_SR + '\n'
    if isinstance(content, list):
        return list(content) + [{'type': 'text', 'text': _WAKEUP_SR}]
    return content


# First-pass message loop — elif-chain strips plan-mode, task-notification, task-tools-nag, deferred-tools, user-interrupt, rejection SRs — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices)
def _apply_first_pass(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
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
            else:
                result.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
                changed_indices.append(idx)
                pass_mods.append("removed_plan_mode_sr")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "Plan mode")
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "<task-notification>"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_task_notification_tags(old_content)
            is_failed_bg = _content_contains(old_content, "<status>failed</status>")
            also_stripped_nag = False
            if _content_contains(new_msg["content"], "task tools haven"):
                new_msg["content"] = _strip_system_reminder(new_msg["content"], "task tools haven")
                pass_mods.append("stripped_task_tools_nag")
                also_stripped_nag = True
            if is_failed_bg:
                new_msg["content"] = _append_wakeup_sr_to_content(new_msg["content"])
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                mod_name = "replaced_task_notification" if is_failed_bg else "trimmed_task_notification"
                pass_mods.append(mod_name)
                removed = _find_task_notification_blocks(old_content)
                if also_stripped_nag:
                    removed = removed + _find_system_reminder_blocks(old_content, "task tools haven")
                pass_removed_by_idx[idx] = removed
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "task tools haven"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "task tools haven")
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_task_tools_nag")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "task tools haven")
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "deferred tools are now available via ToolSearch"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "deferred tools are now available via ToolSearch")
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_deferred_tools_sr")
                pass_removed_by_idx[idx] = _find_system_reminder_blocks(old_content, "deferred tools are now available via ToolSearch")
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
        elif msg.get("role") == "user" and _message_has_rejection(msg.get("content", "")):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_rejection_message(old_content)
            result.append(new_msg)
            if new_msg["content"] != old_content:
                changed_indices.append(idx)
                pass_mods.append("stripped_rejection_message")
                pass_removed_by_idx[idx] = ["(rejection marker stripped by proxy)"]
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices


# Cumulative second pass — strips Skills, claudeMd, pyright SRs from every user message including those already touched by pass 1 — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices)
def _apply_cumulative_sr_strips(messages: list) -> tuple:
    _SKILLS_MARKER = "The following skills are available for use with the Skill tool"
    _CLAUDEMD_MARKER = "# claudeMd"
    _PYRIGHT_ENABLED = _load_config().get("pyright_diagnostics_strip", {}).get("enabled", False)
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
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
            removed = []
            if "stripped_skills_sr" in cur_pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, _SKILLS_MARKER))
            if "stripped_claudemd_sr" in cur_pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, _CLAUDEMD_MARKER))
            if "stripped_pyright_diagnostics" in cur_pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, "<new-diagnostics>"))
            pass_removed_by_idx[idx] = removed
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices


# Final SR pass — strips all remaining system-reminder blocks from every user message — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices)
def _apply_final_sr_pass(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
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
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices


# PO-preview pass — strips Preview sections from persisted-output blocks in user messages — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices)
def _apply_po_preview_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
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
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices


# BG-exit-notification pass — strips "Background command "..." failed with exit code 143/137" lines from user messages — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices)
def _apply_bg_exit_strip(messages: list) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        if not _content_contains(old_content, _BG_CMD_MARKER):
            result.append(msg)
            continue
        new_content, bg_removed = _strip_bg_exit_notifications(old_content)
        if bg_removed:
            result.append({**msg, "content": new_content})
            pass_mods.append("replaced_bg_completed_text")
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = bg_removed
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices


# System-block passes — injects system2 rules and normalizes system3 session-guidance / worktree paths — returns (new_system, original_system2_text, mods, sys_changed)
def _apply_system_passes(system, system_rules: str) -> tuple:
    new_system = list(system) if isinstance(system, list) else system
    original_system2_text = None
    mods = []
    sys_changed = False
    if isinstance(new_system, list) and len(new_system) >= 3:
        block = new_system[2]
        if isinstance(block, dict) and block.get("type") == "text":
            original_system2_text = block.get("text", "")
            new_system[2] = {**block, "text": system_rules if system_rules else "."}
            mods.append("replaced_system_prompt")
            sys_changed = True
    if isinstance(new_system, list) and len(new_system) > 3:
        block3 = new_system[3]
        if isinstance(block3, dict) and block3.get("type") == "text":
            text3 = block3.get("text", "")
            stripped = _strip_session_guidance(text3)
            if stripped != text3:
                text3 = stripped
                mods.append("stripped_session_guidance")
            git_stripped = _strip_git_status(text3)
            if git_stripped != text3:
                text3 = git_stripped
                mods.append("stripped_git_status")
            normalized = _WORKTREE_PATH_PATTERN.sub(r'\1', text3)
            if normalized != text3:
                text3 = normalized
                mods.append("normalized_worktree_path")
            if text3 != block3.get("text", ""):
                new_system[3] = {**block3, "text": text3}
    return new_system, original_system2_text, mods, sys_changed
