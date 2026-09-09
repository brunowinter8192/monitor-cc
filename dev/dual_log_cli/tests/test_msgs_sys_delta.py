"""
Regression suite for `duallog msgs`' sys/tool delta lines (src/dual_log_cli/timeline.py's
`_sys_lines`/`_tool_lines`/`request_boundaries`/`request_markers`, rendered by
src/dual_log_cli/render.py's `_req_delta_lines`). Name-based tool removal/rename coverage lives in
test_tool_name_comparison.py — this file's tool fixtures never shift a tool's index.

Covers: the family's first request lists every system block and every tool, no tag; a later
request lists only what its `system_delta`/`tools_delta` names, tagged `changed` for an index that
existed before and `new` for one beyond the previous request's count; a request whose only delta
is the excluded billing header (system index 0) prints no sys/tool lines at all; a re-fire group
shows the OWNER boundary's lines only; and an untouched separator (no `boundaries`, or a marker
with no delta) stays byte-identical to the pre-feature separator.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file
(`forwarded_delta` entries), so this suite depends only on that fixture and the code under test —
no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_sys_delta.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_boundaries import request_boundaries
from src.dual_log_cli.timeline_markers import request_markers

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


# One forwarded_delta line as addon.py's dual-log writer would shape it
def _delta_entry(flow_id: str, timestamp: str, counts: dict, is_first: bool,
                  system_delta: dict = None, tools_delta: dict = None, messages: int = None) -> dict:
    return {
        "type": "forwarded_delta",
        "flow_id": flow_id,
        "timestamp": timestamp,
        "model": "claude-sonnet-5",
        "is_first": is_first,
        "counts": {**counts, "messages": messages if messages is not None else counts.get("messages", 0)},
        "system_delta": system_delta or {},
        "tools_delta": tools_delta or {},
        "messages_delta": {},
    }


def _sys_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _tool(name: str, extra: str = "") -> dict:
    return {"name": name, "description": extra or f"{name} tool", "input_schema": {"type": "object"}}


# Writes entries to a temp _forwarded.jsonl and runs the real request_boundaries over it
def _boundaries(entries: list) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        path = Path(fh.name)
    try:
        return request_boundaries(path, "sonnet")
    finally:
        path.unlink()


# The family's first request: every system block and every tool listed, no tag at all — including
# the billing header (system index 0), which is excluded only on LATER requests.
def test_first_request_lists_everything_no_tag() -> None:
    entries = [_delta_entry(
        "f0", "2026-09-03T10:00:00Z", {"system": 4, "tools": 2}, True,
        system_delta={"0": _sys_block("x" * 81), "1": _sys_block("y"), "2": _sys_block("z" * 21829), "3": _sys_block("w")},
        tools_delta={"0": _tool("Bash"), "1": _tool("Edit")},
        messages=2,
    )]
    boundaries = _boundaries(entries)
    check("one boundary parsed", len(boundaries) == 1, boundaries)
    sys_lines = boundaries[0]["sys_lines"]
    tool_lines = boundaries[0]["tool_lines"]
    check("first request keeps sys[0] (billing header)", sys_lines[0]["label"] == "sys[0]", sys_lines)
    check("first request lists all 4 sys blocks", [l["label"] for l in sys_lines] == ["sys[0]", "sys[1]", "sys[2]", "sys[3]"], sys_lines)
    check("first request lists all 2 tools", [l["label"] for l in tool_lines] == ["tool[Bash]", "tool[Edit]"], tool_lines)
    check("first request carries no tag anywhere", all(l["tag"] is None for l in sys_lines + tool_lines), sys_lines + tool_lines)
    check("sys[0] chars is the text length", sys_lines[0]["chars"] == 81, sys_lines[0])
    check("sys[2] chars is the text length", sys_lines[2]["chars"] == 21829, sys_lines[2])
    check("tool chars is len(json.dumps(tool))", tool_lines[0]["chars"] == len(json.dumps(_tool("Bash"))), tool_lines[0])


# A later request: system index 0 is excluded even though it is present in system_delta (it
# changes on every request by construction and never invalidates the cache); an index seen before
# whose CONTENT actually differs is tagged "changed", an index never seen before is tagged "new",
# and an index seen before whose content is IDENTICAL (Edit here — carried in the delta but never
# actually touched, the write-side artifact this fix targets) is dropped, not tagged, not shown.
def test_later_request_excludes_billing_header_and_tags_changed_new() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 4, "tools": 2}, True,
                     system_delta={"0": _sys_block("a"), "1": _sys_block("b"), "2": _sys_block("c"), "3": _sys_block("d")},
                     tools_delta={"0": _tool("Bash"), "1": _tool("Edit")}, messages=2),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 5, "tools": 3}, False,
                     system_delta={"0": _sys_block("a2"), "1": _sys_block("b2"), "4": _sys_block("new-sys")},
                     tools_delta={"0": _tool("Bash", "v2"), "1": _tool("Edit"), "2": _tool("Grep")}, messages=5),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    labels = [l["label"] for l in second["sys_lines"]]
    check("system index 0 dropped on the later request", "sys[0]" not in labels, labels)
    check("sys[1] (content differs: 'b' vs 'b2') present and changed",
          any(l["label"] == "sys[1]" and l["tag"] == "changed" for l in second["sys_lines"]), second["sys_lines"])
    check("sys[4] (index never seen before) present and new",
          any(l["label"] == "sys[4]" and l["tag"] == "new" for l in second["sys_lines"]), second["sys_lines"])
    tool_labels = {l["label"]: l["tag"] for l in second["tool_lines"]}
    check("tool[Bash] (content genuinely differs) changed", tool_labels.get("tool[Bash]") == "changed", tool_labels)
    check("tool[Grep] (index never seen before) new", tool_labels.get("tool[Grep]") == "new", tool_labels)
    check("tool[Edit] (index seen before, IDENTICAL content) dropped entirely, not just untagged",
          "tool[Edit]" not in tool_labels, tool_labels)


# A request whose delta is ONLY the billing header prints no sys/tool line at all — the common
# case, since the header changes on every request. tools=1 (not 0) throughout — a zero-tool entry
# is the UNRELATED sidecar shape `timeline._is_sidecar` excludes entirely (see
# test_sidecar_exclusion.py), which would swallow both boundaries here and defeat this fixture.
def test_billing_header_only_delta_yields_no_lines() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 2, "tools": 1}, True,
                     system_delta={"0": _sys_block("a"), "1": _sys_block("b")}, messages=1),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 2, "tools": 1}, False,
                     system_delta={"0": _sys_block("a2")}, messages=3),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    check("no sys lines when only the billing header changed", second["sys_lines"] == [], second["sys_lines"])
    check("no tool lines when tools_delta is empty", second["tool_lines"] == [], second["tool_lines"])


# render_msgs: a marker with no sys/tool lines prints the plain separator untouched (byte-
# identical to the pre-feature output); a marker WITH lines prints them directly under the
# separator, before the first msg line, in the block sub-line's indent/column layout.
def test_render_msgs_prints_delta_lines_under_separator() -> None:
    marker_boundary = {
        "start_index": 0, "message_count": 1, "timestamp": "2026-09-03T10:00:00Z",
        "flow_id": "f0", "restart": False,
        "sys_lines": [{"label": "sys[0]", "chars": 81, "tag": None}, {"label": "sys[2]", "chars": 21829, "tag": None}],
        "tool_lines": [{"label": "tool[Bash]", "chars": 517, "tag": None}],
    }
    data = {
        "boundaries": [marker_boundary],
        "turns": [{"index": 0, "role": "user", "type": "text", "chars": 4,
                   "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]}],
    }
    got = render_msgs(data, 0, 0)
    lines = got.rstrip("\n").split("\n")
    check("separator first", lines[0] == f"── REQ 1  {_local_clock('2026-09-03T10:00:00Z')} ──", lines[0])
    check("sys[0] line right after separator", lines[1].strip().startswith("sys[0]"), lines[1])
    check("sys[2] line next", lines[2].strip().startswith("sys[2]"), lines[2])
    check("tool[Bash] line next", lines[3].strip().startswith("tool[Bash]"), lines[3])
    check("msg line comes after all delta lines", lines[4].startswith("[  0]"), lines[4])
    check("delta line chars right-aligned to the parent's chars column",
          len(lines[1]) == len(lines[4]) and len(lines[2]) == len(lines[4]) + 1,
          (lines[1], lines[2], lines[4]))

    # A marker with no delta lines at all reproduces the exact pre-feature separator+msg pair.
    plain_boundary = dict(marker_boundary, sys_lines=[], tool_lines=[])
    data_plain = {"boundaries": [plain_boundary], "turns": data["turns"]}
    got_plain = render_msgs(data_plain, 0, 0)
    check("no delta -> plain separator immediately followed by the msg line",
          got_plain == f"── REQ 1  {_local_clock('2026-09-03T10:00:00Z')} ──\n[  0] user  text                    4c\n", got_plain)


# A re-fire group (two boundaries opening the same msg index) shows the OWNER boundary's sys/tool
# lines only — the same one whose timestamp the separator already carries — never the earlier
# member's.
def test_refire_group_shows_owner_lines_only() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 3, "tools": 1}, True,
                     system_delta={"0": _sys_block("a"), "1": _sys_block("b"), "2": _sys_block("c")},
                     tools_delta={"0": _tool("Bash")}, messages=2),
        # re-fire: same start_index (0 messages added), OWNS index 0 because it is last in the group
        _delta_entry("f1", "2026-09-03T10:00:02Z", {"system": 3, "tools": 1}, False,
                     system_delta={"1": _sys_block("b2")}, messages=0),
    ]
    boundaries = _boundaries(entries)
    check("second boundary is a restart (message count regressed)", boundaries[1]["restart"] is True, boundaries[1])
    markers = request_markers(boundaries)
    owner_marker = markers[0]
    check("owner marker is the re-fire (later position), 1 re-fire counted", owner_marker["refires"] == 1, owner_marker)
    check("owner marker's sys_lines are the re-fire's own, not the first request's 3 blocks",
          [l["label"] for l in owner_marker["sys_lines"]] == ["sys[1]"], owner_marker["sys_lines"])


# ORCHESTRATOR

def test_msgs_sys_delta_workflow() -> None:
    test_first_request_lists_everything_no_tag()
    test_later_request_excludes_billing_header_and_tags_changed_new()
    test_billing_header_only_delta_yields_no_lines()
    test_render_msgs_prints_delta_lines_under_separator()
    test_refire_group_shows_owner_lines_only()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_msgs_sys_delta_workflow()
