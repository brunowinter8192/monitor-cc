"""
p3_drag_select_regression_test.py — Regression guard for drag-to-select on the proxy pane's
search bar (row 1), process-docs/pane_search/.

Covers, per the milestone spec:
  - button-0 press on row 1 anchors a selection at the char under the pointer (col->char-index
    mapping, _cell_width-aware for wide chars — em-dash/emoji land in queries per the UTF-8 fix)
  - motion (button 32 = left button held, the 0+32 SGR flag) extends the selection; row is
    ignored while dragging, so vertical drift during a fast drag doesn't break it
  - release finalizes: copies the selected substring to the clipboard via the real
    copy_to_clipboard (monkeypatched to a capturing stub, no real pbcopy call)
  - a plain click (press+release, NO motion in between) does NOT copy anything (must never
    clobber the real clipboard with an empty string) and preserves today's focus-only behavior
  - selection renders as SGR reverse-video (\\033[7m...\\033[27m) bracketing the exact substring
  - click elsewhere, new keyboard input, Esc-cancel, and session-change all clear a live
    selection's highlight
  - a drag that starts on a BODY row (not row 1) never arms search-bar dragging — button-32
    motion after a body-row press falls through to the unchanged generic hover bucket
  - editor-style deletion: Backspace with an active selection deletes it; kill-line (Cmd+Backspace
    hypothesis) empties the whole query; neither clears _proxy_search.matches

(2026-08-18, sub-milestone 1 of the pane-search rollout) pane.py's search state is now ONE
search_bar.SearchState instance (`_proxy_search`) instead of 8 separate flat globals — this
file's state-pokes were mechanically updated to the new attribute path
(`mod_pane._proxy_search_dragging` -> `mod_pane._proxy_search.dragging`, etc.); all function-call
shapes (`_handle_proxy_mouse`, `_search_col_to_query_index`, `_render_proxy_search_bar`,
`_KILL_LINE_CHAR`, ...) are UNCHANGED — pane.py keeps thin compat wrappers over search_bar.py's
generic functions specifically so this suite needed no other changes.

Uses REAL src.proxy_display.pane functions against direct (button, col, row) calls — not a
mock of the mouse-event layer itself (read_mouse_event's own SGR parsing is unchanged and out
of scope here; these tests exercise everything downstream of it, matching the milestone's
own investigation: button 32 for a held-left-button drag is a documented SGR protocol fact,
not something this suite re-derives from raw bytes).

Run: ./venv/bin/python dev/pane_search/p3_drag_select_regression_test.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p3_drag_select_regression_fixtures import _RESULTS
from p3_drag_select_regression_cases import (
    test_col_to_index_ascii,
    test_col_to_index_wide_char,
    test_drag_select_copies_to_clipboard,
    test_plain_click_no_motion_no_clipboard,
    test_release_noop_without_active_drag,
    test_body_row_drag_never_arms_search_selection,
    test_click_elsewhere_clears_selection,
    test_new_input_clears_selection,
    test_backspace_deletes_active_selection,
    test_backspace_without_selection_still_trims_last_char,
    test_kill_line_empties_query,
    test_kill_line_ignores_active_selection,
    test_kill_line_not_silently_swallowed_by_isprintable_fallthrough,
    test_editing_never_clears_matches,
    test_esc_cancel_clears_selection,
    test_render_reverse_video_bracket,
    test_session_change_clears_selection,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P3 — proxy-pane search bar drag-to-select regression suite")
    print("=" * 70)
    test_col_to_index_ascii()
    test_col_to_index_wide_char()
    test_drag_select_copies_to_clipboard()
    test_plain_click_no_motion_no_clipboard()
    test_release_noop_without_active_drag()
    test_body_row_drag_never_arms_search_selection()
    test_click_elsewhere_clears_selection()
    test_new_input_clears_selection()
    test_backspace_deletes_active_selection()
    test_backspace_without_selection_still_trims_last_char()
    test_kill_line_empties_query()
    test_kill_line_ignores_active_selection()
    test_kill_line_not_silently_swallowed_by_isprintable_fallthrough()
    test_editing_never_clears_matches()
    test_esc_cancel_clears_selection()
    test_render_reverse_video_bracket()
    test_session_change_clears_selection()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p3_drag_select_regression_test_{ts}.md'
    lines = [f"# P3 drag-select regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
