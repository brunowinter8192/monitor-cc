# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_reqs import render_reqs, render_reqs_merged
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

# ORCHESTRATOR

def test_reqs_rebuild_drop_workflow() -> None:
    test_rebuild_keeps_only_cc_gt_cr()
    test_drop_boundary_exact_equal_does_not_qualify()
    test_drop_req1_never_qualifies()
    test_merged_drop_predecessor_stays_within_session()
    test_unresolved_usage_skipped_under_either_flag()
    test_rebuild_and_drop_combine_with_and()
    test_plain_listing_shows_usage_without_rebuild_or_drop()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")

# FUNCTIONS

def test_rebuild_keeps_only_cc_gt_cr() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 10), "f1": (20, 3)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, rebuild=True)
    expected = (
        "session s\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR 5  CC 10\n"
    )
    check("only the CC>CR, resolved REQ prints; REQ 2 (CC<CR) and REQ 3 (unresolved) omitted",
          got == expected, got)

def test_drop_boundary_exact_equal_does_not_qualify() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (100, 200), "f1": (300, 50), "f2": (250, 10)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, drop=True)
    expected = (
        "session s\n"
        f"REQ 3   {_local_clock('2026-09-04T10:02:00Z')}  CR 250  CC 10\n"
    )
    check("REQ 2 (exactly equal) does not qualify, REQ 3 qualifies, no shortfall figure printed",
          got == expected, got)

def test_drop_req1_never_qualifies() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 5)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, drop=True)
    check("REQ 1 has no predecessor -> never qualifies for --drop, header only",
          got == "session s\n", got)

def test_merged_drop_predecessor_stays_within_session() -> None:
    boundaries_a = _boundaries([
        _delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("a1", "2026-09-04T10:20:00Z", 5),
    ])
    boundaries_b = _boundaries([_delta_entry("b0", "2026-09-04T10:10:00Z", 2, is_first=True)])
    session_a = _session("api_requests_opus_monitor_cc_1788500000")
    session_b = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001")
    usage_by_stem = {
        session_a["stem"]: {"a0": (100, 200), "a1": (250, 10)},
        session_b["stem"]: {"b0": (5, 5)},
    }
    got = render_reqs_merged(
        [(session_a, boundaries_a), (session_b, boundaries_b)],
        usage_by_stem=usage_by_stem, drop=True,
    )
    expected = (
        "merged 2 sessions\n"
        f"REQ 2   {_local_clock('2026-09-04T10:20:00Z')}  monitor_cc  CR 250  CC 10\n"
    )
    check("a1 qualifies against ITS OWN session's a0, not the chronologically nearer b0; "
          "b0 (session B's own REQ 1) never qualifies at all", got == expected, got)

def test_unresolved_usage_skipped_under_either_flag() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
    ])
    session = _session("s")
    got_rebuild = render_reqs([(session, boundaries)], usage_by_stem={"s": {}}, rebuild=True)
    check("no usage resolved at all -> --rebuild shows nothing but the header",
          got_rebuild == "session s\n", got_rebuild)
    got_drop = render_reqs([(session, boundaries)], usage_by_stem={"s": {}}, drop=True)
    check("no usage resolved at all -> --drop shows nothing but the header",
          got_drop == "session s\n", got_drop)

def test_rebuild_and_drop_combine_with_and() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
    ])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 5), "f1": (10, 40)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, rebuild=True, drop=True)
    check("REQ 2 passes --rebuild alone but fails --drop (exact-equal boundary) -> excluded",
          got == "session s\n", got)

def test_plain_listing_shows_usage_without_rebuild_or_drop() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T20:16:02Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T20:16:40Z", 5),
    ])
    session = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000")
    usage_by_stem = {session["stem"]: {"f0": (5, 5), "f1": (100, 200)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem)
    expected = (
        "session api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000\n"
        f"REQ 1   {_local_clock('2026-09-04T20:16:02Z')}  CR 5    CC 5\n"
        f"REQ 2   {_local_clock('2026-09-04T20:16:40Z')}  CR 100  CC 200\n"
    )
    check("CR/CC print on the plain listing with neither --rebuild nor --drop set",
          got == expected, got)

if __name__ == "__main__":
    test_reqs_rebuild_drop_workflow()
