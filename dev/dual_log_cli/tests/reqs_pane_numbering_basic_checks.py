# INFRASTRUCTURE

import io
from contextlib import redirect_stderr

from src.dual_log_cli.commands import _report_numbering_paths, _req_error_text
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.render_reqs import render_reqs, render_reqs_merged
from src.dual_log_cli.timeline_markers import UnknownRequestNumberError, request_markers, resolve_req_range

from dev.dual_log_cli.tests.reqs_pane_numbering_fixtures import (
    _clock, _folded_create_view, _numbered_view, _render, _req_lines, _second_session, _timeline, check)


# FUNCTIONS

def test_continues_are_found_and_haiku_is_not() -> None:
    boundaries, continues = _timeline()
    check("continue_requests returns the five continues in send order",
          [c["flow_id"] for c in continues] == ["k1", "k2", "k3", "k4", "k5"], continues)
    check("the two creates stay the only boundaries, haiku is in neither list",
          [b["flow_id"] for b in boundaries] == ["c1", "c2"], boundaries)


def test_numbering_annotates_creates_and_continues() -> None:
    _session_dict, boundaries, continues, numbering = _numbered_view()
    check("transcript path is used", numbering["path"] == "transcript", numbering["path"])
    check("creates carry the transcript call numbers 1 and 4",
          [b["pane_number"] for b in boundaries] == [1, 4], boundaries)
    check("continues carry 2, 3, 5, 6 and None for the 404",
          [c["pane_number"] for c in continues] == [2, 3, 5, 6, None], continues)
    check("turn of each request comes from the transcript",
          [c["pane_turn"] for c in continues] == [1, 1, 2, 2, None], continues)
    check("time is the transcript call time (response end), not the send time",
          boundaries[0]["pane_time"] == "2026-09-04T10:00:05Z" and continues[0]["pane_time"] == "2026-09-04T10:00:25Z", boundaries)


def test_reqs_lists_every_main_thread_request() -> None:
    out = _render()
    lines = _req_lines(out)
    check("six numbered REQ lines plus one REQ ? line", len(lines) == 7 and sum(1 for l in lines if l.startswith("REQ ?")) == 1, lines)
    check("numbers run 1..6 in response-end order", [l.split()[1] for l in lines if not l.startswith("REQ ?")] == ["1", "2", "3", "4", "5", "6"], lines)
    check("a request line shows the response-end time of its transcript call",
          _clock("2026-09-04T10:00:25Z") in lines[1] and lines[1].startswith("REQ 2"), lines[1])
    check("REQ ? line carries the send time, no usage", lines[-1].startswith("REQ ?") and _clock("2026-09-04T10:31:00Z") in lines[-1], lines[-1])
    check("two turn separators with the transcript prompts", out.count("── turn ") == 2 and "first prompt" in out and "second prompt" in out, out)
    check("the REQ ? row does not repeat a separator", out.count("── turn 2") == 1, out)
    check("haiku never appears", "h0" not in out, out)


def test_gap_pairs_two_continues_of_one_turn() -> None:
    out = _render(gap=2)
    lines = _req_lines(out)
    check("--gap 2 keeps REQ 2+3 (two continues of turn 1) and REQ 5+6 (turn 2)",
          [l.split()[1] for l in lines] == ["2", "3", "5", "6"], lines)
    check("the cross-turn pair REQ 4 -> 5 is dropped, REQ 4 does not print", not any(l.startswith("REQ 4") for l in lines), lines)
    check("each kept pair sits under its own turn separator", out.count("── turn 1") == 1 and out.count("── turn 2") == 1, out)


def test_msgs_uses_pane_numbers() -> None:
    _session_dict, boundaries, continues, numbering = _numbered_view()
    data = {"boundaries": boundaries, "turns": [
        {"index": i, "role": "user", "type": "text", "chars": 4,
         "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]} for i in range(6)]}
    out = render_msgs(data, 0, 5, numbering["usage"])
    seps = [line for line in out.split("\n") if line.startswith("── REQ")]
    check("REQ separators use the pane numbers 1 and 4 with response-end times",
          [s.split()[2] for s in seps] == ["1", "4"] and _clock("2026-09-04T10:04:10Z") in seps[1], seps)
    start, end = resolve_req_range(boundaries, 4, 4, 5)
    check("--req 4 resolves to the second create's msgs", (start, end) == (2, 5), (start, end))
    raised = False
    try:
        resolve_req_range(boundaries, 3, 3, 5)
    except UnknownRequestNumberError:
        raised = True
    check("--req 3 (a continue) is not a msg owner", raised)
    text = _req_error_text(UnknownRequestNumberError("REQ 3 not found"), {"continues": continues}, (3, 3))
    check("the error names it a continue request", "REQ 3 is a continue request" in text, text)


def test_owner_rule_prefers_mapped_boundary() -> None:
    def boundary(start: int, count: int, number, flow: str) -> dict:
        return {"start_index": start, "message_count": count, "timestamp": "2026-09-04T10:00:00Z", "flow_id": flow,
                "restart": False, "sys_lines": [], "tool_lines": [], "pane_number": number, "pane_turn": 1,
                "pane_time": None}
    markers = request_markers([boundary(0, 2, 1, "a"), boundary(2, 2, 7, "b"), boundary(2, 6, None, "c")])
    check("a refire group owned by an unmapped last boundary takes the mapped one's number", markers[2]["number"] == 7 and markers[2]["refires"] == 1, markers[2])
    markers = request_markers([boundary(0, 2, None, "a")])
    check("an all-unmapped group has number None", markers[0]["number"] is None, markers)
    data = {"boundaries": [boundary(0, 1, None, "a")], "turns": [
        {"index": 0, "role": "user", "type": "text", "chars": 4,
         "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]}]}
    check("msgs prints REQ ? for an unmapped group", render_msgs(data, 0, 0).startswith("── REQ ?  "), render_msgs(data, 0, 0))


def test_fallback_when_transcript_unresolved() -> None:
    _session_dict, boundaries, continues, numbering = _numbered_view(transcript_lines=[])
    check("no transcript calls -> boundaries path", numbering["path"] == "boundaries" and numbering["pane_turns"] is None, numbering)
    check("boundaries are left un-annotated, legacy numbering applies",
          all("pane_number" not in b for b in boundaries) and [m["number"] for m in request_markers(boundaries).values()] == [1, 2], boundaries)
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        _report_numbering_paths({"stem_a": {"path": "transcript"}, "stem_b": numbering})
    text = buffer.getvalue()
    check("the stderr line states both paths and names the fallback stem",
          "1 session(s) via transcript" in text and "1 via boundaries fallback" in text and "stem_b" in text, text)


def test_create_sharing_a_start_index_is_its_own_req() -> None:
    view = _folded_create_view()
    boundaries = view[1]
    groups = request_markers(boundaries)
    check("fixture: b3 and b4 share start_index 6, msgs ownership folds them into one group owned by REQ 3",
          groups[6]["number"] == 3 and groups[6]["refires"] == 1, groups)
    out = _render(view=view)
    lines = _req_lines(out)
    check("reqs lists every mapped create as its own line: 1, ?, 2, 3 in response-end order",
          [l.split()[1] for l in lines] == ["1", "?", "2", "3"], lines)
    gap_lines = _req_lines(_render(gap=2, view=view))
    check("--gap 2 pairs REQ 1 -> 2 and REQ 2 -> 3, the folded REQ 2 is present",
          [l.split()[1] for l in gap_lines] == ["1", "2", "3"], gap_lines)


def test_sessions_without_output_are_hidden() -> None:
    session, boundaries, continues, numbering = _numbered_view()
    other, other_boundaries = _second_session()
    stem = session["stem"]
    out = render_reqs(
        [(other, other_boundaries), (session, boundaries)], 0, None, 2, {stem: numbering["usage"]}, False, False,
        {stem: [], other["stem"]: []}, {stem: continues}, {stem: numbering["pane_turns"]})
    check("the session with a surviving gap prints, the empty one prints no header",
          f"session {stem}" in out and other["stem"] not in out, out)
    check("no blank line is left behind by the hidden session", not out.startswith("\n") and "\n\n\n" not in out, out)
    merged = render_reqs_merged(
        [(other, other_boundaries), (session, boundaries)], 0, None, 2, {stem: numbering["usage"]}, False, False,
        {stem: [], other["stem"]: []}, {stem: continues}, {stem: numbering["pane_turns"]})
    check("--merged counts only sessions in the header when something prints", merged.startswith("merged 2 sessions\n"), merged)


def test_no_output_at_all_prints_one_line() -> None:
    session, boundaries, continues, numbering = _numbered_view()
    other, other_boundaries = _second_session()
    stem = session["stem"]
    args = ([(other, other_boundaries), (session, boundaries)], 0, None, 60, {stem: numbering["usage"]}, False, False,
            {stem: [], other["stem"]: []}, {stem: continues}, {stem: numbering["pane_turns"]})
    check("nothing qualifies -> exactly the short line", render_reqs(*args) == "no REQs to show\n", render_reqs(*args))
    check("--merged prints the same line", render_reqs_merged(*args) == "no REQs to show\n", render_reqs_merged(*args))
    with_skipped = render_reqs(*((args[0], 1) + args[2:]))
    check("the skipped-sessions note still follows", with_skipped.startswith("no REQs to show\n") and "1 session skipped" in with_skipped, with_skipped)
    check("an empty scope still says 'no sessions found'", render_reqs([]) == "no sessions found\n", render_reqs([]))
