"""
Regression suite for the PROJECT-over-CONTEXT rework (2026-09-10): `src/dual_log_cli/discovery.py`'s
`project_for_stem`/`display_stem`/`resolve_stem`/`filter_sessions`/`filter_by_family`, and
`src/dual_log_cli/render.py`'s `render_sessions`/`render_expand_full`'s new PROJECT column/header.

Covers: `project_for_stem` resolves a worker's sid8 to the PROJECT's own cwd (never the worker's
own worktree cwd) via a fixture `project_index`, resolves a main stem's label to a matching cwd,
and falls back to the sid8 (worker) / the label (main) / the raw stem (unparseable) when nothing
resolves; `display_stem` strips a worker's sid8 segment while preserving the trailing epoch, and
leaves a main stem (and an unparseable one) unchanged; `resolve_stem` accepts a substring of
either the full on-disk stem OR its displayed form against a real temp directory of empty
stem-shaped files, and raises ambiguity across the UNION of both match sets; `filter_sessions`
matches its `context`/`scope` needle against the PROJECT path OR the stem (case-insensitive),
identically for both parameters now that the CONTEXT string they used to differ over is gone;
`filter_by_family` reads the stem via `stem_identity` directly; `render_sessions` prints a
PROJECT column (widened to the longest path, no truncation) and a SESSION column using the
DISPLAYED stem; `render_expand_full`'s header prints `project   <path>` instead of the old
`context   <string>` line.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_project_display.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.discovery import (
    AmbiguousSessionError,
    UnknownSessionError,
    display_stem,
    filter_sessions,
    project_for_stem,
    resolve_stem,
)
from src.dual_log_cli.render_expand import render_expand_full
from src.dual_log_cli.render_sessions import render_sessions
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


# A fixture project_index shaped exactly like project_map.build_project_index's own return value —
# no filesystem involved, so this suite never touches the real ~/.claude/projects/.
_PROJECT_CWD = "/Users/fake/trading"
_WORKER_SID = _proxy_session_id_for_project(_PROJECT_CWD)
_FIXTURE_INDEX = {
    "cwd_to_dir": {_PROJECT_CWD: Path("/fake/projects/-Users-fake-trading")},
    "sid_to_cwd": {_WORKER_SID: _PROJECT_CWD},
}


# --- project_for_stem -------------------------------------------------------------------------

def test_project_for_stem_worker_resolves_to_project_cwd_not_worktree() -> None:
    stem = f"api_requests_worker_{_WORKER_SID}_reldist-power_1788726467"
    got = project_for_stem(stem, _FIXTURE_INDEX)
    check("worker stem resolves to the PROJECT's own cwd, not a worktree-suffixed path",
          got == _PROJECT_CWD, got)


def test_project_for_stem_main_resolves_via_label_match() -> None:
    stem = "api_requests_opus_trading_1788682222"
    got = project_for_stem(stem, _FIXTURE_INDEX)
    check("main stem's label matches the fixture cwd's own project_label", got == _PROJECT_CWD, got)


def test_project_for_stem_worker_unresolved_falls_back_to_sid8() -> None:
    stem = "api_requests_worker_deadbeef_some-worker_1788000000"
    got = project_for_stem(stem, _FIXTURE_INDEX)
    check("an sid8 absent from sid_to_cwd falls back to the sid8 itself", got == "deadbeef", got)


def test_project_for_stem_main_unresolved_falls_back_to_label() -> None:
    stem = "api_requests_opus_nonexistent_project_1788000001"
    got = project_for_stem(stem, _FIXTURE_INDEX)
    check("a label matching no known cwd falls back to the label itself",
          got == "nonexistent_project", got)


def test_project_for_stem_unparseable_falls_back_to_raw_stem() -> None:
    # No "_" at all -> stem_identity's own partition finds no tail -> returns None (see its
    # Purpose) -- the one genuinely unparseable shape, unlike a body with several underscores
    # (which always parses as SOME "main" identity, however meaningless the label).
    stem = "nostem"
    got = project_for_stem(stem, _FIXTURE_INDEX)
    check("a stem stem_identity cannot parse falls back to the raw stem itself", got == stem, got)


def test_project_for_stem_none_index_degrades_cleanly() -> None:
    stem = f"api_requests_worker_{_WORKER_SID}_reldist-power_1788726467"
    check("a None project_index degrades to the sid8 fallback, never raises",
          project_for_stem(stem, None) == _WORKER_SID)


# --- display_stem ------------------------------------------------------------------------------

def test_display_stem_strips_worker_sid_keeps_epoch() -> None:
    stem = "api_requests_worker_1dda1c81_reldist-power_1788726467"
    got = display_stem(stem)
    check("worker sid8 segment removed, epoch preserved",
          got == "api_requests_worker_reldist-power_1788726467", got)


def test_display_stem_main_unchanged() -> None:
    stem = "api_requests_opus_trading_1788682222"
    check("a main stem is returned unchanged", display_stem(stem) == stem)


def test_display_stem_unparseable_unchanged() -> None:
    stem = "not_a_recognisable_stem_shape"
    check("an unparseable stem is returned unchanged", display_stem(stem) == stem)


# --- resolve_stem: matches the full stem OR the displayed form --------------------------------

def _touch_stem_files(dual_log_dir: Path, stem: str) -> None:
    for suffix in ("original", "forwarded", "stripped", "injected", "response", "errors"):
        (dual_log_dir / f"{stem}_{suffix}.jsonl").write_text("")


def test_resolve_stem_matches_full_stem_and_displayed_form() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dual_log_dir = Path(tmp)
        full_stem = "api_requests_worker_1dda1c81_reldist-power_1788726467"
        _touch_stem_files(dual_log_dir, full_stem)

        check("a substring of the FULL on-disk stem (incl. sid8) resolves",
              resolve_stem(dual_log_dir, "1dda1c81_reldist") == full_stem)
        check("a substring of the DISPLAYED form (sid8 absent) resolves",
              resolve_stem(dual_log_dir, "worker_reldist-power_1788726467") == full_stem)
        check("the exact displayed form (no sid8 at all) resolves",
              resolve_stem(dual_log_dir, display_stem(full_stem)) == full_stem)

        try:
            resolve_stem(dual_log_dir, "does-not-exist")
            check("an unmatched query raises UnknownSessionError", False)
        except UnknownSessionError:
            check("an unmatched query raises UnknownSessionError", True)


def test_resolve_stem_ambiguous_across_both_match_sets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dual_log_dir = Path(tmp)
        # stem A's raw form and stem B's DISPLAYED form both contain "reldist-power" — the
        # ambiguity check must consider the union of both match kinds, not just one.
        stem_a = "api_requests_opus_reldist-power_archive_1788000000"
        stem_b = "api_requests_worker_1dda1c81_reldist-power_1788726467"
        _touch_stem_files(dual_log_dir, stem_a)
        _touch_stem_files(dual_log_dir, stem_b)
        try:
            resolve_stem(dual_log_dir, "reldist-power")
            check("two stems matching via different forms raise AmbiguousSessionError", False)
        except AmbiguousSessionError:
            check("two stems matching via different forms raise AmbiguousSessionError", True)


# --- filter_sessions: context and scope both match PROJECT path OR stem -----------------------

def test_filter_sessions_matches_project_path_or_stem() -> None:
    sessions = [
        {"stem": "api_requests_opus_trading_1788682222", "project": "/Users/fake/trading", "start": "2026-09-06T10:00:00Z"},
        {"stem": "api_requests_opus_wise2627_1788700000", "project": "/Users/fake/wise2627", "start": "2026-09-06T10:00:00Z"},
    ]
    by_context = filter_sessions(sessions, context="TRADING")
    check("context matches the PROJECT path case-insensitively",
          [s["stem"] for s in by_context] == [sessions[0]["stem"]], by_context)

    by_scope_path = filter_sessions(sessions, scope="fake/trading")
    check("scope matches a PROJECT path substring",
          [s["stem"] for s in by_scope_path] == [sessions[0]["stem"]], by_scope_path)

    by_scope_stem = filter_sessions(sessions, scope="wise2627")
    check("scope also matches the stem when the project path does not contain the needle",
          [s["stem"] for s in by_scope_stem] == [sessions[1]["stem"]], by_scope_stem)


# --- render_sessions: PROJECT column widened, SESSION uses the displayed stem ------------------

def test_render_sessions_project_column_and_displayed_stem() -> None:
    sessions = [
        {"start": "2026-09-06T20:16:02Z", "project": "/Users/fake/trading",
         "stem": "api_requests_worker_1dda1c81_reldist-power_1788726467",
         "display_stem": "api_requests_worker_reldist-power_1788726467"},
    ]
    got = render_sessions(sessions)
    check("header reads PROJECT, not CONTEXT", "PROJECT" in got.splitlines()[0], got)
    check("CONTEXT no longer appears anywhere in the header", "CONTEXT" not in got, got)
    check("the row's SESSION column is the DISPLAYED stem (sid8 stripped)",
          "api_requests_worker_reldist-power_1788726467" in got.splitlines()[1], got)
    check("the row's PROJECT column is the real path, not a rendered worker/label/name string",
          "/Users/fake/trading" in got.splitlines()[1], got)


def test_render_sessions_empty() -> None:
    check("no sessions -> 'no sessions found'", render_sessions([]) == "no sessions found\n")


# --- render_expand_full: the header's second line is "project", not "context" ------------------

def test_render_expand_full_project_header_line() -> None:
    data = {
        "session": {"stem": "api_requests_worker_1dda1c81_reldist-power_1788726467",
                    "project": "/Users/fake/trading", "start": "2026-09-06T20:16:02Z"},
        "turns": [{"index": 0, "role": "user", "chars": 4,
                   "blocks": [{"label": "text", "type": "text", "chars": 4, "sig_chars": 0, "preview": "hi"}]}],
        "turn_times": {},
    }
    dumped = [(data["turns"][0], [("text", 4, "hi")])]
    got = render_expand_full(data, 0, 0, 0, "", dumped)
    lines = got.splitlines()
    check("second header line is 'project   <path>', not 'context   ...'",
          lines[1] == "project   /Users/fake/trading", lines[1])


# ORCHESTRATOR

def test_project_display_workflow() -> None:
    test_project_for_stem_worker_resolves_to_project_cwd_not_worktree()
    test_project_for_stem_main_resolves_via_label_match()
    test_project_for_stem_worker_unresolved_falls_back_to_sid8()
    test_project_for_stem_main_unresolved_falls_back_to_label()
    test_project_for_stem_unparseable_falls_back_to_raw_stem()
    test_project_for_stem_none_index_degrades_cleanly()
    test_display_stem_strips_worker_sid_keeps_epoch()
    test_display_stem_main_unchanged()
    test_display_stem_unparseable_unchanged()
    test_resolve_stem_matches_full_stem_and_displayed_form()
    test_resolve_stem_ambiguous_across_both_match_sets()
    test_filter_sessions_matches_project_path_or_stem()
    test_render_sessions_project_column_and_displayed_stem()
    test_render_sessions_empty()
    test_render_expand_full_project_header_line()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_project_display_workflow()
