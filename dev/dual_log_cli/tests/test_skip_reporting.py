# INFRASTRUCTURE

import argparse
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli import commands, diagnostics
from src.dual_log_cli.commands import _report_numbering_paths
from src.dual_log_cli.project_map import build_project_index
from src.dual_log_cli.reader import load_last_request, local_datetime
from src.dual_log_cli.render_reqs import _entries_for_session
from src.dual_log_cli.usage import resolve_transcript

PASS_LIST = []
FAIL_LIST = []

# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))

def _stderr_of(fn, *args) -> tuple:
    buffer = io.StringIO()
    with redirect_stderr(buffer):
        result = fn(*args)
    return result, buffer.getvalue()

def _raises(exc_type, fn, *args) -> bool:
    try:
        fn(*args)
    except exc_type:
        return True
    return False

def test_report_skip_dedup() -> None:
    diagnostics._reported.clear()
    _, text = _stderr_of(lambda: (diagnostics.report_skip("s", "t", "r"), diagnostics.report_skip("s", "t", "r")))
    check("report_skip prints one identical line once", text == "s: t: r\n", text)

def test_project_map_reports() -> None:
    diagnostics._reported.clear()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "-tmp-proj"
        project.mkdir()
        (project / "a.jsonl").write_text('{"cwd": broken\n', encoding="utf-8")
        index, text = _stderr_of(build_project_index, root)
        check("a transcript with a malformed cwd line is reported and skipped",
              index["cwd_to_dir"] == {} and "a.jsonl" in text and "JSONDecodeError" in text, text)
        diagnostics._reported.clear()
        _, missing = _stderr_of(build_project_index, root / "absent")
        check("a missing projects root is reported", "absent" in missing and "FileNotFoundError" in missing, missing)

def test_load_last_request_reports_malformed_line() -> None:
    diagnostics._reported.clear()
    entry = {"model": "claude-sonnet-5", "payload": {"tools": [{"name": "Bash"}], "messages": []}}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x_original.jsonl"
        path.write_text(json.dumps(entry) + "\n" + '{"model": "claude-sonnet-5", "payload": {"tools": [\n', encoding="utf-8")
        result, text = _stderr_of(load_last_request, path)
    check("a malformed last line is reported and the earlier request is returned",
          result[0] == entry and result[2] == 1 and "malformed line skipped" in text, text)

def test_resolve_transcript_reasons() -> None:
    boundaries = [{"flow_id": "f1", "timestamp": "2026-09-04T10:00:00Z"}]
    with tempfile.TemporaryDirectory() as tmp:
        response = Path(tmp) / "r.jsonl"
        response.write_text(json.dumps({"flow_id": "other", "request_id": "req_1", "status_code": 200}) + "\n", encoding="utf-8")
        reasons = {
            "no requests": resolve_transcript({"streams": {}}, [])[2],
            "no _response stream": resolve_transcript({"streams": {}}, boundaries)[2],
            "no request id in _response for any request": resolve_transcript({"streams": {"response": response}}, boundaries)[2],
            "_response unreadable": resolve_transcript({"streams": {"response": Path(tmp) / "gone.jsonl"}}, boundaries)[2],
        }
    for expected, actual in reasons.items():
        check(f"resolve_transcript names the reason: {expected}", actual is not None and actual.startswith(expected), actual)

def test_numbering_line_carries_reason() -> None:
    _, text = _stderr_of(_report_numbering_paths, {"a": {"path": "transcript"}, "b": {"path": "boundaries", "reason": "no _response stream"}})
    check("the numbering line names the fallback stem with its reason", "b (no _response stream)" in text, text)

def test_timestamps() -> None:
    check("local_datetime of an empty timestamp is None", local_datetime("") is None)
    check("local_datetime of an unparseable timestamp raises", _raises(ValueError, local_datetime, "garbage"))
    marker = {"timestamp": "", "clock_timestamp": ""}
    check("a REQ marker without a timestamp raises instead of vanishing",
          _raises(ValueError, _entries_for_session, {0: marker}, {}, {}, "stem"))

def test_command_skip_paths() -> None:
    diagnostics._reported.clear()
    original_load, original_list = commands.load_timeline, commands.list_sessions
    commands.list_sessions = lambda _dir: [{"stem": "s_missing"}, {"stem": "s_valueerror"}]
    args = argparse.Namespace(term="x", case_sensitive=False, only=None, scope="", since="", until="")

    def load(session):
        if session["stem"] == "s_missing":
            raise FileNotFoundError("no _original stream for s_missing")
        raise ValueError("no non-haiku request line in s_valueerror")

    commands.load_timeline = load
    try:
        buffer_out = io.StringIO()
        with redirect_stdout(buffer_out):
            code, text = _stderr_of(commands._run_search, Path("."), args)
        check("search skips FileNotFoundError and ValueError with stem and reason on stderr",
              code == 0 and "timeline: s_missing: FileNotFoundError" in text and "timeline: s_valueerror: ValueError" in text
              and "2 sessions skipped" in buffer_out.getvalue(), text)

        def load_type_error(session):
            raise TypeError("real bug")

        commands.load_timeline = load_type_error
        check("search lets an unexpected exception propagate", _raises(TypeError, commands._run_search, Path("."), args))
    finally:
        commands.load_timeline, commands.list_sessions = original_load, original_list

# ORCHESTRATOR

def test_skip_reporting_workflow() -> None:
    test_report_skip_dedup()
    test_project_map_reports()
    test_load_last_request_reports_malformed_line()
    test_resolve_transcript_reasons()
    test_numbering_line_carries_reason()
    test_timestamps()
    test_command_skip_paths()
    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_skip_reporting_workflow()
