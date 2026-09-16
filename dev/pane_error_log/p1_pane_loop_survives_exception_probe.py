"""
P1 — verifies all 8 pane event loops (7 previously unguarded + worker_tokens_pane.py, the reference
pattern) survive an uncaught exception raised inside the loop body, log it with a pane
identifier via the shared src/pane_error_log.py sink, and keep running — and that the guard
does NOT swallow deliberate termination (KeyboardInterrupt/SystemExit still propagate, `finally:`
cleanup still runs where one exists).

Cannot be verified with a live tmux session (no pane process to kill); instead, each loop's
run_*_loop() is loaded (via importlib, package-qualified — these modules use `from ..constants
import ...` double-dot relative imports, so they must be loaded as real `src.<pkg>.<mod>`
submodules, not path-inserted top-level modules) and invoked directly with its I/O primitives
monkeypatched per-module:
  - 7 of the 8 loops have keyboard/mouse: read_keypress raises a distinctive marker exception on
    its 1st call only, then returns None; setup_keyboard_input/enable_mouse are no-op'd;
    disable_mouse/restore_terminal are counted, to prove the existing `finally:` cleanup still runs
  - the 8th (news_pane/log_pane.py::run_news_log_loop) has NO keyboard/mouse and NO `finally:` —
    it never had one and this milestone does not invent one — so the marker exception is injected
    via find_log_file() instead, and only the catch+log+continue behavior is asserted, not cleanup
  - the tick function (wait_for_input, or time.sleep for news_pane/log_pane.py) counts calls and
    raises _ProbeStop (a BaseException, like Ctrl-C) on the 3rd call — guarantees the loop cannot
    hang, and proves the loop survived 2 full iterations past the injected crash
Real render/data-refresh calls run for real (against whatever real session/tmux state exists on
this machine) — any exception they raise is caught by the SAME new guard and logged with the
SAME pane id, which is harmless to the assertions below (they only check for the specific
injected marker, not for an empty log).

Run from project root or worktree root:
    ./venv/bin/python dev/pane_error_log/p1_pane_loop_survives_exception_probe.py
"""

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
