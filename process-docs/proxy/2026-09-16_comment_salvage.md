# process-docs/proxy/2026-09-16_comment_salvage.md

Session: dev/proxy/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/proxy/*.py` during this milestone, copied verbatim
before deletion, plus the full pre-rewrite content of `dev/proxy/DOCS.md`. Nothing judged and
dropped — see the milestone rules in the calling agent's prompt (module-standards conformance:
relocate then delete, decide nothing).

Grep for `__doc__`, `argparse`, `description=`, `epilog=` across `dev/proxy/*.py` before deletion:
zero matches. No load-bearing docstring found — all 14 docstrings deleted outright, no
constant-rewiring needed. Section markers (`# INFRASTRUCTURE`/`# ORCHESTRATOR`/`# FUNCTIONS`) and
shebang lines are NOT included below since they are kept in the code, not deleted.

Comment/docstring counts confirmed via AST + tokenize before deletion: 368 comments, 14
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/proxy/DOCS.md

Full content of dev/proxy/DOCS.md as it stood before this rewrite (333 lines), preserved
verbatim since the whole file is being replaced with the mandated leaner format (Role capped
at 50 words, Purpose capped at 25 words per module, no Gotchas section in the new format).

```markdown
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
```

## Salvage from dev/proxy/addon_hook_byte_identity.py

DOCSTRING L1-21:
```

Byte-identity regression harness for the ProxyAddon HOOK METHODS themselves (request,
responseheaders, response) — proxy addon-split milestone (collaborator-object split of
ProxyAddon's 15 self.<attr> + request()/response() helper extraction). pipeline_byte_identity.py
covers the pure-function pipeline; this harness is the one that actually calls ProxyAddon(),
addon.request(), addon.responseheaders(), addon.response() — nothing else in dev/ does.

Constructs a real ProxyAddon with MONITOR_CC_ROOT pointed at a fresh temp dir, drives the three
hooks with a minimal fake mitmproxy flow (request: method/pretty_host/path/headers/content;
response: status_code/headers/content/stream; flow: metadata dict/id) over a bounded prefix of a
real *_original.jsonl, with x-request-id pinned per request (so uuid.uuid4() is never invoked —
no monkeypatch needed there) and timestamp-shaped JSONL fields ('timestamp'/'ts') normalized to a
fixed sentinel post-write, hashing the concatenated contents of all six dual-log files plus
captured stderr.

Usage (from project root):
    ./venv/bin/python dev/proxy/addon_hook_byte_identity.py

Prints one HASH line. Run before and after the src/proxy/addon.py split; the hash must match.
Never commits a log snapshot — only reads.

```

COMMENT L37:
```
# bounded prefix — an append-only source file's own prefix never changes
```

COMMENT L56:
```
# tmp_root itself is a fresh random path every run (tempfile.TemporaryDirectory) — the
```

COMMENT L57:
```
# tool_injection "schema store missing" warning embeds it verbatim, so it must be
```

COMMENT L58:
```
# normalized out of stderr before hashing or the hash would never be reproducible.
```

COMMENT L68:
```
# Imported at THIS point — BEFORE MONITOR_CC_ROOT is repointed at a tempdir in main() below —
```

COMMENT L69:
```
# because src/proxy/payload_helpers.py resolves its own sys.path insert from MONITOR_CC_ROOT
```

COMMENT L70:
```
# (falling back to the real src/ only when the env var is unset at import time); importing early
```

COMMENT L71:
```
# avoids resolving `constants` against an empty tempdir.
```

COMMENT L77:
```
# ADDON_HOOK_BYTE_IDENTITY_LOG overrides the source *_original.jsonl path — needed to pin a
```

COMMENT L78:
```
# before/after comparison to the exact same bytes, same pitfall class as
```

COMMENT L79:
```
# dev/proxy/pipeline_byte_identity.py's PROXY_PIPELINE_BYTE_IDENTITY_LOG (see its own docstring).
```

COMMENT L109:
```
# Minimal fake mitmproxy header container — case-insensitive get/pop, same shape as the
```

COMMENT L110:
```
# _FakeHeaders class in dev/native-model-start/p3_cache_breakpoints_probe.py and
```

COMMENT L111:
```
# dev/bg_wakeup_id_line/p2_bg_escape_probe.py (reused here, extended with a response side).
```

COMMENT L149:
```
# Drives every payload through request() + a 2xx responseheaders()/response() pair, plus one
```

COMMENT L150:
```
# dedicated 4xx flow (reusing payloads[0]) to exercise the error-logging branch — its stderr line
```

COMMENT L151:
```
# is part of the hashed signal; the api_errors.jsonl side write is out of scope (not one of the
```

COMMENT L152:
```
# six dual-log files this harness hashes).
```

COMMENT L169:
```
# Strip volatile timestamp-shaped fields so the hash is stable across runs made at different
```

COMMENT L170:
```
# wall-clock times — everything else (including dict key ORDER, which real json.dumps(entry)
```

COMMENT L171:
```
# writes to the JSONL byte-for-byte) stays part of the hashed signal.
```

## Salvage from dev/proxy/pipeline_byte_identity.py

DOCSTRING L1-19:
```

Byte-identity regression harness for the src/proxy/ modification pipeline
(proxy milestone A — message_passes split + helper extraction).

Replays apply_modification_rules + _strip_all_cache_control + _set_cache_breakpoints +
_build_forwarded_delta + _build_stripped_injected_deltas + _build_errors_entries over every
request payload found in a frozen, bounded-prefix copy of the newest *_original.jsonl under
src/logs/dual_log/ (main checkout, read-only — the live file can keep growing during a work
session, see the bounded-prefix + env-var-override notes below), for both worker_context="main"
and worker_context="worker:x", with timestamp-shaped fields normalized out, hashing the full
output sequence (modified payload, modifications list, forwarded/stripped/injected delta
entries, error entries) for every payload x every worker_context.

Usage (from project root):
    ./venv/bin/python dev/proxy/pipeline_byte_identity.py

Prints one HASH line. Run before and after a src/proxy/ refactor; the hash must match. Never
commits a log snapshot — only reads.

```

COMMENT L32:
```
# bounded prefix — an append-only source file's own prefix never changes
```

COMMENT L51:
```
# PROXY_PIPELINE_BYTE_IDENTITY_LOG overrides the source *_original.jsonl path — needed to pin a
```

COMMENT L52:
```
# before/after comparison to the exact same bytes when the default (newest file under the live
```

COMMENT L53:
```
# MAIN checkout) can itself be THIS very session's own actively-growing log (same pitfall class
```

COMMENT L54:
```
# documented for dev/proxy_display/render_byte_identity.py and dev/workers/format_byte_identity.py
```

COMMENT L55:
```
# — see their own Gotchas). Snapshot a real *_original.jsonl to a fixed path once, then point both
```

COMMENT L56:
```
# runs at it via the env var for full reproducibility.
```

COMMENT L86:
```
# Strip volatile timestamp-shaped fields from a dict/list structure so the hash is stable across
```

COMMENT L87:
```
# runs made at different wall-clock times — everything else (including dict key ORDER, which
```

COMMENT L88:
```
# real json.dumps(entry) writes to the JSONL byte-for-byte) stays part of the hashed signal.
```

## Salvage from dev/proxy/poread_inject_tests.py

DOCSTRING L1-23:
```
Regression suite for src/proxy/inject_poread.py (the poread marker-expansion pass).

Covers: a marker minted from this test's own pinned literal copy of the marker contract (the CLI
half that used to mint real markers has moved out of this repo entirely, into the iterative-dev
plugin — see the Gotcha in src/proxy/DOCS.md) expands to the file's full content when run through
the real apply_modification_rules pipeline; the injection shows up in the ops path (all_ops) and
in strip_vocab.attribute_chunk on BOTH the stripped (marker) and injected (wrapped content) sides;
the expansion is byte-identical across two separate pipeline runs against the same unchanged file
(determinism); a source file that changed or vanished between two runs leaves the marker completely
inert (no mods, no ops, original text preserved) rather than injecting stale or wrong content; a
marker whose declared byte count exceeds the 50,000-byte ceiling is refused regardless of what the
actual file contains; a marker that is NOT the first thing in its block (mid-content, false-positive
class) is left untouched; trailing content AFTER the marker in the same block is preserved, not
silently dropped, because the marker must be the entire block for expansion to fire at all; the
source is read exactly once per validated marker (no second read between predicate and replacement,
so no race window can leave a request's whole modification pipeline crashing out on a benign
mid-request file change); a realistic multi-message payload shape (system + user prompt + assistant
tool_use + user tool_result carrying the marker) exercises the full apply_modification_rules pass
order end to end.

Run from project root:
    ./venv/bin/python dev/proxy/poread_inject_tests.py

```

## Salvage from dev/proxy/proxy_bgcomplete_tests.py

DOCSTRING L1-15:
```
Smoke tests for background-completion task-notification single-block fix.

Four cases:
  B01 — completed TN + output-file + task-id → single block, wakeup + Output + ID lines, summary dropped
  B02 — completed TN, task-id only (no output-file) → single block, wakeup + ID line, summary dropped
  B03 — failed TN, neither task-id nor output-file → single block, wakeup only (mirrors bare case)
  B04 — failed TN + output-file + task-id → single block, wakeup + Output + ID lines (mirrors B01)

2026-07-29: injected text gained a third optional line, 'ID: <task-id>', recovered from the same
<task-notification> block as the Output line — fixed order: wakeup, then Output: (if any), then
ID: (if any).

Run from project root:
    ./venv/bin/python dev/proxy_bgcomplete_tests.py

```

COMMENT L36:
```
# string = one logical block
```

COMMENT L45:
```
# B01 — completed TN with output-file + task-id → single block, wakeup + Output + ID lines, summary dropped
```

COMMENT L79:
```
# B02 — completed TN, task-id only (no output-file) → single block, wakeup + ID line, summary dropped
```

COMMENT L108:
```
# B03 — failed TN, neither task-id nor output-file → single block, wakeup only, summary dropped
```

COMMENT L135:
```
# B04 — failed TN with output-file + task-id → single block, wakeup + Output + ID lines (mirrors B01)
```

## Salvage from dev/proxy/replay_env_context_strip.py

DOCSTRING L2-33:
```
Replay verification for `_ENV_CONTEXT_RE` in strip_sr.py — CC 2.1.258 trailing-sentences fix
(2026-09) AND the gitStatus-section widening (2026-09, this task).

Scans every top-level standalone `<system-reminder>` block (str content, or `list[type=='text']`
blocks — never `tool_result`, matching `_strip_system_reminders`'s own 2026-07-28 scope reduction
exactly) in every `src/logs/dual_log/*_original.jsonl` entry, and classifies each DISTINCT
(file, exact inner text) occurrence against both the OLD (pre-gitStatus-fix, quoted verbatim
below — this is the exact regex this task replaced) and the live (post-fix) `_ENV_CONTEXT_RE`:

  - env-context, stripped        — `_ENV_CONTEXT_RE.fullmatch` succeeds
  - env-context, left            — starts with `_PRESERVE_PREAMBLE` AND contains `# userEmail`,
                                    but the fullmatch fails (this is exactly the gitStatus bug
                                    before this task's fix — no `# currentDate` anywhere in a
                                    build that emits `# gitStatus` instead — and the "bundled
                                    CLAUDE.md + userEmail" shape both before and after — see the
                                    report body)
  - CLAUDE.md context, preserved — starts with `_PRESERVE_PREAMBLE`, does NOT match
                                    `_ENV_CONTEXT_RE`, and either has no `# userEmail` at all or
                                    has one only as part of bundled real project content

Each bucket is additionally split by FORM — `currentDate` (the block carries a `# currentDate`
section) vs. `gitStatus` (the block carries a `# gitStatus` section instead) — since the two forms
are structurally different CC-emitted shapes and the whole point of this task's fix is the
gitStatus form moving from "left" to "stripped".

Deduplicated by (file, exact inner text) — dual-logs are cumulative snapshots, the same message
reappears in every later request of the same session, so raw per-entry counts vastly overcount
distinct real occurrences.

Usage: python3 dev/proxy/replay_env_context_strip.py
Output: dev/proxy/md/replay_env_context_strip.md

```

COMMENT L45:
```
# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
```

COMMENT L54:
```
# The pre-this-task pattern, quoted verbatim — the CC 2.1.258 trailing-sentences fix (2026-09,
```

COMMENT L55:
```
# see process-docs/proxy_noise_strip/2026-09_env_context_cc258_trailing_sentences.md) is already
```

COMMENT L56:
```
# folded in (`[^\n]*` after the email sentence), but it still hard-requires a `# currentDate`
```

COMMENT L57:
```
# section immediately after — the current CC build instead emits `# gitStatus` and no
```

COMMENT L58:
```
# `# currentDate` at all, so this pattern's fullmatch fails on that form (this task's bug).
```

COMMENT L69:
```
# Actual runtime dual-log location (main checkout, not this worktree — src/logs/ is gitignored
```

COMMENT L70:
```
# per-worktree; the corpus only exists here).
```

COMMENT L79:
```
# (file, exact inner text) — dedup across cumulative session snapshots
```

COMMENT L115:
```
# A block's FORM is which date/status section it carries — 'other' covers real CLAUDE.md context
```

COMMENT L116:
```
# blocks (no userEmail section at all, so neither marker is present).
```

COMMENT L125:
```
# One classification pass for one env-context regex variant — populates the bucket dict in place.
```

COMMENT L126:
```
# "left" splits into PURE (no `# claudeMd` at all — a genuinely broken env-context block, the bug)
```

COMMENT L127:
```
# and BUNDLED (`# claudeMd` present too — CC folded real project content and env-context into one
```

COMMENT L128:
```
# block; correctly preserved by design regardless of the regex fix, see report body).
```

COMMENT L138:
```
# real CLAUDE.md context, no userEmail hint
```

COMMENT L159:
```
# Yield inner text of every top-level standalone SR block (str content, or list[type=='text']
```

COMMENT L160:
```
# blocks) across all messages — tool_result is never descended into, matching
```

COMMENT L161:
```
# _strip_system_reminders's own 2026-07-28 scope reduction exactly.
```

## Salvage from dev/proxy/replay_sn_notice_strip.py

DOCSTRING L2-20:
```
Replay verification for strip_sn_notice.py over all captured dual-logs.

Runs ONLY `_apply_sn_notice_strip` (no other pass) against every request payload's
`messages` list in every `src/logs/dual_log/*_original.jsonl` entry, then:

  1. Asserts byte-exact equality for every message index NOT reported as changed —
     proves the pass never touches anything outside its own target (tool_result data,
     mid-content occurrences, role != 'user', unrelated blocks).
  2. Asserts every CHANGED message's new content, with the removed paragraph(+blank
     line) spliced back in, reconstructs the original exactly — proves the strip is a
     pure removal, no incidental byte drift elsewhere in the same block.
  3. Reports genuine-strip and untouched-data-occurrence counts, deduplicated per
     (file, exact text) to collapse conversation-growth duplication (dual-logs are full
     cumulative snapshots — the same message reappears in every later request of the
     same session).

Usage: python3 dev/proxy/replay_sn_notice_strip.py
Output: dev/proxy/md/replay_sn_notice_strip.md

```

COMMENT L31:
```
# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
```

COMMENT L39:
```
# Actual runtime dual-log location (main checkout, not this worktree — src/logs/ is gitignored
```

COMMENT L40:
```
# per-worktree; the corpus only exists here).
```

COMMENT L59:
```
# Reconstruct old content from new content + removed chunks for one changed message; True if exact.
```

COMMENT L84:
```
# Accumulates untouched-data occurrences of the SN-notice paragraph found OUTSIDE the pass's own
```

COMMENT L85:
```
# target (tool_result content, mid-content text) for one message's content.
```

COMMENT L109:
```
# genuine — handled by the pass, not "untouched data"
```

COMMENT L120:
```
# Runs _apply_sn_notice_strip over one dual-log entry's messages, recording genuine-strip
```

COMMENT L121:
```
# reconstruction failures and untouched-data occurrences into the shared accumulators.
```

## Salvage from dev/proxy/replay_strip_v2.py

DOCSTRING L2-24:
```
Replay-Validator v2: validate template-based SR strip against all historical logs.

Two independent validations:

PART A — False-Positive elimination:
  For each chunk in stripped_msg_removed (what OLD proxy stripped):
  Classify using NEW template matching (_match_template).
  If inner text does NOT match any template → was a FP (old code wrongly stripped it).
  Verify NEW _apply_sr_strip returns the chunk unchanged (FPs_new should = 0).

PART B — Missed SR coverage:
  For messages in raw_payload NOT processed by old proxy but containing standalone SRs:
  Apply _strip_system_reminders to message content.
  Count how many previously-missed SRs are now stripped.

Expected:
  FPs_new == 0   (code literals no longer stripped)
  Coverage_gained > 0  (missed SRs now stripped)
  Real_drops == 0  (no regression on real SRs)

Usage: python3 dev/proxy/replay_strip_v2.py
Output: /tmp/replay_strip_v2.md

```

DOCSTRING L70:
```
Return template_id for chunk, or None if not a known SR.
```

DOCSTRING L82:
```
True if content contains standalone SR blocks at line beginnings.
```

COMMENT L105:
```
# Part A for one stripped_msg_removed chunk: classify by NEW template matching, record a
```

COMMENT L106:
```
# regression if the old-FP chunk is STILL stripped or a real-SR chunk is NOW dropped.
```

COMMENT L118:
```
# FP check: does the new code strip the outer FP code wrapper?
```

COMMENT L119:
```
# (It should NOT — template matching prevents this.)
```

COMMENT L120:
```
# The outer FP content is the first non-whitespace line after <SR>
```

COMMENT L125:
```
# Outer FP code was stripped — true regression
```

COMMENT L137:
```
# Part B for one entry: messages NOT covered by old_removed but carrying a standalone SR the NEW
```

COMMENT L138:
```
# code strips (or still misses).
```

COMMENT L171:
```
# ─── Part A ───
```

COMMENT L176:
```
# ─── Part B ───
```

COMMENT L243:
```
# still_missed < 5% tolerance: residual are unknown-template SR-like content
```

## Salvage from dev/proxy/scan_sr_catalog.py

DOCSTRING L2-12:
```
Scan all proxy JSONL logs for SR/TN/ND catalog.

Scans all src/logs/api_requests_*.jsonl, outputs SR catalog to /tmp/sr_catalog.md.

Sources:
  stripped_msg_removed  — chunks the proxy stripped (real SRs + false positives)
  raw_payload.messages  — post-strip content (missed SRs still visible to Claude)

Usage:
    python3 dev/proxy/scan_sr_catalog.py

```

COMMENT L23:
```
# Detect false-positive code patterns in stripped chunks
```

COMMENT L25:
```
# regex quantifiers
```

COMMENT L26:
```
# regex \s*
```

COMMENT L71:
```
# Check if a stripped chunk is a false positive (code / non-SR content)
```

COMMENT L84:
```
# Extract first-sentence identifier from SR inner text
```

COMMENT L91:
```
# first non-empty line
```

COMMENT L99:
```
# Classify a chunk into: real-sr, real-tn, false-positive, or other
```

COMMENT L110:
```
# Determine location context (role, content shape) for a message at idx
```

COMMENT L125:
```
# Part 1 of one log entry's scan: classify every stripped_msg_removed chunk into the real-SR /
```

COMMENT L126:
```
# real-TN / false-positive buckets, keyed by first-sentence template and role|shape location.
```

COMMENT L139:
```
# Detect if SR wraps new-diagnostics only
```

COMMENT L167:
```
# Part 2 of one log entry's scan: find SRs still present in raw_payload.messages (missed by the
```

COMMENT L168:
```
# proxy), skipping code false-positives and closing-tag remnants.
```

COMMENT L194:
```
# Skip obvious code
```

COMMENT L197:
```
# Skip very short fragments (closing tag remnants)
```

COMMENT L208:
```
# Scan all logs for stripped chunks and missed SRs
```

COMMENT L237:
```
# Format location dict as concise string
```

COMMENT L320:
```
# Write catalog markdown report
```

## Salvage from dev/proxy/test_role_keyed_rules.py

DOCSTRING L2-26:
```
Unit tests for ROLE-keyed system2 rule selection (rules_config._load_system2_rules).

Selection is keyed off the session role carried in worker_context ("worker:<name>" from a
worker-cli spawn, "main" otherwise), NOT off the model family — model and role became
independent when the menubar Models tab started assigning main/worker models separately.
model_family retains exactly one job: the haiku short-circuit.

Coverage:
  - role selection: main / worker:<name> / "" / None / non-worker-prefixed junk
  - the actual regression: opus-family worker gets WORKER files, sonnet-family main gets MAIN files
  - haiku short-circuit wins over both roles (haiku sidecars live inside main sessions)
  - degraded configs: missing "main" key, missing "worker" key, missing system2_rules entirely,
    missing rule file on disk — global-only / empty, never a crash
  - no legacy "opus" key fallback (one-shot migration by design)
  - exclude_projects (untouched feature) still suppresses under both roles
  - end-to-end through rules.apply_modification_rules: the selected text lands in system[2]

Isolation: builds a synthetic shared-rules tree in a temp dir and repoints the module globals
_SHARED_RULES_DIR / _PROXY_RULES_CONFIG at it (both are read at call time). The real
~/.claude/shared-rules/ is never read or written by this test.

Imports the live proxy modules via the src/-on-sys.path form used by the other dev/ probes.

Run: ./venv/bin/python dev/proxy/test_role_keyed_rules.py

```

COMMENT L51:
```
# ── SYNTHETIC SHARED-RULES TREE ──────────────────────────────────────────────
```

COMMENT L53:
```
# Rule file contents — distinct per file so a concatenation identifies its exact members
```

COMMENT L72:
```
# legacy key — must be ignored, no fallback
```

COMMENT L79:
```
# Materialize the synthetic rules tree and point the module globals at it
```

COMMENT L88:
```
# mtime resolution is coarser than the test's write cadence — clear both caches so a
```

COMMENT L89:
```
# rewritten config/file is never served from the previous case's entry.
```

COMMENT L94:
```
# Minimal payload with a 4-block system array — system[2] is the rule-injection slot
```

COMMENT L112:
```
# ── ROLE SELECTION ───────────────────────────────────────────────────────
```

COMMENT L133:
```
# ── THE REGRESSION: MODEL FAMILY NO LONGER DECIDES ───────────────────────
```

COMMENT L142:
```
# ── HAIKU SHORT-CIRCUIT ──────────────────────────────────────────────────
```

COMMENT L148:
```
# ── DEGRADED CONFIGS ─────────────────────────────────────────────────────
```

COMMENT L175:
```
# ── UNTOUCHED FEATURE: exclude_projects ──────────────────────────────────
```

COMMENT L187:
```
# ── END-TO-END THROUGH apply_modification_rules ──────────────────────────
```

## Salvage from dev/proxy/test_sidecar_delta_chain.py

DOCSTRING L1-16:
```

Regression guard for isolating the zero-tool CC-internal sidecar call (session-titling, quota
check, security-monitor — anything Claude Code sends alongside the real conversation with
`tools == 0`) from the proxy's own per-model-family `forwarded` delta-hash chain
(`src/proxy/addon_dual_log.py::_write_request_dual_logs`, `DeltaState.forwarded_hashes_by_model`).

Covers: `_is_sidecar_payload` matches on tool count alone (model-agnostic, since the sidecar has
shared its model family with the real conversation before — see
process-docs/dual_log_cli/2026-09-03_sidecar_exclusion_and_delta_hash_fix.md); a sidecar written
between two real requests of the SAME family does not advance `forwarded_hashes_by_model`, so the
next real request's `forwarded_delta` reports no spurious changes against content the sidecar
introduced and DOES report a real change the sidecar's own presence must not suppress.

Run (from project root or worktree root):
    ./venv/bin/python dev/proxy/test_sidecar_delta_chain.py

```

COMMENT L104:
```
# Real/sidecar payload pair shared by the chain-isolation tests below — same model family
```

COMMENT L105:
```
# (the historical shape measured 2026-09-03: a sonnet-family sidecar interleaved into a sonnet
```

COMMENT L106:
```
# conversation, generalized here to opus), sidecar has tools == [] and its own system/msg text.
```

COMMENT L120:
```
# Test 1 — _is_sidecar_payload is the exact same tools-count-zero signal
```

COMMENT L121:
```
# dual_log_cli.timeline_boundaries._is_sidecar uses on the read side, applied to the payload
```

COMMENT L122:
```
# directly (counts isn't built yet at this point in the write path).
```

COMMENT L131:
```
# Test 2 — a sidecar sharing the REAL conversation's model family never advances
```

COMMENT L132:
```
# forwarded_hashes_by_model. The next real request's forwarded_delta is empty when its content is
```

COMMENT L133:
```
# byte-identical to the LAST REAL request, proving the diff base is the real request, not the
```

COMMENT L134:
```
# sidecar that sat between them.
```

COMMENT L180:
```
# Test 3 — a REAL change made in the request right after a sidecar is still reported: the chain
```

COMMENT L181:
```
# skip must not silently swallow real content changes, only the sidecar's own.
```

## Salvage from dev/proxy/test_strip_fix_cases_badge_nudge.py

COMMENT L10:
```
# ── claude-f trailing-nudge widening (2026-09-05) ─────────────────────────────
```

COMMENT L11:
```
# On model claude-f, CC's trailing role='system' message can carry one or two fixed nudge
```

COMMENT L12:
```
# sentences BEFORE the total_tokens tag instead of the bare tag alone (measured against the real
```

COMMENT L13:
```
# _stripped.jsonl corpus, dev/proxy_tool_stripping/probe_trailing_message_shapes.py — see
```

COMMENT L14:
```
# process-docs/proxy_tool_stripping/ for the counts). TT10-TT14 cover the widened class.
```

COMMENT L21:
```
# TT10 — positive: single nudge, combined nudges (either order), and a repeated nudge all badge
```

COMMENT L22:
```
# NEITHER word, the same class as the bare tag.
```

COMMENT L39:
```
# TT11 — near-miss: a nudge sentence mixed with REAL content still badges both words — the shape
```

COMMENT L40:
```
# test fails the moment ONE paragraph before the tag is not in the catalog. Covers the actually
```

COMMENT L41:
```
# measured mixed shapes (nudge + the now-removed feedback hook's message, nudge + deferred-tools).
```

COMMENT L61:
```
# TT12 — two-message delta: BOTH messages nudge/bare-shaped -> still non-substantial overall (the
```

COMMENT L62:
```
# "previous trailing message re-sent with the first sentence dropped" shape from the milestone).
```

COMMENT L63:
```
# A THIRD message in the same delta that is a real strip keeps the request loud (mirrors TT07).
```

COMMENT L101:
```
# TT13 — lag correction (`_is_total_tokens_nuke`) widens with the badge filter: a single-text blk
```

COMMENT L102:
```
# whose text is a nudge-prefixed tag now qualifies (previously only the bare tag did); a
```

COMMENT L103:
```
# real-content blk still does not, preserving the marker guard the lag correction depends on.
```

COMMENT L119:
```
# TT14 — end-to-end through the REAL header renderer, mirroring TT09 for the new class: a nudge-
```

COMMENT L120:
```
# prefixed tag renders neither word; a nudge mixed with real content renders both.
```

## Salvage from dev/proxy/test_strip_fix_cases_badge.py

COMMENT L16:
```
# ── TOTAL_TOKENS BADGE-SUPPRESSION TESTS (parser.py read-side, 2026-08-29) ────
```

COMMENT L17:
```
# Newer CC appends a fresh role='system' '<total_tokens>N tokens left</total_tokens>' message to the
```

COMMENT L18:
```
# END of the history on every request. _apply_role_system_strip nukes it to '.' (correct, unchanged),
```

COMMENT L19:
```
# and the delta WRITER records that nuke normally (also unchanged — the expanded view must keep
```

COMMENT L20:
```
# rendering the olive stripped text + green '.' at that message). The nuke lands on a NEW message
```

COMMENT L21:
```
# index each request, so its loc_key is new each request and the writer's hash dedup structurally
```

COMMENT L22:
```
# cannot suppress it — which made the REQ-header badge light up on virtually every request.
```

COMMENT L23:
```
# Fix location is READ-SIDE ONLY: parser.accumulate_dual_log's has_content computation, via
```

COMMENT L24:
```
# _msgs_delta_is_substantial. Two classes stop counting toward the badge:
```

COMMENT L25:
```
#   - stripped: a message whose blocks' stripped texts are exactly ONE text full-matching the marker
```

COMMENT L26:
```
#   - injected: a block whose injected spans are only '.', the API-required empty-block filler
```

COMMENT L27:
```
# Overlay section dicts and _msg_idx_by_flow_id are deliberately NOT filtered, so span rendering and
```

COMMENT L28:
```
# per-flow scoping are byte-identical to before. These tests drive the real
```

COMMENT L29:
```
# _build_stripped_injected_deltas (with real ops from _ops_from_content_change) into the real
```

COMMENT L30:
```
# accumulate_dual_log — the production write path feeding the production read path.
```

COMMENT L35:
```
# Build (stripped_entry, injected_entry) for a single-message payload nuked to `new_content`,
```

COMMENT L36:
```
# with ops recorded exactly as the production passes record them (full_replace for a '.' nuke).
```

COMMENT L49:
```
# Resolve the REQ-header badge pair the way the pane does: accumulate BOTH dual-log lines of one
```

COMMENT L50:
```
# flow through the real accumulate_dual_log, attach the four per-flow lookups exactly as
```

COMMENT L51:
```
# pane.py does, then ask the real parser.badge_flags. Returns (show_strip, show_inject).
```

COMMENT L66:
```
# Run one delta entry through the REAL accumulate_dual_log; returns (has_content, acc_for_family)
```

COMMENT L82:
```
# TT01 — the WRITER is unchanged: the class still produces full delta entries with spans, so the
```

COMMENT L83:
```
# expanded view keeps rendering the olive stripped text and the green '.' filler.
```

COMMENT L93:
```
# TT02 — the BADGE goes quiet on both sides, and the overlay/scoping data survives untouched
```

COMMENT L100:
```
# the badge the header actually renders — BOTH words stay off for this class
```

COMMENT L104:
```
# overlay + per-flow msg scoping must be EXACTLY as before — spans still render
```

COMMENT L111:
```
# TT03 — every OTHER '.'-nuke keeps the one-to-one behavior: `strip inject`. Its '.' IS injected and
```

COMMENT L112:
```
# DOES render as a green span, so the header must say so. Only the total_tokens class goes silent.
```

COMMENT L113:
```
# The inject word here comes from the flow coordination in parser.badge_flags — the injected line
```

COMMENT L114:
```
# alone carries just '.', indistinguishable from the total_tokens one.
```

COMMENT L129:
```
# TT04 — a REAL content injection still badges inject (the bg-exit wake-up replacement, the case
```

COMMENT L130:
```
# the badge exists for). Guards that the '.'-filler rule did not swallow genuine injections.
```

COMMENT L142:
```
# TT05 — FP guard: the marker QUOTED alongside other content keeps badging. This is the shape a
```

COMMENT L143:
```
# real conversation produces (the marker inside a tool_result / a longer message), as opposed to a
```

COMMENT L144:
```
# bare marker-only message. Read-side has no role field, so this text-shape guard is what carries
```

COMMENT L145:
```
# the anti-FP property here.
```

COMMENT L158:
```
# TT06 — anchoring near-misses still badge: only the EXACT whole-text marker is suppressed
```

COMMENT L177:
```
# TT07 — mixed request: a total_tokens nuke AND a real strip in the SAME request must still badge.
```

COMMENT L178:
```
# The suppression is per-MESSAGE on the stripped side, so the real strip at its own index survives
```

COMMENT L179:
```
# the filter (3 such requests exist in the 1788011077 session).
```

COMMENT L203:
```
# TT08 — sections other than messages are untouched by the filter: a system-only or tools-only
```

COMMENT L204:
```
# delta still badges, and a fields-only delta still does not (unchanged pre-existing behavior).
```

COMMENT L220:
```
# TT09 — end-to-end through the REAL header renderer: the rendered badge words themselves. Covers
```

COMMENT L221:
```
# the live-observed case (a task-tools nag nuke rendering only `strip` when it must render
```

COMMENT L222:
```
# `strip inject`) and its counterpart (a total_tokens nuke rendering neither word).
```

COMMENT L229:
```
# noqa: F401 (same path badge_flags takes)
```

## Salvage from dev/proxy/test_strip_fix_cases_env_context.py

COMMENT L6:
```
# ── ENV-CONTEXT SR: CC 2.1.258 TRAILING-SENTENCES FIX (2026-09) ──────────────
```

COMMENT L7:
```
# CC 2.1.258 appends two sentences after the email address before `# currentDate`. The old
```

COMMENT L8:
```
# `_ENV_CONTEXT_RE` required `\n` immediately after `gmail\.com\.`, so `fullmatch` failed and the
```

COMMENT L9:
```
# `_PRESERVE_PREAMBLE` guard (same preamble as CLAUDE.md context blocks) kept the whole block,
```

COMMENT L10:
```
# reaching the API in message 0 of every session. Fix: `[^\n]*` after the email sentence tolerates
```

COMMENT L11:
```
# any trailing text on that one line. Measured over `src/logs/dual_log/*_original.jsonl` (main
```

COMMENT L12:
```
# checkout, 2026-09): 1866 occurrences of the May-2026 form, 699 of the 2.1.258 form, both
```

COMMENT L13:
```
# top-level and both must strip; 242 occurrences of CC bundling `# claudeMd` content AND
```

COMMENT L14:
```
# `# userEmail` into ONE `<system-reminder>` block — must stay preserved (real CLAUDE.md content),
```

COMMENT L15:
```
# T44 pins this exact shape.
```

COMMENT L77:
```
# T44 — real corpus shape (src/logs/dual_log, main checkout, 2026-09, 242 occurrences): CC
```

COMMENT L78:
```
# bundles `# claudeMd` project content AND `# userEmail`/`# currentDate` into ONE SR block rather
```

COMMENT L79:
```
# than two separate blocks. `_ENV_CONTEXT_RE.fullmatch` correctly fails (the inner text is not
```

COMMENT L80:
```
# JUST the env-context block), so the `_PRESERVE_PREAMBLE` guard preserves the whole thing —
```

COMMENT L81:
```
# losing the CLAUDE.md content would be worse than the ~250 bytes of unstripped env-context noise.
```

COMMENT L102:
```
# ── ENV-CONTEXT SR: gitStatus WIDENING (2026-09) ─────────────────────────────
```

COMMENT L103:
```
# Current CC build replaced `# currentDate` with a `# gitStatus` section in the same bundled
```

COMMENT L104:
```
# env-context block — no `# currentDate` anywhere, still exactly one `IMPORTANT:` footer.
```

COMMENT L105:
```
# `_ENV_CONTEXT_RE`'s alternation now accepts EITHER `# currentDate\n...` OR `# gitStatus\n` +
```

COMMENT L106:
```
# the stable header sentence + a free body (`.*?`, DOTALL) up to the `IMPORTANT:` footer — the
```

COMMENT L107:
```
# body is deliberately NOT anchored field-by-field (no per-line `Current branch:`/`Main branch:`/
```

COMMENT L108:
```
# `Git user:`/`Status:`/`Recent commits:` requirement). An initial version of this fix DID
```

COMMENT L109:
```
# enumerate those 5 fields with a fixed blank-line structure, generalized from only the 3 corpus
```

COMMENT L110:
```
# blocks below — review caught that each enumerated field is a brittle anchor with zero protective
```

COMMENT L111:
```
# value (fullmatch is already pinned by the preamble, the literal email, and the IMPORTANT footer;
```

COMMENT L112:
```
# a block carrying all three IS the env-context block) and a guaranteed re-break on the next CC
```

COMMENT L113:
```
# gitStatus layout change. CC issue reports confirm the layout is not fixed: #86891's snapshot
```

COMMENT L114:
```
# has only Current branch / Main branch / Status, no Git user line and no Recent commits section
```

COMMENT L115:
```
# (T50); #43250 has no blank lines between fields at all and an inline `Status: clean` (T51) —
```

COMMENT L116:
```
# both would have failed the field-enumerated version. T45/T46 are copied verbatim from
```

COMMENT L117:
```
# `src/logs/dual_log/*_original.jsonl` (main checkout, 2026-09 measurement, 3 distinct blocks,
```

COMMENT L118:
```
# 973-1045 chars each, see process-docs/proxy_noise_strip/ for the fresh count). T47/T48 cover
```

COMMENT L119:
```
# dirty `git status --short` lines and a detached `HEAD` branch, neither observed in the current
```

COMMENT L120:
```
# corpus window. T49 confirms the bundled `# claudeMd` + gitStatus shape (unobserved in this
```

COMMENT L121:
```
# corpus, but structurally identical to T44's bundled currentDate case) is still preserved whole
```

COMMENT L122:
```
# by the same `_PRESERVE_PREAMBLE` fallback.
```

COMMENT L259:
```
# CC issue #86891 — snapshot has only Current branch / Main branch / Status, no Git user
```

COMMENT L260:
```
# line and no Recent commits section at all.
```

COMMENT L282:
```
# CC issue #43250 — fields have no blank lines between them, Status is inline on one line.
```

## Salvage from dev/proxy/test_strip_fix_cases_launch_ack_interrupt.py

COMMENT L11:
```
# ── LAUNCH-ACK ID + PATH RECOVERY, TN ID LINE (2026-07-29 milestone) ──────────
```

COMMENT L12:
```
# Both bg-launch-ack (strip_bg_launch_ack.py) and TN termination (_apply_first_pass) now emit a
```

COMMENT L13:
```
# 3-line message: <line1>, then 'Output: <path>' (if extracted), then 'ID: <id>' (if extracted) —
```

COMMENT L14:
```
# same fixed order in both places. Extraction verified against real recorded ack/TN bodies from
```

COMMENT L15:
```
# src/logs/dual_log/ (api_requests_opus_monitor_cc_1785336796_original.jsonl +
```

COMMENT L16:
```
# api_requests_opus_posts_1785338463_original.jsonl) — W18/W19 pin the exact real bodies.
```

COMMENT L18:
```
# W15 — genuine ack, id + path both present (the only shape seen in real data) → 3 lines, fixed order
```

COMMENT L32:
```
# W16 — synthetic: id token empty → ID line omitted, no 'ID: None', Output line unaffected
```

COMMENT L44:
```
# W17 — synthetic: no "Output is being written to:" segment → Output line omitted, ID unaffected
```

COMMENT L52:
```
# W18 — real recorded ack body (src/logs/dual_log/api_requests_opus_monitor_cc_1785336796_original.jsonl)
```

COMMENT L71:
```
# W19 — real recorded TN body (same corpus, failed status) → exact 3-line termination text
```

COMMENT L94:
```
# W20 — TN block with <output-file> but no <task-id> → ID line omitted, Output line present
```

COMMENT L105:
```
# W21 — TN block with <task-id> but no <output-file> → Output line omitted, ID line present
```

COMMENT L115:
```
# W22 — neither <task-id> nor <output-file> → reduces to exactly _WAKEUP_TEXT (regression guard for
```

COMMENT L116:
```
# the lines-list refactor: unconditional join must collapse back to the original bare-wakeup shape)
```

COMMENT L124:
```
# ── LAUNCH-ACK WORDING 2 RECOGNITION (2026-07-29 milestone-2) ─────────────────
```

COMMENT L125:
```
# Second CC wording ("Command was manually backgrounded by user with ID: ...") — fired when the
```

COMMENT L126:
```
# user manually backgrounds an already-running Bash call, distinct from the wording-1 initial-
```

COMMENT L127:
```
# launch ack. Measured in dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md (2026-07-29):
```

COMMENT L128:
```
# no ". You will be notified..." trailing sentence, ack IS the complete block in the only measured
```

COMMENT L129:
```
# occurrence. W23 pins the exact 220-char live-observed text verbatim (not a paraphrase). W24 pins
```

COMMENT L130:
```
# the trailing-content-in-same-block shape the M1 blast-radius classification flagged as possible
```

COMMENT L131:
```
# but unobserved ("ANY trailing content after the ack in that block is also discarded").
```

COMMENT L133:
```
# W23 — real live-observed wording-2 body, verbatim (2026-07-29 live observation) — exact 3-line output
```

COMMENT L156:
```
# W24 — wording-2 ack followed by trailing content in the SAME block (unobserved in the measured
```

COMMENT L157:
```
# corpus, but the pass's own replacement mechanism discards "ANY trailing content after the ack in
```

COMMENT L158:
```
# that block" per the M1 blast-radius classification — regression guard for the fix: without a
```

COMMENT L159:
```
# newline bound on _ACK_PATH_RE's no-sentence fallback, this trailing text was swallowed into the
```

COMMENT L160:
```
# Output line instead of being cleanly discarded with the rest of the block)
```

COMMENT L174:
```
# ── LAUNCH-ACK WORDING 3: AUTO-BACKGROUNDED ON TIMEOUT (2026-09-14 milestone) ─────────────────
```

COMMENT L175:
```
# Third CC wording — Bash auto-backgrounds a call that exceeded its own timeout (not a deliberate
```

COMMENT L176:
```
# run_in_background launch, not a manual user backgrounding). Distinct anchored prefix ("Command did
```

COMMENT L177:
```
# not complete within its"), distinct ID shape ("(ID: <id>)" instead of "with ID: <id>."), and a
```

COMMENT L178:
```
# trailing "Session cwd remains ..." sentence in the SAME block that wording 1/2 never carry. The
```

COMMENT L179:
```
# replacement message names the timeout cause explicitly so it reads differently from a deliberate
```

COMMENT L180:
```
# background launch.
```

COMMENT L182:
```
# W34 — real recorded wording-3 body, verbatim (src/logs/dual_log/
```

COMMENT L183:
```
# api_requests_opus_monitor_cc_1789383190_original.jsonl, 2026-09-14) → exact 3-line output, trailing
```

COMMENT L184:
```
# cwd sentence discarded along with the rest of the matched ack (same discard behavior as W24).
```

COMMENT L207:
```
# ── INTERRUPT-MARKER TESTS (strip_interrupt_marker.py, 2026-07-30, re-measured 2026-07-31) ────
```

COMMENT L208:
```
# CC records the proxy's bg_escape.py tmux-Escape into a worker's pane as
```

COMMENT L209:
```
# "[Request interrupted by user]" or "[Request interrupted by user for tool use]" — never a
```

COMMENT L210:
```
# genuine user interrupt. Both real corpus wordings carry a trailing '\n' (11/11 occurrences,
```

COMMENT L211:
```
# src/logs/dual_log/*_original.jsonl, 2026-07-31 re-measurement). Whole-block match anchored
```

COMMENT L212:
```
# (ignoring only surrounding whitespace), NOT substring-anywhere — same FP-nuke class as
```

COMMENT L213:
```
# bg_launch_ack / sn_notice / plan_mode.
```

COMMENT L217:
```
# W25 — real measured shape: tool_result / marker(+trailing '\n') / injected wake-up (3 blocks).
```

COMMENT L218:
```
# Marker emptied to '.'; neighbors byte-identical.
```

COMMENT L232:
```
# W26 — 4 content shapes, each with the real newline-terminated marker.
```

COMMENT L244:
```
# W26b — the 2nd real wording ("for tool use"), newline-terminated and bare, both strip.
```

COMMENT L252:
```
# W27 — false-positive class: marker embedded inside longer text must survive untouched, incl.
```

COMMENT L253:
```
# a real corpus-derived 180-char user message that quotes the bracketed marker mid-sentence
```

COMMENT L254:
```
# (src/logs/dual_log/api_requests_opus_monitor_cc_1785431184_original.jsonl, msg 11).
```

COMMENT L272:
```
# W28 — message-pass wiring: role='user' only, mod name, removed-chunk attribution — real
```

COMMENT L273:
```
# newline-terminated marker.
```

COMMENT L291:
```
# W29 — message-pass wiring for the "for tool use" wording (previously untested — the gap the
```

COMMENT L292:
```
# false-negative shipped through).
```

## Salvage from dev/proxy/test_strip_fix_cases_templates.py

COMMENT L11:
```
# ── TEMPLATE TESTS ────────────────────────────────────────────────────────────
```

COMMENT L13:
```
# T01-T03: task-tools-nag
```

COMMENT L22:
```
# Inside tool_result, the strip no longer descends at all — the mid-line code-literal AND
```

COMMENT L23:
```
# the real trailing standalone SR are both preserved (whole block untouched).
```

COMMENT L36:
```
# T04-T06: pyright-diagnostics
```

COMMENT L45:
```
# Code containing <new-diagnostics> tag mid-line
```

COMMENT L58:
```
# T07-T09: deferred-tools
```

COMMENT L70:
```
# Inside tool_result nothing descends — quoted string AND the real trailing SR both preserved.
```

COMMENT L82:
```
# T10-T12: user-interrupt (partial mode)
```

COMMENT L104:
```
# Partial mode (IMPORTANT-line strip) no longer applies inside tool_result either — untouched.
```

COMMENT L109:
```
# T13-T15: system-notification
```

COMMENT L130:
```
# T16-T18: file-modified
```

COMMENT L153:
```
# T19-T21: claudemd-contents
```

COMMENT L174:
```
# T22-T24: date-changed (new template)
```

COMMENT L195:
```
# ── CONTENT SHAPE TESTS ───────────────────────────────────────────────────────
```

COMMENT L224:
```
# ── PLAN-MODE ────────────────────────────────────────────────────────────────
```

COMMENT L239:
```
# ── find_system_reminder_blocks ───────────────────────────────────────────────
```

COMMENT L242:
```
# Same real+code-literal mix as before the fix — now 0 found either way, tool_result isn't scanned.
```

COMMENT L254:
```
# ── _content_contains ────────────────────────────────────────────────────────
```

COMMENT L255:
```
# _content_contains itself still descends into tool_result — it remains the correct gate for the
```

COMMENT L256:
```
# out-of-scope non-SR passes (git-lock, hook-prefix, bd-noise) whose genuine content only lives
```

COMMENT L257:
```
# there; the SR family switched its own call sites to _top_level_content_contains instead (see
```

COMMENT L258:
```
# _apply_first_pass / _apply_cumulative_sr_strips), it did not change this shared helper.
```

COMMENT L272:
```
# ── SR-FAMILY TOOL_RESULT NON-DESCENT (2026-07-28 FP-nuke fix) ────────────────
```

COMMENT L273:
```
# _apply_final_sr_pass has NO gate at all — it calls _strip_all_system_reminders unconditionally
```

COMMENT L274:
```
# on every user message, so the traversal fix in strip_sr.py is the ONLY thing standing between it
```

COMMENT L275:
```
# and tool_result content. These cases give it extra scrutiny: both tool_result shapes must be
```

COMMENT L276:
```
# untouched, and the block object must come back by IDENTITY (not a rebuilt-but-equal dict), since
```

COMMENT L277:
```
# a rebuild would still register as a change in the diff-based bookkeeping downstream.
```

COMMENT L299:
```
# T37 — real Occurrence-8 shape: a rag-cli/process-docs excerpt fencing a literal env-context
```

COMMENT L300:
```
# system-reminder as a documentation example, inside a tool_result — must survive byte-exact.
```

COMMENT L326:
```
# T38/T39 — top-level SR stripping still works: this is a SCOPE REDUCTION, not a disable. One
```

COMMENT L327:
```
# template from an _apply_first_pass gated branch, one only _apply_final_sr_pass's catch-all covers.
```

## Salvage from dev/proxy/test_strip_fix_cases_wakeup.py

DOCSTRING L11:
```
Return True if _WAKEUP_TEXT (stripped of trailing newline) appears in content.
```

COMMENT L23:
```
# ── WAKEUP FALSE-POSITIVE TESTS ───────────────────────────────────────────────
```

COMMENT L25:
```
# W01 — <task-notification> in tool_result str → TN branch must NOT fire
```

COMMENT L36:
```
# W02 — <task-notification> in tool_result list-of-text → TN branch must NOT fire
```

COMMENT L47:
```
# W03 — complete BGK pattern in tool_result str → BGK branch must NOT fire, data intact
```

COMMENT L58:
```
# W04 — genuine plain-string completed TN → wakeup injected, mod=trimmed_task_notification
```

COMMENT L59:
```
# fixture has no <task-id> and no <output-file> — doubles as the "both missing" case: neither
```

COMMENT L60:
```
# 'Output:' nor 'ID:' line, content reduces to exactly _WAKEUP_TEXT.
```

COMMENT L72:
```
# W05 — genuine plain-string failed TN → wakeup injected, mod=replaced_task_notification
```

COMMENT L83:
```
# W06 — genuine plain-string BGK kill notification → wakeup injected, mod=replaced_bg_completed_text
```

COMMENT L92:
```
# ── SN-NOTICE-PARAGRAPH TESTS ─────────────────────────────────────────────────
```

COMMENT L93:
```
# strip_sn_notice.py — bare 4-line paragraph ahead of <task-notification>, anchored startswith
```

COMMENT L94:
```
# decision (not substring-anywhere) — same FP-nuke class as bg_launch_ack / plan_mode, see
```

COMMENT L95:
```
# process-docs/message_strip_fp_nuke/.
```

COMMENT L97:
```
# W07 — genuine plain-string paragraph + <task-notification> tag → stripped, mod fired
```

COMMENT L109:
```
# W08 — genuine text-block at non-zero block index → stripped (do NOT hardcode index 0)
```

COMMENT L124:
```
# W09 — paragraph quoted as tool_result data → must NOT fire, byte-exact untouched
```

COMMENT L133:
```
# W10 — paragraph mid-content in a text block (not at start) → must NOT fire, untouched
```

COMMENT L142:
```
# W11 — role="system" with paragraph at start → NOT touched by the SN-notice pass (out of scope)
```

COMMENT L151:
```
# ── ROLE=SYSTEM TASK-NOTIFICATION TESTS (2026-07-29 fix) ─────────────────────
```

COMMENT L152:
```
# _apply_role_system_strip previously nuked EVERY role='system' message to '.' before any TN
```

COMMENT L153:
```
# handling could see it — CC delivers bg-task wake-ups as a plain-str role='system' message
```

COMMENT L154:
```
# (measured: 173/280 real TN occurrences in one session log, role='system'/str; the other 107
```

COMMENT L155:
```
# were role='user'/list-text, already handled). Fix: _apply_role_system_strip leaves TN-carrying
```

COMMENT L156:
```
# role='system' messages untouched; _apply_sn_notice_strip + _apply_first_pass's TN branch (both
```

COMMENT L157:
```
# widened to accept role='system', narrowly gated on the TN tag itself) do the actual wake-up
```

COMMENT L158:
```
# construction — single source of truth, no duplicated TN-building logic. These tests run the
```

COMMENT L159:
```
# real 3-pass sequence (role_system_strip -> sn_notice_strip -> first_pass) matching rules.py's
```

COMMENT L160:
```
# `_passes` order.
```

COMMENT L208:
```
# W30 — CC 2.1.223 mid-turn user message (role='system') preserved whole (issue #61). Pre-223 this
```

COMMENT L209:
```
# arrived as a role='user' <system-reminder> ('user-interrupt' template, PARTIAL mode in
```

COMMENT L210:
```
# strip_sr.py — IMPORTANT line stripped, user body kept). The 223 role=system form bypasses that
```

COMMENT L211:
```
# SR-based guard entirely and was falling through to _apply_role_system_strip's unconditional '.'
```

COMMENT L212:
```
# replacement, silently dropping the user's text before it reached the model. Real body (recorded
```

COMMENT L213:
```
# session api_requests_opus_posts_1786051932, msg 274): 'jetzt' + CC's own boilerplate explainer.
```

COMMENT L231:
```
# Leading whitespace before the marker — guard checks lstrip()'d text, not exact prefix.
```

## Salvage from dev/proxy/test_strip_fix_cases_wrapped_tn.py

COMMENT L6:
```
# ── SR-WRAPPED TASK-NOTIFICATION TESTS (2026-09-04) ───────────────────────────
```

COMMENT L7:
```
# CC now sometimes delivers a bg-task wake-up as a role='user' message whose single text block is
```

COMMENT L8:
```
# a <system-reminder> wrapping BOTH the SN-notice paragraph AND the <task-notification> tag — real
```

COMMENT L9:
```
# fixture below, reconstructed verbatim from src/logs/dual_log/
```

COMMENT L10:
```
# api_requests_opus_wise2627_1788533758_stripped.jsonl, request_id 65c964d6-90c6-46ec-81de-
```

COMMENT L11:
```
# 190487d92e55, messages_delta["411"]["0"] (a list of 3 strings whose concatenation is this exact
```

COMMENT L12:
```
# text; the matching _original.jsonl entry, flow_id 13fca4a5-45f6-40be-bdaf-f8f0d10e765e, confirms
```

COMMENT L13:
```
# the shape: role='user', content=[{'type':'text','text': <this text>}], one block). Before the
```

COMMENT L14:
```
# fix: _apply_sn_notice_strip's anchored lstrip().startswith() check missed the paragraph (the
```

COMMENT L15:
```
# wrapper, not the paragraph, sits at position 0), so the wrapper survived _apply_first_pass's
```

COMMENT L16:
```
# TN-tag replace, and _apply_final_sr_pass then full-stripped the whole <system-reminder> block —
```

COMMENT L17:
```
# wrapper AND the just-injected wake-up text — leaving "." (20/22 wake-ups lost in the referenced
```

COMMENT L18:
```
# session, api_requests_opus_monitor_cc_1788464543, 2026-09-03/04). Full-chain tests here run
```

COMMENT L19:
```
# apply_modification_rules end to end (the real _passes order in rules.py), not a hand-picked
```

COMMENT L20:
```
# subset of passes.
```

COMMENT L45:
```
# W31 — real wrapped fixture, full apply_modification_rules chain: wire content is exactly the
```

COMMENT L46:
```
# wake-up text, wrapper AND SN paragraph gone — the same wire result the unwrapped shape produces.
```

COMMENT L65:
```
# W32 — bare role='system' str TN (the shape that already worked before the fix, no SR wrapper)
```

COMMENT L66:
```
# stays byte-identical through the full chain.
```

COMMENT L85:
```
# W33 — pre-existing unwrapped role='user' list-text TN (2026-07-29 shape, no SR wrapper) stays
```

COMMENT L86:
```
# byte-identical through the full chain.
```

## Salvage from dev/proxy/test_strip_fix_fixtures.py

COMMENT L71:
```
# Code-literal: <system-reminder> appears mid-line inside a string
```

## Salvage from dev/proxy/test_strip_fix.py

DOCSTRING L2-19:
```
Unit tests for template-based exact-match SR strip (Phase B).

Coverage:
  - 8 core templates × 3 cases each = 24 tests (real strip at top level, FP preserve, tool_result
    content PRESERVED — SR family no longer descends into tool_result, 2026-07-28 FP-nuke fix;
    see process-docs/message_strip_fp_nuke/2026-07-28_tool_result_sr_audit.md)
  - 4 content-shape tests (str / list[text] stripped; list[tool_result:str] / list[tool_result:list]
    now PRESERVED)
  - user-interrupt partial mode (body preserved, IMPORTANT stripped) — top-level only
  - plan-mode None-return behavior
  - _find_system_reminder_blocks: top-level extraction only (tool_result now finds nothing)
  - SR-family tool_result non-descent: _apply_final_sr_pass identity-preservation (str + list
    tool_result shapes, the pass with no gate at all), the real Occurrence-8 fenced-example shape,
    and top-level-still-works evidence for one `_apply_first_pass`-gated template + one template
    only `_apply_final_sr_pass`'s catch-all covers

Run: python3 dev/proxy/test_strip_fix.py

```

