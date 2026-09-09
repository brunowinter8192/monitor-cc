# INFRASTRUCTURE
from .strip_sr import (
    _strip_all_system_reminders,
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
    _extract_task_notification_output_file,
    _extract_task_notification_task_id,
    _replace_task_notification_tags,
)
from .rules_config import _load_config
from .strip_bg_completed import _WAKEUP_TEXT
from .rule_ops import _ops_from_content_change
from .message_passes_wakeup import _unwrap_full_sr_wrapper

# role=system messages starting with this marker are Read-truncation notices (CC 2.1.205+)
# and must be preserved — the agent needs to know a Read was partial, not silently nuked.
_TRUNCATION_NOTICE_MARKER = "[Truncated:"

# role=system messages starting with this marker are CC 2.1.223+'s mid-turn user message
# delivery (a user typing while the session is working, or worker-cli send to a working worker —
# same mechanism) and must be preserved whole — pre-223 this content arrived as a role='user'
# <system-reminder> ('user-interrupt' template in strip_sr.py, PARTIAL mode: IMPORTANT line
# stripped, user body preserved); the 223 role=system form bypasses that SR-based guard entirely
# and was falling through to this pass's unconditional '.' replacement, silently dropping the
# user's message before it ever reached the model (issue #61). Whole-message preserve, not a
# partial trim like the SR-era guard — losing the user's text is the failure mode this closes,
# the few extra lines of CC's own boilerplate explainer are harmless noise by comparison.
_MID_TURN_USER_MSG_MARKER = "The user sent a new message while you were working:"

# Markers driving _apply_cumulative_sr_strips' 3 identical-shape SR-strip checks (Skills,
# agent-types, claudeMd) — the 4th check (pyright) has its own config-gated + different-strip-fn
# shape and stays inline in that function.
_SKILLS_MARKER = "The following skills are available for use with the Skill tool"
_AGENT_TYPES_MARKER = "Available agent types for the Agent tool"
_CLAUDEMD_MARKER = "# claudeMd"
_CUMULATIVE_SR_MARKERS = (
    (_SKILLS_MARKER, "stripped_skills_sr"),
    (_AGENT_TYPES_MARKER, "stripped_agent_types_sr"),
    (_CLAUDEMD_MARKER, "stripped_claudemd_sr"),
)

# FUNCTIONS

# Role=system pass — strips entire content of every role='system' message by replacing with '.',
# EXCEPT role=system messages carrying a <task-notification> tag (CC delivers bg-task wake-ups as
# a plain-str role='system' message on some paths, alongside the known role='user' path) — those
# are left untouched here and fall through to `_apply_sn_notice_strip` + `_apply_first_pass`'s TN
# branch (both widened to accept role='system'), which own TN wake-up construction exclusively —
# and EXCEPT mid-turn user messages (_MID_TURN_USER_MSG_MARKER, CC 2.1.223+), preserved whole —
# returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
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
        if isinstance(old_content, str) and old_content.startswith(_TRUNCATION_NOTICE_MARKER):
            result.append(msg)
            continue
        if isinstance(old_content, str) and old_content.lstrip().startswith(_MID_TURN_USER_MSG_MARKER):
            result.append(msg)
            continue
        if _top_level_content_contains(old_content, "<task-notification>"):
            result.append(msg)
            continue
        result.append({**msg, "content": "."})
        changed_indices.append(idx)
        pass_mods.append("stripped_role_system_msg")
        pass_removed_by_idx[idx] = [old_content if isinstance(old_content, str) else str(old_content)]
        # full_replace=True: content unconditionally set to the literal "." regardless of shape
        # (line 66) — unambiguous whole-content replacement, no caveat needed.
        pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, ".", full_replace=True)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


# Apply one (marker, mod_name) SR-strip check from _CUMULATIVE_SR_MARKERS — the 3 identical-shape
# checks (Skills / agent-types / claudeMd) share this body. Returns (new_content, mod_name_or_None).
def _apply_marker_sr_strip(content, marker: str, mod_name: str) -> tuple:
    if not _top_level_content_contains(content, marker):
        return content, None
    new_content = _strip_system_reminder(content, marker)
    if new_content == content:
        return content, None
    return new_content, mod_name


# Cumulative second pass — strips Skills, agent-types, claudeMd, pyright, ENV-context SRs from every user message including those already touched by pass 1 — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_cumulative_sr_strips(messages: list) -> tuple:
    pyright_enabled = _load_config().get("pyright_diagnostics_strip", {}).get("enabled", False)
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
        for marker, mod_name in _CUMULATIVE_SR_MARKERS:
            content, mod = _apply_marker_sr_strip(content, marker, mod_name)
            if mod:
                cur_pass_mods.append(mod)
        if pyright_enabled and _top_level_content_contains(content, "<new-diagnostics>"):
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


# TN branch of _apply_first_pass — accepts role='system' too (CC delivers bg-task wake-ups as a
# plain-str role='system' message on some paths; _apply_role_system_strip's TN guard leaves those
# untouched so they reach here). Builds the wake-up + optional Output:/ID: replacement, strips a
# nested task-tools-nag SR if present, unwraps a full <system-reminder> wrap if present.
# Returns (new_msg, mod_names, removed, injected_text).
def _handle_tn_message(msg: dict, old_content) -> tuple:
    new_msg = dict(msg)
    is_failed_bg = _content_contains(old_content, "<status>failed</status>")
    also_stripped_nag = False
    mod_names = []
    # Both failed and completed: single block = wakeup + optional Output line + optional ID
    # line; summary and status dropped. Each optional line is omitted (not emitted empty)
    # when its <task-notification> tag is absent — never "ID: None", never a dangling label.
    output_path = _extract_task_notification_output_file(old_content)
    task_id = _extract_task_notification_task_id(old_content)
    _tn_lines = [_WAKEUP_TEXT.rstrip('\n')]
    if output_path:
        _tn_lines.append('Output: ' + output_path)
    if task_id:
        _tn_lines.append('ID: ' + task_id)
    injected_text = '\n'.join(_tn_lines) + '\n'
    new_msg["content"] = _replace_task_notification_tags(old_content, injected_text)
    if _top_level_content_contains(new_msg["content"], "task tools haven"):
        new_msg["content"] = _strip_system_reminder(new_msg["content"], "task tools haven")
        mod_names.append("stripped_task_tools_nag")
        also_stripped_nag = True
    new_msg["content"], wrapper_removed = _unwrap_full_sr_wrapper(new_msg["content"])
    removed = []
    if new_msg["content"] != old_content:
        mod_name = "replaced_task_notification" if is_failed_bg else "trimmed_task_notification"
        mod_names.append(mod_name)
        removed = _find_task_notification_blocks(old_content) + wrapper_removed
        if also_stripped_nag:
            removed = removed + _find_system_reminder_blocks(old_content, "task tools haven")
    return new_msg, mod_names, removed, injected_text


# Shared body for the NAG and DEF elif branches of _apply_first_pass — both strip a single
# <system-reminder> by marker via _strip_system_reminder, differing only in marker/mod_name.
# Returns (new_msg, changed, removed_or_None).
def _apply_sr_marker_branch(msg: dict, old_content, marker: str) -> tuple:
    new_msg = dict(msg)
    new_msg["content"] = _strip_system_reminder(old_content, marker)
    changed = new_msg["content"] != old_content
    removed = _find_system_reminder_blocks(old_content, marker) if changed else None
    return new_msg, changed, removed


# UI (user-interrupt, partial mode) branch of _apply_first_pass — strips the IMPORTANT line only,
# preserving the user's own body. Returns (new_msg, changed, removed_or_None).
def _handle_ui_message(msg: dict, old_content) -> tuple:
    marker = "user sent a new message while you were working"
    new_msg = dict(msg)
    new_msg["content"] = _strip_user_interrupt_sr(old_content, marker)
    changed = new_msg["content"] != old_content
    removed = None
    if changed:
        _ui_blocks = _find_system_reminder_blocks(old_content, marker)
        removed = [line for block in _ui_blocks for line in _IMP_LINE_RE.findall(block)] or _ui_blocks
    return new_msg, changed, removed


# Commit a simple (non-TN) branch's result into the shared accumulator dict — the tail every one
# of NAG/DEF/UI/REJECTION repeats once its own (new_msg, changed, removed) is computed. No-op when
# changed is False (matches every branch's own pre-existing "only record on real change" gate).
def _commit_simple_branch(idx: int, new_msg: dict, old_content, changed: bool, mod_name: str, removed, acc: dict, full_replace: bool = False) -> None:
    if not changed:
        return
    acc["changed_indices"].append(idx)
    acc["pass_mods"].append(mod_name)
    acc["pass_removed_by_idx"][idx] = removed
    acc["pass_ops_by_msg_blk"][idx] = _ops_from_content_change(old_content, new_msg["content"], full_replace=full_replace)


# REJECTION branch of _apply_first_pass — returns (new_msg, changed).
# full_replace=True: _strip_rejection_message (content_strip.py) mutates PER-BLOCK for list
# content, not the whole message at once — but every block it actually changes is wholesale-set
# to the literal "." (content_strip.py:43, {**block, "content": "."}), never partially edited in
# place; every block it leaves alone is appended by identity (content_strip.py:45), so bt==at
# exactly for those and _extract_block_op's before==after check returns [] before full_replace is
# even consulted. The message-level flag is therefore safe here specifically because this pass
# has no per-block PARTIAL-edit path to protect — the str branch (content_strip.py:31) is
# unambiguously full-replace too.
def _handle_rejection_message(msg: dict, old_content) -> tuple:
    new_msg = dict(msg)
    new_msg["content"] = _strip_rejection_message(old_content)
    return new_msg, new_msg["content"] != old_content


# First-pass message loop — elif-chain strips task-notification, task-tools-nag, deferred-tools, user-interrupt, rejection SRs — returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _apply_first_pass(messages: list) -> tuple:
    result = []
    acc = {"pass_mods": [], "pass_removed_by_idx": {}, "pass_ops_by_msg_blk": {}, "changed_indices": []}
    pass_injected_by_idx = {}
    for idx, msg in enumerate(messages):
        content = msg.get("content", "")
        role = msg.get("role")
        if role in ("user", "system") and _top_level_content_contains(content, "<task-notification>"):
            new_msg, mod_names, removed, injected_text = _handle_tn_message(msg, content)
            result.append(new_msg)
            acc["pass_mods"].extend(mod_names)
            if new_msg["content"] != content:
                acc["changed_indices"].append(idx)
                acc["pass_removed_by_idx"][idx] = removed
                pass_injected_by_idx[idx] = [injected_text]
                acc["pass_ops_by_msg_blk"][idx] = _ops_from_content_change(content, new_msg["content"])
        elif role == "user" and _top_level_content_contains(content, "task tools haven"):
            new_msg, changed, removed = _apply_sr_marker_branch(msg, content, "task tools haven")
            result.append(new_msg)
            _commit_simple_branch(idx, new_msg, content, changed, "stripped_task_tools_nag", removed, acc)
        elif role == "user" and _top_level_content_contains(content, "deferred tools are now available via ToolSearch"):
            new_msg, changed, removed = _apply_sr_marker_branch(msg, content, "deferred tools are now available via ToolSearch")
            result.append(new_msg)
            _commit_simple_branch(idx, new_msg, content, changed, "stripped_deferred_tools_sr", removed, acc)
        elif role == "user" and _top_level_content_contains(content, "user sent a new message while you were working"):
            new_msg, changed, removed = _handle_ui_message(msg, content)
            result.append(new_msg)
            _commit_simple_branch(idx, new_msg, content, changed, "stripped_user_interrupt_sr", removed, acc)
        elif role == "user" and _message_has_rejection(content):
            new_msg, changed = _handle_rejection_message(msg, content)
            result.append(new_msg)
            _commit_simple_branch(idx, new_msg, content, changed, "stripped_rejection_message",
                                   ["(rejection marker stripped by proxy)"], acc, full_replace=True)
        else:
            result.append(msg)
    return (result, acc["pass_mods"], acc["pass_removed_by_idx"], acc["changed_indices"],
            pass_injected_by_idx, acc["pass_ops_by_msg_blk"])
