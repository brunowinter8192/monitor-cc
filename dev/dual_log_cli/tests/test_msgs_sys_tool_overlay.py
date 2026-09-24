# INFRASTRUCTURE
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_boundaries import _system_block_chars, _tool_chars
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_untouched_sys_line_unchanged',
    'test_transformed_sys_line_shows_original_chars_and_tail',
    'test_desc_stripped_tool_uses_measured_wire_not_derived_from_raw_text',
    'test_sys_billing_header_untouched',
    'test_whole_stripped_tool_synthesized_as_standalone_line',
    'test_whole_stripped_tool_scoped_to_owning_flow',
    'test_whole_stripped_tool_unresolvable_name_skipped',
    'test_default_sys_tool_overlay_unchanged',
]

# ORCHESTRATOR

def test_msgs_sys_tool_overlay_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_msgs_sys_tool_overlay')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _msg(index: int, role: str, chars: int, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": chars, "blocks": blocks}

def _block(type_: str, chars: int, label: str = None) -> dict:
    return {"label": label or type_, "type": type_, "chars": chars, "sig_chars": 0, "preview": ""}

def _boundary(start_index: int, message_count: int, timestamp: str, flow_id: str,
             sys_lines: list = None, tool_lines: list = None) -> dict:
    return {
        "start_index": start_index, "message_count": message_count, "timestamp": timestamp,
        "flow_id": flow_id, "restart": False,
        "sys_lines": sys_lines or [], "tool_lines": tool_lines or [],
    }

def _tool(name: str, desc_len: int) -> dict:
    return {"name": name, "description": "x" * desc_len, "input_schema": {"type": "object"}}

def test_untouched_sys_line_unchanged() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  sys_lines=[{"label": "sys[1]", "chars": 50, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [{"type": "text", "text": "x" * 50}], "tools": []},
    }
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, {}))
    lines = got.rstrip("\n").split("\n")
    check("sys[1] line present", lines[1].strip().startswith("sys[1]"), lines[1])
    check("no delta tail appended", "→" not in lines[1], lines[1])
    check("chars value is 50 either way (original == wire, untouched)", lines[1].rstrip().endswith("50c"), lines[1])

def test_transformed_sys_line_shows_original_chars_and_tail() -> None:
    orig_text = "o" * 907
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  sys_lines=[{"label": "sys[2]", "chars": 39307, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [{}, {}, {"type": "text", "text": orig_text}], "tools": []},
    }
    sys_overlay = {"2": {"stripped": ["s" * 907], "injected": ["i" * 39307], "req": 1, "flow_id": "f0"}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=(sys_overlay, {}))
    lines = got.rstrip("\n").split("\n")
    check("leading chars is the ORIGINAL 907c, not the wire 39307c", "907c" in lines[1] and "39307c" not in lines[1].split("c")[0], lines[1])
    check("tail matches −907 +39,307 → 39,307c", lines[1].rstrip().endswith("−907 +39,307 → 39,307c"), lines[1])

def test_desc_stripped_tool_uses_measured_wire_not_derived_from_raw_text() -> None:
    bash_full = _tool("Bash", 480)
    original_chars = _tool_chars(bash_full)
    measured_wire = 435
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  tool_lines=[{"label": "tool[Bash]", "chars": measured_wire, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": [bash_full]},
    }
    tools_overlay = {"Bash": {"stripped": ["x" * 50], "injected": [], "req": 1, "flow_id": "f0", "whole": False}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, tools_overlay))
    lines = got.rstrip("\n").split("\n")
    check("leading chars is the FULL original size, not the wire size",
          f"{original_chars:,}c" in lines[1], lines[1])
    derived_stripped = original_chars - measured_wire
    check(f"tail shows the MEASURED wire ({measured_wire}c), not original_chars-50 ({original_chars - 50})",
          lines[1].rstrip().endswith(f"−{derived_stripped:,} +0 → {measured_wire:,}c"), lines[1])
    check("the buggy derived-from-raw-text wire value does NOT appear",
          f"→ {original_chars - 50:,}c" not in lines[1], lines[1])

def test_sys_billing_header_untouched() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  sys_lines=[{"label": "sys[0]", "chars": 132, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [{"type": "text", "text": "x" * 174}], "tools": []},
    }
    sys_overlay = {"0": {"stripped": ["s" * 999], "injected": [], "req": 1, "flow_id": "f0"}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=(sys_overlay, {}))
    lines = got.rstrip("\n").split("\n")
    check("sys[0] keeps its OWN wire chars (132c), not the last request's system[0] (174c)",
          lines[1].rstrip().endswith("132c"), lines[1])
    check("sys[0] carries no tail even though the overlay has data for it", "→" not in lines[1], lines[1])

def test_whole_stripped_tool_synthesized_as_standalone_line() -> None:
    agent_tool = _tool("Agent", 3000)
    original_chars = _tool_chars(agent_tool)
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": [agent_tool]},
    }
    tools_overlay = {"Agent": {"stripped": [], "injected": [], "req": 1, "flow_id": "f0", "whole": True}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, tools_overlay))
    lines = got.rstrip("\n").split("\n")
    tool_line = next(l for l in lines if "tool[Agent]" in l)
    check("synthesized line carries the tool's full original chars",
          f"{original_chars:,}c" in tool_line, tool_line)
    check("synthesized line shows full strip and wire 0",
          tool_line.rstrip().endswith(f"−{original_chars:,} +0 → 0c"), tool_line)
    check("no tag on a synthesized whole-strip line", "changed" not in tool_line and "new" not in tool_line, tool_line)

def test_whole_stripped_tool_scoped_to_owning_flow() -> None:
    agent_tool = _tool("Agent", 3000)
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": [agent_tool]},
    }
    tools_overlay = {"Agent": {"stripped": [], "injected": [], "req": 7, "flow_id": "OTHER-FLOW", "whole": True}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, tools_overlay))
    check("no tool[Agent] line under a marker that does not own it", "tool[Agent]" not in got, got)

def test_whole_stripped_tool_unresolvable_name_skipped() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": []},
    }
    tools_overlay = {"GhostTool": {"stripped": [], "injected": [], "req": 1, "flow_id": "f0", "whole": True}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, tools_overlay))
    check("unresolvable whole-strip tool produces no line", "GhostTool" not in got, got)

def test_default_sys_tool_overlay_unchanged() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  sys_lines=[{"label": "sys[1]", "chars": 50, "tag": None}],
                                  tool_lines=[{"label": "tool[Bash]", "chars": 517, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got_with_overlay = render_msgs(data, 0, 0, sys_tool_overlay=({}, {}))
    got_default = render_msgs(data, 0, 0)
    check("no sys_tool_overlay argument -> byte-identical to an explicit empty one",
          got_default == got_with_overlay, (got_default, got_with_overlay))
    check("delta lines still print under the separator, no tail/chars-source change with empty overlays",
          "sys[1]" in got_default and "tool[Bash]" in got_default and "→" not in got_default, got_default)

if __name__ == '__main__':
    sys.exit(test_msgs_sys_tool_overlay_workflow())
