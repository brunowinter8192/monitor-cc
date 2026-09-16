# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_reqs import render_reqs_merged
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

def test_reqs_merged_workflow() -> None:
    test_merged_order_interleaved_across_sessions()
    test_merged_gap_bridged_by_another_session_does_not_qualify()
    test_merged_gap_across_sessions_qualifies()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

# --merged: two sessions' REQs interleave in TIME, not in listing order, each line carrying its own
# session's tag (read straight off its stem).
def test_merged_order_interleaved_across_sessions() -> None:
    boundaries_a = _boundaries([
        _delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("a1", "2026-09-04T10:20:00Z", 5),
    ])
    boundaries_b = _boundaries([
        _delta_entry("b0", "2026-09-04T10:10:00Z", 2, is_first=True),
        _delta_entry("b1", "2026-09-04T10:30:00Z", 5),
    ])
    session_a = _session("api_requests_opus_monitor_cc_1788500000")
    session_b = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001")
    got = render_reqs_merged([(session_a, boundaries_a), (session_b, boundaries_b)])
    expected = (
        "merged 2 sessions\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  monitor_cc  CR ?  CC ?\n"
        f"REQ 1   {_local_clock('2026-09-04T10:10:00Z')}  proxy-tn-wrap  CR ?  CC ?\n"
        f"REQ 2   {_local_clock('2026-09-04T10:20:00Z')}  monitor_cc  CR ?  CC ?\n"
        f"REQ 2   {_local_clock('2026-09-04T10:30:00Z')}  proxy-tn-wrap  CR ?  CC ?\n"
    )
    check("merged REQs interleave in strict chronological order, each tagged with its own session",
          got == expected, got)


# --merged --gap: a gap that exists WITHIN one session but is BRIDGED by another session's request
# must NOT qualify — the merged chain only ever compares GLOBAL chronological neighbors.
def test_merged_gap_bridged_by_another_session_does_not_qualify() -> None:
    boundaries_a = _boundaries([
        _delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("a1", "2026-09-04T11:35:00Z", 5),   # +95m from a0 — would qualify ALONE
    ])
    boundaries_b = _boundaries([
        _delta_entry("b0", "2026-09-04T10:30:00Z", 2, is_first=True),  # +30m after a0, +65m before a1
    ])
    session_a = _session("api_requests_opus_monitor_cc_1788500000")
    session_b = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001")
    got = render_reqs_merged([(session_a, boundaries_a), (session_b, boundaries_b)], gap_minutes=90)
    check("the within-session gap is bridged — no qualifying pair, header only",
          got == "merged 2 sessions\n", got)


# --merged --gap: a gap that exists ACROSS sessions (nothing bridging it) DOES qualify.
def test_merged_gap_across_sessions_qualifies() -> None:
    boundaries_a = _boundaries([_delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    boundaries_b = _boundaries([_delta_entry("b0", "2026-09-04T11:40:00Z", 2, is_first=True)])  # +100m
    session_a = _session("api_requests_opus_monitor_cc_1788500000")
    session_b = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001")
    got = render_reqs_merged([(session_a, boundaries_a), (session_b, boundaries_b)], gap_minutes=90)
    expected = (
        "merged 2 sessions\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  monitor_cc  CR ?  CC ?\n"
        f"REQ 1   {_local_clock('2026-09-04T11:40:00Z')}  proxy-tn-wrap  CR ?  CC ?\n"
    )
    check("a genuine cross-session gap qualifies, both REQs print with their tags", got == expected, got)


if __name__ == "__main__":
    test_reqs_merged_workflow()
