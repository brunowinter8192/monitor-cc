# INFRASTRUCTURE
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)

from .payload_helpers import _strip_blocked_tool_references  # re-exported for addon.py
from .content_strip import _strip_session_guidance, _strip_git_status
from .rules_config import _load_system2_rules
from .message_passes import (
    _apply_role_system_strip,
    _apply_first_pass,
    _apply_cumulative_sr_strips,
    _apply_final_sr_pass,
    _apply_po_preview_strip,
    _apply_bg_exit_strip,
    _apply_hook_prefix_strip,
    _apply_git_lock_strip,
    _apply_bd_noise_strip,
    _dedup_wakeup_blocks,
)
from .rule_ops import _merge_ops

_WORKTREE_PATH_PATTERN = re.compile(r'(/[^\s]+)/\.claude/worktrees/[^/\s]+')

# ORCHESTRATOR

# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added)
def apply_modification_rules(payload: dict, model_family: str = "opus", project_path: str = "") -> tuple:
    system_rules = _load_system2_rules(model_family, project_path)

    messages_to_process = list(payload.get("messages", []))
    modifications = []
    changed = False
    stripped_msg_indices = []
    stripped_msg_originals = {}
    stripped_msg_removed = {}
    injected_msg_added = {}
    _all_ops: dict = {}

    _passes = [
        _apply_role_system_strip,
        _apply_first_pass,
        _apply_cumulative_sr_strips,
        _apply_final_sr_pass,
        _apply_po_preview_strip,
        _apply_bg_exit_strip,
        _apply_hook_prefix_strip,
        _apply_git_lock_strip,
        _apply_bd_noise_strip,
    ]

    new_messages = messages_to_process
    for pass_fn in _passes:
        new_messages, pass_mods, pass_removed, c_idxs, pass_injected, _pass_ops = pass_fn(new_messages)
        modifications.extend(pass_mods)
        for idx in c_idxs:
            if idx not in stripped_msg_indices:
                stripped_msg_indices.append(idx)
                stripped_msg_originals[idx] = messages_to_process[idx].get("content", "")
            stripped_msg_removed.setdefault(idx, []).extend(pass_removed.get(idx, []))
            injected_msg_added.setdefault(idx, []).extend(pass_injected.get(idx, []))
        if c_idxs:
            changed = True
        _merge_ops(_all_ops, _pass_ops)

    new_messages, _pass_ops = _dedup_wakeup_blocks(new_messages)
    _merge_ops(_all_ops, _pass_ops)

    new_system, original_system2_text, sys_mods, sys_changed = _apply_system_passes(
        payload.get("system", []), system_rules
    )
    modifications.extend(sys_mods)
    if sys_changed:
        changed = True

    if not changed:
        return payload, modifications, None, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, _all_ops
    modified = dict(payload)
    modified["messages"] = new_messages
    modified["system"] = new_system
    return modified, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, _all_ops


# FUNCTIONS

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
