# dev/proxy/

## Role
Per-pass unit tests and targeted replay proofs for individual proxy strip/inject functions
(`src/proxy/message_passes.py` and its `strip_*.py` sub-passes, `src/proxy/rules_config.py`) plus one
bash regression for the proxy marker-file lifecycle (`src/claude_proxy_start.sh`). Each script
verifies one function or one narrow behavior in isolation. Use `dev/proxy_dual_log/` instead when the
check depends on the dual-log quartet's own losslessness/self-consistency invariants; use
`dev/proxy_instrumentation/` instead when the check must drive the full production pipeline
end-to-end against one recorded request.

## Flow
Each script either builds synthetic fixtures in-process or replays a recorded dual-log corpus through
one real pass function, then prints PASS/FAIL to stdout or writes a report to `md/`.

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

### replay_sn_notice_strip.py (215 LOC)

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

### replay_strip_v2.py (241 LOC)

**Purpose:** Two-part validator for the template-based SR strip (`strip_sr.py`) against an old
proxy's recorded `stripped_msg_removed` field.
**Reads:** a hardcoded log directory path that does not exist on the current tree (see Gotchas).
**Writes:** a report to a scratch path outside `dev/proxy/md/` (see Gotchas).
**Called by:** none — manual CLI, currently non-functional (see Gotchas).
**Calls out:** `src/proxy/strip_sr.py` (`_apply_sr_strip`, `_match_template`, `_ALL_TEMPLATES`,
`_STANDALONE_SR_RE`, `_INNER_SR_RE`, `_strip_system_reminders`).

---

### scan_sr_catalog.py (313 LOC)

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

### test_strip_fix.py (1575 LOC)

**Purpose:** The largest suite in this directory — regression tests for the template-based
exact-match system-reminder strip (core templates, content-shape variants, preserve guards), the
full per-message pass chain for task-notification/launch-ack/interrupt-marker/sn-notice strips, the
system-reminder-wrapped task-notification wakeup shape, and the `<total_tokens>` badge/render delta
including the trailing-nudge widening.
**Reads:** synthetic in-script fixtures, except one fixture's text copied verbatim from a real corpus
line (see the module's own W31-W33 fixture).
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src/proxy/strip_sr.py`, `src/proxy/payload_helpers.py`, `src/proxy/message_passes.py`
(`_apply_first_pass`, `_apply_final_sr_pass`, `_apply_role_system_strip`),
`src/proxy/message_passes_simple.py` (`_apply_bg_exit_strip`, `_apply_sn_notice_strip`,
`_apply_interrupt_marker_strip`), `src/proxy/rules.py` (`apply_modification_rules`),
`src/proxy/strip_bg_completed.py`, `src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_launch_ack.py`,
`src/proxy/strip_interrupt_marker.py`, `src/proxy_display/parser.py` (`badge_flags`,
`accumulate_dual_log`), `src/proxy_display/render_turn.py` (`_build_req_header_line`).

---

### replay_env_context_strip.py (192 LOC)

**Purpose:** Before/after replay for the CC 2.1.258 `_ENV_CONTEXT_RE` fix — scans every top-level
standalone system-reminder block across the dual-log corpus, classifies each against both the old and
live regex into stripped / left-pure (the bug) / left-bundled (preserved by design) /
CLAUDE.md-preserved.
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

## Gotchas
- `replay_strip_v2.py` and `scan_sr_catalog.py` both hardcode a log directory under the project's OLD
  name/casing, which does not exist on the current tree. Neither script raises on the missing path —
  `Path.glob` on a nonexistent directory yields nothing — so both silently "pass" having verified
  zero entries. Repoint the hardcoded log directory at the current corpus before trusting either
  script's output.
- `replay_sn_notice_strip.py` and `replay_env_context_strip.py` hardcode the current project's
  absolute path and read from the main checkout's src/logs/dual_log, not the worktree's — src/logs is
  gitignored per-worktree, so the dual-log corpus only exists in the main checkout.
- Scripts importing `from src.<module>` (via `importlib`, or `test_strip_fix.py`'s direct form) vs.
  `from proxy.<module>` after inserting `src/` directly onto `sys.path` (`proxy_bgcomplete_tests.py`,
  `test_role_keyed_rules.py`) both work in this directory, but the two import styles are not
  interchangeable in every `dev/` area.
