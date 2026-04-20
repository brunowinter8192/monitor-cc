# INFRASTRUCTURE
import json
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)

from .content_strip import (
    _strip_all_system_reminders,
    _strip_plan_mode_blocks,
    _strip_system_reminder,
    _strip_user_interrupt_sr,
    _strip_pyright_diagnostics,
    _message_has_rejection,
    _strip_rejection_message,
    _strip_session_guidance,
    _strip_git_status,
)
from .payload_helpers import (
    _find_system_reminder_blocks,
    _strip_blocked_tool_references,
    _content_contains,
    _strip_task_notification_tags,
)

_SHARED_RULES_DIR = Path.home() / ".claude" / "shared-rules"
_PROXY_RULES_CONFIG = _SHARED_RULES_DIR / "proxy_rules.json"
_file_cache: dict = {}
_config_cache: list = [None]
_WORKTREE_PATH_PATTERN = re.compile(r'(/[^\s]+)/\.claude/worktrees/[^/\s]+')

# FUNCTIONS

# Load proxy_rules.json config, re-reading only when mtime changes
def _load_config() -> dict:
    try:
        mtime = _PROXY_RULES_CONFIG.stat().st_mtime
        cached = _config_cache[0]
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(_PROXY_RULES_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
        _config_cache[0] = (mtime, config)
        return config
    except Exception:
        return {}


# Read a rule file by path relative to shared-rules dir, caching by mtime
def _read_rule_file(rel_path: str) -> str:
    path = _SHARED_RULES_DIR / rel_path
    try:
        mtime = path.stat().st_mtime
        cached = _file_cache.get(rel_path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        content = path.read_text(encoding="utf-8")
        _file_cache[rel_path] = (mtime, content)
        return content
    except Exception:
        return ""


# Concatenate system2 rule files for a given model family (global + model-specific + project)
def _load_system2_rules(model_family: str, project_path: str = "") -> str:
    config = _load_config()
    s2 = config.get("system2_rules", {})
    # Project-level opt-out: exclude_projects patterns suppress all system2 injection
    for pattern in s2.get("exclude_projects", []):
        if pattern and pattern in project_path:
            return ""
    global_files = s2.get("global", {}).get("files", [])
    # Map model family to config key: opus → "opus", sonnet/haiku → "worker"
    model_key = "opus" if model_family == "opus" else "worker"
    model_files = s2.get(model_key, {}).get("files", [])
    # haiku gets no rules (returns empty → system[2] becomes ".")
    if model_family == "haiku":
        return ""
    # Load project-specific files from system2_rules.projects
    project_files = []
    exclusive_files = None
    if project_path:
        for _name, proj in s2.get("projects", {}).items():
            path_contains = proj.get("path_contains", "")
            if path_contains and path_contains in project_path:
                # Exclusive project: skip global+model, load ONLY these files.
                # Optional exclusive_model_families restricts to listed families;
                # other families fall through to empty rules.
                if proj.get("exclusive"):
                    allowed = proj.get("exclusive_model_families")
                    if allowed is not None and model_family not in allowed:
                        return ""
                    exclusive_files = list(proj.get("files", []))
                    break
                project_files.extend(proj.get("files", []))
    if exclusive_files is not None:
        all_files = exclusive_files
    else:
        all_files = global_files + model_files + project_files
    parts = [c for c in (_read_rule_file(f) for f in all_files) if c]
    return "\n\n".join(parts)


# Apply all proxy modification rules — returns (modified_payload, list_of_applied_rules, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)
def apply_modification_rules(payload: dict, model_family: str = "opus", project_path: str = "") -> tuple:
    modifications = []
    changed = False

    system_rules = _load_system2_rules(model_family, project_path)

    messages_to_process = list(payload.get("messages", []))

    new_messages = []
    stripped_msg_indices = []
    stripped_msg_originals = {}
    stripped_msg_removed = {}
    _tag_pat = re.compile(r'<task-notification>.*?</task-notification>', re.DOTALL)
    _pm_pat = re.compile(r'<system-reminder>\s*Plan mode.*?</system-reminder>', re.DOTALL)
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
                    if isinstance(old_content, str):
                        stripped_msg_removed[idx] = _pm_pat.findall(old_content)
                    elif isinstance(old_content, list):
                        stripped_msg_removed[idx] = [
                            b.get("text", "") for b in old_content
                            if isinstance(b, dict) and "Plan mode is active" in b.get("text", "")
                        ]
                    else:
                        stripped_msg_removed[idx] = []
                    changed = True
            else:
                new_messages.append({"role": "user", "content": "(plan-mode reminder stripped by proxy)"})
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("removed_plan_mode_sr")
                if isinstance(old_content, str):
                    stripped_msg_removed[idx] = _pm_pat.findall(old_content)
                elif isinstance(old_content, list):
                    stripped_msg_removed[idx] = [
                        b.get("text", "") for b in old_content
                        if isinstance(b, dict) and "Plan mode is active" in b.get("text", "")
                    ]
                else:
                    stripped_msg_removed[idx] = []
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
                removed = []
                if isinstance(old_content, str):
                    removed.extend(_tag_pat.findall(old_content))
                elif isinstance(old_content, list):
                    for _b in old_content:
                        if isinstance(_b, dict) and _b.get("type") == "text":
                            removed.extend(_tag_pat.findall(_b.get("text", "")))
                if also_stripped_nag:
                    removed.extend(_find_system_reminder_blocks(old_content, "task tools haven"))
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
                stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "user sent a new message while you were working")
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
        elif msg.get("role") == "user" and _content_contains(msg.get("content", ""), "<new-diagnostics>") and _load_config().get("pyright_diagnostics_strip", {}).get("enabled", False):
            old_content = msg.get("content", "")
            new_msg = dict(msg)
            new_msg["content"] = _strip_pyright_diagnostics(old_content)
            new_messages.append(new_msg)
            if new_msg["content"] != old_content:
                stripped_msg_originals[idx] = old_content
                stripped_msg_indices.append(idx)
                modifications.append("stripped_pyright_diagnostics")
                stripped_msg_removed[idx] = _find_system_reminder_blocks(old_content, "<new-diagnostics>")
                changed = True
        else:
            new_messages.append(msg)

    # Cumulative second pass: strip Skills sr + claudeMd sr from any user message,
    # even if the message already went through a strip branch above.
    _SKILLS_MARKER = "The following skills are available for use with the Skill tool"
    _CLAUDEMD_MARKER = "# claudeMd"
    for idx, msg in enumerate(new_messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if not content:
            continue
        original_before_pass = content
        pass_mods = []
        if _content_contains(content, _SKILLS_MARKER):
            content = _strip_system_reminder(content, _SKILLS_MARKER)
            pass_mods.append("stripped_skills_sr")
        if _content_contains(content, _CLAUDEMD_MARKER):
            content = _strip_system_reminder(content, _CLAUDEMD_MARKER)
            pass_mods.append("stripped_claudemd_sr")
        if content != original_before_pass:
            new_messages[idx] = {**msg, "content": content}
            modifications.extend(pass_mods)
            if idx not in stripped_msg_indices:
                stripped_msg_indices.append(idx)
                stripped_msg_originals[idx] = original_before_pass
            changed = True

    # Final pass: strip ALL remaining <system-reminder> blocks from msg[0]
    if new_messages and new_messages[0].get("role") == "user":
        msg0 = new_messages[0]
        old_content = msg0.get("content", "")
        new_content = _strip_all_system_reminders(old_content)
        if new_content != old_content:
            new_messages[0] = {**msg0, "content": new_content}
            modifications.append("stripped_all_sr_msg0")
            if 0 not in stripped_msg_indices:
                stripped_msg_indices.append(0)
                stripped_msg_originals[0] = old_content
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
