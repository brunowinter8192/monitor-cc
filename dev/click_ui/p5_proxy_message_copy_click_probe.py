# INFRASTRUCTURE
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from proxy_copy_probe_shared import _RESULTS
from proxy_copy_message_probe import (
    test_message_row_gets_key_and_copy_registration,
    test_message_copy_matches_serializer_and_req_subset,
    test_main_pane_message_copy_click,
    test_worker_pane_message_copy_click,
    test_width_guard_suppresses_msg_row_symbol,
)
from proxy_copy_thinking_probe import (
    test_thinking_row_gets_key_and_copy_registration,
    test_thinking_copy_matches_serializer_and_msg_subset,
    test_main_pane_thinking_copy_click,
    test_worker_pane_thinking_copy_click,
    test_width_guard_suppresses_thinking_row_symbol,
)
from proxy_copy_block_probe import (
    test_block_row_gets_key_and_copy_registration,
    test_block_copy_matches_serializer_and_nests_in_msg_and_req,
    test_main_pane_block_copy_click,
    test_worker_pane_block_copy_click,
    test_width_guard_suppresses_block_row_symbol,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("proxy pane message-row and thinking-block copy-by-click probe")
    print("=" * 70)
    test_message_row_gets_key_and_copy_registration()
    test_message_copy_matches_serializer_and_req_subset()
    test_main_pane_message_copy_click()
    test_worker_pane_message_copy_click()
    test_width_guard_suppresses_msg_row_symbol()
    test_thinking_row_gets_key_and_copy_registration()
    test_thinking_copy_matches_serializer_and_msg_subset()
    test_main_pane_thinking_copy_click()
    test_worker_pane_thinking_copy_click()
    test_width_guard_suppresses_thinking_row_symbol()
    test_block_row_gets_key_and_copy_registration()
    test_block_copy_matches_serializer_and_nests_in_msg_and_req()
    test_main_pane_block_copy_click()
    test_worker_pane_block_copy_click()
    test_width_guard_suppresses_block_row_symbol()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p5_proxy_message_copy_click_probe_{stamp}.md"
    lines = [
        f"# P5 -- proxy pane message-row copy-by-click probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
