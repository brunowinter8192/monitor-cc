"""Unit tests for CC 2.1.176 background-launch-ack strip (Item 4).

Fixtures: launch-ack as tool_result string AND as standalone text block.
Marker: 'running in background with ID'.

Run from project root:
    ./venv/bin/python dev/proxy_176_bg_launch_ack_tests.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from proxy.message_passes import _apply_bg_launch_ack_strip
from proxy.strip_inject_delta import _process_messages_section, _MSG_CODE_TO_FN
from proxy.diff_engine import _diff_messages
from proxy.logging import _normalize_msg_shape_for_hash
from proxy.rule_ops import _ops_from_content_change

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


def test_tool_result_str_content():
    print("Item 4a — tool_result string content replaced with '.'")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": _LAUNCH_ACK},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("tool_result content → '.'", tr["content"] == ".")
    check("tool_use_id preserved", tr["tool_use_id"] == "toolu_01")
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0]", removed.get(0) == [_LAUNCH_ACK])
    print()


def test_text_block_content():
    print("Item 4b — standalone text block replaced with '.'")
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
    check("text block → '.'", text_block["text"] == ".")
    check("unrelated tool_result preserved", tool_block["content"] == "some output")
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    print()


def test_str_message_content():
    print("Item 4c — string-content message replaced with '.'")
    messages = [{"role": "user", "content": _LAUNCH_ACK}]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    check("string content → '.'", result[0]["content"] == ".")
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    print()


def test_tool_result_list_content():
    print("Item 4d — tool_result with list content (sub-text block) replaced with '.'")
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
    check("sub-text block → '.'", sub["text"] == ".")
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
    print("Done.")
