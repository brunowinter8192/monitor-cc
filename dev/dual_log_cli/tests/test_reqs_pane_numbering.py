# INFRASTRUCTURE

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.cli_args import _parse_args
from src.dual_log_cli.commands import _report_numbering_paths, _req_error_text, _req_output_window, _resolve_range
from src.dual_log_cli.numbering import build_session_numbering
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_expand import render_expand_full
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.render_reqs import render_reqs, render_reqs_merged
from src.dual_log_cli.timeline_boundaries import continue_requests, request_boundaries
from src.dual_log_cli.timeline_markers import (
    UnknownRequestNumberError, request_markers, resolve_req_output_range, resolve_req_range,
    resolve_req_range_with_next,
)
from src.proxy_display.forwarded_parser import _proxy_session_id_for_project

PASS_LIST = []
FAIL_LIST = []

_PROJECT_CWD = "/Users/fake/pane-project"
_WORKER = "fake-worker"
_MODEL = "claude-sonnet-5"
_HAIKU = "claude-haiku-4-5-20251001"


# ORCHESTRATOR

def test_reqs_pane_numbering_workflow() -> None:
    test_continues_are_found_and_haiku_is_not()
    test_numbering_annotates_creates_and_continues()
    test_reqs_lists_every_main_thread_request()
    test_gap_pairs_two_continues_of_one_turn()
    test_msgs_uses_pane_numbers()
    test_owner_rule_prefers_mapped_boundary()
    test_fallback_when_transcript_unresolved()
    test_create_sharing_a_start_index_is_its_own_req()
    test_sessions_without_output_are_hidden()
    test_no_output_at_all_prints_one_line()
    test_msg_start_of_creates_and_continues()
    test_req_range_covers_own_group_and_next()
    test_unlocated_continues_own_no_msgs()
    test_msgs_prints_continue_separators()
    test_expand_req_selects_reply_and_returned_result()
    test_expand_req_errors_and_cli()
    test_unmapped_req_sits_in_its_turn_by_send_time()
    test_unmapped_req_stays_out_of_gap_pairs()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


def _clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")


def _create(flow_id: str, timestamp: str, messages: int, is_first: bool = False) -> dict:
    return _entry(flow_id, timestamp, _MODEL, 1, messages, is_first, None)


def _continue(flow_id: str, timestamp: str, previous: str) -> dict:
    return _entry(flow_id, timestamp, _MODEL, 0, 2, False, previous)


def _entry(flow_id: str, timestamp: str, model: str, tools: int, messages: int, is_first: bool, previous) -> dict:
    return {
        "type": "forwarded_delta", "flow_id": flow_id, "timestamp": timestamp, "model": model,
        "is_first": is_first, "counts": {"system": 1, "tools": tools, "messages": messages},
        "system_delta": {}, "tools_delta": {}, "messages_delta": {},
        "diagnostics": {"previous_message_id": previous},
    }


def _forwarded_entries() -> list:
    return [
        _entry("h0", "2026-09-04T09:59:00Z", _HAIKU, 0, 1, True, None),
        _create("c1", "2026-09-04T10:00:00Z", 2, True),
        _continue("k1", "2026-09-04T10:00:20Z", "m1"),
        _continue("k2", "2026-09-04T10:03:30Z", "m2"),
        _create("c2", "2026-09-04T10:04:00Z", 6),
        _continue("k3", "2026-09-04T10:10:20Z", "m3"),
        _continue("k4", "2026-09-04T10:30:00Z", "m4"),
        _continue("k5", "2026-09-04T10:31:00Z", "m5"),
    ]


def _write_forwarded(entries: list) -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix="_forwarded.jsonl", delete=False)
    with handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return Path(handle.name)


def _timeline(entries: list = None) -> tuple:
    path = _write_forwarded(_forwarded_entries() if entries is None else entries)
    try:
        return request_boundaries(path, "sonnet"), continue_requests(path, "sonnet")
    finally:
        path.unlink()


def _assistant(request_id: str, timestamp: str) -> dict:
    usage = {"cache_read_input_tokens": 100, "cache_creation_input_tokens": 10, "input_tokens": 2, "output_tokens": 5}
    return {"type": "assistant", "requestId": request_id, "timestamp": timestamp,
            "message": {"usage": usage, "content": [{"type": "text", "text": "x"}]}}


def _prompt(text: str, timestamp: str) -> dict:
    return {"type": "user", "userType": "external", "timestamp": timestamp, "message": {"content": text}}


def _transcript_lines() -> list:
    return [
        _prompt("first prompt", "2026-09-04T09:59:59Z"),
        _assistant("r1", "2026-09-04T10:00:05Z"),
        _assistant("r2", "2026-09-04T10:00:25Z"),
        _assistant("r3", "2026-09-04T10:03:35Z"),
        _assistant("r4", "2026-09-04T10:04:10Z"),
        _prompt("second prompt", "2026-09-04T10:10:00Z"),
        _assistant("r5", "2026-09-04T10:10:25Z"),
        _assistant("r6", "2026-09-04T10:30:05Z"),
    ]


def _response_lines() -> list:
    flows = [("c1", "r1", 200), ("k1", "r2", 200), ("k2", "r3", 200), ("c2", "r4", 200),
             ("k3", "r5", 200), ("k4", "r6", 200), ("k5", "r7", 404)]
    return [{"flow_id": flow, "request_id": request_id, "status_code": status} for flow, request_id, status in flows]


def _write_projects(root: Path, transcript_lines: list) -> None:
    worktree = f"{_PROJECT_CWD}/.claude/worktrees/{_WORKER}"
    for name, cwd, lines in (
        ("-Users-fake-pane-project", _PROJECT_CWD, []),
        (f"-Users-fake-pane-project--claude-worktrees-{_WORKER}", worktree, transcript_lines),
    ):
        directory = root / name
        directory.mkdir(parents=True)
        records = [{"cwd": cwd}] + lines
        (directory / "22222222-2222-2222-2222-222222222222.jsonl").write_text(
            "\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n")


def _session(tmp_path: Path, responses: list = None) -> dict:
    response = tmp_path / "session_response.jsonl"
    response.write_text("\n".join(json.dumps(line) for line in (_response_lines() if responses is None else responses)) + "\n")
    stem = f"api_requests_worker_{_proxy_session_id_for_project(_PROJECT_CWD)}_{_WORKER}_1788400000"
    return {"stem": stem, "streams": {"response": response}}


def _numbered_view(transcript_lines: list = None, entries: list = None, responses: list = None) -> tuple:
    boundaries, continues = _timeline(entries)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        projects_root = tmp_path / "projects"
        _write_projects(projects_root, _transcript_lines() if transcript_lines is None else transcript_lines)
        session = _session(tmp_path, responses)
        numbering = build_session_numbering(session, boundaries, continues, projects_root)
    return session, boundaries, continues, numbering


def _render(gap=None, view: tuple = None) -> str:
    session, boundaries, continues, numbering = view or _numbered_view()
    stem = session["stem"]
    return render_reqs(
        [(session, boundaries)], 0, None, gap, {stem: numbering["usage"]}, False, False, {stem: []},
        {stem: continues}, {stem: numbering["pane_turns"]})


def _req_lines(text: str) -> list:
    return [line for line in text.split("\n") if line.startswith("REQ")]


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


def _folded_create_view() -> tuple:
    entries = [
        _create("b1", "2026-09-04T10:00:00Z", 2, True),
        _create("b2", "2026-09-04T10:05:00Z", 6),
        _create("b3", "2026-09-04T10:19:00Z", 6),
        _create("b4", "2026-09-04T10:20:20Z", 9),
    ]
    transcript = [
        _prompt("only prompt", "2026-09-04T09:59:59Z"),
        _assistant("r1", "2026-09-04T10:00:05Z"),
        _assistant("r3", "2026-09-04T10:20:10Z"),
        _assistant("r4", "2026-09-04T10:23:40Z"),
    ]
    responses = [{"flow_id": flow, "request_id": request_id, "status_code": 200}
                 for flow, request_id in (("b1", "r1"), ("b2", "r2"), ("b3", "r3"), ("b4", "r4"))]
    return _numbered_view(transcript, entries, responses)


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


def _second_session() -> tuple:
    entries = [_create("z1", "2026-09-04T11:00:00Z", 2, True), _create("z2", "2026-09-04T11:00:30Z", 5)]
    path = _write_forwarded(entries)
    try:
        boundaries = request_boundaries(path, "sonnet")
    finally:
        path.unlink()
    return {"stem": "api_requests_opus_other_1788500000"}, boundaries


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


def _use(tool_id: str) -> dict:
    return {"role": "assistant", "content": [{"type": "tool_use", "id": tool_id, "name": "Bash", "input": {}}]}


def _result(tool_id: str) -> dict:
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}]}


def _reminder() -> dict:
    return {"role": "system", "content": "reminder"}


def _ownership_payload() -> list:
    return [
        {"role": "user", "content": "go"},
        _use("t1"), _result("t1"), _reminder(),
        _use("t2"), _result("t2"), _reminder(),
        _use("t3"), _result("t3"), _reminder(),
        _use("t4"), _result("t4"), _reminder(),
    ]


def _continue_with(flow_id: str, timestamp: str, previous: str, first_msg) -> dict:
    entry = _continue(flow_id, timestamp, previous)
    entry["messages_delta"] = {"0": first_msg}
    return entry


def _ownership_view() -> tuple:
    entries = [
        _create("c1", "2026-09-04T10:00:00Z", 1, True),
        _continue_with("k1", "2026-09-04T10:01:00Z", "m1", _result("t1")),
        _continue_with("k2", "2026-09-04T10:02:00Z", "m2", _result("t2")),
        _create("c2", "2026-09-04T10:03:00Z", 9),
        _continue_with("k3", "2026-09-04T10:04:00Z", "m3", _result("t4")),
        _continue_with("k4", "2026-09-04T10:05:00Z", "m4", {"role": "user", "content": "next prompt"}),
        _continue_with("k5", "2026-09-04T10:06:00Z", "m5", _result("t99")),
    ]
    transcript = [
        _prompt("go", "2026-09-04T09:59:59Z"),
        _assistant("r1", "2026-09-04T10:00:05Z"),
        _assistant("r2", "2026-09-04T10:01:05Z"),
        _assistant("r3", "2026-09-04T10:02:05Z"),
        _assistant("r4", "2026-09-04T10:03:05Z"),
        _assistant("r5", "2026-09-04T10:04:05Z"),
        _assistant("r6", "2026-09-04T10:05:05Z"),
    ]
    flows = [("c1", "r1", 200), ("k1", "r2", 200), ("k2", "r3", 200), ("c2", "r4", 200),
             ("k3", "r5", 200), ("k4", "r6", 200), ("k5", "r7", 404)]
    responses = [{"flow_id": f, "request_id": r, "status_code": c} for f, r, c in flows]
    boundaries, continues = _timeline(entries)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        projects_root = tmp_path / "projects"
        _write_projects(projects_root, transcript)
        session = _session(tmp_path, responses)
        numbering = build_session_numbering(session, boundaries, continues, projects_root, messages=_ownership_payload())
    return session, boundaries, continues, numbering


def test_msg_start_of_creates_and_continues() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    starts = {r["flow_id"]: r.get("msg_start") for r in numbering["requests"]}
    check("each located request starts at the assistant reply it answers: c1 0, k1 1, k2 4, c2 7, k3 10",
          starts == {"c1": 0, "k1": 1, "k2": 4, "c2": 7, "k3": 10, "k4": None, "k5": None}, starts)
    markers = request_markers(numbering["requests"])
    check("markers carry the pane numbers 1..5 at those starts",
          {index: m["number"] for index, m in markers.items()} == {0: 1, 1: 2, 4: 3, 7: 4, 10: 5}, markers)


def test_req_range_covers_own_group_and_next() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    check("--req 2 (a continue) = its own group [1..3] plus the next request's group [4..6], the tool_use it caused sits at msg 4",
          resolve_req_range_with_next(requests, 2, 2, 12) == (1, 6), resolve_req_range_with_next(requests, 2, 2, 12))
    check("--req 3 reaches the create's group that follows: msgs 4..9",
          resolve_req_range_with_next(requests, 3, 3, 12) == (4, 9))
    check("--req 4 (a create) = its group [7..9] plus the next continue's group [10..12]",
          resolve_req_range_with_next(requests, 4, 4, 12) == (7, 12))
    check("--req 5 whose successor owns nothing = its own group only", resolve_req_range_with_next(requests, 5, 5, 12) == (10, 12))
    check("--req 2 3 spans both groups plus the group after: msgs 1..9", resolve_req_range_with_next(requests, 2, 3, 12) == (1, 9))
    data = {"boundaries": boundaries, "continues": continues, "requests": requests}
    check("the command layer routes transcript numbering to the with-next rule",
          _resolve_range(data, numbering, 2, 2, 12) == (1, 6))


def test_unlocated_continues_own_no_msgs() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    raised = False
    try:
        resolve_req_range_with_next(requests, 6, 6, 12)
    except UnknownRequestNumberError:
        raised = True
    check("the opener continue (REQ 6, no tool_result to locate) owns no msgs", raised)
    data = {"boundaries": boundaries, "continues": continues, "requests": requests}
    text = _req_error_text(UnknownRequestNumberError("x"), data, (6, 6))
    check("the message names it a continue whose msgs could not be located", "could not be located" in text and "REQ 6" in text, text)
    unknown = False
    try:
        resolve_req_range_with_next(requests, 99, 99, 12)
    except UnknownRequestNumberError:
        unknown = True
    check("a number outside the recorded requests stays 'not found'", unknown)


def test_msgs_prints_continue_separators() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    turns = [{"index": i, "role": m["role"], "type": "text", "chars": 4,
              "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": ""}]}
             for i, m in enumerate(_ownership_payload())]
    out = render_msgs({"boundaries": boundaries, "requests": numbering["requests"], "turns": turns}, 1, 6, numbering["usage"])
    seps = [line for line in out.split("\n") if line.startswith("── REQ")]
    check("msgs 1..6 print the continue separators REQ 2 and REQ 3 with their response-end times",
          [x.split()[2] for x in seps] == ["2", "3"] and _clock("2026-09-04T10:01:05Z") in seps[0] and _clock("2026-09-04T10:02:05Z") in seps[1], seps)
    check("the tool_use msg 4 sits under REQ 3's separator", out.index("── REQ 3") < out.index("[  4]"), out)


def _raises_text(call) -> str:
    try:
        call()
    except UnknownRequestNumberError as exc:
        return str(exc)
    return ""


def test_expand_req_selects_reply_and_returned_result() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    check("expand --req 1 (a create) = the next request's group: reply msg 1 plus the result that came back",
          resolve_req_output_range(requests, 1, 12) == (1, 3), resolve_req_output_range(requests, 1, 12))
    check("expand --req 2 (a continue) = msgs 4..6, the tool_use it produced and the tool_result REQ 3 sent",
          resolve_req_output_range(requests, 2, 12) == (4, 6))
    check("expand --req 3 = msgs 7..9 (the next request is a create)", resolve_req_output_range(requests, 3, 12) == (7, 9))
    check("expand --req 4 = msgs 10..12", resolve_req_output_range(requests, 4, 12) == (10, 12))
    data = {"requests": requests}
    check("the command layer resolves the same window on the transcript path",
          _req_output_window(data, numbering, 2, 12) == (4, 6))


def test_expand_req_errors_and_cli() -> None:
    _session_dict, boundaries, continues, numbering = _ownership_view()
    requests = numbering["requests"]
    text = _raises_text(lambda: resolve_req_output_range(requests, 5, 12))
    check("REQ 5: the next request is an unlocated opener -> 'could not be located'", "could not be located" in text and "REQ 6" in text, text)
    text = _raises_text(lambda: resolve_req_output_range(requests, 6, 12))
    check("the last request's reply is not recorded", "reply is not recorded" in text, text)
    check("an unknown number stays 'not found'", _raises_text(lambda: resolve_req_output_range(requests, 99, 12)) == "REQ 99 not found")
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        window = _req_output_window({"requests": requests}, {"path": "boundaries"}, 2, 12)
    check("without the transcript path expand --req refuses and says why", window is None and "transcript numbering" in buffer.getvalue(), buffer.getvalue())
    by_req = _parse_args(["expand", "s", "--req", "3"], "")
    by_msg = _parse_args(["expand", "s", "5"], "")
    check("argparse: --req replaces the msg argument, a bare msg still parses",
          (by_req.msg, by_req.req) == (None, 3) and (by_msg.msg, by_msg.req) == (5, None), (by_req, by_msg))
    out = render_expand_full({"turns": [{}] * 13, "turn_times": {}, "session": {"stem": "s", "project": "p", "start": "2026-09-04T10:00:00Z"}},
                             None, 4, 6, "", [], None, "what REQ 2 produced")
    check("the header names the REQ instead of an anchor msg", "what REQ 2 produced" in out and "anchor" not in out, out)


def _unmapped_turn_view() -> tuple:
    entries = [
        _create("f1", "2026-09-04T10:00:00Z", 2, True),
        _continue("u1", "2026-09-04T10:20:01Z", "m1"),
        _create("f2", "2026-09-04T10:20:03Z", 6),
        _continue("k1", "2026-09-04T10:21:00Z", "m2"),
        _continue("u2", "2026-09-04T10:25:00Z", "m3"),
        _continue("k2", "2026-09-04T10:25:05Z", "m4"),
    ]
    transcript = [
        _prompt("first", "2026-09-04T09:59:59Z"),
        _assistant("r1", "2026-09-04T10:00:05Z"),
        _prompt("second", "2026-09-04T10:20:00Z"),
        _assistant("r2", "2026-09-04T10:20:20Z"),
        _assistant("r3", "2026-09-04T10:21:10Z"),
        _assistant("r4", "2026-09-04T10:25:15Z"),
    ]
    flows = [("f1", "r1", 200), ("u1", "rx1", 404), ("f2", "r2", 200), ("k1", "r3", 200),
             ("u2", "rx2", 404), ("k2", "r4", 200)]
    responses = [{"flow_id": f, "request_id": r, "status_code": c} for f, r, c in flows]
    return _numbered_view(transcript, entries, responses)


def _render_filtered(view: tuple, turn=None, gap=None) -> str:
    session, boundaries, continues, numbering = view
    stem = session["stem"]
    return render_reqs(
        [(session, boundaries)], 0, turn, gap, {stem: numbering["usage"]}, False, False, {stem: []},
        {stem: continues}, {stem: numbering["pane_turns"]})


def test_unmapped_req_sits_in_its_turn_by_send_time() -> None:
    view = _unmapped_turn_view()
    out = _render_filtered(view)
    lines = [l for l in out.split("\n") if l.startswith("REQ") or l.startswith("── turn")]
    kinds = [l.split()[1] if l.startswith("REQ") else "T" + l.split()[2] for l in lines]
    check("both rejected attempts sit inside turn 2, before/among the mapped REQs of that turn",
          kinds == ["T1", "1", "T2", "?", "2", "3", "?", "4"], lines)
    turn2 = next(l for l in lines if l.startswith("── turn 2"))
    check("the separator shows the prompt time 10:20:00, not the first REQ's time",
          f"turn 2  {_clock('2026-09-04T10:20:00Z')}  " in turn2 and _clock("2026-09-04T10:20:01Z") not in turn2, turn2)
    check("the span still runs from the first to the last REQ of the turn (10:20:01 -> 10:25:15)", "5m14s" in turn2, turn2)
    only_turn_2 = _render_filtered(view, turn=2)
    check("--turn 2 keeps the REQ ? rows of that turn", only_turn_2.count("REQ ?") == 2 and "── turn 1" not in only_turn_2, only_turn_2)


def test_unmapped_req_stays_out_of_gap_pairs() -> None:
    out = _render_filtered(_unmapped_turn_view(), gap=2)
    lines = [l for l in out.split("\n") if l.startswith("REQ")]
    check("--gap 2 pairs the numbered REQs 3 -> 4 (4m05s) and never lists a REQ ?", [l.split()[1] for l in lines] == ["3", "4"], lines)


if __name__ == "__main__":
    test_reqs_pane_numbering_workflow()
