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


def test_wording3_tool_result_str_content():
    print("Item 4s — wording 3: tool_result string content replaced with timeout-aware hold message")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_w3", "content": _LAUNCH_ACK_W3},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("wording3 tool_result content → timeout-aware 3-line hold message", tr["content"] == _EXPECTED_REPLACEMENT_W3)
    check("mod-name recorded", "stripped_bg_launch_ack" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0] (incl. the trailing cwd sentence)", removed.get(0) == [_LAUNCH_ACK_W3])
    print()


def test_wording3_fp_mid_content_preserved():
    print("Item 4t — FP: wording-3 marker phrase quoted mid-content (not block-initial) preserved")
    messages = [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_fp_w3", "content": _FP_W3_MID_CONTENT},
        ],
    }]
    result, mods, removed, changed, _, _ = _apply_bg_launch_ack_strip(messages)
    tr = result[0]["content"][0]
    check("content UNCHANGED", tr["content"] == _FP_W3_MID_CONTENT)
    check("stripped_bg_launch_ack NOT in mods", "stripped_bg_launch_ack" not in mods)
    check("index 0 NOT in changed_indices", 0 not in changed)
    check("nothing removed at index 0", removed.get(0) is None)
    print()


def test_wording3_attribution_bl_code():
    print("Item 4u — attribution: wording-3 ack chunk → code='BL' (same rule as wording 1/2)")
    code = attribute_chunk(_LAUNCH_ACK_W3)
    check(f"wording3 chunk attributes to BL (got {code!r})", code == "BL")
    print()


def test_wording3_message_differs_and_mentions_timeout():
    print("Item 4v — wording-3 message line differs from wording 1/2 and names the timeout cause")
    messages = [{
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t3", "content": _LAUNCH_ACK_W3}],
    }]
    result, _, _, _, _, _ = _apply_bg_launch_ack_strip(messages)
    msg_line = result[0]["content"][0]["content"].split('\n')[0]
    check("wording3 message line uses the timeout-aware constant", msg_line == _BG_AUTO_TIMEOUT_MSG)
    check("wording3 message line differs from wording1/2's shared message", msg_line != _BG_LAUNCH_ACK_MSG)
    check("wording3 message explicitly names the timeout cause", "timeout" in msg_line.lower())
    print()


def test_wording3_main_vs_worker():
    print("Item 4w — wording-3 replacement wording: is_main=True sharpens vs the default/worker wording")
    messages = [{
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "toolu_w3_main", "content": _LAUNCH_ACK_W3}],
    }]
    default_result, _, _, _, _, _ = _apply_bg_launch_ack_strip(messages)
    main_result, _, _, _, _, _ = _apply_bg_launch_ack_strip(messages, is_main=True)
    default_text = default_result[0]["content"][0]["content"]
    main_text = main_result[0]["content"][0]["content"]
    check("default (is_main=False) wording unchanged", default_text.startswith(_BG_AUTO_TIMEOUT_MSG))
    check("main wording starts with the sharpened timeout-aware message", main_text.startswith(_BG_AUTO_TIMEOUT_MSG_MAIN))
    check("main wording differs from default wording", main_text != default_text)
    check("main wording still carries the recovered ID line", "ID: b1mahby4a" in main_text)
    print()


def test_wording3_ops_path_present():
    print("Item 4x — wording-3 strip is visible in the ops path, not only in the payload")
    messages = [{
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "toolu_w3_ops", "content": _LAUNCH_ACK_W3}],
    }]
    _result, _mods, _removed, _changed, _injected, ops = _apply_bg_launch_ack_strip(messages)
    block_ops = ops.get(0, {}).get(0, [])
    check("exactly one op recorded for the wording-3 strip", len(block_ops) == 1)
    offset, removed, injected = block_ops[0]
    check("op offset is 0 (full_replace, no prefix trim)", offset == 0)
    check("op removed is the FULL original wording-3 ack", removed == _LAUNCH_ACK_W3)
    check("op injected is the FULL timeout-aware replacement", injected == _EXPECTED_REPLACEMENT_W3)

    orig_content = [{"type": "tool_result", "tool_use_id": "toolu_w3_ops", "content": _LAUNCH_ACK_W3}]
    fwd_content = [{"type": "tool_result", "tool_use_id": "toolu_w3_ops", "content": "."}]
    orig_msgs = [{"role": "user", "content": orig_content}]
    fwd_msgs = [{"role": "user", "content": fwd_content}]
    orig_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_norm = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_norm, fwd_norm)
    all_ops = {0: _ops_from_content_change(orig_content, fwd_content)}
    _, _, _, _, s_fn, _ = _process_messages_section(
        msg_diffs, orig_norm, is_first=True, prev_stripped=None, prev_injected=None, all_ops=all_ops
    )
    check("fn_map attributes the wording-3 removal to _apply_bg_launch_ack_strip", s_fn.get("msg.0.0") == "_apply_bg_launch_ack_strip")
    print()


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
