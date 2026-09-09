"""
Regression suite for `duallog msgs`' sys/tool strip-inject delta tail
(src/dual_log_cli/overlay.py's `build_sys_tool_overlay`, rendered by
src/dual_log_cli/render.py's `_req_delta_lines`/`_delta_line`). Sibling to test_msgs_sys_delta.py
(the wire-based label/chars/tag lines this feature enhances) and test_msgs_overlay.py (the
message-level strip/inject tail this feature mirrors for sys/tool lines).

Covers: an untouched sys/tool line stays byte-identical when a sys_tool_overlay is supplied but
carries nothing for that coordinate; a transformed system line switches its leading chars from the
wire size to the ORIGINAL size (looked up in `data["payload"]["system"]`) and appends the same
`_delta_tail` a msg/block line carries; a description-stripped tool line does the same, looked up
in `data["payload"]["tools"]` by name, with its tail's wire figure the MEASURED wire chars
(`item["chars"]`) rather than derived from the recorded stripped TEXT length — the two are NOT
commensurable for a tool (JSON-encoded chars vs. raw description characters), a corrected defect
this suite pins with a fixture where they deliberately disagree; system index 0 (the per-request
billing header) is left completely untouched — wire chars, no tail — since it changes every request
by construction, so the last request's own copy is not a valid "original" for it; a tool the proxy
stripped WHOLE (absent from the wire tools_delta entirely, hence no line today) is synthesized as
its own standalone line with full strip and wire 0, attached to the marker whose own flow_id the
overlay recorded; a whole-stripped tool whose name cannot be resolved in `orig_tools` is skipped
rather than guessed; and a default (missing) sys_tool_overlay argument renders exactly the
pre-feature output.

All fixtures are hand-built dicts shaped like `render_msgs` expects, with `data["payload"]` added
for the original-size lookups this feature reads — no dual-log directory or MONITOR_CC_ROOT
required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_sys_tool_overlay.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.timeline_boundaries import _system_block_chars, _tool_chars

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


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


# An untouched system line stays exactly as the pre-feature output when the overlay carries
# nothing for that coordinate — even with a payload and a (non-matching) sys_tool_overlay present.
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


# A transformed system line: leading chars becomes the ORIGINAL size (907, from data["payload"]),
# not the wire size (39307, the item's own "chars") — reproducing the real corpus example
# (opus_monitor_cc_1788464543 sys[2]: stripped 907, injected 39307, wire 39307).
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


# A description-stripped tool line: leading chars becomes the tool's FULL original size (name +
# full description, JSON-encoded), the tail's WIRE figure is the MEASURED wire chars
# (`item["chars"]`, exactly what `_tool_lines` computed before this feature) — never derived from
# the recorded stripped TEXT length, which is deliberately set here to a DIFFERENT number (raw
# description characters removed vs. the tool's JSON-encoded size delta are not the same unit,
# e.g. escaping) to prove the tail does not silently fall back to the wrong arithmetic. Reproduces
# the corrected defect: `tool[Bash]` on `opus_monitor_cc_1788464543`'s REQ 1 must show wire `517c`
# (the measured figure `_tool_lines` always computed), not a value derived from the 1,356-char raw
# stripped description text.
def test_desc_stripped_tool_uses_measured_wire_not_derived_from_raw_text() -> None:
    bash_full = _tool("Bash", 480)
    original_chars = _tool_chars(bash_full)
    measured_wire = 435  # deliberately NOT original_chars - 50 (the raw stripped-text length below)
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  tool_lines=[{"label": "tool[Bash]", "chars": measured_wire, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": [bash_full]},
    }
    # Raw stripped description text is 50 characters — if the tail derived S from summing this
    # (the pre-correction bug), the displayed wire would be original_chars - 50, not measured_wire.
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


# System index 0 (the billing header) changes on EVERY request by construction, so it is left
# completely untouched — wire chars, no tail — even when the overlay carries data for it (which
# would be wrong to apply: that data reflects THIS request's own strip, but the last request's
# system[0] is a DIFFERENT billing header entirely, not a valid "original" for this one).
def test_sys_billing_header_untouched() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0",
                                  sys_lines=[{"label": "sys[0]", "chars": 132, "tag": None}])],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [{"type": "text", "text": "x" * 174}], "tools": []},  # last request's OWN sys[0]
    }
    sys_overlay = {"0": {"stripped": ["s" * 999], "injected": [], "req": 1, "flow_id": "f0"}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=(sys_overlay, {}))
    lines = got.rstrip("\n").split("\n")
    check("sys[0] keeps its OWN wire chars (132c), not the last request's system[0] (174c)",
          lines[1].rstrip().endswith("132c"), lines[1])
    check("sys[0] carries no tail even though the overlay has data for it", "→" not in lines[1], lines[1])


# A tool the proxy stripped WHOLE never appears in the wire tools_delta (absent both before and
# after), so `marker["tool_lines"]` has no entry for it at all today — the overlay synthesizes a
# standalone line instead, full strip, wire 0.
def test_whole_stripped_tool_synthesized_as_standalone_line() -> None:
    agent_tool = _tool("Agent", 3000)
    original_chars = _tool_chars(agent_tool)
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],  # no wire tool_lines at all
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


# A whole-stripped tool recorded under a DIFFERENT flow_id than the current marker is not shown
# here at all — it belongs under its own marker, never guessed onto this one.
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


# A whole-stripped tool whose name cannot be resolved in `orig_tools` (e.g. a stale/renamed entry)
# is skipped silently — showing nothing is preferred over guessing a size.
def test_whole_stripped_tool_unresolvable_name_skipped() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
        "payload": {"system": [], "tools": []},  # "GhostTool" absent
    }
    tools_overlay = {"GhostTool": {"stripped": [], "injected": [], "req": 1, "flow_id": "f0", "whole": True}}
    got = render_msgs(data, 0, 0, sys_tool_overlay=({}, tools_overlay))
    check("unresolvable whole-strip tool produces no line", "GhostTool" not in got, got)


# A default (missing) sys_tool_overlay argument renders exactly the pre-feature output — additive
# parameter, matching test_msgs_overlay.py's own `test_default_overlay_unchanged` precedent.
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


# ORCHESTRATOR

def test_msgs_sys_tool_overlay_workflow() -> None:
    test_untouched_sys_line_unchanged()
    test_transformed_sys_line_shows_original_chars_and_tail()
    test_desc_stripped_tool_uses_measured_wire_not_derived_from_raw_text()
    test_sys_billing_header_untouched()
    test_whole_stripped_tool_synthesized_as_standalone_line()
    test_whole_stripped_tool_scoped_to_owning_flow()
    test_whole_stripped_tool_unresolvable_name_skipped()
    test_default_sys_tool_overlay_unchanged()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_msgs_sys_tool_overlay_workflow()
