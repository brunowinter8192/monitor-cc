"""
Regression suite for `duallog msgs`' NAME-based tool comparison (src/dual_log_cli/timeline.py's
`_tool_lines`), rendered by src/dual_log_cli/render.py's `_req_delta_lines`.

Covers: a tool that shifts INDEX with byte-identical content prints nothing at all (the exact
false-positive `skill-help_1788343931` REQ 196 showed under index-based comparison: removing one
tool renumbers every tool after it, and each renumbered slot used to print `changed`); a tool
removed from the list (present before, absent now) prints `tool[Name] removed` with no chars
column; a tool whose OWN content changes at its new position still prints `changed`; a brand new
tool name prints `new`; and the exact skill-help shape (6 tools -> 5, one removed from the middle)
end to end via `request_boundaries` reproduces `tool[SendFeedback] removed` and nothing else.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file, so
this suite depends only on that fixture and the code under test — no dual-log directory or
MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_tool_name_comparison.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_boundaries import request_boundaries

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


def _delta_entry(flow_id: str, timestamp: str, counts: dict, is_first: bool,
                  tools_delta: dict = None, messages: int = None) -> dict:
    return {
        "type": "forwarded_delta",
        "flow_id": flow_id,
        "timestamp": timestamp,
        "model": "claude-sonnet-5",
        "is_first": is_first,
        "counts": {**counts, "messages": messages if messages is not None else counts.get("messages", 0)},
        "system_delta": {},
        "tools_delta": tools_delta or {},
        "messages_delta": {},
    }


def _tool(name: str, extra: str = "") -> dict:
    return {"name": name, "description": extra or f"{name} tool", "input_schema": {"type": "object"}}


def _boundaries(entries: list) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        path = Path(fh.name)
    try:
        return request_boundaries(path, "sonnet")
    finally:
        path.unlink()


# A tool removed from the middle of the list renumbers everything after it — the proxy's own
# per-POSITION delta includes every renumbered slot, but NONE of them actually changed content, so
# none should print a line; only the genuinely absent name gets `removed`, with no chars at all.
def test_removed_tool_named_not_its_shifted_neighbours() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 4}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Edit"), "2": _tool("Grep"), "3": _tool("Write")},
                     messages=2),
        # Grep removed: Write shifts from index 3 to index 2, byte-identical content
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 3}, False,
                     tools_delta={"2": _tool("Write")}, messages=5),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    check("exactly one tool line (the removal), not two (removal + shifted neighbour)",
          len(second["tool_lines"]) == 1, second["tool_lines"])
    check("tool[Write] does not appear at all — its content never moved",
          not any(l["label"] == "tool[Write]" for l in second["tool_lines"]), second["tool_lines"])
    removed = second["tool_lines"][0]
    check("tool[Grep] removed", removed["label"] == "tool[Grep]" and removed["tag"] == "removed", removed)
    check("a removed line carries no chars", removed["chars"] is None, removed)


# A tool whose OWN content changes (not just its position) still prints `changed`, even while other
# tools are also shifting around it in the same request.
def test_content_change_at_new_position_still_flagged() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 3}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Grep"), "2": _tool("Write")}, messages=2),
        # Bash removed; Grep shifts 1->0 unchanged; Write shifts 2->1 WITH a real content edit
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 2}, False,
                     tools_delta={"0": _tool("Grep"), "1": _tool("Write", "v2")}, messages=5),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    labels_tags = {l["label"]: l["tag"] for l in second["tool_lines"]}
    check("tool[Grep] silent — shifted, content unchanged", "tool[Grep]" not in labels_tags, labels_tags)
    check("tool[Write] changed — content genuinely differs at its new position",
          labels_tags.get("tool[Write]") == "changed", labels_tags)
    check("tool[Bash] removed", labels_tags.get("tool[Bash]") == "removed", labels_tags)


# A brand new tool name (never seen before) is tagged `new`, same as index-based comparison.
def test_brand_new_tool_name_is_new() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 1}, True,
                     tools_delta={"0": _tool("Bash")}, messages=2),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 2}, False,
                     tools_delta={"1": _tool("Grep")}, messages=5),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    check("tool[Grep] new, one line only", second["tool_lines"] == [{"label": "tool[Grep]", "chars": second["tool_lines"][0]["chars"], "tag": "new"}], second["tool_lines"])


# A name removed and later reintroduced (a different request re-adds a tool of the same name) is
# tagged `new` again — presence is judged against the IMMEDIATELY preceding request's active set,
# not the tool's own history.
def test_reintroduced_tool_is_new_again() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 2}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Grep")}, messages=2),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 1}, False,
                     tools_delta={}, messages=5),  # Grep removed (tools 2->1, no delta needed: index 1 just drops out of range)
        _delta_entry("f2", "2026-09-03T10:00:10Z", {"system": 1, "tools": 2}, False,
                     tools_delta={"1": _tool("Grep")}, messages=8),
    ]
    boundaries = _boundaries(entries)
    check("second request: Grep removed", boundaries[1]["tool_lines"] == [{"label": "tool[Grep]", "chars": None, "tag": "removed"}], boundaries[1]["tool_lines"])
    third = boundaries[2]["tool_lines"]
    check("third request: Grep is new again, not silently dropped as 'still absent'",
          len(third) == 1 and third[0]["label"] == "tool[Grep]" and third[0]["tag"] == "new", third)


# End-to-end reproduction of the real corpus case: skill-help_1788343931 REQ 196, 6 tools -> 5,
# SendFeedback removed from the middle, Skill and Write renumbered into its wake.
def test_skill_help_shape_end_to_end() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 6}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Edit"), "2": _tool("Read"),
                                  "3": _tool("SendFeedback"), "4": _tool("Skill"), "5": _tool("Write")},
                     messages=2),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 5}, False,
                     tools_delta={"3": _tool("Skill"), "4": _tool("Write")}, messages=587),
    ]
    boundaries = _boundaries(entries)
    second = boundaries[1]
    check("exactly one tool line", len(second["tool_lines"]) == 1, second["tool_lines"])
    check("tool[SendFeedback] removed, no chars",
          second["tool_lines"] == [{"label": "tool[SendFeedback]", "chars": None, "tag": "removed"}],
          second["tool_lines"])


# render.py's _req_delta_lines: a `chars: None` item ("removed") skips the numeric chars column
# entirely — never prints a size for content that no longer exists.
def test_render_removed_line_has_no_chars_column() -> None:
    marker_boundary = {
        "start_index": 0, "message_count": 1, "timestamp": "2026-09-03T10:00:00Z",
        "flow_id": "f0", "restart": False,
        "sys_lines": [],
        "tool_lines": [{"label": "tool[SendFeedback]", "chars": None, "tag": "removed"}],
    }
    data = {
        "boundaries": [marker_boundary],
        "turns": [{"index": 0, "role": "user", "type": "text", "chars": 4,
                   "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]}],
    }
    got = render_msgs(data, 0, 0)
    lines = got.rstrip("\n").split("\n")
    check("removed line present directly under the separator, label padded to the block label width",
          lines[1] == f"        {'tool[SendFeedback]':<24}  removed", lines[1])
    check("no digit-grouped chars figure or trailing 'c' anywhere on the removed line",
          "," not in lines[1] and not lines[1].rstrip().endswith("c"), lines[1])


# ORCHESTRATOR

def test_tool_name_comparison_workflow() -> None:
    test_removed_tool_named_not_its_shifted_neighbours()
    test_content_change_at_new_position_still_flagged()
    test_brand_new_tool_name_is_new()
    test_reintroduced_tool_is_new_again()
    test_skill_help_shape_end_to_end()
    test_render_removed_line_has_no_chars_column()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_tool_name_comparison_workflow()
