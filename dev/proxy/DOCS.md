# dev/proxy/

## Role
Per-pass unit tests and targeted replay proofs for individual proxy strip/inject functions, each verifying one function or narrow behavior in isolation. Use `dev/proxy_dual_log/` for dual-log invariants and `dev/proxy_instrumentation/` for full-pipeline checks on one recorded request.

## Public Interface
No `__init__.py`. Each script is its own entry point, run with `python3` or `./venv/bin/python` (some need an env var).

## Flow
Each script builds synthetic fixtures in-process or replays a recorded dual-log corpus through one real pass. Output is pass/fail lines, a hash line, or a report under `dev/proxy/md/` or the temp dir. The strip-fix suite fans out from one entry module into a fixtures module and several case modules. Converted suites run as parallel fail-fast strands via the strand runner in `dev/refactoring/`.

## Modules

### pipeline_byte_identity.py (124 LOC)

**Purpose:** Verification aid: hashes the full modification pipeline over a bounded prefix of a real original log for both worker contexts.
**Reads:** the newest original log, or a pinned path via an env var.
**Writes:** stdout only.
**Called by:** none; run before and after a proxy refactor. Asserts nothing.
**Calls out:** the rules, cache, logging, delta and summary modules of `src.proxy`.

---

### addon_hook_byte_identity.py (160 LOC)

**Purpose:** Verification aid: hashes the addon's hook behavior by driving a real addon with a fake flow.
**Reads:** the newest original log, or a pinned path via an env var; sets its own env and a temp monitor root.
**Writes:** stdout only, plus a temp dir cleaned on exit.
**Called by:** none; run before and after an addon refactor. Asserts nothing.
**Calls out:** `src.proxy.addon`.

---

### proxy_bgcomplete_tests.py (160 LOC)

**Purpose:** Smoke tests for the task-notification wakeup-injection single-block fix across completed and failed cases.
**Reads:** nothing; synthetic fixtures.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.message_passes`, `src.proxy.strip_bg_completed`.

---

### replay_sn_notice_strip.py (206 LOC)

**Purpose:** Replay proof of the SN-notice strip over every captured dual log: byte-exact untouched versus reconstructable-changed, plus counts.
**Reads:** all original logs of the main checkout's dual log (hardcoded path).
**Writes:** `dev/proxy/md/replay_sn_notice_strip.md`.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.message_passes_simple`, `src.proxy.strip_sn_notice`.

---

### replay_strip_v2.py (223 LOC)

**Purpose:** Two-part validator of the template-based system-reminder strip against an old proxy's recorded removal field.
**Reads:** a hardcoded log directory under a pre-rename path, absent now; a glob on it yields zero entries.
**Writes:** a report in the temp dir.
**Called by:** none; currently non-functional against the current tree.
**Calls out:** `src.proxy.strip_sr` via `importlib`.

---

### scan_sr_catalog.py (306 LOC)

**Purpose:** Scans proxy request logs into a catalog of stripped and missed system-reminder and task-notification content, classified by heuristic.
**Reads:** the same absent pre-rename log directory.
**Writes:** a report in the temp dir.
**Called by:** none; currently non-functional against the current tree.
**Calls out:** none at import time.

---

### test_role_keyed_rules.py (204 LOC)

**Purpose:** Unit tests for role-keyed system2 rule selection: role choice, degraded configs, project exclusion and end-to-end resolution.
**Reads:** a synthetic shared-rules tree in a temp dir, never the real one.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.rules_config`, `src.proxy.rules`.

---

### test_strip_fix.py (251 LOC)

**Purpose:** Entry point of the largest suite: imports and runs every test from the sibling fixture and case modules.
**Reads:** nothing external.
**Writes:** stdout; exits 1 if any check fails.
**Called by:** none; manual CLI.
**Calls out:** the sibling `dev/proxy/` modules only.

---

### test_strip_fix_fixtures.py (87 LOC)

**Purpose:** Loads the proxy strip and pass modules under test and builds the shared check helper and content fixtures.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py` and every case module.
**Calls out:** the strip and pass modules of `src.proxy`, loaded via `importlib`.

---

### test_strip_fix_cases_templates.py (308 LOC)

**Purpose:** Core template exact-match system-reminder strip coverage, content shapes, plan mode and tool-result non-descent identity checks.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_env_context.py (264 LOC)

**Purpose:** Env-context strip replay fixtures: CC 2.1.258 trailing sentences, bundled CLAUDE.md-preserved shape, git-status widening.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_git_attribution.py (86 LOC)

**Purpose:** Fixtures for the git-attribution system-reminder strip: verbatim observed block, model-name independence, tool-result preservation.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wakeup.py (200 LOC)

**Purpose:** Wakeup-injection false-positive guards, the anchored SN-notice paragraph strip and system-role message construction.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_launch_ack_interrupt.py (248 LOC)

**Purpose:** Background-launch-ack id and path line recovery across the three recognized wordings, and the interrupt-marker strip's two wordings.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wrapped_tn.py (82 LOC)

**Purpose:** The system-reminder-wrapped task-notification full-chain regression plus two byte-identical control cases.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_pasted_content.py (143 LOC)

**Purpose:** Cases for the pasted-content wrap strip: real wraps stripped, quoted mentions in assistant and tool-result content preserved, pass gating and attribution.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_badge.py (210 LOC)

**Purpose:** The token-count badge-suppression read-side fix: writer spans unchanged, badge quiet only for the exact bare-tag class.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`, `test_strip_fix_cases_badge_nudge.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `src.proxy.strip_inject_delta`, `.rule_ops`, `src.proxy_display.proxy_badge`, `.dual_log_accumulator`, `.render_turn`.

---

### test_strip_fix_cases_badge_nudge.py (131 LOC)

**Purpose:** The trailing-nudge widening of the token-count badge suppression class.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `test_strip_fix_cases_badge.py`.

---

### replay_env_context_strip.py (206 LOC)

**Purpose:** Before and after replay for env-context strip fixes, bucketed by outcome and by date and git-status form.
**Reads:** all original logs of the main checkout's dual log (hardcoded path).
**Writes:** `dev/proxy/md/replay_env_context_strip.md`.
**Called by:** none; manual CLI.
**Calls out:** `src.proxy.strip_sr` via `importlib`.

---

### marker_race_repro.sh (225 LOC)

**Purpose:** Deterministic repro and regression for proxy marker-file lifecycle races: restart, parallel session, crash, PID reuse, heartbeat reclaim.
**Reads:** the live-check shell function, sourced from `src/claude_proxy_start.sh`.
**Writes:** stdout only.
**Called by:** none; run via `bash dev/proxy/marker_race_repro.sh`.
**Calls out:** `src/claude_proxy_start.sh`.

---

### poread_inject_tests.py (323 LOC)

**Purpose:** End-to-end regression guard for the poread marker-expansion pass, mint through apply, across expansion, determinism, false-positive and race cases.
**Reads:** nothing external; writes its own temp files and marker fixtures.
**Writes:** stdout; temp files cleaned per test.
**Called by:** none; re-run after touching the poread injection.
**Calls out:** `proxy.rules`, `proxy.inject_poread`, `proxy.strip_vocab`.

---

### test_sidecar_delta_chain.py (165 LOC)

**Purpose:** Regression guard isolating the CC-internal zero-tool sidecar call from the per-model-family forwarded delta-hash chain.
**Reads:** nothing external; synthetic payloads.
**Writes:** stdout; temp dual-log files cleaned on exit.
**Called by:** none; re-run after touching the dual-log addon or delta state.
**Calls out:** `proxy.addon_dual_log`, `proxy.addon_state`.

---

### test_live_copy_bootstrap.py (133 LOC)

**Purpose:** Builds a mirror repo with the launcher's live-copy layout and proves the addon entry resolves the live package and root, raising when missing.
**Reads:** the repo `src/` (copied into the mirror); a stub mitmproxy module it writes.
**Writes:** stdout pass/fail and case count; cases run in parallel subprocesses.
**Called by:** none; run after a proxy change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_env_and_family.py (162 LOC)

**Purpose:** Cases for the required log-id env var, worker id parsing, dual-log file names, model-family inference and the unmapped-marker raise.
**Reads:** nothing persistent; temp monitor root, in-process fakes.
**Writes:** stdout pass/fail and case count; parallel subprocesses.
**Called by:** none; run after a proxy change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_error_log.py (252 LOC)

**Purpose:** Cases proving each formerly stderr-only proxy handler now writes to the proxy error log, plus log-on-change, size cap and silent logger failure.
**Reads:** nothing persistent; temp monitor root, in-process fakes.
**Writes:** stdout pass/fail and case count; parallel subprocesses.
**Called by:** none; run after a proxy change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_config_trace.py (230 LOC)

**Purpose:** Cases proving config-class swallows return defaults and are noted once per changed error in the proxy error log, re-arming after a healthy read.
**Reads:** nothing persistent; temp HOME and monitor root, in-process fakes.
**Writes:** stdout pass/fail and case count; parallel subprocesses.
**Called by:** none; run after a proxy change.
**Calls out:** `src.proxy.*`.

---

## State
No persistent state. Every script builds and discards its own state. One test repoints the rules-config module's globals for its own run only and never touches the real shared-rules directory.
