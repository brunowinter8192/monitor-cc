# INFRASTRUCTURE
from .payload_helpers import _content_contains, _top_level_content_contains
from .rule_ops import _ops_from_content_change
from .strip_po import _strip_persisted_output_previews, _PO_OPEN_TAG
from .strip_bg_completed import _strip_bg_exit_notifications, _BG_CMD_MARKER, _WAKEUP_TEXT
from .strip_bg_launch_ack import _strip_bg_launch_ack, _BG_LAUNCH_ACK_MARKER, _BG_LAUNCH_ACK_MARKER_2
from .strip_hook_prefix import _strip_hook_prefix, _HOOK_PREFIX_MARKER
from .strip_git_lock import _strip_git_lock_advice, _GIT_LOCK_MARKER
from .strip_bd_noise import _strip_bd_noise, _BD_NOISE_MARKERS
from .strip_sn_notice import _strip_sn_notice, _SN_NOTICE_MARKER
from .strip_interrupt_marker import _strip_interrupt_marker, _INTERRUPT_MARKERS

_USER_ROLES = frozenset({"user"})

# FUNCTIONS

# Guard factory: True when check_fn(content, marker) is True for ANY of markers — shared shape
# for the specs whose guard is "any of N markers present" (bd_noise, interrupt_marker,
# bg_launch_ack's two wordings).
def _any_marker_guard(check_fn, markers):
    return lambda c: any(check_fn(c, m) for m in markers)


# Generic pass runner for the "role filter -> marker guard -> strip -> record" template shared by
# 8 of the 12 message passes (see message_passes.py's own module entry for the split rationale
# — those 8 are the ONLY passes matching this exact shape; the other 4 have their own structural
# logic and stay in message_passes.py). spec fields:
#   roles: frozenset of accepted msg roles
#   skip_fn: Optional[(role, content) -> bool] — extra per-role skip, True to bypass (sn_notice only)
#   marker_guard: (content) -> bool — the fast-path contains-check before the real strip call
#   strip_fn: (content) -> (new_content, removed_chunks)
#   mod_name: str — appended to pass_mods on a real (non-empty-removed) strip
#   injected: Optional[list] — static injected-text list (bg_exit only); a FRESH copy stored per hit
#   full_replace: bool — threaded to _ops_from_content_change (bg_launch_ack, interrupt_marker)
# Returns (new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)
def _run_simple_pass(messages: list, spec: dict) -> tuple:
    result = []
    pass_mods = []
    pass_removed_by_idx = {}
    pass_injected_by_idx: dict = {}
    pass_ops_by_msg_blk: dict = {}
    changed_indices = []
    for idx, msg in enumerate(messages):
        role = msg.get("role")
        if role not in spec["roles"]:
            result.append(msg)
            continue
        old_content = msg.get("content", "")
        skip_fn = spec.get("skip_fn")
        if skip_fn and skip_fn(role, old_content):
            result.append(msg)
            continue
        if not spec["marker_guard"](old_content):
            result.append(msg)
            continue
        new_content, removed = spec["strip_fn"](old_content)
        if removed:
            result.append({**msg, "content": new_content})
            pass_mods.append(spec["mod_name"])
            changed_indices.append(idx)
            pass_removed_by_idx[idx] = removed
            if spec.get("injected") is not None:
                pass_injected_by_idx[idx] = list(spec["injected"])
            pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content, full_replace=spec.get("full_replace", False))
        else:
            result.append(msg)
    return result, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk


_PO_PREVIEW_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _content_contains(c, _PO_OPEN_TAG),
    "strip_fn": _strip_persisted_output_previews,
    "mod_name": "stripped_po_preview",
}

# PO-preview pass — strips Preview sections from persisted-output blocks in user messages
def _apply_po_preview_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _PO_PREVIEW_SPEC)


_BG_EXIT_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _top_level_content_contains(c, _BG_CMD_MARKER),
    "strip_fn": _strip_bg_exit_notifications,
    "mod_name": "replaced_bg_completed_text",
    "injected": [_WAKEUP_TEXT],
}

# BG-exit-notification pass — strips "Background command "..." failed with exit code 143/137" lines from user messages
def _apply_bg_exit_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _BG_EXIT_SPEC)


_HOOK_PREFIX_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _content_contains(c, _HOOK_PREFIX_MARKER),
    "strip_fn": _strip_hook_prefix,
    "mod_name": "stripped_hook_error_prefix",
}

# Hook-prefix pass — strips PreToolUse:<Tool> hook error: [python3 <path>]: prefix from user message tool_result content
def _apply_hook_prefix_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _HOOK_PREFIX_SPEC)


_GIT_LOCK_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _content_contains(c, _GIT_LOCK_MARKER),
    "strip_fn": _strip_git_lock_advice,
    "mod_name": "stripped_git_lock_advice",
}

# Git-lock-advice pass — strips constant git index.lock advice block from user message tool_result content
def _apply_git_lock_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _GIT_LOCK_SPEC)


_BG_LAUNCH_ACK_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": _any_marker_guard(_content_contains, (_BG_LAUNCH_ACK_MARKER, _BG_LAUNCH_ACK_MARKER_2)),
    "mod_name": "stripped_bg_launch_ack",
    "full_replace": True,
}

# BG-launch-ack pass — replaces content of background-command launch-ack blocks with '.' —
# is_main selects the replacement wording (see strip_bg_launch_ack.py). strip_fn is bound to
# is_main per call (the one pass needing an extra argument), via a per-call spec copy so the
# module-level spec dict itself stays immutable.
def _apply_bg_launch_ack_strip(messages: list, is_main: bool = False) -> tuple:
    spec = dict(_BG_LAUNCH_ACK_SPEC)
    spec["strip_fn"] = lambda c: _strip_bg_launch_ack(c, is_main)
    return _run_simple_pass(messages, spec)


_BD_NOISE_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": _any_marker_guard(_content_contains, _BD_NOISE_MARKERS),
    "strip_fn": _strip_bd_noise,
    "mod_name": "stripped_bd_noise",
}

# BD-noise pass — strips bd informational auto-import/export lines from user message tool_result content
def _apply_bd_noise_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _BD_NOISE_SPEC)


_INTERRUPT_MARKER_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": _any_marker_guard(_content_contains, _INTERRUPT_MARKERS),
    "strip_fn": _strip_interrupt_marker,
    "mod_name": "stripped_interrupt_marker",
    "full_replace": True,
}

# Interrupt-marker pass — replaces block content with '.' for blocks whose (whitespace-stripped)
# text IS EXACTLY one of the interrupt-marker wordings (CC's rendering of the proxy's
# bg_escape.py tmux-Escape into a worker's pane, not a genuine user interrupt)
def _apply_interrupt_marker_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _INTERRUPT_MARKER_SPEC)


# system-role sn-notice messages are in scope ONLY when the message also carries a
# <task-notification> tag (the TN wake-ups _apply_role_system_strip's TN guard leaves untouched)
# — a role='system' message without a TN tag stays out of scope here, same as before.
def _sn_notice_skip(role, content) -> bool:
    return role == "system" and not _top_level_content_contains(content, "<task-notification>")


_SN_NOTICE_SPEC = {
    "roles": frozenset({"user", "system"}),
    "skip_fn": _sn_notice_skip,
    "marker_guard": lambda c: _top_level_content_contains(c, _SN_NOTICE_MARKER),
    "strip_fn": _strip_sn_notice,
    "mod_name": "stripped_sn_notice_paragraph",
}

# SN-notice pass — strips the bare 4-line "[SYSTEM NOTIFICATION - NOT USER INPUT]" paragraph CC
# injects ahead of <task-notification> tags in background-task wake-ups, from top-level str/text-block
# content only. Runs BEFORE _apply_first_pass so the TN branch's top-level tag-contains guard and
# tag-replacement operate on an already-cleaned prefix — the two concerns (paragraph noise vs. TN-tag
# consumption) stay decoupled.
def _apply_sn_notice_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _SN_NOTICE_SPEC)
