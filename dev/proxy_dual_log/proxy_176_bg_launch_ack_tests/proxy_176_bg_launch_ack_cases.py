# INFRASTRUCTURE
from src.proxy.message_passes_simple import _apply_bg_launch_ack_strip
from src.proxy.strip_inject_delta import _process_messages_section, _MSG_CODE_TO_FN
from src.proxy.diff_engine import _diff_messages, compose_block
from src.proxy.logging import _normalize_msg_shape_for_hash
from src.proxy.rule_ops import _ops_from_content_change
from src.proxy.strip_vocab import attribute_chunk
from src.proxy.strip_bg_launch_ack import (
    _BG_LAUNCH_ACK_MSG, _BG_LAUNCH_ACK_MSG_MAIN, _BG_AUTO_TIMEOUT_MSG, _BG_AUTO_TIMEOUT_MSG_MAIN,
)

from proxy_176_bg_launch_ack_report import check
from proxy_176_bg_launch_ack_fixtures import (
    _LAUNCH_ACK, _EXPECTED_REPLACEMENT, _COMPLETION_NOTIF,
    _FP_LARGE, _FP_USER_STR, _FP_TEXT_BLOCK_TEXT, _FP_LIST_SUB_TEXT,
    _LAUNCH_ACK_W2, _EXPECTED_REPLACEMENT_W2, _FP_W2_MID_CONTENT,
    _LAUNCH_ACK_W3, _EXPECTED_REPLACEMENT_W3, _FP_W3_MID_CONTENT,
)

# FUNCTIONS

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


