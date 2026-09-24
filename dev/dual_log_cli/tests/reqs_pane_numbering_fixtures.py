# INFRASTRUCTURE

import json
import tempfile
from pathlib import Path

from src.dual_log_cli.numbering import build_session_numbering
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_reqs import render_reqs
from src.dual_log_cli.timeline_boundaries import continue_requests, request_boundaries
from src.proxy_display.forwarded_parser import _proxy_session_id_for_project

PASS_LIST = []
FAIL_LIST = []

_PROJECT_CWD = "/Users/fake/pane-project"
_WORKER = "fake-worker"
_MODEL = "claude-sonnet-5"
_HAIKU = "claude-haiku-4-5-20251001"


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


def _second_session() -> tuple:
    entries = [_create("z1", "2026-09-04T11:00:00Z", 2, True), _create("z2", "2026-09-04T11:00:30Z", 5)]
    path = _write_forwarded(entries)
    try:
        boundaries = request_boundaries(path, "sonnet")
    finally:
        path.unlink()
    return {"stem": "api_requests_opus_other_1788500000"}, boundaries


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
