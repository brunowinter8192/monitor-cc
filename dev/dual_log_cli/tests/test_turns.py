# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render_format import _fmt_duration
from src.dual_log_cli.render_reqs import render_reqs
from src.dual_log_cli.timeline_boundaries import request_boundaries
from src.dual_log_cli.timeline_grouping import (
    _group_markers_by_turn,
    _is_turn_opener,
    _turn_preview,
    turn_openers,
)
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_opener_classification',
    'test_preview_uses_last_text_block',
    'test_assignment_uses_message_count_not_start_index',
    'test_group_markers_by_turn_no_openers',
    'test_fmt_duration_bands',
    'test_turns_render_matches_milestones_worked_example',
    'test_turns_no_opener_prints_flat_list_no_separators',
    'test_turns_by_stem_none_reproduces_flat_listing',
    'test_turn_selects_exactly_one_turn',
    'test_turn_missing_from_session_prints_header_only',
    'test_separator_survives_only_when_a_req_of_its_own_does',
]

# ORCHESTRATOR

def test_turns_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_turns')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _local_clock(iso_timestamp: str) -> str:
    return local_datetime(iso_timestamp).strftime("%H:%M:%S")

def _block(type_: str, preview: str = "", label_override: str = None) -> dict:
    return {"label": label_override if label_override is not None else type_,
            "type": type_, "chars": 10, "sig_chars": 0, "preview": preview}

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

def test_preview_uses_last_text_block() -> None:
    spawn_prompt = _turn(0, "user", [_block("text", "<system-reminder>"), _block("text", "You are a WORKER.")])
    check("preview is the LAST text block, not the reminder wrapper",
          _turn_preview(spawn_prompt) == "You are a WORKER.", _turn_preview(spawn_prompt))

    single_block = _turn(1, "user", [_block("text", "recap")])
    check("a single text block is trivially its own preview", _turn_preview(single_block) == "recap")

    no_text = _turn(2, "user", [_block("tool_result")])
    check("no text block at all -> empty preview", _turn_preview(no_text) == "")

def test_assignment_uses_message_count_not_start_index() -> None:
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
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T10:00:05Z", 4),
        _delta_entry("f3", "2026-09-06T10:05:00Z", 7),
    ])
    markers, openers, groups = _group_markers_by_turn(turns, boundaries)
    check("two turns produced", len(groups) == 2, groups)
    check("turn 1 gets exactly req1+req2's msg indices (0 and 1)", groups[0] == [0, 1], groups)
    check("turn 2 gets exactly req3's msg index (4), NOT grouped by its start_index",
          groups[1] == [4], groups)
    check("openers are msg 0 and msg 5", openers == [0, 5], openers)

def test_group_markers_by_turn_no_openers() -> None:
    turns = [_turn(0, "user", [_block("tool_result")])]
    boundaries = _boundaries([_delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True)])
    markers, openers, groups = _group_markers_by_turn(turns, boundaries)
    check("no openers -> empty openers and groups lists", openers == [] and groups == [], (openers, groups))
    check("markers themselves still resolve normally", len(markers) == 1, markers)

def test_fmt_duration_bands() -> None:
    check("under a minute", _fmt_duration(58) == "58s", _fmt_duration(58))
    check("minutes and seconds", _fmt_duration(41 * 60 + 24) == "41m24s", _fmt_duration(41 * 60 + 24))
    check("hours, minutes and seconds", _fmt_duration(3600 + 5 * 60 + 30) == "1h05m30s", _fmt_duration(3600 + 5 * 60 + 30))
    check("None passes through as '?'", _fmt_duration(None) == "?")

def test_turns_render_matches_milestones_worked_example() -> None:
    turns = [
        _turn(0, "user", [_block("text", "You are a WORKER.")]),
        _turn(1, "assistant", [_block("text", "ack")]),
        _turn(2, "user", [_block("tool_result")]),
        _turn(3, "assistant", [_block("text", "done, going idle")]),
        _turn(4, "system", [_block("system")]),
        _turn(5, "user", [_block("text", "recap")]),
        _turn(6, "assistant", [_block("thinking")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T22:27:49Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T22:27:58Z", 4),
        _delta_entry("f3", "2026-09-06T22:37:44Z", 7),
    ])
    session = {"stem": "api_requests_worker_reldist-power_1788726467"}
    results = [(session, boundaries)]
    turns_by_stem = {session["stem"]: turns}
    usage_by_stem = {session["stem"]: {"f1": (7771, 5496), "f2": (13267, 7006), "f3": (323412, 980)}}
    got = render_reqs(results, turns_by_stem=turns_by_stem, usage_by_stem=usage_by_stem)
    expected = (
        "session api_requests_worker_reldist-power_1788726467\n"
        f"── turn 1  {_local_clock('2026-09-06T22:27:49Z')}  9s  You are a WORKER. ──\n"
        f"REQ 1   {_local_clock('2026-09-06T22:27:49Z')}  CR 7,771    CC 5,496\n"
        f"REQ 2   {_local_clock('2026-09-06T22:27:58Z')}  CR 13,267   CC 7,006\n"
        f"── turn 2  {_local_clock('2026-09-06T22:37:44Z')}  0s  recap ──\n"
        f"REQ 3   {_local_clock('2026-09-06T22:37:44Z')}  CR 323,412  CC 980\n"
    )
    check("turn separators (no flag needed), clocks, spans, previews and CR/CC match exactly",
          got == expected, got)

def test_turns_no_opener_prints_flat_list_no_separators() -> None:
    turns = [_turn(0, "user", [_block("tool_result")])]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T10:00:09Z", 2),
    ])
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)], turns_by_stem={"s": turns})
    check("no '── turn' separator anywhere", "── turn" not in got, got)
    check("both REQ lines print, CR/CC unresolved",
          f"REQ 1   {_local_clock('2026-09-06T10:00:00Z')}  CR ?  CC ?\n" in got
          and f"REQ 2   {_local_clock('2026-09-06T10:00:09Z')}  CR ?  CC ?\n" in got, got)

def test_turns_by_stem_none_reproduces_flat_listing() -> None:
    boundaries = _boundaries([_delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True)])
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)])
    check("turns_by_stem=None (the default) is a flat, separator-free listing",
          got == f"session s\nREQ 1   {_local_clock('2026-09-06T10:00:00Z')}  CR ?  CC ?\n", got)

def _two_turn_fixture() -> tuple:
    turns = [
        _turn(0, "user", [_block("text", "You are a WORKER.")]),
        _turn(1, "assistant", [_block("text", "ack")]),
        _turn(2, "user", [_block("tool_result")]),
        _turn(3, "assistant", [_block("text", "done, going idle")]),
        _turn(4, "system", [_block("system")]),
        _turn(5, "user", [_block("text", "recap")]),
        _turn(6, "assistant", [_block("thinking")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T22:27:49Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T22:27:58Z", 4),
        _delta_entry("f3", "2026-09-06T22:37:44Z", 7),
    ])
    return turns, boundaries

def test_turn_selects_exactly_one_turn() -> None:
    turns, boundaries = _two_turn_fixture()
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)], turn=2, turns_by_stem={"s": turns})
    expected = (
        "session s\n"
        f"── turn 2  {_local_clock('2026-09-06T22:37:44Z')}  0s  recap ──\n"
        f"REQ 3   {_local_clock('2026-09-06T22:37:44Z')}  CR ?  CC ?\n"
    )
    check("--turn 2 keeps only turn 2's separator and its own REQ", got == expected, got)

def test_turn_missing_from_session_prints_header_only() -> None:
    turns, boundaries = _two_turn_fixture()
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)], turn=99, turns_by_stem={"s": turns})
    check("a turn number the session never reaches -> the no-REQ line", got == "no REQs to show\n", got)

def test_separator_survives_only_when_a_req_of_its_own_does() -> None:
    turns, boundaries = _two_turn_fixture()
    session = {"stem": "s"}
    usage_by_stem = {"s": {"f1": (5, 5), "f2": (5, 5), "f3": (10, 40)}}
    got = render_reqs([(session, boundaries)], turns_by_stem={"s": turns},
                      usage_by_stem=usage_by_stem, rebuild=True)
    check("turn 1's separator is absent (neither of its REQs qualifies)",
          "── turn 1" not in got, got)
    check("turn 2's separator prints (REQ 3 qualifies) with its OWN full-turn span, not recomputed",
          f"── turn 2  {_local_clock('2026-09-06T22:37:44Z')}  0s  recap ──\n"
          f"REQ 3   {_local_clock('2026-09-06T22:37:44Z')}  CR 10  CC 40\n" in got, got)

if __name__ == '__main__':
    sys.exit(test_turns_workflow())
