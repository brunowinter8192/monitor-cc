"""Unit tests for CC 2.1.176 background-launch-ack strip (Item 4).

Fixtures: launch-ack as tool_result string AND as standalone text block.
Marker: 'running in background with ID'.

Run from project root:
    ./venv/bin/python dev/proxy_176_bg_launch_ack_tests.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from proxy.message_passes_simple import _apply_bg_launch_ack_strip
from proxy.strip_inject_delta import _process_messages_section, _MSG_CODE_TO_FN
from proxy.diff_engine import _diff_messages, compose_block
from proxy.logging import _normalize_msg_shape_for_hash
from proxy.rule_ops import _ops_from_content_change
from proxy.strip_vocab import attribute_chunk
from proxy.strip_bg_launch_ack import _BG_LAUNCH_ACK_MSG, _BG_LAUNCH_ACK_MSG_MAIN

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

def check(label, condition):
    print(f"  {'  '+_PASS if condition else '  '+_FAIL}  {label}")
    return condition

# Realistic fixture text (~130c, stable prefix)
_LAUNCH_ACK = (
    "Command running in background with ID: bg_01ABC. "
    "Output is being written to: /tmp/output_01ABC.txt. "
    "You will be notified when it completes. "
    "To check interim output, use Read on that file path."
)

# 2026-07-29: replacement is now 3 lines (msg + Output: <path> + ID: <id>, both recovered from
# _LAUNCH_ACK above), not a single-sentence "." placeholder.
_EXPECTED_REPLACEMENT = (
    "Command is running in the background. Do NOT check, poll, or read its output — "
    "just wait until it finishes (you will get a completion notice).\n"
    "Output: /tmp/output_01ABC.txt\n"
    "ID: bg_01ABC\n"
)

# Completion notification — must NOT be falsely triggered
_COMPLETION_NOTIF = 'Background command "sleep 30" failed with exit code 143'

# FP fixtures — each CONTAINS the marker phrase but does NOT start with the ack prefix.
# Simulates large tool_result / pasted user content that quotes the phrase as data.
_FP_LARGE = (
    "RAG search results (hybrid, 5 hits):\n\n"
    "[1] decisions/strip_bg_launch_ack.md (score 0.92)\n"
    "    The strip was added because every CC 2.1.176 session emitted a\n"
    "    'Command running in background with ID: <id>' ack immediately\n"
    "    after bash tool invocations. These acks polluted the context window.\n\n"
    "[2] src/proxy/strip_bg_launch_ack.py (score 0.88)\n"
    "    Marker constant: 'running in background with ID'. Anchored prefix:\n"
    "    'Command running in background with ID:'. The strip ONLY fires\n"
    "    when text.lstrip().startswith(prefix), not substring-anywhere.\n\n"
    "[3] dev/proxy_176_bg_launch_ack_tests.py (score 0.85)\n"
    "    Unit suite. Tests: tool_result string, text block, list content,\n"
    "    str message, non-matching, completion notification, assistant.\n\n"
    "Query: 'running in background with ID strip anchored prefix fix'\n"
    "Collection: monitor-cc-docs | Mode: hybrid | k=5\n"
)

_FP_USER_STR = (
    "I pasted this output from the terminal:\n"
    "  running in background with ID: bxab0pzvo. Output is being written to ...\n"
    "Does the proxy strip this? I want it preserved."
)

_FP_TEXT_BLOCK_TEXT = (
    "The following phrase appears in the decision file:\n"
    "'Command running in background with ID: <id>' — this is the ack prefix.\n"
    "It is quoted here for documentation purposes."
)

_FP_LIST_SUB_TEXT = (
    "Tool output (read file dev/proxy_176_bg_launch_ack_tests.py):\n"
    "Line 28: _LAUNCH_ACK = 'Command running in background with ID: bg_01ABC. '\n"
    "Line 33-35: fixture for completion notification.\n"
)

# Wording 2 (2026-07-29 milestone-2) — user manually backgrounds an already-running Bash call.
# No trailing ". You will be notified..." sentence; ack IS the complete block in the only
# measured corpus occurrence (dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md).
_LAUNCH_ACK_W2 = (
    "Command was manually backgrounded by user with ID: bsxpatpam. "
    "Output is being written to: /tmp/output_w2.txt"
)

_EXPECTED_REPLACEMENT_W2 = (
    "Command is running in the background. Do NOT check, poll, or read its output — "
    "just wait until it finishes (you will get a completion notice).\n"
    "Output: /tmp/output_w2.txt\n"
    "ID: bsxpatpam\n"
)

# FP fixture — CONTAINS the wording-2 marker phrase but does NOT start with the ack prefix.
_FP_W2_MID_CONTENT = (
    "RAG search results (hybrid, 3 hits):\n\n"
    "[1] decisions/strip_bg_launch_ack.md (score 0.90)\n"
    "    Wording 2 marker: 'backgrounded by user with ID'. Anchored prefix:\n"
    "    'Command was manually backgrounded by user with ID:'. Fires only when\n"
    "    text.lstrip().startswith(prefix), not substring-anywhere.\n\n"
    "[2] Example quoted transcript:\n"
    "    'Command was manually backgrounded by user with ID: bxab0pzvo. Output is being written to ...'\n"
    "    — pasted here for documentation purposes, must not be replaced.\n"
)


def test_tool_result_str_content():
    print("Item 4a — tool_result string content replaced with 3-line hold message")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": _LAUNCH_ACK},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("tool_result content → 3-line hold message", tr["content"] == _EXPECTED_REPLACEMENT)
    check("tool_use_id preserved", tr["tool_use_id"] == "toolu_01")
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0]", removed.get(0) == [_LAUNCH_ACK])
    print()


def test_text_block_content():
    print("Item 4b — standalone text block replaced with 3-line hold message")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": "some output"},
            {"type": "text", "text": _LAUNCH_ACK},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    content = result[0]["content"]
    text_block = next(b for b in content if b.get("type") == "text")
    tool_block = next(b for b in content if b.get("type") == "tool_result")
    check("text block → 3-line hold message", text_block["text"] == _EXPECTED_REPLACEMENT)
    check("unrelated tool_result preserved", tool_block["content"] == "some output")
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    print()


def test_str_message_content():
    print("Item 4c — string-content message replaced with 3-line hold message")
    messages = [{"role": "user", "content": _LAUNCH_ACK}]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("string content → 3-line hold message", result[0]["content"] == _EXPECTED_REPLACEMENT)
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    print()


def test_tool_result_list_content():
    print("Item 4d — tool_result with list content (sub-text block) replaced with 3-line hold message")
    messages = [{
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": "toolu_02",
            "content": [{"type": "text", "text": _LAUNCH_ACK}],
        }],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    sub = tr["content"][0]
    check("sub-text block → 3-line hold message", sub["text"] == _EXPECTED_REPLACEMENT)
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    print()


def test_non_matching_tool_result_untouched():
    print("Item 4e — non-matching tool_result untouched")
    other_content = "File read successfully: 42 lines"
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_03", "content": other_content},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("non-matching tool_result preserved", result[0]["content"][0]["content"] == other_content)
    check("no mods", mods == [])
    check("no changed indices", changed == [])
    print()


def test_completion_notification_not_triggered():
    print("Item 4f — completion notification 'Background command...' not falsely triggered")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_04", "content": _COMPLETION_NOTIF},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("completion notification preserved", result[0]["content"][0]["content"] == _COMPLETION_NOTIF)
    check("no mods (marker absent)", mods == [])
    print()


def test_assistant_untouched():
    print("Item 4g — role=assistant message untouched")
    messages = [{"role": "assistant", "content": _LAUNCH_ACK}]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("assistant content unchanged", result[0]["content"] == _LAUNCH_ACK)
    check("no mods", mods == [])
    print()


def test_attribution_bl_code():
    print("Item 4h — attribution: launch-ack chunk → code='BL', fn='_apply_bg_launch_ack_strip'")
    orig_content = [{"type": "tool_result", "tool_use_id": "toolu_01", "content": _LAUNCH_ACK}]
    fwd_content  = [{"type": "tool_result", "tool_use_id": "toolu_01", "content": "."}]
    orig_msgs = [{"role": "user", "content": orig_content}]
    fwd_msgs  = [{"role": "user", "content": fwd_content}]
    orig_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_norm, fwd_norm)
    all_ops = {0: _ops_from_content_change(orig_content, fwd_content)}
    _, _, _, _, s_fn, _ = _process_messages_section(
        msg_diffs, orig_norm, is_first=True, prev_stripped=None, prev_injected=None, all_ops=all_ops
    )
    fn_value = s_fn.get("msg.0.0")
    check("fn attributed to _apply_bg_launch_ack_strip", fn_value == "_apply_bg_launch_ack_strip")
    check("BL → _apply_bg_launch_ack_strip in _MSG_CODE_TO_FN", _MSG_CODE_TO_FN.get('BL') == '_apply_bg_launch_ack_strip')
    print()


def test_fp_tool_result_str_mid_content():
    print("Item 4i — FP: large tool_result containing marker mid-content preserved")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_fp1", "content": _FP_LARGE},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("content UNCHANGED", tr["content"] == _FP_LARGE)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    check("index 0 NOT in changed_indices", 0 not in changed)
    check("nothing removed at index 0", removed.get(0) is None)
    print()


def test_fp_user_str_mid_content():
    print("Item 4j — FP: user string message containing marker mid-content preserved")
    messages = [{"role": "user", "content": _FP_USER_STR}]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("content UNCHANGED", result[0]["content"] == _FP_USER_STR)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    print()


def test_fp_text_block_mid_content():
    print("Item 4k — FP: text block containing marker mid-content preserved")
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": _FP_TEXT_BLOCK_TEXT},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    text_block = result[0]["content"][0]
    check("text UNCHANGED", text_block["text"] == _FP_TEXT_BLOCK_TEXT)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    print()


def test_fp_tool_result_list_mid_content():
    print("Item 4l — FP: tool_result list content with marker mid-content preserved")
    messages = [{
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": "toolu_fp2",
            "content": [{"type": "text", "text": _FP_LIST_SUB_TEXT}],
        }],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    sub = result[0]["content"][0]["content"][0]
    check("sub-text UNCHANGED", sub["text"] == _FP_LIST_SUB_TEXT)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    print()


def test_wording2_tool_result_str_content():
    print("Item 4m — wording 2: tool_result string content replaced with SAME 3-line hold message")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_w2", "content": _LAUNCH_ACK_W2},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("wording2 tool_result content → 3-line hold message", tr["content"] == _EXPECTED_REPLACEMENT_W2)
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0]", removed.get(0) == [_LAUNCH_ACK_W2])
    print()


def test_wording2_fp_mid_content_preserved():
    print("Item 4n — FP: wording-2 marker phrase quoted mid-content (not block-initial) preserved")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_fp_w2", "content": _FP_W2_MID_CONTENT},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("content UNCHANGED", tr["content"] == _FP_W2_MID_CONTENT)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    check("index 0 NOT in changed_indices", 0 not in changed)
    check("nothing removed at index 0", removed.get(0) is None)
    print()


def test_wording2_attribution_bl_code():
    print("Item 4o — attribution: wording-2 ack chunk → code='BL' (same as wording 1)")
    code = attribute_chunk(_LAUNCH_ACK_W2)
    check(f"wording2 chunk attributes to BL (got {code!r})", code == "BL")
    print()


def test_wording1_and_wording2_same_msg_line():
    print("Item 4p — both wordings produce the identical message-line prefix (canonical shape)")
    msgs1 = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": _LAUNCH_ACK}]}]
    msgs2 = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": _LAUNCH_ACK_W2}]}]
    result1, _, _, _, _, _ = _apply_bg_launch_ack_strip(msgs1)
    result2, _, _, _, _, _ = _apply_bg_launch_ack_strip(msgs2)
    r1 = result1[0]["content"][0]["content"]
    r2 = result2[0]["content"][0]["content"]
    msg_line = r1.split('\n')[0]
    check("wording1 message line", msg_line == "Command is running in the background. Do NOT check, poll, or read its output — just wait until it finishes (you will get a completion notice).")
    check("wording2 message line identical to wording1", r2.split('\n')[0] == msg_line)
    print()


# ── FULL-REPLACEMENT SPAN SHAPE (2026-07-29 milestone-3) ──────────────────────
# _apply_bg_launch_ack_strip is one of the 3 full_replace=True call sites in message_passes.py
# (src/proxy/rule_ops.py::_extract_block_op). Before this milestone, the recorded op trimmed the
# shared "Command " prefix between the ack and its replacement, so the pane rendered "Command "
# unhighlighted on its own line, then the rest green below (live-observed 2026-07-29). This test
# pins BOTH the op shape (one contiguous op, no trim) and the composed span shape (one contiguous
# stripped span + one contiguous injected span — no interleaved "equal" fragment) against the real
# launch-ack fixture, through the real production functions.
def test_full_replace_span_is_one_contiguous_block():
    print("Item 4q — full-replacement op is ONE contiguous op, composes to ONE contiguous green span")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_span", "content": _LAUNCH_ACK},
        ],
    }]
    _result, _mods, _removed, _changed, _injected, ops = _apply_bg_launch_ack_strip(messages)
    block_ops = ops.get(0, {}).get(0, [])
    check("exactly one op recorded", len(block_ops) == 1)
    offset, removed, injected = block_ops[0]
    check("op offset is 0 (no prefix trim)", offset == 0)
    check("op removed is the FULL original ack (no trim)", removed == _LAUNCH_ACK)
    check("op injected is the FULL replacement (no trim)", injected == _EXPECTED_REPLACEMENT)
    check("shared 'Command ' prefix is NOT split off",
          not (removed.startswith("Command ") and injected.startswith("Command ")
               and offset > 0))

    spans = compose_block(_LAUNCH_ACK, block_ops)
    check("composed spans: exactly 2 spans (one stripped, one injected)", len(spans) == 2)
    check("span 0 is one contiguous 'stripped' span covering the WHOLE original ack",
          spans[0] == ("stripped", _LAUNCH_ACK))
    check("span 1 is one contiguous 'injected' span covering the WHOLE replacement",
          spans[1] == ("injected", _EXPECTED_REPLACEMENT))
    check("no 'equal' span present (would indicate a leftover shared-prefix split)",
          all(tag != "equal" for tag, _ in spans))
    print()


# ── MAIN-CONTEXT WORDING SHARPENING (2026-08-06 milestone-2) ──────────────────
# Folded in from dev/timer-loop/p2_pending_bg_state_probe.py (Test 12) when that probe was
# deleted (Milestone 3, 2026-08 — its subject module src/proxy/pending_bg_state.py was removed
# and this was the one still-relevant, otherwise-uncovered case in it: is_main is unrelated to
# pending_bg_state, it selects strip_bg_launch_ack.py's replacement wording via
# _apply_bg_launch_ack_strip's own is_main param). See process-docs/timer-loop/ for the removal.
def test_wording_main_vs_worker():
    print("Item 4r — replacement wording: is_main=True sharpens vs the default/worker wording")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_main", "content": _LAUNCH_ACK},
        ],
    }]
    default_result, _, _, _, _, _ = _apply_bg_launch_ack_strip(messages)
    main_result, _, _, _, _, _ = _apply_bg_launch_ack_strip(messages, is_main=True)
    default_text = default_result[0]["content"][0]["content"]
    main_text = main_result[0]["content"][0]["content"]
    check("default (is_main=False) wording unchanged", default_text.startswith(_BG_LAUNCH_ACK_MSG))
    check("main wording starts with the sharpened message", main_text.startswith(_BG_LAUNCH_ACK_MSG_MAIN))
    check("main wording differs from default wording", main_text != default_text)
    check("main wording explicitly mentions going idle", "idle" in _BG_LAUNCH_ACK_MSG_MAIN.lower())
    check("main wording explicitly mentions this task's ID", "task ID" in _BG_LAUNCH_ACK_MSG_MAIN)
    check("main wording still carries the recovered ID line", "ID: bg_01ABC" in main_text)
    print()


if __name__ == "__main__":
    test_tool_result_str_content()
    test_text_block_content()
    test_str_message_content()
    test_tool_result_list_content()
    test_non_matching_tool_result_untouched()
    test_completion_notification_not_triggered()
    test_assistant_untouched()
    test_attribution_bl_code()
    test_fp_tool_result_str_mid_content()
    test_fp_user_str_mid_content()
    test_fp_text_block_mid_content()
    test_fp_tool_result_list_mid_content()
    test_wording2_tool_result_str_content()
    test_wording2_fp_mid_content_preserved()
    test_wording2_attribution_bl_code()
    test_wording1_and_wording2_same_msg_line()
    test_full_replace_span_is_one_contiguous_block()
    test_wording_main_vs_worker()
    print("Done.")
