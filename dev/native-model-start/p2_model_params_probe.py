# INFRASTRUCTURE
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from model_params_test_infra import _RESULTS
from model_override_injection_tests import (
    test_legacy_only_unchanged,
    test_model_params_hit,
    test_model_params_miss,
    test_suffixed_model_id_is_deliberate_miss,
    test_model_params_presence_wins_over_legacy,
    test_empty_and_partial_entries,
    test_config_load_failure_fails_open,
    test_fixation_pins_model_params_snapshot,
    test_fixation_fresh_instance_picks_up_new_config,
    test_fixation_legacy_path_pinned_and_unchanged,
    test_fixation_miss_is_pinned_too,
    test_fixation_load_failure_does_not_pin,
)
from thinking_context_management_tests import (
    test_clear_thinking_edit_stripped_when_thinking_disabled,
    test_forwarded_delta_includes_thinking,
    test_context_management_strip_is_attributed,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("model_params probe — per-model config replacing the legacy model override")
    print("=" * 70)
    test_legacy_only_unchanged()
    test_model_params_hit()
    test_model_params_miss()
    test_suffixed_model_id_is_deliberate_miss()
    test_model_params_presence_wins_over_legacy()
    test_empty_and_partial_entries()
    test_config_load_failure_fails_open()
    test_fixation_pins_model_params_snapshot()
    test_fixation_fresh_instance_picks_up_new_config()
    test_fixation_legacy_path_pinned_and_unchanged()
    test_fixation_miss_is_pinned_too()
    test_fixation_load_failure_does_not_pin()
    test_clear_thinking_edit_stripped_when_thinking_disabled()
    test_forwarded_delta_includes_thinking()
    test_context_management_strip_is_attributed()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "native-model-start" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p2_model_params_probe_{stamp}.md"
    lines = [
        f"# P2 — model_params probe run ({datetime.now(timezone.utc).isoformat()})",
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
