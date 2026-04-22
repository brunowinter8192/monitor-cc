"""
Visual test script for strip_marker.py helper.

Usage (from repo root):
    ./venv/bin/python dev/display/test_strip_markers.py

Feeds synthetic proxy entries and session events through the strip-marker pipeline,
prints ANSI-colored output to terminal — no live proxy required.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.format.strip_marker import (
    highlight_stripped,
    get_stripped_data,
    build_tool_result_strip_lookup,
    build_tool_id_strip_lookup,
)
from src.constants import DIM_YELLOW_BG, SOFT_RESET, RESET, DIM, ZEBRA_BG_B

# ── helpers ─────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n\033[1;34m{'='*60}\n  {title}\n{'='*60}\033[0m")

def label(text):
    print(f"\033[2m  {text}\033[0m")

# ── synthetic data ───────────────────────────────────────────────────────────

SKILLS_SR = "<system-reminder>The following skills are available for use with the Skill tool:\n- bead-cli\n- iterative-dev\n</system-reminder>"
PLAN_SR   = "<system-reminder>Plan mode is active. All tool use is disabled.</system-reminder>"

TOOL_RESULT_TEXT = "Found 3 matching files:\n  src/foo.py\n  src/bar.py\n  tests/test_foo.py"

# Pre-strip: user message whose content is [text_block(SR), tool_result_block]
# _summarize_content_for_log joins text + tool_result content → flat string
PRE_STRIP_MSG2 = f"{SKILLS_SR}\n{TOOL_RESULT_TEXT}"
POST_STRIP_MSG2 = TOOL_RESULT_TEXT

PRE_STRIP_MSG5 = f"{PLAN_SR}\nUser message text here."
POST_STRIP_MSG5 = "User message text here."

SYNTHETIC_ENTRY = {
    "timestamp": "2026-04-21T10:00:00.000Z",
    "stripped_msg_indices": [2, 5],
    "stripped_msg_originals": {
        "2": PRE_STRIP_MSG2,
        "5": PRE_STRIP_MSG5,
    },
    "stripped_msg_removed": {
        "2": [SKILLS_SR],
        "5": [PLAN_SR],
    },
    "modifications": ["stripped_skills_sr", "removed_plan_mode_sr"],
    "messages": [
        {"role": "user", "type": "text", "chars": 100, "blocks": []},
        {"role": "assistant", "type": "tool_use", "chars": 200, "blocks": [
            {"type": "tool_use", "id": "tu_abc123", "chars": 50}
        ]},
        {"role": "user", "type": "tool_result", "chars": len(POST_STRIP_MSG2), "blocks": [
            {"type": "tool_result", "tool_use_id": "tu_abc123", "chars": len(POST_STRIP_MSG2),
             "full_text": POST_STRIP_MSG2}
        ]},
        {"role": "assistant", "type": "tool_use", "chars": 80, "blocks": [
            {"type": "tool_use", "id": "tu_def456", "chars": 80}
        ]},
        {"role": "user", "type": "text", "chars": 30, "blocks": []},
        {"role": "user", "type": "text", "chars": len(POST_STRIP_MSG5), "blocks": [
            {"type": "text", "chars": len(POST_STRIP_MSG5)}
        ]},
    ],
    "raw_payload": {
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_abc123", "name": "Glob", "input": {"pattern": "**/*.py"}}]},
            {"role": "user", "content": [
                {"type": "text", "text": SKILLS_SR},
                {"type": "tool_result", "tool_use_id": "tu_abc123", "content": TOOL_RESULT_TEXT}
            ]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_def456", "name": "Read", "input": {"file_path": "/foo"}}]},
            {"role": "user", "content": "next turn"},
            {"role": "user", "content": [
                {"type": "text", "text": f"{PLAN_SR}\nUser message text here."}
            ]},
        ]
    }
}

# ── test 1: highlight_stripped ───────────────────────────────────────────────

section("1. highlight_stripped — basic")
label("outer_bg='' (ZEBRA_BG_A)")
result = highlight_stripped(PRE_STRIP_MSG2, [SKILLS_SR], outer_bg='')
print(result[:200] + ('...' if len(result) > 200 else ''))

label("outer_bg=ZEBRA_BG_B")
result2 = highlight_stripped(PRE_STRIP_MSG2, [SKILLS_SR], outer_bg=ZEBRA_BG_B)
print(result2[:200] + ('...' if len(result2) > 200 else ''))

label("no chunks → passthrough")
result3 = highlight_stripped(PRE_STRIP_MSG2, [], outer_bg='')
assert result3 == PRE_STRIP_MSG2, "passthrough failed"
print(f"  ✓ unchanged: {result3[:60]}")

label("chunk not found → graceful skip")
result4 = highlight_stripped("foo bar", ["NOTHERE"], outer_bg='')
assert result4 == "foo bar", "graceful skip failed"
print(f"  ✓ unchanged: {result4}")

label("multiple occurrences")
text_multi = "AAA remove_me BBB remove_me CCC"
result5 = highlight_stripped(text_multi, ["remove_me"], outer_bg='')
count = result5.count(DIM_YELLOW_BG)
assert count == 2, f"expected 2 highlights, got {count}"
print(f"  ✓ 2 occurrences highlighted: {result5}")
print(RESET, end='')

# ── test 1b: multi-line chunk — every split line must carry DIM_YELLOW_BG ────

section("1b. highlight_stripped — multi-line chunk per-line coverage")
chunk_ml = "A\nB\nC"
text_ml = f"PREFIX\n{chunk_ml}\nSUFFIX"
result_ml = highlight_stripped(text_ml, [chunk_ml], outer_bg='')
split_lines = result_ml.split('\n')
label(f"input text lines: {len(text_ml.split(chr(10)))}, output split lines: {len(split_lines)}")
for i, sl in enumerate(split_lines):
    has_bg = DIM_YELLOW_BG in sl
    label(f"  line {i}: bg={'YES' if has_bg else 'no '} | {repr(sl[:80])}")
# Lines 1, 2, 3 correspond to A, B, C (the chunk)
chunk_lines = result_ml.split('\n')[1:4]  # PREFIX is line 0, chunk occupies lines 1-3, SUFFIX is line 4
for i, cl in enumerate(chunk_lines):
    assert DIM_YELLOW_BG in cl, f"chunk line {i} ('{cl[:40]}') missing DIM_YELLOW_BG"
print(f"  ✓ all 3 chunk lines carry DIM_YELLOW_BG")

label("outer_bg=ZEBRA_BG_B — restored after final chunk line")
result_ml2 = highlight_stripped(f"X{chunk_ml}Y", [chunk_ml], outer_bg=ZEBRA_BG_B)
last_chunk_line = result_ml2.split('\n')[2]  # "C" line
assert DIM_YELLOW_BG in last_chunk_line, "last chunk line missing DIM_YELLOW_BG"
assert ZEBRA_BG_B in last_chunk_line, "outer_bg not restored after final chunk line"
print(f"  ✓ outer_bg ZEBRA_BG_B present on final chunk line after SOFT_RESET")
print(RESET, end='')

# ── test 2: get_stripped_data ────────────────────────────────────────────────

section("2. get_stripped_data")
pre, chunks = get_stripped_data(SYNTHETIC_ENTRY, 2)
assert pre == PRE_STRIP_MSG2
assert chunks == [SKILLS_SR]
label("msg_idx=2 → pre_strip + chunks found ✓")

pre_none, chunks_none = get_stripped_data(SYNTHETIC_ENTRY, 0)
assert pre_none is None
assert chunks_none == []
label("msg_idx=0 (not stripped) → None, [] ✓")

pre5, chunks5 = get_stripped_data(SYNTHETIC_ENTRY, 5)
assert pre5 == PRE_STRIP_MSG5
assert chunks5 == [PLAN_SR]
label(f"msg_idx=5 → plan-mode SR found ✓")

# ── test 3: build_tool_result_strip_lookup (waste_pane) ──────────────────────

section("3. build_tool_result_strip_lookup")
lookup = build_tool_result_strip_lookup([SYNTHETIC_ENTRY])
assert "tu_abc123" in lookup, f"tu_abc123 not in lookup, got {list(lookup.keys())}"
pre_r, chunks_r = lookup["tu_abc123"]
assert pre_r == PRE_STRIP_MSG2
assert chunks_r == [SKILLS_SR]
label("tu_abc123 → pre_strip + chunks ✓")
assert "tu_def456" not in lookup, "tu_def456 should not be in lookup (msg 3 not stripped)"
label("tu_def456 not in lookup (msg[3] not stripped) ✓")

# ── test 4: build_tool_id_strip_lookup (main-pane) ───────────────────────────

section("4. build_tool_id_strip_lookup")
lookup2 = build_tool_id_strip_lookup([SYNTHETIC_ENTRY])
assert "tu_abc123" in lookup2, f"tu_abc123 not in lookup2: {list(lookup2.keys())}"
pre_m, chunks_m = lookup2["tu_abc123"]
assert pre_m == PRE_STRIP_MSG2
label("tu_abc123 found via parsed-entry messages.blocks ✓")

# ── test 5: warnings_pane scan simulation ────────────────────────────────────

section("5. warnings_pane _scan_proxy_entries_for_errors simulation")
# Simulate what _scan_proxy_entries_for_errors does with msg_idx=2 (tool_result)
pre, chunks = get_stripped_data(SYNTHETIC_ENTRY, 2)
display_text = highlight_stripped(pre, chunks) if pre else POST_STRIP_MSG2
label("expanded full_text with strip highlight (msg[2]):")
for line in display_text.split('\n'):
    print(f"    {DIM}{line}{SOFT_RESET}")
print(RESET, end='')

# ── test 6: user_prompt timestamp bucket ─────────────────────────────────────

section("6. user_prompt timestamp bucket (main-pane)")
entry_ts = SYNTHETIC_ENTRY["timestamp"]  # "2026-04-21T10:00:00.000Z"
bucket = entry_ts[:19]  # "2026-04-21T10:00:00"
prompt_ts = "2026-04-21T09:59:58.500Z"
in_bucket = prompt_ts[:19] in {bucket}
label(f"prompt_ts={prompt_ts[:19]}  bucket={bucket}  match={in_bucket}")
# Note: exact match on seconds — proximity matching handled by monitor._refresh_strip_cache
# scanning incrementally, so prompt naturally precedes next proxy entry it would match

print(f"\n\033[1;32m✓ All assertions passed.\033[0m\n")
