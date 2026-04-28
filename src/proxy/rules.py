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

_WORKTREE_PATH_PATTERN = re.compile(r'(/[^\s]+)/\.claude/worktrees/[^/\s]+')

# FUNCTIONS

# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)
def apply_modification_rules(payload: dict, model_family: str = "opus", project_path: str = "") -> tuple:
    modifications = []
    changed = False

    system_rules = _load_system2_rules(model_family, project_path)

    messages_to_process = list(payload.get("messages", []))

    # Idle-recap short-circuit: CC-injected fake user message when user goes idle
    if _detect_idle_recap(payload):
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

    # Sidecar short-circuit: single-message plain-string payload with empty system
    # Runs before all passes so no spurious stripped_all_sr_msg0 can fire on the marker
    if _detect_sidecar(payload):
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

    new_messages = []
    stripped_msg_indices = []
    stripped_msg_originals = {}
    stripped_msg_removed = {}
    for idx, msg in enumerate(messages_to_process):
        if msg.get("role") == "user" and _content_contains(msg.get("content", ""), "Plan mode is active"):
            old_content = msg.get("content", "")
            stripped = _strip_plan_mode_blocks(old_content)
            if stripped:
                new_msg = dict(msg)
                new_msg["content"] = stripped
                new_messages.append(new_msg)
                if stripped != old_content:
                    stripped_msg_originals[idx] = old_content
                    stripped_msg_indices.append(idx)
                    modifications.append("removed_plan_mode_sr")
                    stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "Plan mode")
                    changed = True
            else:
                new_messages.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("removed_plan_mode_sr")
                stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "Plan mode")
                changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "<task-notification>"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_task_notification_tags(old_content)
            also_stripped_nag = False
            if _content_contains(new_msg["content"], "task tools haven"):
                new_msg["content"] = _strip_system_reminder(new_msg["content"], "task tools haven")
                modifications.append("stripped_task_tools_nag")
                also_stripped_nag = True
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("trimmed_task_notification")
                removed = stripped_msg_removed.get(idx, [])
                removed = removed + _find_task_notification_blocks(old_content)
                if also_stripped_nag:
                    removed = removed + _find_system_reminder_blocks(old_content, "task tools haven")
                stripped_msg_removed[idx] = removed
                changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "task tools haven"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "task tools haven")
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("stripped_task_tools_nag")
                stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "task tools haven")
                changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "deferred tools are now available via ToolSearch"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_system_reminder(old_content, "deferred tools are now available via ToolSearch")
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("stripped_deferred_tools_sr")
                stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "deferred tools are now available via ToolSearch")
                changed = True
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "user sent a new message while you were working"):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_user_interrupt_sr(old_content, "user sent a new message while you were working")
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("stripped_user_interrupt_sr")
                _ui_blocks = _find_system_reminder_blocks(old_content, "user sent a new message while you were working")
                stripped_msg_removed[idx] = [
                    line for block in _ui_blocks for line in _IMP_LINE_RE.findall(block)
                ] or _ui_blocks  # fallback: no IMPORTANT line found → record full block
                changed = True
        elif msg.get("role") == "user" and _message_has_rejection(msg.get("content", "")):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_rejection_message(old_content)
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("stripped_rejection_message")
                stripped_msg_removed[idx] = ["(rejection marker stripped by proxy)"]
                changed = True
        else:
            new_messages.append(msg)

    # Cumulative second pass: strip Skills sr + claudeMd sr + pyright diagnostics sr from any
    # user message, even if the message already went through a strip branch above.
    # IMPORTANT: markers that can co-occur with the first-pass elif conditions MUST live here,
    # not in the elif chain — elif is exclusive per message, so a message matching "task tools
    # haven" would never reach a pyright elif branch even if both SRs are present.
    _SKILLS_MARKER = "The following skills are available for use with the Skill tool"
    _CLAUDEMD_MARKER = "# claudeMd"
    _PYRIGHT_ENABLED = _load_config().get("pyright_diagnostics_strip", {}).get("enabled", False)
    for idx, msg in enumerate(new_messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if not content:
            continue
        original_before_pass = content
        pass_mods = []
        if _content_contains(content, _SKILLS_MARKER):
            new_content = _strip_system_reminder(content, _SKILLS_MARKER)
            if new_content != content:
                content = new_content
                pass_mods.append("stripped_skills_sr")
        if _content_contains(content, _CLAUDEMD_MARKER):
            new_content = _strip_system_reminder(content, _CLAUDEMD_MARKER)
            if new_content != content:
                content = new_content
                pass_mods.append("stripped_claudemd_sr")
        if _PYRIGHT_ENABLED and _content_contains(content, "<new-diagnostics>"):
            new_content = _strip_pyright_diagnostics(content)
            if new_content != content:
                content = new_content
                pass_mods.append("stripped_pyright_diagnostics")
        if content != original_before_pass:
            new_messages[idx] = {**msg, "content": content}
            modifications.extend(pass_mods)
            if idx not in stripped_msg_indices:
                stripped_msg_indices.append(idx)
                stripped_msg_originals[idx] = original_before_pass
            removed = stripped_msg_removed.setdefault(idx, [])
            if "stripped_skills_sr" in pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, _SKILLS_MARKER))
            if "stripped_claudemd_sr" in pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, _CLAUDEMD_MARKER))
            if "stripped_pyright_diagnostics" in pass_mods:
                removed.extend(_find_system_reminder_blocks(original_before_pass, "<new-diagnostics>"))
            changed = True

    # Final pass: strip ALL remaining <system-reminder> blocks from ALL user messages.
    # Extends the original msg[0]-only pass to catch templates without dedicated elif branches
    # (system-notification, date-changed, file-modified) in any message position.
    # claudeMD preamble blocks are preserved by _apply_sr_strip._replace (93l preserve-check).
    for _fp_idx, _fp_msg in enumerate(new_messages):
        if _fp_msg.get("role") != "user":
            continue
        old_content = _fp_msg.get("content", "")
        new_content = _strip_all_system_reminders(old_content)
        if new_content != old_content:
            new_messages[_fp_idx] = {**_fp_msg, "content": new_content}
            modifications.append("stripped_all_sr_msg0" if _fp_idx == 0 else "stripped_all_sr")
            if _fp_idx not in stripped_msg_indices:
                stripped_msg_indices.append(_fp_idx)
                stripped_msg_originals[_fp_idx] = old_content
            remaining = _find_all_system_reminder_blocks(new_content)
            removed = stripped_msg_removed.setdefault(_fp_idx, [])
            removed.extend(sr for sr in _find_all_system_reminder_blocks(old_content) if sr not in remaining)
            changed = True

    # PO-Preview pass: strip Preview sections from <persisted-output> blocks in any user message.
    # Runs after all SR passes — independent, no interaction with SR handling.
    for _po_idx, _po_msg in enumerate(new_messages):
        if _po_msg.get("role") != "user":
            continue
        old_content = _po_msg.get("content", "")
        if not _content_contains(old_content, _PO_OPEN_TAG):
            continue
        new_content, po_removed = _strip_persisted_output_previews(old_content)
        if po_removed:
            new_messages[_po_idx] = {**_po_msg, "content": new_content}
            modifications.append("stripped_po_preview")
            if _po_idx not in stripped_msg_indices:
                stripped_msg_indices.append(_po_idx)
                stripped_msg_originals[_po_idx] = old_content
            stripped_msg_removed.setdefault(_po_idx, []).extend(po_removed)
            changed = True

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
            text3 = block3.get("text", "")
            stripped = _strip_session_guidance(text3)
            if stripped != text3:
                text3 = stripped
                modifications.append("stripped_session_guidance")
            git_stripped = _strip_git_status(text3)
            if git_stripped != text3:
                text3 = git_stripped
                modifications.append("stripped_git_status")
            normalized = _WORKTREE_PATH_PATTERN.sub(r'\1', text3)
            if normalized != text3:
                text3 = normalized
                modifications.append("normalized_worktree_path")
            if text3 != block3.get("text", ""):
                new_system[3] = {**block3, "text": text3}

    if not changed:
        return payload, modifications, None, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed
