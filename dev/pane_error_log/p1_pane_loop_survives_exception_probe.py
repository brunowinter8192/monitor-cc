# INFRASTRUCTURE
import sys
from datetime import datetime, timezone

from p1_shared import _RESULTS
from p1_pane_modules import WORKTREE_ROOT
from p1_pane_tests import (
    test_gpu_pane, test_keyboard_interrupt_and_system_exit_not_swallowed, test_news_log_pane,
    test_news_pane, test_proxy_pane, test_tokens_pane, test_warnings_pane,
    test_worker_proxy_pane, test_worker_tokens_pane,
)
from p1_sink_tests import test_failing_log_write_does_not_raise, test_log_size_capping


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("pane_error_log probe — 8 pane loops survive an uncaught exception")
    print("=" * 70)
    test_worker_tokens_pane()
    test_proxy_pane()
    test_worker_proxy_pane()
    test_tokens_pane()
    test_warnings_pane()
    test_gpu_pane()
    test_news_pane()
    test_news_log_pane()
    test_keyboard_interrupt_and_system_exit_not_swallowed()
    test_failing_log_write_does_not_raise()
    test_log_size_capping()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


# FUNCTIONS

def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "pane_error_log" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p1_pane_loop_survives_exception_probe_{stamp}.md"
    lines = [
        f"# P1 — pane_error_log probe run ({datetime.now(timezone.utc).isoformat()})",
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
