"""
Regression suite for `duallog reqs` (src/dual_log_cli/render.py's `render_reqs`, and
src/dual_log_cli/discovery.py's `filter_by_family`).

Covers: a session's REQ lines match `msgs`' own numbers/timestamps exactly (built via the real
`request_boundaries`/`request_markers`, matching this area's established fixture style); multiple
sessions blank-line separated, newest-first order preserved (listing order, unchanged by
`render_reqs`); a session with zero requests still gets its `session <stem>` header and no REQ
lines; the trailing skipped-sessions note, reused from `search`; an empty result set;
`--gap MINUTES` (2026-09-04) — one qualifying pair (only its two REQs print, the after carrying
`  +Nm`, everything else omitted), two adjacent qualifying gaps sharing a REQ (it prints exactly
once), no qualifying gap (only the session header line), and the `>=` threshold boundary (a gap of
precisely the threshold qualifies, one second short does not); `--merged` (2026-09-04, same day) —
two sessions' REQs interleave in strict chronological order under one `merged <N> sessions` header,
each tagged with its own session; combined with `--gap`, a within-session gap bridged by another
session's request does NOT qualify (the merge only ever compares GLOBAL chronological neighbors),
while a gap that exists only ACROSS sessions does; and `filter_by_family` keeping only
opus-identifying stems for `--main`, only worker-identifying stems for `--worker` (2026-09-10:
reads `stem_identity` directly now, the rendered CONTEXT string it used to check having been
removed), and the list unchanged when neither flag is set.

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
from src.dual_log_cli.render import render_reqs, render_reqs_merged
from src.dual_log_cli.timeline import request_boundaries

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


# A session dict carrying only what render_reqs/render_reqs_merged actually read (2026-09-10: no
# "context" field any more — `_session_tag` now derives the --merged tag straight from the STEM
# via `discovery.stem_identity`, so a realistic stem is what a fixture needs, not a fake context
# string).
def _session(stem: str) -> dict:
    return {"stem": stem}


# A session's REQ lines carry exactly the numbers and clock times `msgs`' own separators print.
def test_single_session_req_lines_match_msgs_numbering() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T20:16:02Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T20:16:40Z", 5),
        _delta_entry("f2", "2026-09-04T20:17:10Z", 9),
    ])
    session = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000")
    got = render_reqs([(session, boundaries)])
    # The milestone's own example shows these UTC instants rendering as LOCAL time (verified
    # against the real proxy pane: the same instant read 20:16:02 there, local, against 18:16:02
    # in `reqs` before local-time conversion existed) — so the expected clocks here are computed
    # from the SAME UTC instants via the SAME conversion, not the milestone's illustrative digits.
    expected = (
        "session api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000\n"
        f"REQ 1   {_local_clock('2026-09-04T20:16:02Z')}\n"
        f"REQ 2   {_local_clock('2026-09-04T20:16:40Z')}\n"
        f"REQ 3   {_local_clock('2026-09-04T20:17:10Z')}\n"
    )
    check("output matches the spec's own example byte-for-byte", got == expected, got)


# A re-fire (adds no new msg) opens the SAME group as the boundary that eventually completes it
# (both share one start_index) and is collapsed into that group's number/timestamp, exactly as
# `msgs`' own separator does — no extra REQ line for the re-fire itself.
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
          lines[1] == f"REQ 2   {_local_clock('2026-09-04T10:00:05Z')}", lines)


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
        f"REQ 1   {_local_clock('2026-09-04T09:00:00Z')}\n"
        "\n"
        "session older_session\n"
        f"REQ 1   {_local_clock('2026-09-04T08:00:00Z')}\n"
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


# --gap: one qualifying pair. REQ1->REQ2 is exactly the threshold (qualifies, prints both, the
# after carrying "  +90m"); REQ2->REQ3 is a small gap (does not qualify) — REQ3 must not appear at
# all, since it touches no qualifying gap.
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
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}\n"
        f"REQ 2   {_local_clock('2026-09-04T11:30:00Z')}  +90m\n"
    )
    check("only the qualifying pair's REQs print, after carries the tail, REQ 3 omitted",
          got == expected, got)


# --gap: two adjacent qualifying gaps sharing REQ 2 — it prints exactly ONCE, carrying only its
# OWN (after-of-gap-1) tail, never re-printed tail-less as the before of gap 2.
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
    expected = (
        "session s\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}\n"
        f"REQ 2   {_local_clock('2026-09-04T11:30:00Z')}  +90m\n"
        f"REQ 3   {_local_clock('2026-09-04T13:30:00Z')}  +120m\n"
    )
    check("exactly 3 REQ lines, REQ 4 omitted (its own gap does not qualify)", got == expected, got)


# --gap: no pair qualifies — the session prints ONLY its header line, no REQ lines at all, so the
# reader can see the session WAS checked rather than it silently vanishing.
def test_gap_no_qualifying_gap() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T10:01:00Z", 5),
        _delta_entry("f2", "2026-09-04T10:02:00Z", 9),
    ])
    session = _session("s")
    got = render_reqs([(session, boundaries)], gap_minutes=90)
    check("no qualifying gap -> only the session header line", got == "session s\n", got)


# --gap threshold is inclusive (>=): a gap of EXACTLY the threshold qualifies; one second short of
# it does not — floored to whole minutes, never rounded, so the boundary is exact.
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
          got_exact == f"session s\nREQ 1   {_local_clock('2026-09-04T10:00:00Z')}\n"
                       f"REQ 2   {_local_clock('2026-09-04T11:30:00Z')}  +90m\n", got_exact)
    check("one second short of the threshold does NOT qualify",
          got_under == "session s\n", got_under)


# --merged: two sessions' REQs interleave in TIME, not in listing order — the merged output must
# follow strict chronological order across sessions, each line carrying its own session's tag
# (read straight off its stem — a worker's name, a main session's project label).
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
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  monitor_cc\n"
        f"REQ 1   {_local_clock('2026-09-04T10:10:00Z')}  proxy-tn-wrap\n"
        f"REQ 2   {_local_clock('2026-09-04T10:20:00Z')}  monitor_cc\n"
        f"REQ 2   {_local_clock('2026-09-04T10:30:00Z')}  proxy-tn-wrap\n"
    )
    check("merged REQs interleave in strict chronological order, each tagged with its own session",
          got == expected, got)


# --merged --gap: a gap that exists WITHIN one session (95m, would qualify alone at --gap 90) but
# is BRIDGED by another session's request landing in between must NOT qualify — the merged chain
# only ever compares GLOBAL chronological neighbors, so the 95m same-session gap is replaced by two
# smaller cross-session gaps (30m, 65m), neither of which reaches the threshold.
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


# --merged --gap: a gap that exists ACROSS sessions (nothing bridging it) DOES qualify — both REQs
# print, the after carrying the tail and its own session's tag.
def test_merged_gap_across_sessions_qualifies() -> None:
    boundaries_a = _boundaries([_delta_entry("a0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    boundaries_b = _boundaries([_delta_entry("b0", "2026-09-04T11:40:00Z", 2, is_first=True)])  # +100m
    session_a = _session("api_requests_opus_monitor_cc_1788500000")
    session_b = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788500001")
    got = render_reqs_merged([(session_a, boundaries_a), (session_b, boundaries_b)], gap_minutes=90)
    expected = (
        "merged 2 sessions\n"
        f"REQ 1   {_local_clock('2026-09-04T10:00:00Z')}  monitor_cc\n"
        f"REQ 1   {_local_clock('2026-09-04T11:40:00Z')}  proxy-tn-wrap  +100m\n"
    )
    check("a genuine cross-session gap qualifies, after-REQ carries tag AND tail", got == expected, got)


# --rebuild: only REQs where CC > CR. REQ 1 (CC 10 > CR 5) qualifies; REQ 2 (CC 3 < CR 20) does
# not; REQ 3 has no entry in the usage map at all (unresolved) and must be skipped, not shown
# tail-less. Every printed line carries the "  CR c  CC c" tail, digit-grouped.
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
# CR+CC (100+200=300) — the boundary, does NOT qualify (strict <). REQ 3's CR (250) is less than
# REQ 2's CR+CC (300+50=350) — qualifies, carrying the shortfall "  −100".
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
        f"REQ 3   {_local_clock('2026-09-04T10:02:00Z')}  CR 250  CC 10  −100\n"
    )
    check("REQ 2 (exactly equal) does not qualify, REQ 3 qualifies with the shortfall tail",
          got == expected, got)


# --drop: REQ 1 of a chain never qualifies (no predecessor), even when its own usage resolves and
# would otherwise pass every other check.
def test_drop_req1_never_qualifies() -> None:
    boundaries = _boundaries([_delta_entry("f0", "2026-09-04T10:00:00Z", 2, is_first=True)])
    session = _session("s")
    usage_by_stem = {"s": {"f0": (5, 5)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem, drop=True)
    check("REQ 1 has no predecessor -> never qualifies for --drop, header only",
          got == "session s\n", got)


# --drop --merged: the predecessor is ALWAYS the previous request of the SAME session, never the
# merged chain's chronological neighbor — the shared prompt-cache prefix a cache drop measures is
# system blocks + tools, never the conversation, so comparing across sessions is meaningless.
# Session B's single request (b0) sits chronologically BETWEEN session A's two requests (a0, a1) —
# a0 -> b0 -> a1 in time — but b0 is session B's own first request (no same-session predecessor) and
# must NOT qualify for --drop no matter how its usage compares to a0's; a1, whose real same-session
# predecessor is a0 (not the chronologically nearer b0), must be evaluated against A0's usage.
# Constructed so the two readings disagree: against b0 (cr=5, cc=5, total=10) a1's cr=250 would NOT
# qualify (250 >= 10); against the correct same-session predecessor a0 (cr=100, cc=200, total=300)
# it DOES (250 < 300, shortfall 50) — only the correct reading produces any output line at all.
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
        f"REQ 2   {_local_clock('2026-09-04T10:20:00Z')}  monitor_cc  CR 250  CC 10  −50\n"
    )
    check("a1 qualifies against ITS OWN session's a0, not the chronologically nearer b0; "
          "b0 (session B's own REQ 1) never qualifies at all", got == expected, got)


# A REQ whose own usage never resolves (absent from the usage map entirely) is skipped under
# EITHER flag, even one that would otherwise qualify for --rebuild by CC/CR alone.
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


# --rebuild AND --drop combine with AND: a REQ must satisfy both. REQ 2 alone satisfies --rebuild
# (CC 40 > CR 10) but NOT --drop (CR 10 is not < REQ 1's CR+CC = 5+5=10, exactly equal) — combined,
# it must not appear.
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


# Neither --rebuild nor --drop set (the default): output is byte-identical to the pre-existing
# listing, even when a usage_by_stem map happens to be passed in — the new params are additive.
def test_no_rebuild_no_drop_output_unchanged() -> None:
    boundaries = _boundaries([
        _delta_entry("f0", "2026-09-04T20:16:02Z", 2, is_first=True),
        _delta_entry("f1", "2026-09-04T20:16:40Z", 5),
    ])
    session = _session("api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000")
    usage_by_stem = {session["stem"]: {"f0": (5, 5), "f1": (100, 200)}}
    got = render_reqs([(session, boundaries)], usage_by_stem=usage_by_stem)
    expected = (
        "session api_requests_worker_25c51a2e_proxy-tn-wrap_1788545000\n"
        f"REQ 1   {_local_clock('2026-09-04T20:16:02Z')}\n"
        f"REQ 2   {_local_clock('2026-09-04T20:16:40Z')}\n"
    )
    check("passing usage_by_stem with neither flag set leaves the plain listing untouched",
          got == expected, got)


# filter_by_family: --main keeps only opus-identifying stems, --worker keeps only
# worker-identifying stems (2026-09-10: reads stem_identity directly, no CONTEXT field involved
# at all), neither flag returns the list unchanged.
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
    test_single_session_req_lines_match_msgs_numbering()
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
    test_no_rebuild_no_drop_output_unchanged()
    test_filter_by_family()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_reqs_workflow()
