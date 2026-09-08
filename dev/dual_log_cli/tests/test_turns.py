"""
Regression suite for `reqs --turns` (2026-09-10, replaces the removed `turns` subcommand — see
process-docs/dual_log_cli/ for the pivot): src/dual_log_cli/timeline.py's `_is_turn_opener`/
`turn_openers`/`_turn_preview`/`_group_markers_by_turn`, src/dual_log_cli/render.py's
`_turn_grouped_lines`/`_elapsed_req_lines`/`_fmt_duration`/`render_reqs`'s `turns_by_stem` branch,
and src/dual_log_cli/__main__.py's `_run_reqs` usage-error validation.

Covers: turn-opener classification (a `user` msg with a `text` block and no `tool_result` block
opens a turn; a tool_result-carrying user msg, an assistant msg, and a str-content pseudo-block
msg — e.g. `system-reminder` — do not); the preview is the LAST `text`-type block of the opener,
not the first; the turn-ASSIGNMENT rule this area's investigation found and `_group_markers_by_turn`
still owns — a request whose msg-index KEY (`start_index`) sits before the next opener but whose
OWN `message_count` already reaches past it belongs to the NEXT turn; `_fmt_duration`'s three
duration bands plus its "?" passthrough; `_turn_grouped_lines`' separator format (turn number,
first-request clock, SPAN = last send minus first send within the turn, preview) reproducing the
milestone's own worked example byte-for-byte; the elapsed tail's per-turn RESET (a turn's own
first REQ never carries `+<elapsed>`, every other REQ carries it since the PREVIOUS request of the
SAME turn); a session with no turn opener falling back to a flat, still-tailed REQ list with no
separators; and `_run_reqs` rejecting `--turns` combined with `--merged`/`--gap`/`--rebuild`/
`--drop` before ever touching the filesystem.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_turns.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.__main__ import _run_reqs
from src.dual_log_cli.reader import local_datetime
from src.dual_log_cli.render import _fmt_duration, render_reqs
from src.dual_log_cli.timeline import (
    _group_markers_by_turn,
    _is_turn_opener,
    _turn_preview,
    request_boundaries,
    turn_openers,
)

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


# --- the turn-assignment rule: message_count decides, not the marker's msg-index key ---------

def test_assignment_uses_message_count_not_start_index() -> None:
    # opener1 at msg 0, opener2 at msg 5. req3's OWN start_index (4) sits before opener2 (5), but
    # its message_count (7) already reaches past it -- it must land in turn 2, not turn 1, exactly
    # the reldist-power case this area's investigation found (an idle text reply bundled together
    # with the next prompt in one send).
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
    markers, openers, groups = _group_markers_by_turn(turns, boundaries)
    check("two turns produced", len(groups) == 2, groups)
    check("turn 1 gets exactly req1+req2's msg indices (0 and 1)", groups[0] == [0, 1], groups)
    check("turn 2 gets exactly req3's msg index (4), NOT grouped by its start_index",
          groups[1] == [4], groups)
    check("openers are msg 0 and msg 5", openers == [0, 5], openers)


def test_group_markers_by_turn_no_openers() -> None:
    turns = [_turn(0, "user", [_block("tool_result")])]  # no opener at all
    boundaries = _boundaries([_delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True)])
    markers, openers, groups = _group_markers_by_turn(turns, boundaries)
    check("no openers -> empty openers and groups lists", openers == [] and groups == [], (openers, groups))
    check("markers themselves still resolve normally", len(markers) == 1, markers)


# --- _fmt_duration bands (unchanged by this milestone, still used by --turns) ------------------

def test_fmt_duration_bands() -> None:
    check("under a minute", _fmt_duration(58) == "58s", _fmt_duration(58))
    check("minutes and seconds", _fmt_duration(41 * 60 + 24) == "41m24s", _fmt_duration(41 * 60 + 24))
    check("hours, minutes and seconds", _fmt_duration(3600 + 5 * 60 + 30) == "1h05m30s", _fmt_duration(3600 + 5 * 60 + 30))
    check("None passes through as '?'", _fmt_duration(None) == "?")


# --- render_reqs(turns_by_stem=...): the milestone's own worked example, byte-for-byte ---------

def test_turns_render_matches_milestones_worked_example() -> None:
    # Two turns: turn 1 has 3 requests (REQ1 opener, REQ2 +9s, REQ43-shaped +9m46s), turn 2 has 2
    # (REQ78 opener, REQ79 +8s) -- msg-index/message_count shapes mirror the real reldist-power
    # session's own turn-1/turn-2 boundary (idle text reply bundled with the next prompt).
    turns = [
        _turn(0, "user", [_block("text", "You are a WORKER.")]),   # turn 1 opener
        _turn(1, "assistant", [_block("text", "ack")]),
        _turn(2, "user", [_block("tool_result")]),
        _turn(3, "assistant", [_block("text", "done, going idle")]),
        _turn(4, "system", [_block("system")]),
        _turn(5, "user", [_block("text", "recap")]),                # turn 2 opener
        _turn(6, "assistant", [_block("thinking")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T22:27:49Z", 1, is_first=True),   # REQ 1, turn 1 opener
        _delta_entry("f2", "2026-09-06T22:27:58Z", 4),                  # REQ 2, +9s
        _delta_entry("f3", "2026-09-06T22:37:44Z", 7),                  # REQ 3 (start=4 < opener2=5,
                                                                          # but message_count=7 -> turn 2)
    ])
    session = {"stem": "api_requests_worker_reldist-power_1788726467"}
    results = [(session, boundaries)]
    turns_by_stem = {session["stem"]: turns}
    got = render_reqs(results, turns_by_stem=turns_by_stem)
    expected = (
        "session api_requests_worker_reldist-power_1788726467\n"
        f"── turn 1  {_local_clock('2026-09-06T22:27:49Z')}  9s  You are a WORKER. ──\n"
        f"REQ 1   {_local_clock('2026-09-06T22:27:49Z')}\n"
        f"REQ 2   {_local_clock('2026-09-06T22:27:58Z')}  +9s\n"
        f"── turn 2  {_local_clock('2026-09-06T22:37:44Z')}  0s  recap ──\n"
        f"REQ 3   {_local_clock('2026-09-06T22:37:44Z')}\n"
    )
    check("turn separators, clocks, spans, previews and elapsed tails match exactly",
          got == expected, got)


def test_turns_elapsed_tail_resets_at_turn_boundary() -> None:
    # The exact detail the milestone's own example calls out: REQ 78 (a turn's own FIRST request)
    # carries NO elapsed tail, even though the immediately preceding REQ (77, the previous turn's
    # last) is only seconds earlier in absolute session time.
    turns = [
        _turn(0, "user", [_block("text", "go")]),
        _turn(1, "assistant", [_block("text", "idle")]),
        _turn(2, "user", [_block("text", "next")]),
    ]
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T23:09:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T23:10:14Z", 3),   # start=1 < opener2=2, but count=3 -> turn 2
    ])
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)], turns_by_stem={"s": turns})
    lines = [l for l in got.split("\n") if l.startswith("REQ")]
    check("turn 2's own first REQ carries no elapsed tail despite following turn 1 by ~74s",
          lines[-1] == f"REQ 2   {_local_clock('2026-09-06T23:10:14Z')}", lines)


def test_turns_no_opener_prints_flat_tailed_list_no_separators() -> None:
    turns = [_turn(0, "user", [_block("tool_result")])]  # no opener anywhere
    boundaries = _boundaries([
        _delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True),
        _delta_entry("f2", "2026-09-06T10:00:09Z", 2),
    ])
    session = {"stem": "s"}
    got = render_reqs([(session, boundaries)], turns_by_stem={"s": turns})
    check("no '── turn' separator anywhere", "── turn" not in got, got)
    check("REQ 1 has no tail, REQ 2 carries +9s (elapsed tail stays unconditional)",
          f"REQ 1   {_local_clock('2026-09-06T10:00:00Z')}\n" in got
          and f"REQ 2   {_local_clock('2026-09-06T10:00:09Z')}  +9s\n" in got, got)


def test_turns_by_stem_none_reproduces_plain_listing() -> None:
    boundaries = _boundaries([_delta_entry("f1", "2026-09-06T10:00:00Z", 1, is_first=True)])
    session = {"stem": "s"}
    plain = render_reqs([(session, boundaries)])
    check("turns_by_stem=None (the default) is the pre-existing plain listing, unchanged",
          plain == f"session s\nREQ 1   {_local_clock('2026-09-06T10:00:00Z')}\n", plain)


# --- _run_reqs: --turns usage errors, validated before any filesystem access -------------------

def _reqs_args(**overrides) -> argparse.Namespace:
    base = {"scope": "", "since": "", "until": "", "main": False, "worker": False,
            "gap": None, "merged": False, "rebuild": False, "drop": False, "turns": False}
    base.update(overrides)
    return argparse.Namespace(**base)


def _run_reqs_capturing_stderr(args: argparse.Namespace) -> tuple:
    stderr, stdout = io.StringIO(), io.StringIO()
    # The validation this exercises runs BEFORE `list_sessions`/`filter_sessions` ever touch the
    # filesystem, so a nonexistent directory is safe to pass here -- if that ordering regresses,
    # this call would raise or hang instead of returning 2, which is itself a useful failure mode.
    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
        code = _run_reqs(Path("/nonexistent-dual-log-dir-for-testing"), args)
    return code, stderr.getvalue()


def test_turns_rejects_merged() -> None:
    code, err = _run_reqs_capturing_stderr(_reqs_args(turns=True, merged=True))
    check("--turns + --merged exits 2", code == 2, code)
    check("--turns + --merged prints a usage message naming --merged", "--merged" in err, err)


def test_turns_rejects_gap() -> None:
    code, err = _run_reqs_capturing_stderr(_reqs_args(turns=True, gap=5))
    check("--turns + --gap exits 2", code == 2, code)
    check("--turns + --gap prints a usage message", "--gap" in err, err)


def test_turns_rejects_rebuild_and_drop() -> None:
    code_rebuild, err_rebuild = _run_reqs_capturing_stderr(_reqs_args(turns=True, rebuild=True))
    code_drop, err_drop = _run_reqs_capturing_stderr(_reqs_args(turns=True, drop=True))
    check("--turns + --rebuild exits 2", code_rebuild == 2, code_rebuild)
    check("--turns + --drop exits 2", code_drop == 2, code_drop)
    check("both print a usage message", "--rebuild" in err_rebuild and "--drop" in err_drop,
          (err_rebuild, err_drop))


def test_turns_alone_is_not_rejected_by_the_combination_check() -> None:
    # --turns alone (or with --main/--worker/--since/--until/scope) must NOT hit the combination
    # check -- it only runs past validation into the (nonexistent-directory) session-loading step,
    # which is a separate, expected failure mode (an empty session list, not a usage error).
    code, err = _run_reqs_capturing_stderr(_reqs_args(turns=True))
    check("--turns alone is not a usage error (falls through to session loading)",
          code == 0, (code, err))


# ORCHESTRATOR

def test_turns_workflow() -> None:
    test_opener_classification()
    test_preview_uses_last_text_block()
    test_assignment_uses_message_count_not_start_index()
    test_group_markers_by_turn_no_openers()
    test_fmt_duration_bands()
    test_turns_render_matches_milestones_worked_example()
    test_turns_elapsed_tail_resets_at_turn_boundary()
    test_turns_no_opener_prints_flat_tailed_list_no_separators()
    test_turns_by_stem_none_reproduces_plain_listing()
    test_turns_rejects_merged()
    test_turns_rejects_gap()
    test_turns_rejects_rebuild_and_drop()
    test_turns_alone_is_not_rejected_by_the_combination_check()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_turns_workflow()
