# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_boundaries import request_boundaries
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_removed_tool_named_not_its_shifted_neighbours',
    'test_content_change_at_new_position_still_flagged',
    'test_brand_new_tool_name_is_new',
    'test_reintroduced_tool_is_new_again',
    'test_skill_help_shape_end_to_end',
    'test_render_removed_line_has_no_chars_column',
]

# ORCHESTRATOR

def test_tool_name_comparison_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_tool_name_comparison')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

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

def test_removed_tool_named_not_its_shifted_neighbours() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 4}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Edit"), "2": _tool("Grep"), "3": _tool("Write")},
                     messages=2),
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

def test_content_change_at_new_position_still_flagged() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 3}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Grep"), "2": _tool("Write")}, messages=2),
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

def test_reintroduced_tool_is_new_again() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", {"system": 1, "tools": 2}, True,
                     tools_delta={"0": _tool("Bash"), "1": _tool("Grep")}, messages=2),
        _delta_entry("f1", "2026-09-03T10:00:05Z", {"system": 1, "tools": 1}, False,
                     tools_delta={}, messages=5),
        _delta_entry("f2", "2026-09-03T10:00:10Z", {"system": 1, "tools": 2}, False,
                     tools_delta={"1": _tool("Grep")}, messages=8),
    ]
    boundaries = _boundaries(entries)
    check("second request: Grep removed", boundaries[1]["tool_lines"] == [{"label": "tool[Grep]", "chars": None, "tag": "removed"}], boundaries[1]["tool_lines"])
    third = boundaries[2]["tool_lines"]
    check("third request: Grep is new again, not silently dropped as 'still absent'",
          len(third) == 1 and third[0]["label"] == "tool[Grep]" and third[0]["tag"] == "new", third)

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

if __name__ == '__main__':
    sys.exit(test_tool_name_comparison_workflow())
