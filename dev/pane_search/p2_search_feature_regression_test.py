"""
p2_search_feature_regression_test.py — Regression guard for the M2 proxy-pane search bar
(process-docs/pane_search/).

Covers, per the M2 spec:
  - search bar renders at row 1 (always visible)
  - line_map shift correctness (body rows start at row 2, header row never gets a body key)
  - collapsed-hit marks REQ row; expanded-hit ALSO highlights the matching inner line (header
    stays marked when expanded — decision: uniform, keeps orientation when scrolling)
  - n/N jump ordering (wraps both directions)
  - Esc clears the query (matches cleared, bar stays — it's a permanent row, not a toggle)
  - scroll-jump respects the existing max_scroll clamp
  - the flow_id-based _lazy_load_messages_forwarded fix (the _fwd_req_idx collision bug found
    during M2 investigation — verified against a self-contained synthetic 2-batch fixture, not
    the real gitignored log, so this guard is portable)
  - (follow-up, 2026-08-18) UTF-8 multi-byte keypress decoding in input.click_handler.read_keypress
    — em-dash/ä-ö-ü/emoji fed through the REAL byte-wise reader via a real os.pipe() fd (not a
    mock), asserting a single correctly-decoded character comes out (not N replacement chars),
    and that the full search-bar input path accumulates the real characters into the query

(2026-08-18, sub-milestone 1 of the pane-search rollout) pane.py's search state is now ONE
search_bar.SearchState instance (`_proxy_search`) instead of 8 separate flat globals — this
file's state-pokes were mechanically updated to the new attribute path
(`mod_pane._proxy_search_query` -> `mod_pane._proxy_search.query`, etc.); all function-call
shapes (`_handle_proxy_search_input`, `_search_col_to_query_index`, `_render_proxy_search_bar`,
`_KILL_LINE_CHAR`, ...) are UNCHANGED — pane.py keeps thin compat wrappers over search_bar.py's
generic functions specifically so this suite (and any other caller) needed no other changes.

Uses REAL render_turn.py / format.py / search.py / forwarded_parser.py / pane.py functions
against synthetic data — not mocks. importlib.import_module used throughout (dev/ scripts may
not use a literal 'from src.' import line).

Run: ./venv/bin/python dev/pane_search/p2_search_feature_regression_test.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p2_search_feature_regression_fixtures import _RESULTS
from p2_search_feature_regression_cases import (
    test_search_bar_renders_at_row1,
    test_line_map_shift,
    test_collapsed_hit_marks_req_row,
    test_expanded_hit_marks_line,
    test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows,
    test_n_N_ordering,
    test_esc_clears_query_bar_stays,
    test_scroll_jump_clamps,
    test_flow_id_lazy_load_fix,
    test_utf8_multibyte_keypress,
    test_utf8_search_query_accumulation,
    test_kill_line_after_a_real_search_run,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P2 — proxy-pane search feature regression suite (M2)")
    print("=" * 70)
    test_search_bar_renders_at_row1()
    test_line_map_shift()
    test_collapsed_hit_marks_req_row()
    test_expanded_hit_marks_line()
    test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows()
    test_n_N_ordering()
    test_esc_clears_query_bar_stays()
    test_scroll_jump_clamps()
    test_flow_id_lazy_load_fix()
    test_utf8_multibyte_keypress()
    test_utf8_search_query_accumulation()
    test_kill_line_after_a_real_search_run()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p2_search_feature_regression_test_{ts}.md'
    lines = [f"# P2 search feature regression — {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
