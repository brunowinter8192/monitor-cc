"""
Regression suite for `duallog msgs --req F [T]` (src/dual_log_cli/timeline.py's
`request_msg_range`/`resolve_req_range`) — translating a REQ number range into the msg-index
range `render_msgs` already knows how to handle, the way the FROM/TO positionals do today.

Covers: a single REQ number resolves to exactly its own group's msg range; a REQ range (F T)
spans from F's start to T's end; the LAST REQ of a session runs to the session's last msg index
(not to whatever its own group's natural end would otherwise be); an unknown REQ number raises
UnknownRequestNumberError; a REQ number that TWO different msg indices both carry — proven
possible even without a restart, via a trailing re-fire that adds no new msg — raises
AmbiguousRequestNumberError rather than silently picking either.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file,
matching this area's existing style (`test_msgs_sys_delta.py`) — no dual-log directory or
MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_req_range.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.timeline_boundaries import request_boundaries
from src.dual_log_cli.timeline_markers import (
    AmbiguousRequestNumberError,
    UnknownRequestNumberError,
    request_markers,
    request_msg_range,
    resolve_req_range,
)

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


# One forwarded_delta line as addon.py's dual-log writer would shape it
def _delta_entry(flow_id: str, timestamp: str, messages: int, is_first: bool = False) -> dict:
    return {
        "type": "forwarded_delta",
        "flow_id": flow_id,
        "timestamp": timestamp,
        "model": "claude-sonnet-5",
        "is_first": is_first,
        "counts": {"system": 1, "tools": 1, "messages": messages},
        "system_delta": {},
        "tools_delta": {},
        "messages_delta": {},
    }


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


# Three ordinary, non-overlapping request groups: REQ 1 opens msg 0 (2 msgs), REQ 2 opens msg 2
# (3 msgs), REQ 3 opens msg 5 (4 msgs) — session has 9 msgs total, last index 8.
def _three_group_boundaries() -> list:
    return _boundaries([
        _delta_entry("f0", "2026-09-04T00:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T00:00:01Z", 5),
        _delta_entry("f2", "2026-09-04T00:00:02Z", 9),
    ])


# A single REQ number resolves to exactly its own group's msg range.
def test_single_req_resolves_own_group() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 2, 2, last_msg_index=8)
    check("REQ 2 starts at msg 2", start == 2, start)
    check("REQ 2 ends right before REQ 3's start (msg 4)", end == 4, end)


# A REQ range (F T) spans from F's own start to T's own end.
def test_range_spans_from_f_start_to_t_end() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 1, 2, last_msg_index=8)
    check("REQ 1..2 starts at REQ 1's own start (msg 0)", start == 0, start)
    check("REQ 1..2 ends right before REQ 3's start (msg 4)", end == 4, end)


# The LAST REQ of a session runs all the way to the session's last msg index, not to a
# next-marker boundary that does not exist.
def test_last_req_runs_to_session_end() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 3, 3, last_msg_index=8)
    check("REQ 3 (last) starts at msg 5", start == 5, start)
    check("REQ 3 (last) ends at the session's last msg index (8)", end == 8, end)


# An unknown REQ number raises UnknownRequestNumberError rather than an empty listing.
def test_unknown_req_number_raises() -> None:
    raised = False
    try:
        resolve_req_range(_three_group_boundaries(), 99, 99, last_msg_index=8)
    except UnknownRequestNumberError as exc:
        raised = True
        check("error names the unknown number", "99" in str(exc), str(exc))
    check("unknown REQ number raises UnknownRequestNumberError", raised)


# A REQ number that TWO different msg indices both carry raises AmbiguousRequestNumberError.
# Reproduced WITHOUT a restart: a re-fire that adds no NEW msg (message_count does not exceed its
# own start_index) opens its own group at a start_index no earlier group used, but the running
# REQ-number counter does not advance for a non-adding boundary — so that group's owner is
# assigned the SAME number as the group before it.
def test_duplicate_req_number_raises() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T00:00:00Z", 2, is_first=True),  # opens msg 0, adds, REQ 1
        _delta_entry("f1", "2026-09-04T00:00:01Z", 2),                 # start=2, count=2: re-fire, no add, stays REQ 1
    ])
    numbers = set()
    markers = request_markers(boundaries)
    for marker in markers.values():
        numbers.add(marker["number"])
    check("fixture actually produces two groups sharing one REQ number",
          len(markers) == 2 and len(numbers) == 1, (markers, numbers))

    raised = False
    try:
        request_msg_range(markers, 1, 1, last_msg_index=5)
    except AmbiguousRequestNumberError as exc:
        raised = True
        check("error names the ambiguous number and both msg indices",
              "1" in str(exc) and "0" in str(exc) and "2" in str(exc), str(exc))
    check("duplicate REQ number raises AmbiguousRequestNumberError", raised)


# ORCHESTRATOR

def test_msgs_req_range_workflow() -> None:
    test_single_req_resolves_own_group()
    test_range_spans_from_f_start_to_t_end()
    test_last_req_runs_to_session_end()
    test_unknown_req_number_raises()
    test_duplicate_req_number_raises()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_msgs_req_range_workflow()
