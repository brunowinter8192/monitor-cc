"""
p8_warnings_gpu_news_parity_test.py -- Regression guard for the FINAL three panes reaching
search-bar parity (rollout sub-milestones 6-8, bundled, process-docs/pane_search/): warnings
(src/panes/warnings_pane.py + warnings_render.py), gpu (src/gpu_pane/pane.py), and news
(src/news_pane/pane.py ONLY -- log_pane.py is EXCLUDED per the approved decision).

WARNINGS: 1-level expand (error_expand_states[idx]), full data always loaded. The verification
this milestone explicitly required: warnings_render.py's row-bg loop was read at line level
before assuming anything -- it ALREADY used `DIM_YELLOW_BG in line` (substring), not
`.startswith()`, so no collateral fix was needed there (unlike every prior pane). ZEBRA_BG_A==''
DOES still apply (same shared constant) -- search_bar.resolve_bg_restore is threaded into this
same (already-correct) loop. Match key is a bare int err_idx (no nesting -- one expand level).
Two-stage marking: collapsed error container-marks its whole header row; expanded ADDITIONALLY
substring-highlights the matching detail line(s). header_lines param generalizes the previously
hardcoded single-header-row offset (default 1, warnings_pane.py passes 2 for search bar +
[refresh]).

GPU + NEWS: flat, small live-fetched lists, NO scroll/viewport infra at all (pane_height is
accepted by _render_pane but never read -- confirmed by grep before implementing). Per the
approved decision: full bar mechanics (drag-select, editor-style deletion, kill-line) but
HIGHLIGHT-ONLY -- no jump-to-match. n/N still cycles current_idx (which on-screen match gets
SEARCH_CURRENT_BG vs SEARCH_MATCH_BG, and the N/M counter) with ZERO scroll call. No sentinel
needed in either pane -- neither has a per-row background/zebra/hover loop at all, so
utils.highlight_query_in_line's default restore_bg is directly correct (same simple case as the
main pane). _render_pane's OWN row numbering stays UNSHIFTED/relative to its own top in both
panes -- the search-bar row shift for _button_regions happens externally, in the loop, exactly
mirroring worker_proxy_pane's precedent -- verified by dev/click_ui/p4_gpu_news_button_probe.py
needing ZERO changes (it calls _render_pane directly).

Uses REAL src.panes.warnings_pane / warnings_render / src.gpu_pane.pane / src.news_pane.pane
functions against synthetic data -- not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p8_warnings_gpu_news_parity_test.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

from p8_warnings_gpu_news_parity_fixtures import _RESULTS
from p8_warnings_gpu_news_parity_cases_warnings import (
    test_warnings_state_shape,
    test_warnings_dim_yellow_bg_already_used_in_not_startswith,
    test_warnings_search_bar_row1_and_refresh_header_shifted,
    test_warnings_row1_press_focuses_and_arms_drag,
    test_warnings_drag_select_copies_to_clipboard,
    test_warnings_plain_click_no_clipboard_and_body_clears_selection,
    test_warnings_editing_mechanics,
    test_warnings_collapsed_container_mark_and_expanded_substring_mark,
    test_warnings_sentinel_resolves_to_default_bg_not_empty_string,
    test_warnings_n_N_cycles_without_touching_scroll,
    test_warnings_esc_cancel_and_reverse_video,
)
from p8_warnings_gpu_news_parity_cases_gpu import (
    test_gpu_state_shape,
    test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally,
    test_gpu_row1_click_focuses_search_bar,
    test_gpu_drag_select_and_editing,
    test_gpu_highlight_only_match_no_sentinel_needed,
    test_gpu_n_N_cycles_current_idx_no_scroll_infra,
    test_gpu_esc_cancel_bar_stays,
)
from p8_warnings_gpu_news_parity_cases_news import (
    test_news_state_shape,
    test_news_render_pane_stays_unshifted,
    test_news_highlight_only_match,
    test_news_drag_select_and_n_N,
    test_news_esc_cancel_bar_stays,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("P8 -- warnings + gpu + news panes search bar parity regression suite")
    print("=" * 70)

    test_warnings_state_shape()
    test_warnings_dim_yellow_bg_already_used_in_not_startswith()
    test_warnings_search_bar_row1_and_refresh_header_shifted()
    test_warnings_row1_press_focuses_and_arms_drag()
    test_warnings_drag_select_copies_to_clipboard()
    test_warnings_plain_click_no_clipboard_and_body_clears_selection()
    test_warnings_editing_mechanics()
    test_warnings_collapsed_container_mark_and_expanded_substring_mark()
    test_warnings_sentinel_resolves_to_default_bg_not_empty_string()
    test_warnings_n_N_cycles_without_touching_scroll()
    test_warnings_esc_cancel_and_reverse_video()

    test_gpu_state_shape()
    test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally()
    test_gpu_row1_click_focuses_search_bar()
    test_gpu_drag_select_and_editing()
    test_gpu_highlight_only_match_no_sentinel_needed()
    test_gpu_n_N_cycles_current_idx_no_scroll_infra()
    test_gpu_esc_cancel_bar_stays()

    test_news_state_shape()
    test_news_render_pane_stays_unshifted()
    test_news_highlight_only_match()
    test_news_drag_select_and_n_N()
    test_news_esc_cancel_bar_stays()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    report_dir = Path(__file__).resolve().parent / 'md'
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f'p8_warnings_gpu_news_parity_test_{ts}.md'
    lines = [f"# P8 warnings + gpu + news panes parity regression -- {ts}", "", f"{passed}/{total} checks passed", ""]
    for label, ok in _RESULTS:
        lines.append(f"- [{'x' if ok else ' '}] {label}")
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"\nReport written to: {report_path}")

    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    run_probe_workflow()
