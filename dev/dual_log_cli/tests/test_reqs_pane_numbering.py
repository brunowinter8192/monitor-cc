# INFRASTRUCTURE

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.commands import _report_numbering_paths, _req_error_text
from src.dual_log_cli.numbering import build_session_numbering
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.render_reqs import render_reqs
from src.dual_log_cli.timeline_boundaries import continue_requests, request_boundaries
from src.dual_log_cli.timeline_markers import UnknownRequestNumberError, request_markers, resolve_req_range
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


def _timeline() -> tuple:
    path = _write_forwarded(_forwarded_entries())
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


def _session(tmp_path: Path) -> dict:
    response = tmp_path / "session_response.jsonl"
    response.write_text("\n".join(json.dumps(line) for line in _response_lines()) + "\n")
    stem = f"api_requests_worker_{_proxy_session_id_for_project(_PROJECT_CWD)}_{_WORKER}_1788400000"
    return {"stem": stem, "streams": {"response": response}}


def _numbered_view(transcript_lines: list = None) -> tuple:
    boundaries, continues = _timeline()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        projects_root = tmp_path / "projects"
        _write_projects(projects_root, _transcript_lines() if transcript_lines is None else transcript_lines)
        session = _session(tmp_path)
        numbering = build_session_numbering(session, boundaries, continues, projects_root)
    return session, boundaries, continues, numbering


def _render(gap=None) -> str:
    session, boundaries, continues, numbering = _numbered_view()
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


if __name__ == "__main__":
    test_reqs_pane_numbering_workflow()
