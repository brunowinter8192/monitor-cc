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

from src.dual_log_cli.discovery import filter_by_family
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_reqs import render_reqs, render_reqs_merged
from src.dual_log_cli.timeline_boundaries import request_boundaries

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

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


# --- the fixed CR/CC line form -----------------------------------------------------------------

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


# --- --gap: pairing, "prints once", threshold ---------------------------------------------------

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


# --- --merged: cross-session ordering, tagging, gap pairing --------------------------------------

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


# --- --rebuild/--drop predicates ------------------------------------------------------------------

# --rebuild: only REQs where CC > CR. REQ 3 has no entry in the usage map at all and must be
# skipped, not shown with a "?" tail — an unresolved REQ fails the predicate outright.
def test_rebuild_keeps_only_cc_gt_cr() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 10), "f1": (20, 3)}}  # f2 (REQ 3) unresolved
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, rebuild=True)
    expected = (
        "session s\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  CR 5  CC 10\n"
    )
    check("only the CC>CR, resolved REQ prints; REQ 2 (CC<CR) and REQ 3 (unresolved) omitted",
          got == expected, got)


# --drop: REQ n qualifies when CR(n) < CR(n-1) + CC(n-1). REQ 2's CR (300) is exactly REQ 1's
# CR+CC (300) — the boundary, does NOT qualify (strict <). REQ 3's CR (250) is less than REQ 2's
# CR+CC (350) — qualifies, no shortfall figure printed anywhere.
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


# --drop: REQ 1 of a chain never qualifies (no predecessor), even when its own usage resolves.
def test_drop_req1_never_qualifies() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 5)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, drop=True)
    check("REQ 1 has no predecessor -> never qualifies for --drop, header only",
          got == "session s\n", got)


# --drop --merged: the predecessor is ALWAYS the previous request of the SAME session, never the
# merged chain's chronological neighbor.
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


# A REQ whose own usage never resolves is skipped under EITHER flag.
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


# --rebuild AND --drop combine with AND: a REQ must satisfy both.
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


# Neither --rebuild nor --drop set: CR/CC still print (baseline behavior, not an opt-in tail).
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


# --- --turn narrows first, then the other filters apply within it -------------------------------

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


# --- filter_by_family -----------------------------------------------------------------------------

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


# ORCHESTRATOR

def test_reqs_workflow() -> None:
    test_single_session_req_lines_show_cr_cc()
    test_unresolved_usage_shows_question_marks()
    test_refire_collapsed_same_as_msgs()
    test_multiple_sessions_blank_line_separated()
    test_session_with_zero_requests_still_gets_header()
    test_skipped_note_appended()
    test_empty_results()
    test_gap_one_qualifying_pair()
    test_gap_two_adjacent_gaps_sharing_req()
    test_gap_no_qualifying_gap()
    test_gap_threshold_boundary()
    test_merged_order_interleaved_across_sessions()
    test_merged_gap_bridged_by_another_session_does_not_qualify()
    test_merged_gap_across_sessions_qualifies()
    test_rebuild_keeps_only_cc_gt_cr()
    test_drop_boundary_exact_equal_does_not_qualify()
    test_drop_req1_never_qualifies()
    test_merged_drop_predecessor_stays_within_session()
    test_unresolved_usage_skipped_under_either_flag()
    test_rebuild_and_drop_combine_with_and()
    test_plain_listing_shows_usage_without_rebuild_or_drop()
    test_turn_narrows_before_gap_applies()
    test_turn_out_of_range_prints_header_only()
    test_filter_by_family()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_reqs_workflow()
