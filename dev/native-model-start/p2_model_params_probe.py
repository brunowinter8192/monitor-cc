"""
P2 — verifies src/proxy/inject_helpers.py::_inject_model_override's rework: per-model 'model_params'
config path replacing the legacy family-bucketed model_override/model_override_worker rewrite.

Covers: legacy-config-only -> byte-identical legacy behavior incl. model rewrite; model_params hit
-> thinking/effort/max_tokens applied, model field untouched; model_params miss -> payload
untouched; model_params present (even empty {}) alongside legacy sections -> model_params wins, no
rewrite; empty per-model entry -> untouched; partial entry (one key only) -> only that key applied;
config load failure -> fail-open untouched; a suffixed model-id variant is a deliberate MISS
(exact-match only, no normalization).

2026-09 fixation coverage: a caller-owned dict (fixated_model_override, ProxyAddon.model_params_
fixated in production) pins the WHOLE resolved unit (model_params entry, or the legacy section) on
the first call for a given exact model id, and every subsequent call for that model id replays the
pinned snapshot instead of re-reading _load_config() — proves (a) first request uses the
then-current config, (b) a config change AFTER the first request does not alter subsequent
injections against the SAME dict (same simulated proxy process), (c) a FRESH dict (simulated fresh
addon instance / hot-reload) picks up the new config, (d) the legacy path is pinned the same way
and stays byte-identical to the unfixated legacy behavior. Also covers: a genuine miss (hit but no
per-model entry) pins "no injection" too; a genuine _load_config() exception does NOT pin, so the
very next call retries live. All 7 pre-fixation tests below call _inject_model_override with only
2 positional args (no fixated_model_override) — the default (None -> a fresh, discarded dict per
call) keeps them independent, proving the old 2-arg call form is unaffected by this rework.

2026-09 thinking/context_management self-consistency coverage (Test 13): once thinking can be
switched to {"type": "disabled"} (menubar thinking toggle, or any future path), a surviving
`clear_thinking_20251015` context_management edit makes the request self-contradictory and the API
returns a 400 (reproduced verbatim from a real capture,
`api_requests_worker_25c51a2e_cache-write-run_1789308787`). Covers `_strip_clear_thinking_edit`:
the edit is removed when thinking ends up disabled regardless of which path disabled it, sibling
edits like `clear_tool_uses_20250919` survive, an emptied edits list drops the whole
`context_management` key rather than carrying an empty list, and a non-disabled thinking value
leaves `context_management` byte-identical (same object, not just equal). Test 14 covers
`src/proxy/logging.py::_build_forwarded_delta` recording the forwarded `thinking` value (on/off/
absent), added so this exact failure is now readable straight off the forwarded dual-log.

Test 15 covers a follow-up review point: a context_management removal now reaches the
stripped-delta path for the first time (previously that field only ever got INJECTED, never
STRIPPED). `src/proxy/strip_inject_delta.py` used to hold its own `_FIELD_STRIP_FN`/
`_FIELD_INJECT_FN` maps, proven dead code (the real `fn_map` written to the stripped/injected
JSONL never carries a field-level entry for ANY top-level field, thinking/output_config/max_tokens
included — verified directly, not just by absence of a call site) and already drifted from the live
copy (missing `context_management` on the strip side); those maps have since been removed from that
module entirely. The tool that DOES actually attribute `fields_delta` entries is
`dev/proxy_dual_log/attribution_coverage.py`'s own `_FIELD_STRIP_FN` dict, which was missing
`context_management` on the strip side and would have reported the removal as
`UNATTR:context_management`; fixed there, verified here.

Run from project root or worktree root:
    ./venv/bin/python dev/native-model-start/p2_model_params_probe.py
"""

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
