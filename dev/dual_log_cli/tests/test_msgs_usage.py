# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_msgs import render_msgs
from src.dual_log_cli.usage import build_usage_by_flow, _find_transcript
from src.proxy_display.forwarded_parser import _proxy_session_id_for_project

PASS_LIST = []
FAIL_LIST = []

# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))

def _local_clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")

def _msg(index: int, role: str, chars: int, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": chars, "blocks": blocks}

def _block(type_: str, chars: int) -> dict:
    return {"label": type_, "type": type_, "chars": chars, "sig_chars": 0, "preview": ""}

def _boundary(start_index: int, message_count: int, timestamp: str, flow_id: str) -> dict:
    return {"start_index": start_index, "message_count": message_count, "timestamp": timestamp,
            "flow_id": flow_id, "restart": False}

def _write_fake_transcript(projects_root: Path, dir_name: str, cwd: str, records: list) -> Path:
    project_dir = projects_root / dir_name
    project_dir.mkdir(parents=True)
    transcript_path = project_dir / "11111111-1111-1111-1111-111111111111.jsonl"
    lines = [{"cwd": cwd}]
    for request_id, cache_read, cache_creation in records:
        lines.append({"type": "assistant", "requestId": request_id,
                      "message": {"usage": {"cache_read_input_tokens": cache_read,
                                             "cache_creation_input_tokens": cache_creation}}})
    transcript_path.write_text(
        "\n".join(json.dumps(line, separators=(",", ":")) for line in lines) + "\n"
    )
    return transcript_path

def test_separator_shows_resolved_usage() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-02T16:41:13Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got = render_msgs(data, 0, 0, usage_by_flow={"f0": (9096, 1928)})
    expected = f"── REQ 1  {_local_clock('2026-09-02T16:41:13Z')}  CR 9,096  CC 1,928 ──\n[  0] user  text                    4c\n"
    check("resolved usage renders CR/CC in the right spot", got == expected, got)

def test_separator_omits_unresolved_usage() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-02T16:41:13Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got = render_msgs(data, 0, 0, usage_by_flow={"other-flow": (1, 2)})
    check("unresolved usage keeps the plain separator",
          got.startswith(f"── REQ 1  {_local_clock('2026-09-02T16:41:13Z')} ──\n"), got)
    check("unresolved usage carries no CR/CC/placeholder", "CR" not in got and "CC" not in got, got)

def test_separator_default_unchanged() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-02T09:00:00Z", "f0")],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got = render_msgs(data, 0, 0)
    check("default (no usage map) separator unchanged",
          got.startswith(f"── REQ 1  {_local_clock('2026-09-02T09:00:00Z')} ──\n"), got)

def test_refire_suffix_stays_outside_usage() -> None:
    data = {
        "boundaries": [
            _boundary(0, 0, "2026-09-02T10:00:00Z", "f0"),
            _boundary(0, 1, "2026-09-02T10:00:05Z", "f1"),
        ],
        "turns": [_msg(0, "user", 4, [_block("text", 4)])],
    }
    got = render_msgs(data, 0, 0, usage_by_flow={"f1": (100, 200)})
    expected_line = f"── REQ 1  {_local_clock('2026-09-02T10:00:05Z')}  CR 100  CC 200 ──  (+1 re-fire)"
    check("re-fire suffix sits after usage, outside the '──'", got.startswith(expected_line), got)

def test_find_transcript_scopes_to_directories_and_mtime() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        inside = _write_fake_transcript(tmp_path, "-in-scope", "/Users/fake/inscope",
                                        [("req_AAA", 500, 25)])
        outside = _write_fake_transcript(tmp_path, "-out-of-scope", "/Users/fake/outscope",
                                         [("req_AAA", 999, 999)])

        found = _find_transcript("req_AAA", [inside.parent])
        check("match found within the given directory", found == inside, found)

        found_excluded = _find_transcript("req_AAA", [outside.parent.parent / "nonexistent"])
        check("no match outside the given directories", found_excluded is None, found_excluded)

        far_future = 9_999_999_999.0
        found_by_mtime = _find_transcript("req_AAA", [inside.parent], since_epoch=far_future)
        check("mtime cutoff excludes a file older than the session start",
              found_by_mtime is None, found_by_mtime)

def test_build_usage_by_flow_main_stem() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        response_path = tmp_path / "session_response.jsonl"
        response_path.write_text("\n".join(json.dumps(line) for line in [
            {"flow_id": "f0", "request_id": "req_AAA", "status_code": 200},
            {"flow_id": "f1", "request_id": "req_BBB", "status_code": 400},
        ]) + "\n")

        projects_root = tmp_path / "projects"
        _write_fake_transcript(projects_root, "-Users-fake-fakeproject", "/Users/fake/fakeproject",
                               [("req_AAA", 500, 25), ("req_BBB", 999, 999)])

        session = {"stem": "api_requests_opus_fakeproject_1788367120",
                   "streams": {"response": response_path}}
        boundaries = [
            _boundary(0, 1, "2026-01-01T00:00:00Z", "f0"),
            _boundary(1, 2, "2026-01-01T00:00:05Z", "f1"),
        ]
        result = build_usage_by_flow(session, boundaries, projects_root=projects_root)

        check("200-status flow resolves to its transcript usage", result.get("f0") == (500, 25), result)
        check("400-status flow is dropped despite a resolvable request id", "f1" not in result, result)

def test_build_usage_by_flow_worker_stem() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        response_path = tmp_path / "session_response.jsonl"
        response_path.write_text(json.dumps({"flow_id": "f0", "request_id": "req_CCC", "status_code": 200}) + "\n")

        project_cwd = "/Users/fake/monitor-cc"
        sid = _proxy_session_id_for_project(project_cwd)
        worktree_cwd = f"{project_cwd}/.claude/worktrees/some-worker"

        projects_root = tmp_path / "projects"
        _write_fake_transcript(projects_root, "-Users-fake-monitor-cc", project_cwd, [])
        _write_fake_transcript(projects_root, "-Users-fake-monitor-cc--claude-worktrees-some-worker",
                               worktree_cwd, [("req_CCC", 700, 70)])

        session = {"stem": f"api_requests_worker_{sid}_some-worker_1788400000",
                   "streams": {"response": response_path}}
        boundaries = [_boundary(0, 1, "2026-01-01T00:00:00Z", "f0")]
        result = build_usage_by_flow(session, boundaries, projects_root=projects_root)

        check("worker stem resolves through sid8 -> cwd -> worktree cwd", result.get("f0") == (700, 70), result)

def test_build_usage_by_flow_degrades_cleanly() -> None:
    check("empty boundaries -> {}", build_usage_by_flow({"streams": {}}, []) == {})
    check("missing _response stream -> {}",
          build_usage_by_flow({"streams": {}}, [_boundary(0, 1, "t", "f0")]) == {})

# ORCHESTRATOR

def test_msgs_usage_workflow() -> None:
    test_separator_shows_resolved_usage()
    test_separator_omits_unresolved_usage()
    test_separator_default_unchanged()
    test_refire_suffix_stays_outside_usage()
    test_find_transcript_scopes_to_directories_and_mtime()
    test_build_usage_by_flow_main_stem()
    test_build_usage_by_flow_worker_stem()
    test_build_usage_by_flow_degrades_cleanly()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")

if __name__ == "__main__":
    test_msgs_usage_workflow()
