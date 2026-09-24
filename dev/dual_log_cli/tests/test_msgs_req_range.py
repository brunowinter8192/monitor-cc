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
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_single_req_resolves_own_group',
    'test_range_spans_from_f_start_to_t_end',
    'test_last_req_runs_to_session_end',
    'test_unknown_req_number_raises',
    'test_duplicate_req_number_raises',
]

# ORCHESTRATOR

def test_msgs_req_range_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_msgs_req_range')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

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

def _boundaries(entries: list) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        path = Path(fh.name)
    try:
        return request_boundaries(path, "sonnet")
    finally:
        path.unlink()

def _three_group_boundaries() -> list:
    return _boundaries([
        _delta_entry("f0", "2026-09-04T00:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T00:00:01Z", 5),
        _delta_entry("f2", "2026-09-04T00:00:02Z", 9),
    ])

def test_single_req_resolves_own_group() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 2, 2, last_msg_index=8)
    check("REQ 2 starts at msg 2", start == 2, start)
    check("REQ 2 ends right before REQ 3's start (msg 4)", end == 4, end)

def test_range_spans_from_f_start_to_t_end() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 1, 2, last_msg_index=8)
    check("REQ 1..2 starts at REQ 1's own start (msg 0)", start == 0, start)
    check("REQ 1..2 ends right before REQ 3's start (msg 4)", end == 4, end)

def test_last_req_runs_to_session_end() -> None:
    start, end = resolve_req_range(_three_group_boundaries(), 3, 3, last_msg_index=8)
    check("REQ 3 (last) starts at msg 5", start == 5, start)
    check("REQ 3 (last) ends at the session's last msg index (8)", end == 8, end)

def test_unknown_req_number_raises() -> None:
    raised = False
    try:
        resolve_req_range(_three_group_boundaries(), 99, 99, last_msg_index=8)
    except UnknownRequestNumberError as exc:
        raised = True
        check("error names the unknown number", "99" in str(exc), str(exc))
    check("unknown REQ number raises UnknownRequestNumberError", raised)

def test_duplicate_req_number_raises() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T00:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T00:00:01Z", 2),
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

if __name__ == '__main__':
    sys.exit(test_msgs_req_range_workflow())
