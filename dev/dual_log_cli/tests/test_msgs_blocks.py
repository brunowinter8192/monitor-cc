"""
Regression suite for `duallog msgs`' block sub-lines (src/dual_log_cli/render.py).

Covers: a multi-block msg renders one indented sub-line per block (type, chars, alignment),
a single-block msg stays byte-identical to the pre-sub-line format, tool_use sub-lines carry
the tool name and an is_error tool_result renders `tool_result!err` (both via the real
timeline.build_turns pipeline, not hand-built labels), and REQ separators are untouched.

All fixtures are synthetic and hand-built or fed through the real `message_summary` /
`timeline` pipeline — no dual-log directory or MONITOR_CC_ROOT is required, so this suite
depends only on the code under test.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_blocks.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_turns import build_turns

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


# The LOCAL "HH:MM:SS" a UTC "...Z" timestamp renders as — computed the same way production code
# does (reader.local_datetime), so an expected string built from this is correct on ANY machine's
# timezone, not just the one this suite happened to be written on.
def _local_clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")


# A msg row shaped like timeline.build_turns' output, without going through it — used where the
# test wants to pin exact block chars rather than derive them from real block text.
def _msg(index: int, role: str, chars: int, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": chars, "blocks": blocks}


def _block(type_: str, chars: int, label: str = None) -> dict:
    return {"label": label or type_, "type": type_, "chars": chars, "sig_chars": 0, "preview": ""}


# 25 msg-adding boundaries ending with one that opens msg index 70 — reproduces the exact
# `── REQ 25  14:49:03 ──` separator this feature's spec sample uses, via the real
# timeline.request_markers machinery (imported indirectly through render_msgs).
def _boundaries_opening_req25_at_70() -> list:
    boundaries = [
        {"start_index": i, "message_count": i + 1, "timestamp": f"2026-08-30T00:00:{i:02d}Z",
         "flow_id": f"f{i}", "restart": False}
        for i in range(24)
    ]
    boundaries.append({
        "start_index": 70, "message_count": 72, "timestamp": "2026-08-30T14:49:03Z",
        "flow_id": "f25", "restart": False,
    })
    return boundaries


# Reproduces this feature's own spec sample byte-for-byte: a 3-block assistant msg (thinking,
# thinking, tool_use[Bash]) followed by a single-block tool_result msg, under a REQ 25 separator.
def test_multiblock_matches_spec_sample() -> None:
    data = {
        "boundaries": _boundaries_opening_req25_at_70(),
        "turns": [
            _msg(70, "assistant", 3862, [
                _block("thinking", 2451),
                _block("thinking", 282),
                _block("tool_use", 1129, label="tool_use[Bash]"),
            ]),
            _msg(71, "user", 1038, [_block("tool_result", 1038)]),
        ],
    }
    expected = (
        f"── REQ 25  {_local_clock('2026-08-30T14:49:03Z')} ──\n"
        "[ 70] assi  3 blocks            3,862c\n"
        "        thinking                2,451c\n"
        "        thinking                  282c\n"
        "        tool_use[Bash]          1,129c\n"
        "[ 71] user  tool_result         1,038c\n"
    )
    # render_msgs slices data["turns"] by LIST POSITION, not by msg["index"] — the two happen to
    # coincide in production (build_turns enumerates in order) but this fixture only carries the
    # two msgs it needs, at positions 0 and 1, while their "index" fields stay 70/71 for display
    # and for the REQ-25 marker lookup.
    got = render_msgs(data, 0, 1)
    check("multiblock matches spec sample byte-for-byte", got == expected, f"got:\n{got!r}\nwant:\n{expected!r}")


# A single-block msg must render exactly the one line it rendered before this feature — no
# trailing sub-line, and the same `[idx] role type chars` column widths.
def test_singleblock_unchanged_format() -> None:
    data = {
        "boundaries": [],
        "turns": [_msg(5, "user", 454, [_block("text", 454)])],
    }
    expected = "[  5] user  text                  454c\n"
    got = render_msgs(data, 0, 0)
    check("single-block msg is exactly one line", got == expected, f"got {got!r}")
    check("single-block msg has no sub-line indent", "\n        " not in got, got)


# A msg with N blocks must produce exactly 1 + N lines (parent + one sub-line per block), in
# block order, each sub-line carrying that block's own chars, not the msg total.
def test_multiblock_line_count_and_order() -> None:
    data = {
        "boundaries": [],
        "turns": [_msg(0, "assistant", 100, [
            _block("text", 10), _block("tool_use", 30, label="tool_use[Grep]"), _block("text", 60),
        ])],
    }
    got = render_msgs(data, 0, 0).rstrip("\n").split("\n")
    check("1 parent + 3 sub-lines = 4 lines", len(got) == 4, got)
    check("sub-line order matches block order", [l.split()[0] for l in got[1:]] == ["text", "tool_use[Grep]", "text"], got)
    check("sub-line 1 carries its own chars, not the msg total", got[1].endswith("10c"), got[1])
    check("sub-line 3 carries its own chars, not the msg total", got[3].endswith("60c"), got[3])


# Sub-line chars must right-align to the SAME column the parent line's chars use, regardless of
# label length — checked by column position, not by a fixed string, so it survives width tuning.
# Both labels here stay inside the block label field's width, same as the spec-sample fixture
# above; a label or chars value wide enough to overflow its own field is a documented, expected
# one-character (or more) jog — see the module's fixed-width Gotcha — not covered here.
def test_subline_chars_align_to_parent_column() -> None:
    data = {
        "boundaries": [],
        "turns": [_msg(0, "assistant", 100, [
            _block("thinking", 5), _block("tool_use", 1234, label="tool_use[Grep]"),
        ])],
    }
    lines = render_msgs(data, 0, 0).rstrip("\n").split("\n")
    parent_chars_end = len(lines[0])
    for sub in lines[1:]:
        check(f"sub-line ends at parent's column ({sub!r})", len(sub) == parent_chars_end, (len(sub), parent_chars_end))


# tool_use and is_error tool_result labels come from timeline._block_label via the real
# message_summary → build_turns pipeline, not from a hand-built dict — this proves the label
# grammar (`tool_use[Bash]`, `tool_result!err`) survives end to end into the msgs sub-line.
def test_real_pipeline_tool_labels() -> None:
    payload = {"messages": [
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "reasoning", "signature": ""},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "content": "boom", "is_error": True, "tool_use_id": "t1"},
        ]},
    ]}
    turns = build_turns(payload)
    data = {"boundaries": [], "turns": turns}
    got = render_msgs(data, 0, 1)
    check("tool_use sub-line carries the tool name", "tool_use[Bash]" in got, got)
    check("single-block is_error tool_result stays type-only (unchanged single-line rule)",
          "[  1] user  tool_result" in got and "tool_result!err" not in got, got)

    # Force the error tool_result into a multi-block msg to exercise its sub-line label
    payload["messages"][1]["content"].append({"type": "text", "text": "note"})
    turns = build_turns(payload)
    data = {"boundaries": [], "turns": turns}
    got = render_msgs(data, 0, 1)
    check("multi-block is_error tool_result sub-line renders tool_result!err", "tool_result!err" in got, got)


# REQ separators must be untouched — same line for the same marker, whether the group's msgs are
# single- or multi-block.
def test_req_separator_unchanged() -> None:
    data = {
        "boundaries": [{"start_index": 0, "message_count": 1, "timestamp": "2026-08-30T09:00:00Z",
                         "flow_id": "f0", "restart": False}],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got = render_msgs(data, 0, 0)
    check("REQ separator format unchanged",
          got.startswith(f"── REQ 1  {_local_clock('2026-08-30T09:00:00Z')} ──\n"), got)


# ORCHESTRATOR

def test_msgs_blocks_workflow() -> None:
    test_multiblock_matches_spec_sample()
    test_singleblock_unchanged_format()
    test_multiblock_line_count_and_order()
    test_subline_chars_align_to_parent_column()
    test_real_pipeline_tool_labels()
    test_req_separator_unchanged()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_msgs_blocks_workflow()
