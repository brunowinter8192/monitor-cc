# dev/proxy/

## Role

Per-pass unit tests and targeted replay proofs for individual proxy strip/inject functions
(`src/proxy/message_passes.py` and its `strip_*.py` sub-passes, `src/proxy/rules_config.py`) plus
one bash regression for the proxy marker-file lifecycle (`src/claude_proxy_start.sh`). Each script
here verifies one function or one narrow behavior in isolation — either against synthetic fixtures
built in-script or by replaying real recorded proxy logs through the single pass under test.

Add a script here when the check targets one strip/inject pass or one shell-script function in
isolation. Use `dev/proxy_dual_log/` instead when the check depends on the dual-log quartet's own
invariants — losslessness/self-consistency of the `_original`/`_forwarded`/`_stripped`/`_injected`
delta chain, or the diff engine that reconstructs it. Use `dev/proxy_instrumentation/` instead when
the check must drive the full production pipeline end-to-end (all passes in `rules.py`'s real
order, through to `proxy_display/render_messages.py`) against one recorded request, e.g. validating
a pane-render or span-computation change.

## Modules

### pipeline_byte_identity.py (153 LOC, new 2026-09, proxy milestone A — message_passes split + helper extraction)

**Purpose:** Byte-identity regression harness for the full `src/proxy/` modification pipeline.
Replays `apply_modification_rules` → `_strip_all_cache_control` → `_set_cache_breakpoints` →
`_build_forwarded_delta` → `_build_stripped_injected_deltas` → `_build_errors_entries` over every
request payload found in a bounded prefix (60 lines) of a real `*_original.jsonl`, for both
`worker_context="main"` and `"worker:x"`, with timestamp-shaped fields normalized out (dict key
ORDER stays part of the hashed signal — matches what the real `json.dumps(entry)` in `addon.py`
actually writes to the JSONL), hashing the full output sequence (modified payload, modifications
list, forwarded/stripped/injected delta entries, error entries) for every payload × every
worker_context.
**Reads:** One `*_original.jsonl` file — newest under `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/`
by default, or `$PROXY_PIPELINE_BYTE_IDENTITY_LOG` when set.
**Writes:** Nothing — stdout only (`source`, `payloads`, one `HASH: <hex>` line).
**Run:** `./venv/bin/python dev/proxy/pipeline_byte_identity.py`
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.cache`
(`_strip_all_cache_control`, `_set_cache_breakpoints`), `src.proxy.logging`
(`_build_forwarded_delta`, `_build_errors_entries`), `src.proxy.strip_inject_delta`
(`_build_stripped_injected_deltas`), `src.proxy.message_summary` (`_summarize_message`)

**`PROXY_PIPELINE_BYTE_IDENTITY_LOG` env var** overrides the source path — needed to pin a
before/after comparison to the exact same bytes when the default (newest `*_original.jsonl` under
the live MAIN checkout) can itself be THIS very session's own actively-growing log — same pitfall
class as `dev/proxy_display/render_byte_identity.py`'s `RENDER_BYTE_IDENTITY_LOG_DIR` and
`dev/workers/format_byte_identity.py`'s `WORKERS_BYTE_IDENTITY_JSONL` (see their own Gotchas).
Snapshot a real `*_original.jsonl` to a fixed path once (a bounded prefix — the harness only reads
the first 60 lines regardless), then point both runs at it via the env var.

Status: hash `8bc6bde611342924989faf234f728969d31b2112c58d3ceb415254da9ec4d825` — identical before
and after the milestone A split (60 real payloads × 2 worker_contexts, pinned snapshot).

---

### proxy_bgcomplete_tests.py (173 LOC)

**Purpose:** Smoke tests (B01–B04) for the task-notification wakeup-injection single-block fix —
completed/failed TN with/without `<output-file>`+`<task-id>` must collapse into one block with the
wakeup line plus optional `Output:`/`ID:` lines in fixed order, summary always dropped.
**Reads:** In-script synthetic fixtures only.
**Writes:** stdout PASS/FAIL lines only.
**Run:** `./venv/bin/python dev/proxy/proxy_bgcomplete_tests.py`
**Calls out:** `src/proxy/message_passes.py` (`_apply_first_pass`), `src/proxy/strip_bg_completed.py`
(`_WAKEUP_TEXT`).

Status: runs clean — 32/32 checks PASS on the current tree.

---

### replay_sn_notice_strip.py (215 LOC)

**Purpose:** Replay proof for `_apply_sn_notice_strip` over every captured dual-log — asserts (1)
every message NOT reported as changed is byte-exact untouched (tool_result data, mid-content
occurrences, role != 'user' all left alone), (2) every CHANGED message reconstructs the original
exactly when the removed paragraph is spliced back in (pure removal, no incidental drift), and
reports genuine-strip vs. untouched-data-occurrence counts deduplicated per (file, exact text).
**Reads:** `src/logs/dual_log/*_original.jsonl` (real recorded corpus, main checkout —
`/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log`, hardcoded absolute path since
`src/logs/` is gitignored per-worktree).
**Writes:** `dev/proxy/md/replay_sn_notice_strip.md`.
**Run:** `./venv/bin/python dev/proxy/replay_sn_notice_strip.py`
**Calls out:** `src/proxy/message_passes_simple.py` (`_apply_sn_notice_strip` — re-pointed 2026-09,
helper-extraction milestone: moved out of `message_passes.py`), `src/proxy/strip_sn_notice.py`
(`_SN_NOTICE_PARAGRAPH`, `_SN_NOTICE_BLOCK`).

Status: runs clean — 0 byte-exact failures across every request entry in the current corpus.
Absolute counts (genuine strips, untouched occurrences) drift from the baseline the script's own
report text quotes, because the dual-log corpus is a rolling window (files rotate between runs);
the script frames this explicitly and treats the byte-exact invariant, not the raw counts, as the
correctness proof.

---

### replay_strip_v2.py (241 LOC)

**Purpose:** Two-part validator for the template-based SR strip (`strip_sr.py`) against the OLD
proxy's recorded `stripped_msg_removed` field — Part A checks that chunks the old code stripped
without a template match (false positives) are no longer stripped by the new code, and that chunks
with a template match (real SRs) are still stripped (no regression); Part B checks that standalone
SRs present in `raw_payload` but missed by the old proxy are now caught by
`_strip_system_reminders`.
**Reads:** `LOGS_DIR = /Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs` (hardcoded, capital
`Monitor_CC` — the project's old name/casing). **This path does not exist on the current tree.**
`Path.glob` on a missing directory returns an empty list rather than raising, so the script does
not crash — it silently scans 0 logs, all counters stay 0, and it prints "ALL PASS" vacuously.
**Writes:** `/tmp/replay_strip_v2.md` (not under `dev/proxy/md/`).
**Run:** `python3 dev/proxy/replay_strip_v2.py`
**Calls out:** `src/proxy/strip_sr.py` (`_apply_sr_strip`, `_match_template`, `_ALL_TEMPLATES`,
`_STANDALONE_SR_RE`, `_INNER_SR_RE`, `_strip_system_reminders`).

Status: does NOT perform its stated verification today — the hardcoded log path is stale and the
script processes zero entries. Left as-is per scope (document, don't repair).

---

### scan_sr_catalog.py (313 LOC)

**Purpose:** Scans all proxy request logs to build a catalog of system-reminder (SR) / task-
notification (TN) content: what the proxy stripped (`stripped_msg_removed`, classified real-SR /
real-TN / false-positive via code-pattern heuristics) and what it missed (standalone SRs still
present in `raw_payload.messages` after proxy processing).
**Reads:** `LOGS_DIR = /Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs` (same hardcoded,
capitalized old-project-name path as `replay_strip_v2.py`). **This path does not exist on the
current tree**, so `LOGS_DIR.glob('api_requests_*.jsonl')` returns 0 files and the script produces
an empty catalog (0 templates, 0 false-positives, 0 missed SRs) without erroring.
**Writes:** `/tmp/sr_catalog.md` (not under `dev/proxy/md/`).
**Run:** `python3 dev/proxy/scan_sr_catalog.py`
**Calls out:** none at import time — parses raw JSONL directly, no `src/` imports.

Status: does NOT perform its stated scan today — the hardcoded log path is stale and the script
finds zero log files. Left as-is per scope (document, don't repair).

---

### test_role_keyed_rules.py (219 LOC)

**Purpose:** Unit tests for ROLE-keyed system2 rule selection (`rules_config._load_system2_rules`)
— selection is keyed off the session role (`"worker:<name>"` vs. `"main"`), not model family, which
retains only the haiku short-circuit. Covers role selection (main/worker/empty/None/non-worker-
prefixed junk), the opus-worker / sonnet-main regression this guards against, haiku short-circuit
precedence, degraded configs (missing `main`/`worker` keys, missing `system2_rules`, missing rule
file on disk), `exclude_projects` under both roles, and end-to-end through
`rules.apply_modification_rules` landing text in `system[2]`.
**Reads:** Builds its own synthetic shared-rules tree in a tempdir and repoints
`rules_config._SHARED_RULES_DIR` / `_PROXY_RULES_CONFIG` at it; never reads the real
`~/.claude/shared-rules/`.
**Writes:** stdout PASS/FAIL lines only.
**Run:** `./venv/bin/python dev/proxy/test_role_keyed_rules.py`
**Calls out:** `src/proxy/rules_config.py` (`_load_system2_rules`, module globals, caches),
`src/proxy/rules.py` (`apply_modification_rules`).

Status: runs clean — 26/26 checks PASS on the current tree.

---

### test_strip_fix.py (1575 LOC)

**Purpose:** The largest suite in this directory (255 checks) for the template-based exact-match SR
strip (Phase B). Five groups: (1) 8 core SR templates × 3 cases each — real strip at top level, FP
code-literal preserved, tool_result content preserved (SR family no longer descends into
`tool_result`) — plus 4 content-shape tests, user-interrupt partial mode, plan-mode None-return,
`_find_system_reminder_blocks` top-level-only extraction, and T40–T44 (2026-09, CC 2.1.258
`_ENV_CONTEXT_RE` fix): the May-2026 form strips, the 2.1.258 form (2 extra sentences after the
email) strips, a CLAUDE.md context block with the same preamble is preserved, an env-context block
with a DIFFERENT email is preserved (the hardcoded email literal never matches), and the real
corpus shape where CC bundles `# claudeMd` project content AND `# userEmail`/`# currentDate` into
ONE `<system-reminder>` block is preserved whole (`fullmatch` correctly never matches it — see
`src/proxy/DOCS.md`'s `strip_sr.py` entry); (2) "w"-prefixed full-chain tests —
task-notification, launch-ack, interrupt-marker, sn-notice and role-system strips run through the
real per-message passes together, asserting neighbor content and exact real-corpus bodies survive;
(3) "w31"–"w33" full-`apply_modification_rules`-chain tests (2026-09-04) for the `<system-reminder>`-
wrapped TN wake-up shape (`_unwrap_full_sr_wrapper`, `message_passes_wakeup.py` since the 2026-09
helper-extraction milestone) — real corpus fixture
(`src/logs/dual_log/api_requests_opus_wise2627_1788533758_stripped.jsonl`, request_id
`65c964d6-90c6-46ec-81de-190487d92e55`) asserts the wire content is exactly the bare wake-up text,
plus regression pins for the two shapes that already worked (bare role='system' str, unwrapped
role='user' list-text); (4) "tt"-prefixed tests (TT01–TT09) for the `<total_tokens>` badge/render
delta — whether a stripped/injected entry lights the `strip`/`inject` word in the rendered
request-header line — extended TT10–TT14 (2026-09-05) for the claude-f trailing-nudge widening:
single/combined/repeated known nudge sentences badge neither word; a nudge mixed with real content
(deferred-tools, the old feedback-hook message) or an UNKNOWN/uncatalogued sentence still badges
both, proving the catalog-based shape test fails toward showing a strip rather than silently
absorbing something new; two nudge-shaped messages in one delta stay quiet together, a third real
strip in the same delta keeps it loud; `_is_total_tokens_nuke` (the lag-correction classifier)
widens in step with the badge filter and still rejects real content; TT14 drives the real header
renderer end to end for the new class, mirroring TT09.
**Reads:** In-script synthetic fixtures only, except the W31–W33 fixture text which is copied
verbatim from the real corpus (see above) rather than read from the log file at test time.
**Writes:** stdout PASS/FAIL lines only.
**Run:** `python3 dev/proxy/test_strip_fix.py`
**Calls out:** `src/proxy/strip_sr.py`, `src/proxy/payload_helpers.py`, `src/proxy/message_passes.py`
(`_apply_first_pass`, `_apply_final_sr_pass`, `_apply_role_system_strip`),
`src/proxy/message_passes_simple.py` (`_apply_bg_exit_strip`, `_apply_sn_notice_strip`,
`_apply_interrupt_marker_strip` — re-pointed 2026-09, helper-extraction milestone: moved out of
`message_passes.py`, imported via a second `importlib.import_module` call alongside the
pre-existing `message_passes` one), `src/proxy/rules.py` (`apply_modification_rules`, W31–W33 only,
imported via `importlib` to satisfy `block_dev_imports_src`), `src/proxy/strip_bg_completed.py`,
`src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_launch_ack.py`, `src/proxy/strip_interrupt_marker.py`,
`src/proxy_display/parser.py` (`badge_flags`, `accumulate_dual_log`), `src/proxy_display/render_turn.py`
(`_build_req_header_line`).

Status: runs clean — 255/255 checks PASS on the current tree.

---

### replay_env_context_strip.py (192 LOC, new 2026-09)

**Purpose:** Before/after replay for the CC 2.1.258 `_ENV_CONTEXT_RE` fix — scans every top-level
standalone `<system-reminder>` block (str content or `list[type=='text']`, never `tool_result`,
matching `_strip_system_reminders`'s own scope) across every dual-log entry, deduplicates by
(file, exact inner text), and classifies each occurrence against BOTH the OLD (pre-fix, quoted
verbatim in-script) and the live (post-fix) `_ENV_CONTEXT_RE` into 4 buckets: stripped; left-PURE
(no `# claudeMd` — genuinely broken by CC 2.1.258, the bug); left-BUNDLED (`# claudeMd` present
too — preserved by design, unaffected by the fix either way); and CLAUDE.md-preserved (no
`# userEmail` hint at all).
**Reads:** `src/logs/dual_log/*_original.jsonl` (main checkout, hardcoded absolute path — same
convention as `replay_sn_notice_strip.py`, `src/logs/` is gitignored per-worktree).
**Writes:** `dev/proxy/md/replay_env_context_strip.md`.
**Run:** `python3 dev/proxy/replay_env_context_strip.py`
**Calls out:** `src/proxy/strip_sr.py` (`_ENV_CONTEXT_RE`, `_PRESERVE_PREAMBLE`,
`_STANDALONE_SR_RE`, `_INNER_SR_RE`, imported via `importlib`).

Status (2026-09, 14 files, 2888 entries, unique-by-text): before — 7 stripped, 3 left-PURE
(the bug), 3 left-BUNDLED, 0 CLAUDE.md-preserved; after — 10 stripped, 0 left-PURE, 3 left-BUNDLED
(unchanged, correct), 0 CLAUDE.md-preserved (unchanged, correct — a rotating-corpus property, not
evidence the guard stopped firing, see `process-docs/strip_efficacy_audit/`). The 3
newly-stripped blocks are exactly the CC 2.1.258 form this task fixes.

---

### marker_race_repro.sh (225 LOC)

**Purpose:** Deterministic repro/regression for proxy marker-file lifecycle race conditions:
restart-within-60s with a dead PID (S1), a parallel live session must not be clobbered (S2/S2b),
crash/kill-9 with a stale log (S3), PID-reuse by an unrelated alive process must still read as
stale via identity check, not bare `kill -0` (S4), and the heartbeat reclaim decision — missing
marker / dead-PID marker / live-owner marker (S5a–c). `_is_stale` and `_heartbeat_check` in this
script mirror the inline write-guard and `_marker_heartbeat` logic in the real start script; they
are test harness, not duplicated production logic, since both call the real
`_proxy_pid_is_live` sourced from it.
**Reads:** `_proxy_pid_is_live()` sourced live (via `awk` function extraction + `eval`) from
`src/claude_proxy_start.sh`; spawns real background subprocesses (`sleep`, `exec -a
claude_proxy_start.sh sleep 30`) and fake log files under a `mktemp -d` tmpdir — no repo fixtures.
**Writes:** stdout PASS/FAIL lines only.
**Run:** `bash dev/proxy/marker_race_repro.sh` (from project root)
**Calls out:** `src/claude_proxy_start.sh` (`_proxy_pid_is_live`).

Status: runs clean — 12/12 checks PASS on the current tree.

---

## Gotchas

- `replay_strip_v2.py` and `scan_sr_catalog.py` both hardcode a log directory under the OLD project
  name/casing (`.../ai/Monitor_CC/src/logs`, capital M/CC) instead of the current
  `.../ai/monitor-cc/src/logs`. Neither script raises on the missing path — `Path.glob` on a
  nonexistent directory just yields nothing — so both silently "pass" having verified nothing.
  Before trusting either script's output, repoint `LOGS_DIR` at the current corpus.
- `replay_sn_notice_strip.py` hardcodes the CURRENT `monitor-cc` (lowercase) absolute path and reads
  from the main checkout's `src/logs/dual_log/`, not the worktree's — `src/logs/` is gitignored
  per-worktree, so the dual-log corpus only exists in the main checkout.
- Scripts importing `from src.<module>` (`replay_sn_notice_strip.py` via `importlib`,
  `replay_strip_v2.py`, `test_strip_fix.py`) vs. `from proxy.<module>` after a direct `src/` path
  insert (`proxy_bgcomplete_tests.py`, `test_role_keyed_rules.py`) both work here — the two import
  styles are not interchangeable in every dev/ area (see `dev/proxy_instrumentation/DOCS.md`'s
  `pN_*.py` convention), but neither is enforced in this directory.
