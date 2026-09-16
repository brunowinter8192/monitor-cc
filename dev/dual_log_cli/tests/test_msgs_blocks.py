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

def _local_clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")

def _msg(index: int, role: str, chars: int, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": chars, "blocks": blocks}

def _block(type_: str, chars: int, label: str = None) -> dict:
    return {"label": label or type_, "type": type_, "chars": chars, "sig_chars": 0, "preview": ""}

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
    got = render_msgs(data, 0, 1)
    check("multiblock matches spec sample byte-for-byte", got == expected, f"got:\n{got!r}\nwant:\n{expected!r}")

def test_singleblock_unchanged_format() -> None:
    data = {
        "boundaries": [],
        "turns": [_msg(5, "user", 454, [_block("text", 454)])],
    }
    expected = "[  5] user  text                  454c\n"
    got = render_msgs(data, 0, 0)
    check("single-block msg is exactly one line", got == expected, f"got {got!r}")
    check("single-block msg has no sub-line indent", "\n        " not in got, got)

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

    payload["messages"][1]["content"].append({"type": "text", "text": "note"})
    turns = build_turns(payload)
    data = {"boundaries": [], "turns": turns}
    got = render_msgs(data, 0, 1)
    check("multi-block is_error tool_result sub-line renders tool_result!err", "tool_result!err" in got, got)

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
