"""Unit tests for CC 2.1.176 proxy drift fixes.

Fix 1: 'Workflow' added to TOOL_BLOCKLIST → _strip_unused_tools removes it.
Fix 2: _apply_role_system_strip strips role='system' messages unconditionally.

Run from project root:
    ./venv/bin/python dev/proxy_176_strip_tests.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from proxy.tools import _strip_unused_tools
from proxy.message_passes import _apply_role_system_strip
from proxy.strip_inject_delta import _process_messages_section, _MSG_CODE_TO_FN
from proxy.diff_engine import _diff_messages
from proxy.logging import _normalize_msg_shape_for_hash

_SYSTEM_CONTENT = (
    "The following deferred tools are now available via ToolSearch. "
    "Their schemas are NOT loaded yet. CronCreate, CronDelete, CronList, "
    "Agent, ToolSearch, Workflow, EnterWorktree, ExitWorktree. "
    + "x" * 9400
)

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

def check(label, condition):
    print(f"  {'  '+_PASS if condition else '  '+_FAIL}  {label}")
    return condition


# Fix 1 — Workflow removed by _strip_unused_tools

def test_workflow_blocklist():
    print("Fix 1 — Workflow blocklist removal")
    payload = {"tools": [
        {"name": "Bash", "description": "run bash"},
        {"name": "Workflow", "description": "big description " * 100},
        {"name": "Read", "description": "read file"},
    ]}
    modified, removed_count, removed_names = _strip_unused_tools(payload)
    remaining = [t["name"] for t in modified["tools"]]
    check("Workflow removed from tools list", "Workflow" not in remaining)
    check("Bash retained", "Bash" in remaining)
    check("Read retained", "Read" in remaining)
    check("removed_count == 1", removed_count == 1)
    check("removed_names == ['Workflow']", removed_names == ["Workflow"])
    print()


# Fix 2 — _apply_role_system_strip

def test_role_system_strip_fires():
    print("Fix 2a — role=system content replaced with '.'")
    messages = [
        {"role": "system", "content": _SYSTEM_CONTENT},
    ]
    result, mods, removed, changed, injected, ops = _apply_role_system_strip(messages)
    check("content replaced with '.'", result[0]["content"] == ".")
    check("role preserved", result[0]["role"] == "system")
    check("mod-name recorded", "stripped_role_system_msg" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0]", removed.get(0) == [_SYSTEM_CONTENT])
    check("ops recorded for block 0", ops.get(0, {}).get(0) is not None)
    print()


def test_role_system_strip_unconditional():
    print("Fix 2b — strip fires regardless of content (arbitrary string)")
    messages = [{"role": "system", "content": "some future unknown content xyz"}]
    result, mods, removed, changed, _, _ = _apply_role_system_strip(messages)
    check("content → '.' for arbitrary content", result[0]["content"] == ".")
    check("mod-name present", "stripped_role_system_msg" in mods)
    print()


def test_role_user_assistant_untouched():
    print("Fix 2c — role=user and role=assistant messages untouched")
    user_content = "Please help me with this task."
    assistant_content = "Sure, I can help."
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": assistant_content},
    ]
    result, mods, removed, changed, _, _ = _apply_role_system_strip(messages)
    check("user message content unchanged", result[0]["content"] == user_content)
    check("assistant message content unchanged", result[1]["content"] == assistant_content)
    check("no mods recorded", mods == [])
    check("no changed indices", changed == [])
    print()


def test_idempotency():
    print("Fix 2d — idempotency: already-'.' content not re-processed")
    messages = [{"role": "system", "content": "."}]
    result, mods, removed, changed, _, _ = _apply_role_system_strip(messages)
    check("already-'.' skipped", result[0]["content"] == ".")
    check("no mods for already-stripped", mods == [])
    check("no changed indices", changed == [])
    print()


def test_empty_content_skipped():
    print("Fix 2e — empty content skipped")
    messages = [{"role": "system", "content": ""}]
    result, mods, removed, changed, _, _ = _apply_role_system_strip(messages)
    check("empty content not modified", result[0]["content"] == "")
    check("no mods", mods == [])
    print()


def test_multiple_system_messages():
    print("Fix 2f — multiple role=system messages all stripped")
    messages = [
        {"role": "system", "content": "first system message"},
        {"role": "user", "content": "user turn"},
        {"role": "system", "content": "second system message"},
    ]
    result, mods, removed, changed, _, _ = _apply_role_system_strip(messages)
    check("first system → '.'", result[0]["content"] == ".")
    check("user untouched", result[1]["content"] == "user turn")
    check("second system → '.'", result[2]["content"] == ".")
    check("two mods recorded", mods.count("stripped_role_system_msg") == 2)
    check("indices 0 and 2 changed", set(changed) == {0, 2})
    print()


# Attribution — role-based code='RS' in _process_messages_section

def test_attribution_rs_code():
    print("Fix 2g — attribution: role=system → code='RS', fn='_apply_role_system_strip'")
    orig_msgs = [{"role": "system", "content": _SYSTEM_CONTENT}]
    fwd_msgs  = [{"role": "system", "content": "."}]
    orig_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_norm, fwd_norm)
    # Build ops the same way the pass does
    from proxy.rule_ops import _ops_from_content_change
    all_ops = {0: _ops_from_content_change(_SYSTEM_CONTENT, ".")}
    s_msgs, _, _, _, s_fn, _ = _process_messages_section(
        msg_diffs, orig_norm, is_first=True, prev_stripped=None, prev_injected=None, all_ops=all_ops
    )
    fn_value = s_fn.get("msg.0.0")
    check("s_msgs has entry for msg 0", "0" in s_msgs)
    check("s_fn key 'msg.0.0' present", fn_value is not None)
    check("fn attributed to _apply_role_system_strip", fn_value == "_apply_role_system_strip")
    check("RS → _apply_role_system_strip in _MSG_CODE_TO_FN", _MSG_CODE_TO_FN.get('RS') == '_apply_role_system_strip')
    print()


def test_attribution_user_unaffected():
    print("Fix 2h — attribution: role=user still uses _attribute_chunk (not RS)")
    orig_msgs = [{"role": "user", "content": "The following skills are available for use with the Skill tool\nsome skill text"}]
    fwd_msgs  = [{"role": "user", "content": "."}]
    orig_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_norm, fwd_norm)
    from proxy.rule_ops import _ops_from_content_change
    all_ops = {0: _ops_from_content_change(orig_msgs[0]["content"], ".")}
    _, _, _, _, s_fn, _ = _process_messages_section(
        msg_diffs, orig_norm, is_first=True, prev_stripped=None, prev_injected=None, all_ops=all_ops
    )
    fn_value = s_fn.get("msg.0.0")
    check("user attribution NOT _apply_role_system_strip", fn_value != "_apply_role_system_strip")
    check("user attribution uses content-based path (SK → _apply_cumulative_sr_strips)", fn_value == "_apply_cumulative_sr_strips")
    print()


if __name__ == "__main__":
    test_workflow_blocklist()
    test_role_system_strip_fires()
    test_role_system_strip_unconditional()
    test_role_user_assistant_untouched()
    test_idempotency()
    test_empty_content_skipped()
    test_multiple_system_messages()
    test_attribution_rs_code()
    test_attribution_user_unaffected()
    print("Done.")
