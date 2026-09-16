# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.discovery import filter_by_family
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

def test_reqs_turn_and_family_workflow() -> None:
    test_turn_narrows_before_gap_applies()
    test_turn_out_of_range_prints_header_only()
    test_filter_by_family()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

# --turn combined with --gap: --turn narrows the candidate REQ sequence FIRST, so --gap's pairing
# walk only ever sees the turn's own REQs — a qualifying gap straddling the turn boundary (not
# inside the kept turn) must not leak a REQ from the OTHER turn into the output.
def _text_block(preview: str) -> dict:
    return {"label": "text", "type": "text", "chars": 1, "sig_chars": 0, "preview": preview}


def _turn_row(index: int, role: str, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": 1, "blocks": blocks}


def test_turn_narrows_before_gap_applies() -> None:
    turns = [
        _turn_row(0, "user", [_text_block("go")]),
        _turn_row(1, "assistant", [_text_block("ack")]),
        _turn_row(2, "user", [{"label": "tool_result", "type": "tool_result", "chars": 1,
                               "sig_chars": 0, "preview": ""}]),
        _turn_row(3, "assistant", [_text_block("done")]),
        _turn_row(4, "system", [{"label": "system", "type": "system", "chars": 1,
                                 "sig_chars": 0, "preview": ""}]),
        _turn_row(5, "user", [_text_block("next")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True),   # turn 1
        _delta_entry("f1", "2026-09-04T10:05:00Z", 2),                  # turn 1, +5m from f0
        _delta_entry("f2", "2026-09-04T13:00:00Z", 6),                  # turn 2 (start=2<5, count=6>=5)
    ])
    session = _session("s")
    turns_by_stem = {"s": turns}
    got_turn1_gap = render_reqs([(session, boundaries)], turn=1, gap_minutes=1,
                                turns_by_stem=turns_by_stem)
    lines = [l for l in got_turn1_gap.split("\n") if l.startswith("REQ")]
    check("--turn 1 --gap 1 only ever sees turn 1's own two REQs, both qualify",
          [l.split()[1] for l in lines] == ["1", "2"], lines)


# --turn N missing from a session prints only its header line.
def test_turn_out_of_range_prints_header_only() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True)])
    session = _session("s")
    got = render_reqs([(session, boundaries)], turn=5)
    check("no turn concept at all (no turns_by_stem) -> --turn N never matches -> header only",
          got == "session s\n", got)


# filter_by_family: --main keeps only opus-identifying stems, --worker keeps only
# worker-identifying stems, neither flag returns the list unchanged.
def test_filter_by_family() -> None:
    sessions = [
        _session("api_requests_opus_monitor_cc_1788000001"),
        _session("api_requests_worker_11111111_foo_1788000002"),
        _session("api_requests_opus_websearch_1788000003"),
        _session("api_requests_worker_22222222_bar_1788000004"),
    ]
    stems = [s["stem"] for s in sessions]
    main_only = filter_by_family(sessions, main=True)
    check("--main keeps only opus-identifying sessions",
          [s["stem"] for s in main_only] == [stems[0], stems[2]], main_only)
    worker_only = filter_by_family(sessions, worker=True)
    check("--worker keeps only worker-identifying sessions",
          [s["stem"] for s in worker_only] == [stems[1], stems[3]], worker_only)
    unfiltered = filter_by_family(sessions)
    check("neither flag set returns the list unchanged",
          [s["stem"] for s in unfiltered] == stems, unfiltered)


if __name__ == "__main__":
    test_reqs_turn_and_family_workflow()
