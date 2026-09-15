# dev/proxy/

## Role
Per-pass unit tests and targeted replay proofs for individual proxy strip/inject functions
(`src/proxy/message_passes.py` and its `strip_*.py`/`inject_poread.py` sub-passes, `src/proxy/rules_config.py`) plus one
bash regression for the proxy marker-file lifecycle (`src/claude_proxy_start.sh`). Each script
verifies one function or one narrow behavior in isolation. Use `dev/proxy_dual_log/` instead when the
check depends on the dual-log quartet's own losslessness/self-consistency invariants; use
`dev/proxy_instrumentation/` instead when the check must drive the full production pipeline
end-to-end against one recorded request.

## Flow
Each script either builds synthetic fixtures in-process or replays a recorded dual-log corpus through
one real pass function, then prints PASS/FAIL to stdout or writes a report to `md/`.

`test_strip_fix.py` (the largest suite here) splits into a thin entry script plus sibling
`test_strip_fix_fixtures.py` (module loads, `check()`/`PASS`/`FAIL`, shared content builders) and
several `test_strip_fix_cases_*.py` modules (the `test_*`/`tNN_*`/`wNN_*`/`ttNN_*` functions,
grouped by the concern each covers), following the split convention already used in
`dev/proxy_dual_log/` and `dev/pane_search/`. Sibling modules import each other with plain
`from test_strip_fix_... import name`; none of them literally write `from src.`/`import src.` at
module level (blocked by `src/hooks/block_dev_imports_src.py` for any `dev/` file outside
`*/tests/`) — they load `src` via `importlib.import_module` instead, same as the pre-existing
`replay_*.py` scripts in this directory.

## Modules

### pipeline_byte_identity.py (153 LOC)

**Purpose:** Byte-identity regression harness for the full `src/proxy/` modification pipeline —
replays `apply_modification_rules` through `_build_errors_entries` over a bounded prefix of a real
`_original.jsonl`, for both `worker_context="main"` and `"worker:x"`, hashing the full output
sequence.
**Reads:** one `_original.jsonl` file — newest under src/logs/dual_log by default, or the path in
`PROXY_PIPELINE_BYTE_IDENTITY_LOG` when set.
**Writes:** nothing — stdout only (`source`, `payloads`, one `HASH:` line).
**Called by:** none — manual regression harness, run before and after a `src/proxy/` refactor.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.cache`
(`_strip_all_cache_control`, `_set_cache_breakpoints`), `src.proxy.logging`
(`_build_forwarded_delta`, `_build_errors_entries`), `src.proxy.strip_inject_delta`
(`_build_stripped_injected_deltas`), `src.proxy.message_summary` (`_summarize_message`).

---

### addon_hook_byte_identity.py (202 LOC)

**Purpose:** Byte-identity regression harness for the `ProxyAddon` hook methods themselves
(`request`, `responseheaders`, `response`) — constructs a real `ProxyAddon` against a temp root and
drives all three hooks with a minimal fake mitmproxy flow over a bounded prefix of a real
`_original.jsonl`, hashing the resulting dual-log files plus normalized stderr.
**Reads:** one `_original.jsonl` file — newest under src/logs/dual_log by default, or the path in
`ADDON_HOOK_BYTE_IDENTITY_LOG` when set.
**Writes:** nothing outside its own temp directory (cleaned up on exit) — stdout only.
**Called by:** none — manual regression harness, run before and after a `ProxyAddon` refactor.
**Calls out:** `src.proxy.addon` (`ProxyAddon`).

---

### proxy_bgcomplete_tests.py (173 LOC)

**Purpose:** Smoke tests for the task-notification wakeup-injection single-block fix — a
completed/failed task notification with or without output-file/task-id metadata must collapse into
one block with the wakeup line in fixed order, summary always dropped.
**Reads:** nothing — synthetic in-script fixtures.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src/proxy/message_passes.py` (`_apply_first_pass`), `src/proxy/strip_bg_completed.py`
(`_WAKEUP_TEXT`).

---

### replay_sn_notice_strip.py (233 LOC)

**Purpose:** Replay proof for `_apply_sn_notice_strip` over every captured dual-log — asserts every
message not reported as changed is byte-exact untouched, every changed message reconstructs exactly
when the removed paragraph is spliced back in, and reports genuine-strip vs. untouched-occurrence
counts.
**Reads:** all `*_original.jsonl` files under src/logs/dual_log in the main checkout (hardcoded
absolute path, since src/logs is gitignored per-worktree).
**Writes:** `dev/proxy/md/replay_sn_notice_strip.md`.
**Called by:** none — manual CLI.
**Calls out:** `src/proxy/message_passes_simple.py` (`_apply_sn_notice_strip`),
`src/proxy/strip_sn_notice.py` (`_SN_NOTICE_PARAGRAPH`, `_SN_NOTICE_BLOCK`).

---

### replay_strip_v2.py (259 LOC)

**Purpose:** Two-part validator for the template-based SR strip (`strip_sr.py`) against an old
proxy's recorded `stripped_msg_removed` field.
**Reads:** a hardcoded log directory path that does not exist on the current tree (see Gotchas).
**Writes:** a report to a scratch path outside `dev/proxy/md/` (see Gotchas).
**Called by:** none — manual CLI, currently non-functional (see Gotchas).
**Calls out:** `src/proxy/strip_sr.py` (`_apply_sr_strip`, `_match_template`, `_ALL_TEMPLATES`,
`_STANDALONE_SR_RE`, `_INNER_SR_RE`, `_strip_system_reminders`) — loaded via `importlib`.

---

### scan_sr_catalog.py (333 LOC)

**Purpose:** Scans proxy request logs to build a catalog of system-reminder/task-notification content
— what the proxy stripped (classified real-SR/real-TN/false-positive by heuristic) and what it missed
(standalone SRs still present in `raw_payload.messages` after processing).
**Reads:** a hardcoded log directory path that does not exist on the current tree (see Gotchas).
**Writes:** a report to a scratch path outside `dev/proxy/md/` (see Gotchas).
**Called by:** none — manual CLI, currently non-functional (see Gotchas).
**Calls out:** none at import time — parses raw JSONL directly.

---

### test_role_keyed_rules.py (219 LOC)

**Purpose:** Unit tests for role-keyed system2 rule selection (`rules_config._load_system2_rules`) —
selection is keyed off session role (`"worker:<name>"` vs. `"main"`), retaining only the haiku
short-circuit from model-family keying. Covers role selection, degraded configs, `exclude_projects`
under both roles, and end-to-end resolution through `apply_modification_rules`.
**Reads:** a synthetic shared-rules tree it builds in a temp directory (repoints
`rules_config._SHARED_RULES_DIR`/`_PROXY_RULES_CONFIG`); never reads the real shared-rules directory.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src/proxy/rules_config.py` (`_load_system2_rules`, module globals/caches),
`src/proxy/rules.py` (`apply_modification_rules`).

---

### test_strip_fix.py (207 LOC)

**Purpose:** Entry point for the largest suite in this directory — imports every `test_*`/`tNN_*`/
`wNN_*`/`ttNN_*` function from the sibling `test_strip_fix_fixtures.py`/`test_strip_fix_cases_*.py`
modules and runs them in the original fixed order.
**Reads:** nothing external.
**Writes:** PASS/FAIL lines to stdout; exits 1 if any check fails.
**Called by:** none — manual CLI.
**Calls out:** `test_strip_fix_fixtures.py`, `test_strip_fix_cases_templates.py`,
`test_strip_fix_cases_env_context.py`, `test_strip_fix_cases_wakeup.py`,
`test_strip_fix_cases_launch_ack_interrupt.py`, `test_strip_fix_cases_wrapped_tn.py`,
`test_strip_fix_cases_badge.py`, `test_strip_fix_cases_badge_nudge.py`.

---

### test_strip_fix_fixtures.py (84 LOC)

**Purpose:** Loads the `src.proxy` strip/pass modules under test, holds the shared `check()`/
`PASS`/`FAIL`, and builds the SR/tool_result/text-block content fixtures every case module uses.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py` and every `test_strip_fix_cases_*.py` module.
**Calls out:** `src.proxy.strip_sr`, `src.proxy.payload_helpers`, `src.proxy.message_passes`,
`src.proxy.message_passes_simple`, `src.proxy.strip_bg_completed`, `src.proxy.strip_sn_notice`,
`src.proxy.strip_bg_launch_ack`, `src.proxy.strip_interrupt_marker`, `src.proxy.rules` — loaded via
`importlib.import_module`.

---

### test_strip_fix_cases_templates.py (341 LOC)

**Purpose:** `T01`-`T39` — core template exact-match SR strip coverage (8 templates × 3 cases),
content-shape tests, plan-mode, `_find_system_reminder_blocks`, `_content_contains`, the SR-family
tool_result non-descent identity checks, and top-level-still-works evidence.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_env_context.py (303 LOC)

**Purpose:** `T40`-`T51` — the env-context `_ENV_CONTEXT_RE` replay fixtures: the CC 2.1.258
trailing-sentences form, the bundled CLAUDE.md-preserved shape, and the gitStatus-section widening
(including two real CC issue-report layouts).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wakeup.py (236 LOC)

**Purpose:** `W01`-`W14`, `W30` — wakeup-injection false-positive guards (TN/BGK tag quoted inside
tool_result), the SN-notice-paragraph anchored strip, and role='system' task-notification/mid-turn
message construction.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_launch_ack_interrupt.py (305 LOC)

**Purpose:** `W15`-`W29`, `W34` — bg-launch-ack ID/path line recovery across all three recognized
CC wordings (initial launch, manual backgrounding, auto-backgrounded-on-timeout), and
`strip_interrupt_marker.py`'s two wordings.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_wrapped_tn.py (103 LOC)

**Purpose:** `W31`-`W33` — the SR-wrapped task-notification full-chain regression (real
`apply_modification_rules` pipeline, not a hand-picked pass subset) plus its two byte-identical
control cases (bare role='system' TN, unwrapped role='user' TN).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`.

---

### test_strip_fix_cases_badge.py (255 LOC)

**Purpose:** `TT01`-`TT09` — the `<total_tokens>` badge-suppression read-side fix: writer spans
unchanged, badge goes quiet only for the exact bare-tag class, every other nuke/injection still
badges, end to end through the real header renderer.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`, `test_strip_fix_cases_badge_nudge.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `src.proxy.strip_inject_delta`, `src.proxy.rule_ops`,
`src.proxy_display.proxy_badge`, `src.proxy_display.dual_log_accumulator`,
`src.proxy_display.render_turn` — loaded via `importlib.import_module`/inline `from src.` (indented,
not module-level, so outside the dev-import-hook's pattern).

---

### test_strip_fix_cases_badge_nudge.py (149 LOC)

**Purpose:** `TT10`-`TT14` — the claude-f trailing-nudge widening of the total_tokens badge
suppression class (single/combined/repeated nudge sentences, near-miss real-content mixes).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `test_strip_fix.py`.
**Calls out:** `test_strip_fix_fixtures.py`, `test_strip_fix_cases_badge.py`.

---

### replay_env_context_strip.py (255 LOC)

**Purpose:** Before/after replay for `_ENV_CONTEXT_RE` fixes (CC 2.1.258 trailing-sentences, and the
gitStatus-section widening) — scans every top-level standalone system-reminder block across the
dual-log corpus, classifies each against both the old and live regex, split by bucket (stripped /
left-pure / left-bundled / CLAUDE.md-preserved) AND by form (`currentDate` vs `gitStatus`).
**Reads:** all `*_original.jsonl` files under src/logs/dual_log in the main checkout (hardcoded
absolute path).
**Writes:** `dev/proxy/md/replay_env_context_strip.md`.
**Called by:** none — manual CLI.
**Calls out:** `src/proxy/strip_sr.py` (`_ENV_CONTEXT_RE`, `_PRESERVE_PREAMBLE`,
`_STANDALONE_SR_RE`, `_INNER_SR_RE`, imported via `importlib`).

---

### marker_race_repro.sh (225 LOC)

**Purpose:** Deterministic repro/regression for proxy marker-file lifecycle race conditions:
restart-within-60s with a dead PID, a parallel live session not getting clobbered, crash with a stale
log, PID-reuse by an unrelated alive process reading as stale via identity check (not bare `kill -0`),
and the heartbeat reclaim decision across missing/dead-PID/live-owner marker states.
**Reads:** the `_proxy_pid_is_live` bash function, sourced live from `src/claude_proxy_start.sh`; spawns real background
subprocesses and fake log files under a `mktemp -d` directory.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI, run via `bash dev/proxy/marker_race_repro.sh` from project root.
**Calls out:** `src/claude_proxy_start.sh` (`_proxy_pid_is_live`).

---

### poread_inject_tests.py (362 LOC)

**Purpose:** End-to-end regression guard for `src/proxy/inject_poread.py` — mints markers from this
file's own pinned literal copy of the marker contract (`_PINNED_MARKER_PREFIX`, `_PINNED_HASH_LEN`,
`POREAD_NOTICE`, hardcoded here, independent of `inject_poread.py`'s own hand-maintained copy — the
CLI that used to mint real markers moved out of this repo into the iterative-dev plugin; see the
Gotcha in `src/proxy/DOCS.md`), then drives the real `apply_modification_rules`. Covers expansion,
the ops path, `strip_vocab.attribute_chunk` on both the stripped and injected sides, determinism
across two runs, a source file changed or vanished between two runs (including that the fixed
notice sentence survives untouched in that case, exactly where the agent needs it), an
oversize-declared marker, the anchored-prefix false-positive guard, trailing content after the
marker in the same block being preserved rather than silently dropped (the marker must be the whole
block), a marker with only its own trailing newline still expanding, the source file being opened
exactly once per validated marker (no second read, no race window), a marker with no notice
sentence under it being ineligible, and marker-plus-notice expanding with the notice disappearing
along with the marker.
**Reads:** nothing external — writes its own temp files; mints its own marker fixtures from its
own pinned literal constants, no subprocess.
**Writes:** stdout (pass/fail via `check()`); its own temp files, cleaned up per test.
**Called by:** none — manual regression guard, re-run after any change to
`src/proxy/inject_poread.py` or `src/proxy/message_passes_simple.py`'s `_POREAD_SPEC`; if this
file's own pinned constants ever need to change, the matching hand-maintained copy in the
iterative-dev plugin's `src/poread_cli/__main__.py` needs the same change too (not machine-checked
across repos — see the Gotcha in `src/proxy/DOCS.md`).
**Calls out:** `proxy.rules` (`apply_modification_rules`), `proxy.inject_poread`
(`_parse_poread_marker`, `_POREAD_HEADER_PREFIX`), `proxy.strip_vocab` (`attribute_chunk`).

---

### test_sidecar_delta_chain.py (211 LOC)

**Purpose:** Regression guard for isolating the CC-internal zero-tool sidecar call
(session-titling, quota check, security-monitor) from `addon_dual_log.py`'s per-model-family
`forwarded` delta-hash chain — a sidecar written between two real requests of the same family must
not advance `DeltaState.forwarded_hashes_by_model`, so the next real request still diffs against
the last REAL request.
**Reads:** nothing external — synthetic in-process payloads, writes to its own temp directory.
**Writes:** PASS/FAIL lines to stdout; its own temp dual-log files (`tempfile.TemporaryDirectory`,
cleaned up on exit).
**Called by:** none — manual regression guard, re-run after touching
`addon_dual_log._write_request_dual_logs`/`_is_sidecar_payload` or `DeltaState`.
**Calls out:** `proxy.addon_dual_log` (`_is_sidecar_payload`, `_write_request_dual_logs`),
`proxy.addon_state` (`DeltaState`, `DualLogPaths`, `SessionIdentity`).

---

## Gotchas
- `replay_strip_v2.py` and `scan_sr_catalog.py` both hardcode a log directory under the project's OLD
  name/casing, which does not exist on the current tree. Neither script raises on the missing path —
  `Path.glob` on a nonexistent directory yields nothing — so both silently "pass" having verified
  zero entries. Repoint the hardcoded log directory at the current corpus before trusting either
  script's output.
- `replay_sn_notice_strip.py` and `replay_env_context_strip.py` hardcode the current project's
  absolute path and read from the main checkout's src/logs/dual_log, not the worktree's — src/logs is
  gitignored per-worktree, so the dual-log corpus only exists in the main checkout.
- Scripts importing `from src.<module>` (via `importlib`, or indented inside a function body — both
  outside `src/hooks/block_dev_imports_src.py`'s module-level-only pattern) vs. `from proxy.<module>`
  after inserting `src/` directly onto `sys.path` (`proxy_bgcomplete_tests.py`,
  `test_role_keyed_rules.py`, `test_sidecar_delta_chain.py`) both work in this directory, but the two
  import styles are not interchangeable in every `dev/` area.
- The main checkout's `src/logs/dual_log/` corpus is live and actively growing on the dev machine —
  two back-to-back runs of a replay script can differ by exactly the handful of requests the real
  proxy logged in between; this is expected drift, not a regression, as long as every other reported
  count (bucket tables, byte-exact-failure count) matches.
