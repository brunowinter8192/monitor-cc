# dev/proxy/

## Role
Per-pass unit tests and targeted replay proofs for individual proxy strip/inject functions. Each
script verifies one function or narrow behavior in isolation. Use `dev/proxy_dual_log/` for
dual-log-quartet invariants; use `dev/proxy_instrumentation/` for full-pipeline end-to-end checks
against one recorded request.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly, e.g.
`python3 dev/proxy/<script>.py` or `./venv/bin/python dev/proxy/<script>.py` (see each module's
own usage for the exact invocation and any required env var).

## Flow
Each script either builds synthetic fixtures in-process or replays a recorded dual-log corpus
through one real pass function. Output is PASS/FAIL lines to stdout, a `HASH:` line, or a report
written to `dev/proxy/md/` or `/tmp/`. `test_strip_fix.py` fans out into `test_strip_fix_fixtures.py`
plus several sibling `test_strip_fix_cases_*.py` modules, all loading `src` via
`importlib.import_module` rather than a module-level `from src.` import.

## Modules

### pipeline_byte_identity.py (124 LOC)

**Purpose:** Byte-identity regression harness for the full modification pipeline over a bounded
prefix of a real `_original.jsonl`, for both worker contexts.
**Reads:** newest `_original.jsonl` under `src/logs/dual_log`, or `PROXY_PIPELINE_BYTE_IDENTITY_LOG`.
**Writes:** nothing — stdout only (`source`, `payloads`, one `HASH:` line).
**Called by:** none — manual regression harness, run before/after a `src/proxy/` refactor.
**Calls out:** `src.proxy.rules`, `src.proxy.cache`, `src.proxy.logging`,
`src.proxy.strip_inject_delta`, `src.proxy.message_summary`.

---

### addon_hook_byte_identity.py (160 LOC)

**Purpose:** Byte-identity regression harness for `ProxyAddon`'s hook methods themselves, driving a
real `ProxyAddon` with a fake mitmproxy flow.
**Reads:** newest `_original.jsonl` under `src/logs/dual_log`, or `ADDON_HOOK_BYTE_IDENTITY_LOG`; sets `PROXY_LOG_ID` and `MONITOR_CC_ROOT` (temp dir) itself. The hash covers the six dual logs plus captured stderr, which is empty now that the proxy reports errors to `proxy_error.log`.
**Writes:** nothing outside its own temp directory (cleaned up on exit) — stdout only.
**Called by:** none — manual regression harness, run before/after a `ProxyAddon` refactor.
**Calls out:** `src.proxy.addon` (`ProxyAddon`).

---

### proxy_bgcomplete_tests.py (155 LOC)

**Purpose:** Smoke tests for the task-notification wakeup-injection single-block fix across the
completed/failed x with/without output-file/task-id combinations.
**Reads:** nothing — synthetic in-script fixtures.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.message_passes` (`_apply_first_pass`), `src.proxy.strip_bg_completed`
(`_WAKEUP_TEXT`).

---

### replay_sn_notice_strip.py (206 LOC)

**Purpose:** Replay proof for `_apply_sn_notice_strip` over every captured dual-log — byte-exact
untouched vs. reconstructable-changed, plus strip/untouched counts.
**Reads:** all `*_original.jsonl` under the main checkout's `src/logs/dual_log` (hardcoded absolute
path — gitignored per-worktree).
**Writes:** `dev/proxy/md/replay_sn_notice_strip.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.message_passes_simple`, `src.proxy.strip_sn_notice`.

---

### replay_strip_v2.py (223 LOC)

**Purpose:** Two-part validator for the template-based SR strip against an old proxy's recorded
`stripped_msg_removed` field.
**Reads:** a hardcoded log directory under the project's pre-rename casing, absent on the current
tree — glob on a missing directory yields zero entries, not an error.
**Writes:** a report to `/tmp/replay_strip_v2.md`.
**Called by:** none — manual CLI, currently non-functional against the current tree.
**Calls out:** `src.proxy.strip_sr` — loaded via `importlib`.

---

### scan_sr_catalog.py (306 LOC)

**Purpose:** Scans proxy request logs into a catalog of stripped/missed system-reminder and
task-notification content, classified real/false-positive by heuristic.
**Reads:** a hardcoded log directory under the project's pre-rename casing, absent on the current
tree — glob on a missing directory yields zero entries, not an error.
**Writes:** a report to `/tmp/sr_catalog.md`.
**Called by:** none — manual CLI, currently non-functional against the current tree.
**Calls out:** none at import time — parses raw JSONL directly.

---

### test_role_keyed_rules.py (183 LOC)

**Purpose:** Unit tests for role-keyed system2 rule selection, covering role selection, degraded
configs, `exclude_projects`, and end-to-end resolution.
**Reads:** a synthetic shared-rules tree built in a temp directory; never reads the real
shared-rules directory.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.rules_config`, `src.proxy.rules`.

---

### test_strip_fix.py (221 LOC)

**Purpose:** Entry point for the largest suite in this directory — imports and runs every test
function from the sibling fixture/cases modules.
**Reads:** nothing external.
**Writes:** PASS/FAIL lines to stdout; exits 1 if any check fails.
**Called by:** none — manual CLI.
**Calls out:** none directly — imports sibling `dev/proxy/` modules only.

---

### test_strip_fix_fixtures.py (83 LOC)

**Purpose:** Loads the `src.proxy` strip/pass modules under test and builds the shared
`check()`/content fixtures every case module uses.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py` and every `test_strip_fix_cases_*.py` module.
**Calls out:** `src.proxy.strip_sr`, `src.proxy.payload_helpers`, `src.proxy.message_passes`,
`src.proxy.message_passes_simple`, `src.proxy.strip_bg_completed`, `src.proxy.strip_sn_notice`,
`src.proxy.strip_bg_launch_ack`, `src.proxy.strip_interrupt_marker`, `src.proxy.rules` — loaded via
`importlib.import_module`.

---

### test_strip_fix_cases_templates.py (308 LOC)

**Purpose:** Core template exact-match SR strip coverage, content-shape tests, plan-mode, and the
SR-family tool_result non-descent identity checks.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_env_context.py (264 LOC)

**Purpose:** The env-context `_ENV_CONTEXT_RE` replay fixtures — CC 2.1.258 trailing sentences,
bundled CLAUDE.md-preserved shape, and gitStatus-section widening.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_git_attribution.py (86 LOC)

**Purpose:** Fixtures for the git-attribution system-reminder strip: verbatim observed block in a 3-block msg #0, model-name independence, tool_result preservation, main/worker pipeline.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wakeup.py (200 LOC)

**Purpose:** Wakeup-injection false-positive guards, the SN-notice-paragraph anchored strip, and
role='system' task-notification/mid-turn message construction.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_launch_ack_interrupt.py (248 LOC)

**Purpose:** Bg-launch-ack ID/path line recovery across all three recognized CC wordings, and
`strip_interrupt_marker.py`'s two wordings.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wrapped_tn.py (82 LOC)

**Purpose:** The SR-wrapped task-notification full-chain regression plus its two byte-identical
control cases.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_badge.py (210 LOC)

**Purpose:** The `<total_tokens>` badge-suppression read-side fix — writer spans unchanged, badge
quiet only for the exact bare-tag class.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`, `test_strip_fix_cases_badge_nudge.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `src.proxy.strip_inject_delta`, `src.proxy.rule_ops`,
`src.proxy_display.proxy_badge`, `src.proxy_display.dual_log_accumulator`,
`src.proxy_display.render_turn`.

---

### test_strip_fix_cases_badge_nudge.py (131 LOC)

**Purpose:** The claude-f trailing-nudge widening of the total_tokens badge suppression class.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `test_strip_fix_cases_badge.py`.

---

### replay_env_context_strip.py (206 LOC)

**Purpose:** Before/after replay for `_ENV_CONTEXT_RE` fixes, bucketed by strip outcome and by
`currentDate`/`gitStatus` form.
**Reads:** all `*_original.jsonl` under the main checkout's `src/logs/dual_log` (hardcoded absolute
path).
**Writes:** `dev/proxy/md/replay_env_context_strip.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_sr` — loaded via `importlib`.

---

### marker_race_repro.sh (225 LOC)

**Purpose:** Deterministic repro/regression for proxy marker-file lifecycle race conditions
(restart, parallel session, crash, PID reuse, heartbeat reclaim).
**Reads:** the `_proxy_pid_is_live` bash function, sourced live from `src/claude_proxy_start.sh`.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI, run via `bash dev/proxy/marker_race_repro.sh`.
**Calls out:** `src/claude_proxy_start.sh` (`_proxy_pid_is_live`).

---

### poread_inject_tests.py (340 LOC)

**Purpose:** End-to-end regression guard for `inject_poread.py`'s marker-expansion pass, mint through
apply, across expansion/determinism/false-positive/race cases.
**Reads:** nothing external — writes its own temp files, mints its own marker fixtures.
**Writes:** stdout (pass/fail); its own temp files, cleaned up per test.
**Called by:** none — manual regression guard, re-run after touching `src/proxy/inject_poread.py` or
`_POREAD_SPEC`.
**Calls out:** `proxy.rules`, `proxy.inject_poread`, `proxy.strip_vocab`.

---

### test_sidecar_delta_chain.py (183 LOC)

**Purpose:** Regression guard isolating the CC-internal zero-tool sidecar call from the
per-model-family forwarded delta-hash chain.
**Reads:** nothing external — synthetic in-process payloads, writes to its own temp directory.
**Writes:** PASS/FAIL lines to stdout; its own temp dual-log files, cleaned up on exit.
**Called by:** none — manual regression guard, re-run after touching `addon_dual_log.py`/`DeltaState`.
**Calls out:** `proxy.addon_dual_log`, `proxy.addon_state`.

---

## State
No persistent state lives in this directory. Every script builds its own synthetic state locally
(tempdirs, in-process dicts, or its own temp log files) and discards it before exit.
`test_role_keyed_rules.py` is the one exception: it repoints `src.proxy.rules_config`'s
module-level globals (`_SHARED_RULES_DIR`, `_PROXY_RULES_CONFIG`, plus its two caches) for the
duration of its own run only, never touching the real shared-rules directory.

### test_live_copy_bootstrap.py (133 LOC)

**Purpose:** Builds a mirror repo in a temp directory with the exact copy layout of `claude_proxy_start.sh` (live shim + `.proxy_live_<id>/proxy/`) and proves `src/proxy_addon.py` resolves the live package and the mirror root, with and without `MONITOR_CC_ROOT`, in the non-live layout, and raises for a missing package or root.
**Reads:** the repo `src/` (copied into the mirror); a stub `mitmproxy` module it writes itself.
**Writes:** nothing — PASS/FAIL lines and a case count on stdout; cases run in parallel subprocesses.
**Called by:** none — manual test, run after a `src/proxy/` change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_env_and_family.py (162 LOC)

**Purpose:** Cases for `PROXY_LOG_ID` (missing raises at addon import, worker id parsing, dual-log file names), `_infer_model_family` (`unknown` for anything but haiku/sonnet/opus, logged once by the addon) and the unmapped-marker raise in `strip_sr`.
**Reads:** nothing persistent — temp `MONITOR_CC_ROOT`, in-process fakes.
**Writes:** nothing — PASS/FAIL lines and a case count on stdout; cases run in parallel subprocesses.
**Called by:** none — manual test, run after a `src/proxy/` change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_error_log.py (252 LOC)

**Purpose:** Cases proving each formerly stderr-only handler in `src/proxy/` now writes to `proxy_error.log` (request/response hooks fail open, decode/parse bypass, dual-log write failures, 4xx decode, bg_escape event log, poread refusal, schema store), plus log-on-change, size cap and silent logger failure.
**Reads:** nothing persistent — temp `MONITOR_CC_ROOT`, in-process fakes.
**Writes:** nothing — PASS/FAIL lines and a case count on stdout; cases run in parallel subprocesses.
**Called by:** none — manual test, run after a `src/proxy/` change.
**Calls out:** `src.proxy.*`.

---

### test_proxy_config_trace.py (230 LOC)

**Purpose:** Cases proving config-class swallows (`proxy_rules.json`, rule files, model override, context management, active plugins, exclude list, schema files) return their defaults and are noted in `proxy_error.log` once per changed error, re-arming after a healthy read.
**Reads:** nothing persistent — temp `HOME` and `MONITOR_CC_ROOT`, in-process fakes.
**Writes:** nothing — PASS/FAIL lines and a case count on stdout; cases run in parallel subprocesses.
**Called by:** none — manual test, run after a `src/proxy/` change.
**Calls out:** `src.proxy.*`.

---
