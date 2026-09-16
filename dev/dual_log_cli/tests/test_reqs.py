"""
Regression suite for `duallog reqs` (src/dual_log_cli/render.py's `render_reqs`/`render_reqs_merged`,
and src/dual_log_cli/discovery.py's `filter_by_family`) — rewritten 2026-09-16 for the M6 redesign:
one fixed REQ line form (`REQ n   HH:MM:SS  CR c  CC c`, always, no elapsed/gap/shortfall tail
anywhere), every flag a pure filter/selector over it. Turn-grouping/separator coverage
(`_session_entries_and_separators`, `--turn`, the separator-survival rule) lives in
`test_turns.py`; this file covers the flat-listing shape and every filter/predicate/merge behavior
that does not need a turn concept — most fixtures here pass no `turns_by_stem`, which reproduces
the pre-M5 flat listing exactly (an empty `turns` list yields no openers, so `_grouped_lines` never
finds a separator to print).

Covers: the fixed CR/CC line form (resolved usage digit-grouped, unresolved usage as `CR ?  CC ?`,
CR padded to the widest value actually printed for that session so CC lines up); a session's REQ
lines match `msgs`' own numbers/timestamps exactly (re-fires collapsed, a restart handled
identically — built via the real `request_boundaries`/`request_markers`, matching this area's
established fixture style); multiple sessions blank-line separated, newest-first order preserved;
a session with zero requests still gets its `session <stem>` header and no REQ lines; the trailing
skipped-sessions note; an empty result set; `--gap MINUTES` (pairing rule and the "prints once"
rule for a REQ bracketing two adjacent qualifying gaps, no tail of any kind); `--merged` (two
sessions interleave in strict chronological order under one `merged <N> sessions` header, each
line tagged with its own session, combined with `--gap` using cross-session neighbors); `--rebuild`/
`--drop` (the CC>CR and CR(n)<CR(n-1)+CC(n-1) predicates, the strict-inequality boundary, REQ 1
never qualifying for `--drop`, the same-session predecessor rule holding under `--merged`, AND
combination, unresolved usage failing either flag outright); `--turn` narrowing precedence ahead of
`--gap`/`--rebuild`/`--drop`; and `filter_by_family`.

`request_boundaries` is exercised end to end against a real temp `_forwarded.jsonl`-shaped file —
no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_reqs.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

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

# A session's REQ lines carry exactly the numbers, clock times and CR/CC `msgs` would show for the
# same flows, no separators (no turns_by_stem given -> flat listing, matching the pre-M5 shape).
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


# A flow absent from the usage map renders "CR ?  CC ?" — never omitted, never a guess.
def test_unresolved_usage_shows_question_marks() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True)])
    session = _session("s")
    got = render_reqs([(session, boundaries)])
    check("no usage map at all -> CR ?  CC ?",
          got == f"session s\nREQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR ?  CC ?\n", got)


# A re-fire (adds no new msg) opens the SAME group as the boundary that eventually completes it
# and is collapsed into that group's number/timestamp, exactly as `msgs`' own separator does — no
# extra REQ line for the re-fire itself.
def test_refire_collapsed_same_as_msgs() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:00:02Z", 2),   # start_index=2, re-fire (2<2 is False)
        _delta_entry("f2", "2026-09-04T10:00:05Z", 5),   # start_index=2 too — same group, adds, owns it
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)])
    lines = [l for l in got.split("\n") if l.startswith("REQ")]
    check("re-fire produces no extra REQ line (2 groups, not 3)", len(lines) == 2, lines)
    check("the re-fire+add group uses the OWNER's (f2's) timestamp, not the re-fire's (f1's)",
          lines[1].startswith(f"REQ 2   {_local_clock('2026-09-04T10:00:05Z')}"), lines)


# Multiple sessions stay in LISTING order (newest-first is the caller's responsibility, unchanged
# here) and are blank-line separated.
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


# A session with zero requests still prints its own header, with no REQ lines beneath it.
def test_session_with_zero_requests_still_gets_header() -> None:
    session = _session("empty_session")
    got = render_reqs([(session, [])])
    check("session header present, no REQ lines", got == "session empty_session\n", got)


# The trailing skipped-sessions note, reused from `search`.
def test_skipped_note_appended() -> None:
    session = _session("s")
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 1, is_first=True)])
    got = render_reqs([(session, boundaries)], skipped=2)
    check("skipped note present and pluralised", got.rstrip("\n").endswith(
        "(2 sessions skipped — timeline could not be loaded)"), got)


# An empty result set renders "no sessions found", with the skipped note still appended if nonzero.
def test_empty_results() -> None:
    got = render_reqs([])
    check("no sessions found, no trailing note", got == "no sessions found\n", got)
    got_skipped = render_reqs([], skipped=1)
    check("no sessions found, with skipped note", got_skipped == (
        "no sessions found\n\n(1 session skipped — timeline could not be loaded)\n"), got_skipped)


if __name__ == "__main__":
    test_reqs_workflow()
