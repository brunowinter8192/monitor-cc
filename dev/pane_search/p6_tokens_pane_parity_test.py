"""
p6_tokens_pane_parity_test.py — Regression guard for the tokens pane's search bar reaching
parity with the proxy pane (rollout sub-milestone 4, process-docs/pane_search/).

token_pane.py is structurally simpler than the proxy family: single expand level
(cache_expand_states[(turn_idx, call_idx)], turns themselves never collapse), data ALWAYS
fully loaded incrementally (no windowing, no reconstruction step — on_commit just builds
matches over what's in memory via token_search.build_token_search_matches). Three genuinely
new pieces this milestone had to build:

  - THE SENTINEL BUG, SAME CLASS AS THE PROXY PANE: ZEBRA_BG_A == '' (confirmed in
    constants.py) is the chosen_bg for every non-hovered/non-error row and every detail line.
    Search highlights are embedded with search_bar._BG_RESTORE_SENTINEL at construction time
    (token_format.py) and resolved via search_bar.resolve_bg_restore(line, chosen_bg) in
    token_pane.py's own hand-rolled row loop, right after chosen_bg is chosen — exact same
    fix shape as process-docs/pane_search/2026-08-18_highlight_flood_empty_bg_fix.md.
  - 2-ROW HEADER: format_cache_tracker's optional sticky_header (row 1 when scrolled, before
    this milestone) now shifts to row 2 — the search bar (_TOKENS_SEARCH_BAR_LINES=1, fixed)
    always wins row 1. format_cache_tracker's own internal viewport reservation (-1, for the
    sticky-header slot) is UNTOUCHED; _build_tokens_output now passes pane_height -
    _TOKENS_SEARCH_BAR_LINES as format_cache_tracker's own pane_height argument instead.
  - TWO-KEY MATCH SEMANTICS: a match key is either (turn_idx, call_idx) [found in that call's
    own header or force-expanded detail content] or ('turn', turn_idx) [found in the turn's
    own prompt/timestamp line — turns have no expand state]. BOTH get an UNCONDITIONAL
    whole-line "container mark" (not a literal-substring-only wrap) regardless of expand
    state — mirrors proxy's REQ-header "text extent" marking, since the actual matching text
    may be buried in unrendered (collapsed) detail. An EXPANDED matching call additionally
    gets its specific matching detail line(s) browser-find substring-highlighted. ('turn', idx)
    keys are deliberately kept OUT of line_keys/cache_line_map (turn headers stay
    non-interactive for clicks, exactly as before) — see format_cache_tracker's new nav_out
    param, populated separately for jump-to-match scroll math only.

format_cache_tracker's signature grew (search_match_set/search_current_key/search_query/
nav_out, all optional, all default to a no-op) WITHOUT changing its return arity — verified
byte-identical against all 4 real callers (token_pane.py, workers/worker_format.py,
dev/click_ui/p2_copy_click_probe.py, dev/display/A_format_cache_tracker_proof.py) via a
frozen-turns old-vs-new comparison (the live dev/display/A_format_cache_tracker_proof.py
harness reads directly from ~/.claude/projects/.../*.jsonl — the top-10-most-recently-modified
REAL session files — which turned out to be actively growing during this session, producing a
false-positive mismatch on a naive capture-then-verify-later run; the frozen-snapshot
comparison, held constant across both code versions in the same process, is the reliable
evidence and is not re-run here — see process-docs/pane_search/ for the full writeup).

Uses REAL src.panes.token_pane / src.format.token_format / src.panes.token_search functions
against synthetic turns — not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p6_tokens_pane_parity_test.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p6_tokens_pane_parity_fixtures import _RESULTS
from p6_tokens_pane_parity_cases_mechanics import (
    test_state_shape_and_label,
    test_search_bar_row1_renders_no_arrows,
    test_row1_press_focuses_and_arms_drag,
    test_drag_select_copies_to_clipboard,
    test_plain_click_no_motion_no_clipboard,
    test_release_noop_without_active_drag,
    test_body_click_clears_selection,
    test_body_drag_never_arms_search_selection,
    test_new_input_clears_selection,
    test_backspace_deletes_active_selection,
    test_backspace_without_selection_still_trims_last_char,
    test_kill_line_empties_query,
    test_editing_never_clears_matches,
    test_esc_cancel_clears_state_bar_stays,
    test_render_reverse_video_bracket,
)
from p6_tokens_pane_parity_cases_matching import (
    test_call_level_match_collapsed_container_marked,
    test_call_level_match_expanded_substring_marked,
    test_turn_level_match,
    test_n_N_jump_wraps_both_directions,
    test_sentinel_resolves_to_default_bg_not_empty_string,
    test_light_red_bg_still_detected_when_call_is_also_a_match,
    test_jump_to_match_moves_scroll_offset,
    test_session_change_resets_search_state,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P6 — tokens pane search bar parity regression suite")
    print("=" * 70)
    test_state_shape_and_label()
    test_search_bar_row1_renders_no_arrows()
    test_row1_press_focuses_and_arms_drag()
    test_drag_select_copies_to_clipboard()
    test_plain_click_no_motion_no_clipboard()
    test_release_noop_without_active_drag()
    test_body_click_clears_selection()
    test_body_drag_never_arms_search_selection()
    test_new_input_clears_selection()
    test_backspace_deletes_active_selection()
    test_backspace_without_selection_still_trims_last_char()
    test_kill_line_empties_query()
    test_editing_never_clears_matches()
    test_call_level_match_collapsed_container_marked()
    test_call_level_match_expanded_substring_marked()
    test_turn_level_match()
    test_n_N_jump_wraps_both_directions()
    test_esc_cancel_clears_state_bar_stays()
    test_render_reverse_video_bracket()
    test_sentinel_resolves_to_default_bg_not_empty_string()
    test_light_red_bg_still_detected_when_call_is_also_a_match()
    test_jump_to_match_moves_scroll_offset()
    test_session_change_resets_search_state()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p6_tokens_pane_parity_test_{ts}.md'
    lines = [f"# P6 tokens pane parity regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
