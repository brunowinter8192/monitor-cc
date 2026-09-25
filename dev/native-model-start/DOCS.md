# dev/native-model-start/

## Role
Verification scripts for starting the orchestrator's main CC session natively on a chosen model: launcher flag precedence, the proxy's per-model parameter injection, and historical live-verifies of a CC pin bump. Touch when changing either; the pin-bump probes need no re-run otherwise.

## Public Interface
No `__init__.py`. Each script is its own entry point, run directly (Python with `python3`, the argv dry run with `bash`).

## Flow
Synthetic argv, mocked config or recorded dual-log payloads go in. Each script drives real production code (the launcher parse loop mirrored in bash, or a real proxy addon) and asserts invariants. Converted suites run as parallel fail-fast strands through the strand runner in `dev/refactoring/`; output is stdout plus fixed-name reports in `md/`.

## Modules

### p1_arg_parse_dry_run.sh (137 LOC)

**Purpose:** Dry-runs the launcher's model-flag precedence, mirrored from its parse loop; never starts the proxy or claude.
**Reads:** nothing persistent; in-process argv simulation.
**Writes:** `md/p1_arg_parse_dry_run_<timestamp>.md`.
**Called by:** none; manual guard, re-run after editing the parse loop.
**Calls out:** bash only.

---

### p2_model_params_probe.py (54 LOC)

**Purpose:** Entry point of the model-parameter probe: runs the test groups from the two group modules and writes the report.
**Reads:** nothing persistent; fixtures are built in-process.
**Writes:** `md/p2_model_params_probe_<timestamp>.md`.
**Called by:** none; manual guard.
**Calls out:** `model_params_test_infra.py`, `model_override_injection_tests.py`, `thinking_context_management_tests.py`.

---

### model_params_test_infra.py (24 LOC)

**Purpose:** Shared raising assertion helper and config helper used by every test group of the probe.
**Reads:** nothing.
**Writes:** nothing; prints a pass line or raises.
**Called by:** `p2_model_params_probe.py`, `model_override_injection_tests.py`, `thinking_context_management_tests.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### model_override_injection_tests.py (220 LOC)

**Purpose:** Tests 1-12: the per-model parameter lookup of the model override injection and the cross-call fixation mechanism.
**Reads:** nothing persistent; in-process fixtures.
**Writes:** nothing; results go through the shared assertion helper.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### thinking_context_management_tests.py (158 LOC)

**Purpose:** Tests 13-15: thinking and context-management self-consistency, the forwarded thinking field and strip-side field attribution.
**Reads:** nothing persistent; in-process fixtures.
**Writes:** nothing; results go through the shared assertion helper.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`, `src.proxy.logging`, `src.proxy.strip_inject_delta`, the attribution classifier in `dev/proxy_dual_log/attribution_coverage/` via `importlib`.

---

### p3_cache_breakpoints_probe.py (284 LOC)

**Purpose:** Replays two recorded pin-bump-era sessions through a real proxy addon and checks cache-breakpoint positional stability.
**Reads:** two pinned dual-log session stems, currently rotated out of the live corpus, so the script raises before writing.
**Writes:** `md/p3_cache_breakpoints_probe_report.md`, a historical snapshot not regenerated.
**Called by:** none; historical pin-bump live-verify.
**Calls out:** `src.proxy.addon`.

---

### p4_dual_log_integrity_probe.py (243 LOC)

**Purpose:** Verifies the composition invariant and top-level payload and schema stability on the same two recorded sessions.
**Reads:** the same two pinned session stems, currently absent.
**Writes:** `md/p4_dual_log_integrity_probe_report.md`, a historical snapshot.
**Called by:** none; historical pin-bump live-verify.
**Calls out:** `src.proxy.rules`, `src.proxy.diff_engine`.

---

### p5_strip_wordings_probe.py (205 LOC)

**Purpose:** Checks strip coverage of background-launch, completion and task-notification wordings via a dual-log census plus a current-code replay.
**Reads:** the same two pinned sessions' log streams, currently absent.
**Writes:** `md/p5_strip_wordings_probe_report.md`, a historical snapshot.
**Called by:** none; historical pin-bump live-verify.
**Calls out:** `src.proxy.rules`, `src.proxy.payload_helpers`.

---

## State
No persistent state. Test-group modules share only the assertion helper; every strand is its own subprocess.
