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

def test_reqs_workflow() -> None:
    test_single_session_req_lines_show_cr_cc()
    test_unresolved_usage_shows_question_marks()
    test_refire_collapsed_same_as_msgs()
    test_multiple_sessions_blank_line_separated()
    test_session_with_zero_requests_still_gets_header()
    test_skipped_note_appended()
    test_empty_results()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")

# FUNCTIONS

def test_single_session_req_lines_show_cr_cc() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T20:16:02Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T20:16:40Z", 5),
    ])
    session = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000")
    usage_by_stem = {session["stem"]: {"f0": (7771, 5496), "f1": (13267, 7006)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem)
    expected = (
        "session api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000\n"
        f"REQ 1   {_local_clock('2026-09-04T20:16:02Z')}  CR 7,771   CC 5,496\n"
        f"REQ 2   {_local_clock('2026-09-04T20:16:40Z')}  CR 13,267  CC 7,006\n"
    )
    check("CR is padded to the widest value printed for the session, CC unpadded", got == expected, got)

def test_unresolved_usage_shows_question_marks() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True)])
    session = _session("s")
    got = render_reqs([(session, boundaries)])
    check("no usage map at all -> CR ?  CC ?",
          got == f"session s\nREQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR ?  CC ?\n", got)

def test_refire_collapsed_same_as_msgs() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:00:02Z", 2),
        _delta_entry("f2", "2026-09-04T10:00:05Z", 5),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)])
    lines = [l for l in got.split("\n") if l.startswith("REQ")]
    check("re-fire produces no extra REQ line (2 groups, not 3)", len(lines) == 2, lines)
    check("the re-fire+add group uses the OWNER's (f2's) timestamp, not the re-fire's (f1's)",
          lines[1].startswith(f"REQ 2   {_local_clock('2026-09-04T10:00:05Z')}"), lines)

def test_multiple_sessions_blank_line_separated() -> None:
    boundaries_a = _boundaries([_delta_entry("fa", "2026-09-04T09:00:00Z", 1, is_first=True)])
    boundaries_b = _boundaries([_delta_entry("fb", "2026-09-04T08:00:00Z", 1, is_first=True)])
    session_a = _session("newer_session")
    session_b = _session("older_session")
    got = render_reqs([(session_a, boundaries_a), (session_b, boundaries_b)])
    expected = (
        "session newer_session\n"
        f"REQ 1   {_local_clock('2026-09-04T09:00:00Z')}  CR ?  CC ?\n"
        "\n"
        "session older_session\n"
        f"REQ 1   {_local_clock('2026-09-04T08:00:00Z')}  CR ?  CC ?\n"
    )
    check("two sessions render in the order given, blank-line separated", got == expected, got)

def test_session_with_zero_requests_still_gets_header() -> None:
    session = _session("empty_session")
    got = render_reqs([(session, [])])
    check("session header present, no REQ lines", got == "session empty_session\n", got)

def test_skipped_note_appended() -> None:
    session = _session("s")
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True)])
    got = render_reqs([(session, boundaries)], skipped=2)
    check("skipped note present and pluralised", got.rstrip("\n").endswith(
        "(2 sessions skipped — timeline could not be loaded)"), got)

def test_empty_results() -> None:
    got = render_reqs([])
    check("no sessions found, no trailing note", got == "no sessions found\n", got)
    got_skipped = render_reqs([], skipped=1)
    check("no sessions found, with skipped note", got_skipped == (
        "no sessions found\n\n(1 session skipped — timeline could not be loaded)\n"), got_skipped)

if __name__ == "__main__":
    test_reqs_workflow()
