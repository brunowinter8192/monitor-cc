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

PASS_LIST = []
FAIL_LIST = []


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


# A session dict carrying only what render_reqs/render_reqs_merged actually read — `_session_tag`
# derives the --merged tag straight from the STEM via `discovery.stem_identity`, so a realistic
# stem is what a fixture needs, not a fake context string.
def _session(stem: str) -> dict:
    return {"stem": stem}


# ORCHESTRATOR

def test_reqs_gap_workflow() -> None:
    test_gap_one_qualifying_pair()
    test_gap_two_adjacent_gaps_sharing_req()
    test_gap_no_qualifying_gap()
    test_gap_threshold_boundary()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

# --gap: one qualifying pair. REQ1->REQ2 is exactly the threshold (qualifies, prints both, NO tail
# of any kind); REQ2->REQ3 is a small gap (does not qualify) — REQ3 must not appear at all.
def test_gap_one_qualifying_pair() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),   # +90m
        _delta_entry("f2", "2026-09-04T11:35:00Z", 9),   # +5m
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90)
    expected = (
        "session s\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR ?  CC ?\n"
        f"REQ 2   {_local_clock('2026-09-04T11:30:00Z')}  CR ?  CC ?\n"
    )
    check("only the qualifying pair's REQs print, no tail, REQ 3 omitted", got == expected, got)


# --gap: two adjacent qualifying gaps sharing REQ 2 — it prints exactly ONCE.
def test_gap_two_adjacent_gaps_sharing_req() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),   # +90m from f0 — qualifies
        _delta_entry("f2", "2026-09-04T13:30:00Z", 9),   # +120m from f1 — qualifies
        _delta_entry("f3", "2026-09-04T13:35:00Z", 12),  # +5m from f2 — does not qualify
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90)
    lines = [l for l in got.split("\n") if l.startswith("REQ")]
    check("REQ 2 appears exactly once (bracketing both qualifying gaps)",
          sum(1 for l in lines if l.startswith("REQ 2 ")) == 1, lines)
    check("exactly 3 REQ lines, REQ 4 omitted (its own gap does not qualify)", len(lines) == 3, lines)


# --gap: no pair qualifies — the session prints ONLY its header line.
def test_gap_no_qualifying_gap() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90)
    check("no qualifying gap -> only the session header line", got == "session s\n", got)


# --gap threshold is inclusive (>=): a gap of EXACTLY the threshold qualifies; one second short
# does not — floored to whole minutes, never rounded.
def test_gap_threshold_boundary() -> None:
    exact_boundary = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:30:00Z", 5),   # exactly +5400s = +90m
    ])
    just_under = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T11:29:59Z", 5),   # +5399s = 89m59s -> floors to 89m
    ])
    session = _session("s")
    got_exact = render_reqs([(session, exact_boundary)], gap_minutes=90)
    got_under = render_reqs([(session, just_under)], gap_minutes=90)
    check("a gap of exactly the threshold QUALIFIES (>=)",
          got_exact.count("REQ") == 2, got_exact)
    check("one second short of the threshold does NOT qualify",
          got_under == "session s\n", got_under)


if __name__ == "__main__":
    test_reqs_gap_workflow()
