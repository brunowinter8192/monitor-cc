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

def _turns(stems: list, openers: list) -> dict:
    rows = [{"index": i, "role": "user" if i in openers else "assistant", "type": "text", "chars": 10,
             "blocks": [{"label": "text", "type": "text", "chars": 10, "sig_chars": 0, "preview": "p"}]}
            for i in range(max(openers) + 1)]
    return {stem: rows for stem in stems}

def _req_lines(got: str) -> list:
    return [l for l in got.split("\n") if l.startswith("REQ")]

STEM_A = "api_requests_opus_monitor_cc_1788500000"
STEM_B = "api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001"

# ORCHESTRATOR

def test_reqs_merged_workflow() -> None:
    test_merged_order_interleaved_across_sessions()
    test_merged_gap_interleaved_by_another_session_still_qualifies()
    test_merged_gap_across_sessions_dropped()
    test_merged_gap_cross_turn_dropped()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")

# FUNCTIONS

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

def test_merged_gap_interleaved_by_another_session_still_qualifies() -> None:
    boundaries_a = _boundaries([
        _delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("a1", "2026-09-04T11:35:00Z", 5),
    ])
    boundaries_b = _boundaries([
        _delta_entry("b0", "2026-09-04T10:30:00Z", 2, is_first=True),
    ])
    got = render_reqs_merged([(_session(STEM_A), boundaries_a), (_session(STEM_B), boundaries_b)],
                             gap_minutes=90, turns_by_stem=_turns([STEM_A, STEM_B], [0]))
    lines = _req_lines(got)
    check("the same-turn gap of session A qualifies although B's REQ sits chronologically between",
          len(lines) == 2 and all("monitor_cc" in l for l in lines), lines)

def test_merged_gap_across_sessions_dropped() -> None:
    boundaries_a = _boundaries([_delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    boundaries_b = _boundaries([_delta_entry("b0", "2026-09-04T11:40:00Z", 2, is_first=True)])
    got = render_reqs_merged([(_session(STEM_A), boundaries_a), (_session(STEM_B), boundaries_b)],
                             gap_minutes=90, turns_by_stem=_turns([STEM_A, STEM_B], [0]))
    check("a cross-session chronological neighbor never forms a gap, the no-REQ line",
          got == "no REQs to show\n", got)

def test_merged_gap_cross_turn_dropped() -> None:
    boundaries_a = _boundaries([
        _delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("a1", "2026-09-04T11:35:00Z", 9),
    ])
    got = render_reqs_merged([(_session(STEM_A), boundaries_a)], gap_minutes=90,
                             turns_by_stem=_turns([STEM_A], [0, 7]))
    check("under --merged a gap between two turns of one session is dropped",
          got == "no REQs to show\n", got)

if __name__ == "__main__":
    test_reqs_merged_workflow()
