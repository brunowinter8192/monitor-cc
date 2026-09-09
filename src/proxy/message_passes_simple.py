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

def _any_marker_guard(check_fn, markers):
    return lambda c: any(check_fn(c, m) for m in markers)


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


def _apply_po_preview_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _PO_PREVIEW_SPEC)


_BG_EXIT_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _top_level_content_contains(c, _BG_CMD_MARKER),
    "strip_fn": _strip_bg_exit_notifications,
    "mod_name": "replaced_bg_completed_text",
    "injected": [_WAKEUP_TEXT],
}


def _apply_bg_exit_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _BG_EXIT_SPEC)


_HOOK_PREFIX_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _content_contains(c, _HOOK_PREFIX_MARKER),
    "strip_fn": _strip_hook_prefix,
    "mod_name": "stripped_hook_error_prefix",
}


def _apply_hook_prefix_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _HOOK_PREFIX_SPEC)


_GIT_LOCK_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": lambda c: _content_contains(c, _GIT_LOCK_MARKER),
    "strip_fn": _strip_git_lock_advice,
    "mod_name": "stripped_git_lock_advice",
}


def _apply_git_lock_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _GIT_LOCK_SPEC)


_BG_LAUNCH_ACK_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": _any_marker_guard(_content_contains, (_BG_LAUNCH_ACK_MARKER, _BG_LAUNCH_ACK_MARKER_2)),
    "mod_name": "stripped_bg_launch_ack",
    "full_replace": True,
}


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


def _apply_bd_noise_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _BD_NOISE_SPEC)


_INTERRUPT_MARKER_SPEC = {
    "roles": _USER_ROLES,
    "marker_guard": _any_marker_guard(_content_contains, _INTERRUPT_MARKERS),
    "strip_fn": _strip_interrupt_marker,
    "mod_name": "stripped_interrupt_marker",
    "full_replace": True,
}


def _apply_interrupt_marker_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _INTERRUPT_MARKER_SPEC)


def _sn_notice_skip(role, content) -> bool:
    return role == "system" and not _top_level_content_contains(content, "<task-notification>")


_SN_NOTICE_SPEC = {
    "roles": frozenset({"user", "system"}),
    "skip_fn": _sn_notice_skip,
    "marker_guard": lambda c: _top_level_content_contains(c, _SN_NOTICE_MARKER),
    "strip_fn": _strip_sn_notice,
    "mod_name": "stripped_sn_notice_paragraph",
}


def _apply_sn_notice_strip(messages: list) -> tuple:
    return _run_simple_pass(messages, _SN_NOTICE_SPEC)
