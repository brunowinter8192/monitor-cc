# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_reqs import render_reqs
from src.dual_log_cli.timeline_boundaries import request_boundaries
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_gap_one_qualifying_pair',
    'test_gap_two_adjacent_gaps_sharing_req',
    'test_gap_no_qualifying_gap',
    'test_gap_threshold_boundary',
    'test_gap_cross_turn_dropped',
    'test_gap_within_turn_kept_beside_cross_turn',
    'test_gap_no_turn_never_qualifies',
]

# ORCHESTRATOR

def test_reqs_gap_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_reqs_gap')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _local_clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")

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

def _session(stem: str) -> dict:
    return {"stem": stem}

def _turns(openers: list) -> dict:
    rows = [{"index": i, "role": "user" if i in openers else "assistant", "type": "text", "chars": 10,
             "blocks": [{"label": "text", "type": "text", "chars": 10, "sig_chars": 0, "preview": "p"}]}
            for i in range(max(openers) + 1)]
    return {"s": rows}

def _req_lines(got: str) -> list:
    return [l for l in got.split("\n") if l.startswith("REQ")]

def test_gap_one_qualifying_pair() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),
        _delta_entry("f2", "2026-09-04T11:35:00Z", 9),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90, turns_by_stem=_turns([0]))
    expected = (
        "session s\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR ?  CC ?\n"
        f"REQ 2   {_local_clock('2026-09-04T11:30:00Z')}  CR ?  CC ?\n"
    )
    check("only the qualifying pair's REQs print, no tail, REQ 3 omitted",
          _req_lines(got) == _req_lines(expected) and got.count("REQ") == 2, got)

def test_gap_two_adjacent_gaps_sharing_req() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),
        _delta_entry("f2", "2026-09-04T13:30:00Z", 9),
        _delta_entry("f3", "2026-09-04T13:35:00Z", 12),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90, turns_by_stem=_turns([0]))
    lines = [l for l in got.split("\n") if l.startswith("REQ")]
    check("REQ 2 appears exactly once (bracketing both qualifying gaps)",
          sum(1 for l in lines if l.startswith("REQ 2 ")) == 1, lines)
    check("exactly 3 REQ lines, REQ 4 omitted (its own gap does not qualify)", len(lines) == 3, lines)

def test_gap_no_qualifying_gap() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90, turns_by_stem=_turns([0]))
    check("no qualifying gap -> the no-REQ line", got == "no REQs to show\n", got)

def test_gap_threshold_boundary() -> None:
    exact_boundary = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),
    ])
    just_under = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:29:59Z", 5),
    ])
    session = _session("s")
    got_exact = render_reqs([(session, exact_boundary)], gap_minutes=90, turns_by_stem=_turns([0]))
    got_under = render_reqs([(session, just_under)], gap_minutes=90, turns_by_stem=_turns([0]))
    check("a gap of exactly the threshold QUALIFIES (>=)",
          got_exact.count("REQ") == 2, got_exact)
    check("one second short of the threshold does NOT qualify",
          got_under == "no REQs to show\n", got_under)

def test_gap_cross_turn_dropped() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:18:00Z", 9),
    ])
    got = render_reqs([(_session("s"), boundaries)], gap_minutes=2, turns_by_stem=_turns([0, 7]))
    check("a gap between the last REQ of turn 1 and the first of turn 2 is dropped",
          got == "no REQs to show\n", got)

def test_gap_within_turn_kept_beside_cross_turn() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:30:00Z", 9),
        _delta_entry("f2", "2026-09-04T11:10:00Z", 11),
    ])
    got = render_reqs([(_session("s"), boundaries)], gap_minutes=2, turns_by_stem=_turns([0, 7]))
    lines = _req_lines(got)
    check("only the within-turn-2 pair prints, REQ 1 (cross-turn neighbor) is dropped",
          len(lines) == 2 and lines[0].startswith("REQ 2 ") and lines[1].startswith("REQ 3 "), lines)
    check("turn 1 separator is not printed, turn 2 separator is",
          "── turn 1" not in got and "── turn 2" in got, got)

def test_gap_no_turn_never_qualifies() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T12:00:00Z", 5),
    ])
    got = render_reqs([(_session("s"), boundaries)], gap_minutes=2)
    check("REQs of a session with no turn opener never form a gap", got == "no REQs to show\n", got)

if __name__ == '__main__':
    sys.exit(test_reqs_gap_workflow())
