# dev/native-model-start/

## Role
Verification scripts for starting the orchestrator's main CC session natively on a chosen model:
the launcher's flag precedence, the proxy's per-model `model_params` injection, and a historical
live-verify of the CC 2.1.223 pin bump. Touch it when changing either; the pin-bump probes don't
need re-running otherwise.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly, e.g.
`python3 dev/native-model-start/p2_model_params_probe.py` or `bash p1_arg_parse_dry_run.sh`.

## Flow
Synthetic argv (`p1`), mocked config (`p2` and its test-group modules), or recorded dual-log
payloads (`p3`/`p4`/`p5`) go in. Each script drives real production code (the launcher's parse
loop mirrored in bash, or a real `ProxyAddon`/`apply_modification_rules` instance) and asserts
specific invariants. Output is stdout PASS/FAIL plus a fixed-name report `md/p2_model_params_probe.md` for the strand run of `p2`.
Converted suites run as parallel strands through `dev/refactoring/strand_runner.py`: `python <file>` starts one subprocess per strand (`--strand <name>`), each strand aborts at its first failing `check`, sibling strands still finish, and the exit code is 1 if any strand aborted. The strand names are the module constant `_STRANDS`.

## Modules

### p1_arg_parse_dry_run.sh (154 LOC)

**Purpose:** Dry-runs the `--fable`/`--opus`/`--model` precedence logic mirrored from
`src/claude_proxy_start.sh`'s parse loop; never starts the proxy or claude.
**Reads:** nothing persistent — pure in-process argv simulation.
**Writes:** `md/p1_arg_parse_dry_run_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after editing the parse loop.
**Calls out:** stdlib bash only.

---

### p2_model_params_probe.py (54 LOC)

**Purpose:** Entry point for the model_params probe — runs the 15 test groups imported from the
two test-group modules in order and writes the report.
**Reads:** nothing persistent — builds all fixtures in-process.
**Writes:** `md/p2_model_params_probe_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after touching `_inject_model_override`.
**Calls out:** `model_params_test_infra`, `model_override_injection_tests`,
`thinking_context_management_tests`.

---

### model_params_test_infra.py (24 LOC)

**Purpose:** Shared raising `check()` assertion infra and the `_with_config` helper
used by every test group in this probe.
**Reads:** nothing.
**Writes:** nothing — `check()` prints a PASS line or raises `AssertionError`.
**Called by:** `p2_model_params_probe.py`, `model_override_injection_tests.py`,
`thinking_context_management_tests.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### model_override_injection_tests.py (220 LOC)

**Purpose:** Tests 1-12 — `_inject_model_override`'s per-model `model_params` lookup (a config without `model_params` is ignored), plus the cross-call fixation mechanism.
**Reads:** nothing persistent — builds all fixtures in-process.
**Writes:** nothing — results recorded via `model_params_test_infra.check`.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### thinking_context_management_tests.py (158 LOC)

**Purpose:** Tests 13-15 — `_strip_clear_thinking_edit`'s thinking/context_management
self-consistency, the forwarded `thinking` field, and strip-side field attribution.
**Reads:** nothing persistent — builds all fixtures in-process.
**Writes:** nothing — results recorded via `model_params_test_infra.check`.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`, `src.proxy.logging`, `src.proxy.strip_inject_delta`,
`dev/proxy_dual_log/attribution_coverage/attribution_coverage_classify.py` (loaded via `importlib.util`).

---

### p3_cache_breakpoints_probe.py (282 LOC)

**Purpose:** Replays two 223-era recorded sessions through a real `ProxyAddon()` and checks cache
breakpoint positional stability plus shared-index content diffs.
**Reads:** two pinned `_original.jsonl` session stems under `src/logs/dual_log` — currently
absent (rotated out of the live corpus); the script raises before writing its report.
**Writes:** `md/p3_cache_breakpoints_probe_report.md` — not regenerated while the source sessions
are absent; the tracked file is a historical snapshot.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.addon` (`ProxyAddon`, `_derive_worker_context`).

---

### p4_dual_log_integrity_probe.py (241 LOC)

**Purpose:** Verifies the composition invariant against `compose_block` and top-level payload/
schema stability, on the same two 223-era sessions as `p3_`.
**Reads:** the same two pinned session stems as `p3_cache_breakpoints_probe.py` — currently
absent; the script raises before writing its report.
**Writes:** `md/p4_dual_log_integrity_probe_report.md` — a historical snapshot, not regenerated.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.diff_engine`.

---

### p5_strip_wordings_probe.py (203 LOC)

**Purpose:** Checks bg-launch-ack/bg-completed/task-notification strip coverage on 223-era
wordings via a dual-log fn_map census plus a current-code replay sweep.
**Reads:** the same two pinned session stems' `_original`/`_stripped`/`_injected.jsonl` files —
currently absent; the script raises before writing its report.
**Writes:** `md/p5_strip_wordings_probe_report.md` — a historical snapshot, not regenerated.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.payload_helpers`.

---

## State
No persistent state lives in this directory. Test-group modules share only the raising `check()` of `model_params_test_infra.py`; every strand is its own subprocess.
