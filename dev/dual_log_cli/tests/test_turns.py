"""
Regression suite for `duallog turns` (src/dual_log_cli/timeline.py's `_is_turn_opener`/
`turn_openers`/`_turn_preview`/`build_turn_rows`, src/dual_log_cli/usage.py's
`_transcript_stream_ends`/`build_request_times_by_flow`, and src/dual_log_cli/render.py's
`render_turns`/`_fmt_duration`/`_fmt_tokens`).

Covers: turn-opener classification (a `user` msg with a `text` block and no `tool_result` block
opens a turn; a tool_result-carrying user msg, an assistant msg, and a str-content pseudo-block
msg — e.g. `system-reminder` — do not); the preview is the LAST `text`-type block of the opener,
not the first (a spawn-prompt-shaped fixture: a leading `<system-reminder>`-wrapped block ahead of
the real prompt); the turn-ASSIGNMENT regression this milestone's own investigation found — a
request whose msg-index KEY (`start_index`) sits before the next opener but whose OWN
`message_count` already reaches past it belongs to the NEXT turn, not the one its key would
naively suggest; per-turn duration/model/tool/token arithmetic over a multi-request turn, with the
turn's LAST request contributing no tool time; the three `?`-gating conditions (empty
`times_by_flow` for the whole session, one request's flow absent from it, an unparseable stream-end
timestamp) collapsing a turn's four numeric columns to `None` while the request count and preview
still print; `_transcript_stream_ends`'s last-record-timestamp / first-record-output-tokens rule;
`build_request_times_by_flow` end to end against a fixture `~/.claude/projects/`-shaped tree; and
`_fmt_duration`'s three duration bands plus its "?" passthrough.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_turns.py

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
from src.dual_log_cli.render import _fmt_duration, _fmt_tokens, render_turns
from src.dual_log_cli.timeline import (
    _is_turn_opener,
    _turn_preview,
    build_turn_rows,
    request_boundaries,
    turn_openers,
)
from src.dual_log_cli.usage import _transcript_stream_ends, build_request_times_by_flow

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


def _block(type_: str, preview: str = "") -> dict:
    return {"label": type_, "type": type_, "chars": 10, "sig_chars": 0, "preview": preview}


def _turn(index: int, role: str, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": 10, "blocks": blocks}


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


def _boundaries(entries: list) -> list:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        path = Path(fh.name)
    try:
        return request_boundaries(path, "sonnet")
    finally:
        path.unlink()


# --- turn-opener classification -------------------------------------------------------------

def test_opener_classification() -> None:
    opener = _turn(0, "user", [_block("text", "hello")])
    tool_result_only = _turn(1, "user", [_block("tool_result")])
    text_plus_tool_result = _turn(2, "user", [_block("text", "hi"), _block("tool_result")])
    assistant_text = _turn(3, "assistant", [_block("text", "reply")])
    system_reminder_pseudo = _turn(4, "user", [_block("system-reminder", "<system-reminder>")])

    check("plain user text opens a turn", _is_turn_opener(opener))
    check("a tool_result-only user msg does not", not _is_turn_opener(tool_result_only))
    check("a user msg carrying BOTH text and tool_result does not",
          not _is_turn_opener(text_plus_tool_result))
    check("an assistant text msg does not (wrong role)", not _is_turn_opener(assistant_text))
    check("a system-reminder pseudo-block msg does not (no literal 'text' type)",
          not _is_turn_opener(system_reminder_pseudo))

    turns = [opener, tool_result_only, text_plus_tool_result, assistant_text, system_reminder_pseudo]
    check("turn_openers keeps only msg 0", turn_openers(turns) == [0], turn_openers(turns))


# --- preview: last text block wins, not first ------------------------------------------------

def test_preview_uses_last_text_block() -> None:
    spawn_prompt = _turn(0, "user", [_block("text", "<system-reminder>"), _block("text", "You are a WORKER.")])
    check("preview is the LAST text block, not the reminder wrapper",
          _turn_preview(spawn_prompt) == "You are a WORKER.", _turn_preview(spawn_prompt))

    single_block = _turn(1, "user", [_block("text", "recap")])
    check("a single text block is trivially its own preview", _turn_preview(single_block) == "recap")

    no_text = _turn(2, "user", [_block("tool_result")])
    check("no text block at all -> empty preview", _turn_preview(no_text) == "")


# --- the turn-assignment regression: message_count decides, not the marker's msg-index key ---

def test_assignment_uses_message_count_not_start_index() -> None:
    # opener1 at msg 0, opener2 at msg 5. req3's OWN start_index (4) sits before opener2 (5), but
    # its message_count (7) already reaches past it -- it must land in turn 2, not turn 1, exactly
    # the reldist-power bug this milestone's investigation found (an idle text reply bundled
    # together with the next prompt in one send).
    turns = [
        _turn(0, "user", [_block("text", "start")]),
        _turn(1, "assistant", [_block("text", "hi")]),
        _turn(2, "user", [_block("tool_result")]),
        _turn(3, "assistant", [_block("text", "done, going idle")]),
        _turn(4, "system", [_block("system")]),
        _turn(5, "user", [_block("text", "next prompt")]),
        _turn(6, "assistant", [_block("thinking")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),   # req1: start=0, count=1
        _delta_entry("f2", "2026-09-06T10:00:05Z", 4),                  # req2: start=1, count=4
        _delta_entry("f3", "2026-09-06T10:05:00Z", 7),                  # req3: start=4, count=7
    ])
    rows = build_turn_rows(turns, boundaries, {})
    check("two turns produced", len(rows) == 2, rows)
    check("turn 1 gets exactly req1+req2 (2 requests)", rows[0]["requests"] == 2, rows[0])
    check("turn 2 gets exactly req3 (1 request), NOT grouped by its start_index",
          rows[1]["requests"] == 1, rows[1])


# --- duration / model / tool arithmetic over a multi-request turn ---------------------------

def test_duration_model_tool_arithmetic() -> None:
    turns = [_turn(0, "user", [_block("text", "go")])]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T10:01:00Z", 2),
        _delta_entry("f3", "2026-09-06T10:02:00Z", 3),
    ])
    times_by_flow = {
        "f1": ("2026-09-06T10:00:20Z", 100),   # model 20s, tool (next send - this end) = 40s
        "f2": ("2026-09-06T10:01:10Z", 200),   # model 10s, tool = 50s
        "f3": ("2026-09-06T10:02:30Z", 300),   # model 30s, LAST request -> no tool time
    }
    rows = build_turn_rows(turns, boundaries, times_by_flow)
    row = rows[0]
    check("duration is last stream-end minus first send (150s)", row["duration"] == 150.0, row)
    check("model time sums each request's own stream time (60s)", row["model_time"] == 60.0, row)
    check("tool time sums inter-request gaps, excluding the last request (90s)",
          row["tool_time"] == 90.0, row)
    check("tokens sum across all three requests (600)", row["tokens"] == 600, row)
    check("request count is 3", row["requests"] == 3, row)
    check("clock is the FIRST request's own send timestamp",
          row["timestamp"] == "2026-09-06T10:00:00Z", row)


# --- "?" gating: whole-session join failure, one request's flow unresolved, and a bad timestamp

def test_unresolved_turn_shows_question_marks_but_keeps_count_and_clock() -> None:
    turns = [_turn(0, "user", [_block("text", "go")])]
    boundaries = _boundaries([_delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True)])

    empty_join = build_turn_rows(turns, boundaries, {})[0]
    check("empty times_by_flow -> duration/model/tool/tokens all None",
          empty_join["duration"] is None and empty_join["model_time"] is None
          and empty_join["tool_time"] is None and empty_join["tokens"] is None, empty_join)
    check("request count and clock still print when unresolved",
          empty_join["requests"] == 1 and empty_join["timestamp"] == "2026-09-06T10:00:00Z", empty_join)

    turns_two_req = [_turn(0, "user", [_block("text", "go")])]
    boundaries_two_req = _boundaries([
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T10:01:00Z", 2),
    ])
    # f1 resolves, f2 does not -- the whole turn must still go "?", not a partial sum over f1 alone
    partial = build_turn_rows(turns_two_req, boundaries_two_req, {"f1": ("2026-09-06T10:00:10Z", 50)})[0]
    check("one unresolved request in the turn makes the WHOLE turn '?'",
          partial["duration"] is None and partial["tokens"] is None, partial)
    check("request count still reflects both requests (2), not just the resolved one",
          partial["requests"] == 2, partial)


# --- usage.py's new transcript join -----------------------------------------------------------

def _write_fake_assistant_transcript(projects_root: Path, dir_name: str, cwd: str, records: list) -> Path:
    project_dir = projects_root / dir_name
    project_dir.mkdir(parents=True)
    transcript_path = project_dir / "22222222-2222-2222-2222-222222222222.jsonl"
    lines = [{"cwd": cwd}]
    for request_id, timestamp, output_tokens in records:
        lines.append({"type": "assistant", "requestId": request_id, "timestamp": timestamp,
                      "message": {"usage": {"output_tokens": output_tokens}}})
    transcript_path.write_text(
        "\n".join(json.dumps(line, separators=(",", ":")) for line in lines) + "\n"
    )
    return transcript_path


def test_transcript_stream_ends_keeps_last_timestamp_first_tokens() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_fake_assistant_transcript(Path(tmp), "-x", "/x", [
            ("req_A", "2026-09-06T10:00:00.100Z", 50),
            ("req_A", "2026-09-06T10:00:00.300Z", 999),   # same rid: ts overwritten, tokens NOT
            ("req_B", "2026-09-06T10:00:05.000Z", 30),
        ])
        ends = _transcript_stream_ends(path)
        check("timestamp is the LAST record's for a repeated requestId",
              ends["req_A"][0] == "2026-09-06T10:00:00.300Z", ends)
        check("output_tokens is the FIRST record's, never overwritten by a later one",
              ends["req_A"][1] == 50, ends)
        check("a single-record id resolves normally", ends["req_B"] == ["2026-09-06T10:00:05.000Z", 30], ends)


def test_build_request_times_by_flow_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        response_path = tmp_path / "session_response.jsonl"
        response_path.write_text("\n".join(json.dumps(line) for line in [
            {"flow_id": "f0", "request_id": "req_AAA", "status_code": 200},
            {"flow_id": "f1", "request_id": "req_BBB", "status_code": 400},
        ]) + "\n")

        projects_root = tmp_path / "projects"
        _write_fake_assistant_transcript(projects_root, "-Users-fake-fakeproject", "/Users/fake/fakeproject", [
            ("req_AAA", "2026-01-01T00:00:10Z", 1234),
            ("req_BBB", "2026-01-01T00:00:20Z", 5678),
        ])

        session = {"stem": "api_requests_opus_fakeproject_1788367120",
                   "streams": {"response": response_path}}
        boundaries = [
            {"start_index": 0, "message_count": 1, "timestamp": "2026-01-01T00:00:00Z", "flow_id": "f0", "restart": False},
            {"start_index": 1, "message_count": 2, "timestamp": "2026-01-01T00:00:05Z", "flow_id": "f1", "restart": False},
        ]
        result = build_request_times_by_flow(session, boundaries, projects_root=projects_root)
        check("200-status flow resolves to (stream_end, output_tokens)",
              result.get("f0") == ("2026-01-01T00:00:10Z", 1234), result)
        check("400-status flow is dropped despite a resolvable request id", "f1" not in result, result)


def test_build_request_times_by_flow_degrades_cleanly() -> None:
    check("empty boundaries -> {}", build_request_times_by_flow({"streams": {}}, []) == {})
    check("missing _response stream -> {}",
          build_request_times_by_flow({"streams": {}}, [
              {"start_index": 0, "message_count": 1, "timestamp": "t", "flow_id": "f0", "restart": False}
          ]) == {})


# --- render_turns / _fmt_duration / _fmt_tokens -----------------------------------------------

def test_fmt_duration_bands() -> None:
    check("under a minute", _fmt_duration(58) == "58s", _fmt_duration(58))
    check("minutes and seconds", _fmt_duration(41 * 60 + 24) == "41m24s", _fmt_duration(41 * 60 + 24))
    check("hours, minutes and seconds", _fmt_duration(3600 + 5 * 60 + 30) == "1h05m30s", _fmt_duration(3600 + 5 * 60 + 30))
    check("None passes through as '?'", _fmt_duration(None) == "?")


def test_fmt_tokens() -> None:
    check("digit-grouped", _fmt_tokens(102389) == "102,389")
    check("None passes through as '?'", _fmt_tokens(None) == "?")


def test_render_turns_line_shape() -> None:
    rows = [{
        "number": 1, "timestamp": "2026-09-06T20:27:49Z", "requests": 77,
        "preview": "You are a WORKER.", "duration": 41 * 60 + 27, "model_time": 20 * 60 + 23,
        "tool_time": 21 * 60 + 4, "tokens": 102389,
    }]
    got = render_turns(rows)
    expected = (
        f"turn 1   {_local_clock('2026-09-06T20:27:49Z')}    41m27s  model   20m23s  "
        f"tool   21m04s   77 reqs    102,389 tok  You are a WORKER.\n"
    )
    check("turn line matches the exact expected layout", got == expected, got)


def test_render_turns_unresolved_row_shows_question_marks() -> None:
    rows = [{
        "number": 2, "timestamp": "2026-09-06T21:10:14Z", "requests": 2,
        "preview": "recap", "duration": None, "model_time": None, "tool_time": None, "tokens": None,
    }]
    got = render_turns(rows)
    check("every numeric column renders '?', request count and preview still print",
          "?" in got and "2 reqs" in got and got.endswith("recap\n"), got)


def test_render_turns_empty() -> None:
    check("no rows -> 'no turns found'", render_turns([]) == "no turns found\n")


# ORCHESTRATOR

def test_turns_workflow() -> None:
    test_opener_classification()
    test_preview_uses_last_text_block()
    test_assignment_uses_message_count_not_start_index()
    test_duration_model_tool_arithmetic()
    test_unresolved_turn_shows_question_marks_but_keeps_count_and_clock()
    test_transcript_stream_ends_keeps_last_timestamp_first_tokens()
    test_build_request_times_by_flow_end_to_end()
    test_build_request_times_by_flow_degrades_cleanly()
    test_fmt_duration_bands()
    test_fmt_tokens()
    test_render_turns_line_shape()
    test_render_turns_unresolved_row_shows_question_marks()
    test_render_turns_empty()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_turns_workflow()
