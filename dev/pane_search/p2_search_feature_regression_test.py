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
