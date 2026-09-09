"""
P3 — verifies src/proxy/strip_interrupt_marker.py and its full wiring (message_passes.py,
rules.py, strip_vocab.py, strip_inject_delta.py).

The proxy sends a tmux Escape into a worker's pane when one of its calls is backgrounded
(src/proxy/bg_escape.py). Claude Code records that interruption in the conversation as a block
whose (whitespace-stripped) text is EXACTLY one of two real wordings — "[Request interrupted by
user]" or "[Request interrupted by user for tool use]", both always trailing-newline-terminated
in the corpus — no user interrupted anything, but a worker reading the marker halts and waits for
an instruction nobody intended to give. This probe proves the marker never reaches the model.

Covers: the measured real payload shape (3 blocks: tool_result / marker(+'\\n') / injected
wake-up, neighbors byte-identical after strip), all 4 content shapes for both wordings, the
false-positive class (marker embedded inside longer text must survive untouched, incl. a real
corpus-derived 180-char quote), and attribution resolving to a named function through the real
apply_modification_rules -> _build_stripped_injected_deltas path.

Run from project root or worktree root:
    ./venv/bin/python dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.strip_interrupt_marker import _strip_interrupt_marker
from proxy.message_passes_simple import _apply_interrupt_marker_strip
from proxy.rules import apply_modification_rules
from proxy.strip_vocab import attribute_chunk, RULES
from proxy.strip_inject_delta import _MSG_CODE_TO_FN, _build_stripped_injected_deltas

# Real corpus wordings (src/logs/dual_log/*_original.jsonl, 2026-07-31 re-measurement) — both
# always trailing-newline-terminated; 10x base wording, 1x "for tool use" wording, 11/11 total.
_INTERRUPT_MARKER = '[Request interrupted by user]\n'
_INTERRUPT_MARKER_TOOL_USE = '[Request interrupted by user for tool use]\n'

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

# Test 1 — real measured shape: tool_result / marker / injected wake-up, 3 blocks. Marker block
# emptied to '.'; the two neighbor blocks are byte-identical afterwards (dict equality).
def test_real_shape_neighbors_untouched():
    print("\n[Test 1] Real 3-block shape (tool_result / marker / wake-up) — neighbors intact")
    tool_result_block = {"type": "tool_result", "tool_use_id": "toolu_01", "content": "some prior tool output"}
    marker_block = {"type": "text", "text": _INTERRUPT_MARKER}
    wakeup_block = {"type": "text", "text": "background done — check worker or other process\n"}
    content = [tool_result_block, marker_block, wakeup_block]
    new_content, removed = _strip_interrupt_marker(content)
    check("marker text captured in removed_chunks", removed == [_INTERRUPT_MARKER])
    check("block count unchanged (3)", len(new_content) == 3)
    check("marker block emptied to '.'", new_content[1] == {"type": "text", "text": "."})
    check("preceding tool_result block byte-identical", new_content[0] == tool_result_block)
    check("following wake-up block byte-identical", new_content[2] == wakeup_block)


# Test 2 — all 4 content shapes strip the exact-match marker.
def test_four_content_shapes():
    print("\n[Test 2] All 4 content shapes")
    new_str, r1 = _strip_interrupt_marker(_INTERRUPT_MARKER)
    check("str shape -> '.'", new_str == "." and r1 == [_INTERRUPT_MARKER])

    new_list_text, r2 = _strip_interrupt_marker([{"type": "text", "text": _INTERRUPT_MARKER}])
    check("list[text] shape -> block text '.'", new_list_text[0]["text"] == "." and r2 == [_INTERRUPT_MARKER])

    new_tr_str, r3 = _strip_interrupt_marker(
        [{"type": "tool_result", "tool_use_id": "x", "content": _INTERRUPT_MARKER}]
    )
    check("list[tool_result+str] shape -> content '.'", new_tr_str[0]["content"] == "." and r3 == [_INTERRUPT_MARKER])

    new_tr_list, r4 = _strip_interrupt_marker(
        [{"type": "tool_result", "tool_use_id": "x", "content": [{"type": "text", "text": _INTERRUPT_MARKER}]}]
    )
    check("list[tool_result+list] shape -> inner text '.'",
          new_tr_list[0]["content"][0]["text"] == "." and r4 == [_INTERRUPT_MARKER])


# Test 2b — the 2nd real wording ("for tool use", 1/11 measured occurrences) strips too — this
# wording was never covered before the 2026-07-31 fix and is why the false negative shipped.
def test_tool_use_wording():
    print("\n[Test 2b] 'for tool use' wording strips (newline-terminated and bare)")
    new_nl, r1 = _strip_interrupt_marker(_INTERRUPT_MARKER_TOOL_USE)
    check("tool-use wording (real, trailing '\\n') -> '.'", new_nl == "." and r1 == [_INTERRUPT_MARKER_TOOL_USE])
    bare = _INTERRUPT_MARKER_TOOL_USE.rstrip('\n')
    new_bare, r2 = _strip_interrupt_marker(bare)
    check("tool-use wording (bare, no '\\n') -> '.'", new_bare == "." and r2 == [bare])


# Test 3 — false-positive class: marker embedded inside longer text (top-level text block and
# tool_result data) must be left byte-identical, no removal recorded. Includes a real
# corpus-derived 180-char user message that quotes the bracketed marker mid-sentence
# (src/logs/dual_log/api_requests_opus_monitor_cc_1785431184_original.jsonl, msg 11).
def test_marker_embedded_in_longer_text_untouched():
    print("\n[Test 3] Marker embedded in longer text is NOT destroyed")
    longer_text = f"Earlier in the transcript: {_INTERRUPT_MARKER} — but that was quoted, not live."
    new_text_block, r1 = _strip_interrupt_marker([{"type": "text", "text": longer_text}])
    check("longer top-level text block untouched", new_text_block[0]["text"] == longer_text and r1 == [])

    new_tr, r2 = _strip_interrupt_marker(
        [{"type": "tool_result", "tool_use_id": "x", "content": f"grep result: {_INTERRUPT_MARKER}\n"}]
    )
    check("longer tool_result content untouched", new_tr[0]["content"] == f"grep result: {_INTERRUPT_MARKER}\n" and r2 == [])

    new_str, r3 = _strip_interrupt_marker(longer_text)
    check("longer top-level str content untouched", new_str == longer_text and r3 == [])

    corpus_quote = (
        "[Image #3] ok live verify da. hast du  [Request interrupted by user] gesehen? wenn ja "
        "funktionniert der strip nicht. wenn nein funktionniert der strip aber das rendering ist broken"
    )
    new_cq, r4 = _strip_interrupt_marker([{"type": "text", "text": corpus_quote}])
    check("real corpus 180-char quote untouched", new_cq[0]["text"] == corpus_quote and r4 == [])


# Test 4a — message-pass level: gate fires only for role='user', mod name is stripped_interrupt_marker.
def test_message_pass_wiring():
    print("\n[Test 4a] _apply_interrupt_marker_strip pass wiring")
    msgs = [
        {"role": "assistant", "content": [{"type": "text", "text": _INTERRUPT_MARKER}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_02", "content": "output"},
            {"type": "text", "text": _INTERRUPT_MARKER},
            {"type": "text", "text": "background done — check worker or other process\n"},
        ]},
    ]
    new_msgs, mods, removed_by_idx, changed, _injected, ops = _apply_interrupt_marker_strip(msgs)
    check("assistant-role message never touched (role gate)", new_msgs[0] == msgs[0])
    check("user message changed", changed == [1])
    check("mod name is stripped_interrupt_marker", mods == ["stripped_interrupt_marker"])
    check("removed chunk recorded for user message", removed_by_idx[1] == [_INTERRUPT_MARKER])
    check("marker block in user message emptied", new_msgs[1]["content"][1]["text"] == ".")
    check("ops recorded for block 1", 1 in ops.get(1, {}))


# Test 4b — vocabulary + attribution: attribute_chunk resolves to 'IM', and IM maps to a named
# function (not 'unknown') in strip_inject_delta's _MSG_CODE_TO_FN.
def test_attribution_vocab():
    print("\n[Test 4b] strip_vocab / strip_inject_delta attribution")
    check("'IM' registered in RULES", 'IM' in RULES)
    check("RULES['IM'] full name is stripped_interrupt_marker", RULES['IM'][0] == 'stripped_interrupt_marker')
    check("attribute_chunk(base wording) resolves to 'IM'", attribute_chunk(_INTERRUPT_MARKER) == 'IM')
    check("attribute_chunk(tool-use wording) resolves to 'IM'", attribute_chunk(_INTERRUPT_MARKER_TOOL_USE) == 'IM')
    check("'IM' -> named function in _MSG_CODE_TO_FN (not missing)", _MSG_CODE_TO_FN.get('IM') == '_apply_interrupt_marker_strip')


# Test 5 — full pipeline: real apply_modification_rules -> real _build_stripped_injected_deltas,
# fn_map for the stripped block resolves to '_apply_interrupt_marker_strip', never 'unknown'.
def test_full_pipeline_attribution():
    print("\n[Test 5] Full pipeline: apply_modification_rules -> _build_stripped_injected_deltas fn_map")
    orig_payload = {
        "model": "claude-opus-4-6",
        "max_tokens": 8000,
        "system": [
            {"type": "text", "text": "sys0"},
            {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."},
            {"type": "text", "text": "sys2"},
        ],
        "messages": [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_03", "content": "some tool output"},
                {"type": "text", "text": _INTERRUPT_MARKER},
                {"type": "text", "text": "background done — check worker or other process\n"},
            ]},
        ],
        "tools": [],
    }
    modified, modifications, _orig_sys2, _smi, _smo, stripped_msg_removed, _ima, all_ops = apply_modification_rules(
        orig_payload, model_family="opus", project_path=str(WORKTREE_ROOT)
    )
    check("mod fired: stripped_interrupt_marker", "stripped_interrupt_marker" in modifications)
    check("marker block emptied in modified payload", modified["messages"][0]["content"][1]["text"] == ".")
    check("stripped_msg_removed carries the raw marker text", stripped_msg_removed.get(0) == [_INTERRUPT_MARKER])

    stripped_entry, injected_entry, _ns, _ni = _build_stripped_injected_deltas(
        orig_payload, modified, "req-001", None, None, "claude-opus-4-6", all_ops
    )
    fn_map = stripped_entry.get("fn_map", {})
    lk = "msg.0.1"
    check(f"fn_map[{lk!r}] present", lk in fn_map)
    check(f"fn_map[{lk!r}] == '_apply_interrupt_marker_strip' (not 'unknown')", fn_map.get(lk) == "_apply_interrupt_marker_strip")
    check("messages_delta carries the stripped marker text", stripped_entry["messages_delta"].get("0", {}).get("1") == [_INTERRUPT_MARKER])


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("strip_interrupt_marker probe — [Request interrupted by user] strip")
    print("=" * 70)
    test_real_shape_neighbors_untouched()
    test_four_content_shapes()
    test_tool_use_wording()
    test_marker_embedded_in_longer_text_untouched()
    test_message_pass_wiring()
    test_attribution_vocab()
    test_full_pipeline_attribution()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "bg_wakeup_id_line" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p3_strip_interrupt_marker_probe_{stamp}.md"
    lines = [
        f"# P3 — strip_interrupt_marker probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
