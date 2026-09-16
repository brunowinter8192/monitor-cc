# process-docs/native-model-start/2026-09-16_comment_salvage.md

Session: dev/native-model-start/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/native-model-start/*.py` during this milestone,
copied verbatim before deletion, plus the full pre-rewrite content of
`dev/native-model-start/DOCS.md`. Nothing judged and dropped — see the milestone rules in the
calling agent's prompt (module-standards conformance: relocate then delete, decide nothing).

File-count note: the milestone prompt stated "6 .py files"; the actual count in
`dev/native-model-start/` is 7 `.py` files. `model_params_test_infra.py` already had zero
comments and zero docstrings before this milestone touched it — 7 minus that 1 is exactly 6, so
the prompt's figure is read as "files with at least one comment/docstring," not the true file
count. The stated comment/docstring totals (107 comments, 4 docstrings) matched exactly what
AST+tokenize measured across all 7 files.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/native-model-start/*.py`
before deletion: zero matches. The 4 module-level docstrings (in `p2_model_params_probe.py`,
`p3_cache_breakpoints_probe.py`, `p4_dual_log_integrity_probe.py`, `p5_strip_wordings_probe.py`)
are plain narrative, never read at runtime. All 4 deleted outright, no constant-rewiring needed.

## Execution-safety note for this session

`p3_cache_breakpoints_probe.py`, `p4_dual_log_integrity_probe.py`, and
`p5_strip_wordings_probe.py` each target two specific historical session log stems
(`api_requests_opus_posts_1786051932`, `api_requests_opus_websearch_1786052022`) under the main
checkout's `src/logs/dual_log/`. Those exact files no longer exist on disk (rotated out of the
live/rolling corpus since these probes were last run) — confirmed by actually running all three:
each raises `FileNotFoundError` before ever reaching its `REPORT_PATH.write_text(...)` call, so
the tracked `md/p3_..._report.md`/`p4_..._report.md`/`p5_..._report.md` files were never at risk
during this session's before/after verification runs (`git status` on `md/` stayed clean both
times). `p2_model_params_probe.py` writes a freshly-timestamped report file every run and never
overwrites an existing one; any such file created during this session's verification was deleted
before commit, never staged. No script in this directory touches the macOS desktop.

Comment/docstring counts confirmed via AST + tokenize before deletion: 107 comments, 4
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/native-model-start/DOCS.md

Full content of dev/native-model-start/DOCS.md as it stood before this rewrite (143 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / State sections added).

```markdown
# dev/native-model-start/

## Role
Verification scripts for starting the orchestrator's main CC session natively on a chosen model.
Covers the launcher's `--fable`/`--opus`/`--model` argument precedence (`src/claude_proxy_start.sh`),
the proxy's per-model `model_params` injection path (`src/proxy/inject_helpers.py`), and a live-verify
of the CC 2.1.223 pin bump (cache breakpoint stability, dual-log composition integrity, strip-wording
coverage) against two recorded 223-era sessions. Touch when changing the launcher's flag precedence or
`inject_helpers.py`'s model-override resolution; the 223 pin-bump probes are historical live-verify
records and don't need re-running unless the same class of pin bump recurs. `md/` holds every script's
report.

## Flow
Each script drives real production code (the launcher's parse loop mirrored in bash, or a real
`ProxyAddon`/`apply_modification_rules` instance) against synthetic argv or recorded dual-log payloads,
then asserts specific invariants and writes a timestamped report to `md/`.

## Modules

### p1_arg_parse_dry_run.sh (154 LOC)

**Purpose:** Dry-runs the `--fable`/`--opus`/`--model` precedence logic mirrored verbatim from
`src/claude_proxy_start.sh`'s parse loop — 8 cases covering explicit-vs-shortcut precedence,
position-independence, and last-shortcut-wins ordering. Never starts the proxy or claude.
**Reads:** nothing persistent — pure in-process argv simulation.
**Writes:** `md/p1_arg_parse_dry_run_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after editing `claude_proxy_start.sh`'s parse loop.
**Calls out:** stdlib bash only.

---

### p2_model_params_probe.py (135 LOC)

**Purpose:** Entry point for the model_params probe — runs the 15 test groups (imported from
`model_override_injection_tests.py`/`thinking_context_management_tests.py`) in order and writes
the report. 15 test groups, 73 checks.
**Reads:** nothing persistent — builds all fixtures in-process, config injected via
`mock.patch.object(inject_helpers, "_load_config", ...)`.
**Writes:** `md/p2_model_params_probe_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after changing `_inject_model_override`, its
fixation mechanics, `_strip_clear_thinking_edit`, `_build_forwarded_delta`, or
`attribution_coverage.py`'s field-attribution maps.
**Calls out:** `model_params_test_infra`, `model_override_injection_tests`,
`thinking_context_management_tests`.

---

### model_params_test_infra.py (27 LOC)

**Purpose:** Shared `check()`/`_RESULTS` assertion-recording infra and the `_with_config` context
helper used by every test group in this probe.
**Reads:** nothing.
**Writes:** nothing — mutates the shared in-memory `_RESULTS` list other modules import by reference.
**Called by:** `p2_model_params_probe.py`, `model_override_injection_tests.py`,
`thinking_context_management_tests.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### model_override_injection_tests.py (259 LOC)

**Purpose:** Tests 1-12 of the model_params probe — `_inject_model_override`'s per-model
`model_params` config lookup (exact model-id match, never writes `model`) vs. the legacy
family-bucketed `model_override`/`model_override_worker` fallback, plus the fixation mechanism that
pins a resolved override to a caller-owned dict across calls.
**Reads:** nothing persistent — builds all fixtures in-process.
**Writes:** nothing — results recorded via `model_params_test_infra.check`.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`.

---

### thinking_context_management_tests.py (187 LOC)

**Purpose:** Tests 13-15 of the model_params probe — `_strip_clear_thinking_edit` (a
`clear_thinking_20251015` context_management edit is removed whenever the payload's thinking ends
up `{"type": "disabled"}`, whichever path disabled it, siblings like `clear_tool_uses_20250919`
survive, an emptied edits list drops the whole `context_management` key, a non-disabled thinking
value leaves it byte-identical), `src/proxy/logging.py::_build_forwarded_delta`'s forwarded
`thinking` field, and (Test 15) that a `context_management` strip is attributed correctly by
`dev/proxy_dual_log/attribution_coverage.py`'s own field-attribution map rather than falling
through to `UNATTR` — while confirming `src/proxy/strip_inject_delta.py`'s own same-shaped maps
(proven dead code, since the real `fn_map` never carried a field-level entry for any top-level
field) have been removed from that module entirely.
**Reads:** nothing persistent — builds all fixtures in-process.
**Writes:** nothing — results recorded via `model_params_test_infra.check`.
**Called by:** `p2_model_params_probe.py`.
**Calls out:** `src.proxy.inject_helpers`, `src.proxy.logging` (`_build_forwarded_delta`),
`src.proxy.strip_inject_delta` (`_build_stripped_injected_deltas`),
`dev/proxy_dual_log/attribution_coverage.py` (loaded via
`importlib.util.spec_from_file_location`).

---

### p3_cache_breakpoints_probe.py (331 LOC)

**Purpose:** Replays every recorded request from two 223-era sessions through a real `ProxyAddon()`
instance in order (fresh addon per session) and checks breakpoint positional stability (BP1
`system[2]`, BP2 last non-defer tool) and message-content diffs at shared indices.
**Reads:** recorded dual-log `_original.jsonl` pairs under src/logs/dual_log (gitignored runtime data,
session stems `api_requests_opus_posts_1786051932` and `api_requests_opus_websearch_1786052022`).
**Writes:** `md/p3_cache_breakpoints_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.addon` (`ProxyAddon`, `_derive_worker_context`).

---

### p4_dual_log_integrity_probe.py (275 LOC)

**Purpose:** Verifies the composition invariant (C0/Cfwd reconstruction from recorded ops matches
`compose_block`) and top-level payload/schema stability, on the same two 223-era sessions as `p3_`.
**Reads:** the same two `_original.jsonl` files as `p3_cache_breakpoints_probe.py`.
**Writes:** `md/p4_dual_log_integrity_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.diff_engine`
(`compose_block`, `_get_inner_text`).

---

### p5_strip_wordings_probe.py (241 LOC)

**Purpose:** Checks bg-launch-ack / bg-completed / task-notification strip coverage on 223-era
wordings — a fn_map census over the recorded `_stripped`/`_injected` dual-logs, plus a replay sweep
through the current `apply_modification_rules` for any surviving marker string.
**Reads:** the same two sessions' `_original.jsonl` + `_stripped.jsonl` + `_injected.jsonl` files.
**Writes:** `md/p5_strip_wordings_probe_report.md`.
**Called by:** none — manual, historical 223 pin-bump live-verify.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.payload_helpers`
(`_top_level_content_contains`).

---

## Gotchas
- The two 223-era recorded sessions under src/logs/dual_log are live/growing corpus files — a re-run
  shifts denominators (composition-block and marker-occurrence counts change run to run) but does not
  change the CLEAN/FINDING classification itself.
- `p3_`'s cache-content comparison needs TWO shape normalizations before comparing message content
  across requests: `cache.py`'s own `_normalize_user_content_shape` (role='user' only), plus a second
  normalization for `_add_cache_control_to_message`'s string-to-single-block wrapping (applies to ANY
  role). Skipping the second normalization produces large false-positive "content changed" counts.
- The ready-to-paste `model_params` JSON values for `~/.claude/shared-rules/proxy_rules.json` are not
  in this directory — see `process-docs/native-model-start/` (user config outside the repo, never
  edited by any script here).
```

## Salvage from dev/proxy/model_override_injection_tests.py

COMMENT L51:
```
# Test 1 — legacy-only config (no 'model_params' key) -> byte-identical legacy behavior, INCLUDING
```

COMMENT L52:
```
# the model-field rewrite, for both opus and sonnet families.
```

COMMENT L74:
```
# Test 2 — model_params hit: thinking/effort/max_tokens applied, model field left untouched.
```

COMMENT L96:
```
# Test 3 — model_params miss: model not in the table -> payload untouched.
```

COMMENT L105:
```
# Test 4 — suffixed model-id variant is a DELIBERATE miss: exact-match only, no normalization.
```

COMMENT L106:
```
# Pinned so a future "should we strip suffixes?" question is a conscious follow-up, not a silent
```

COMMENT L107:
```
# behavior change nobody noticed.
```

COMMENT L111:
```
# suffix variant, e.g. a context-window tag
```

COMMENT L117:
```
# Test 5 — model_params present (even as an empty {}) alongside legacy sections -> model_params
```

COMMENT L118:
```
# wins, legacy is ignored entirely, no model rewrite happens.
```

COMMENT L126:
```
# already claude-fable-5 going in — key check is params source below
```

COMMENT L138:
```
# Test 6 — empty per-model entry ({}) and a partial entry (one key only).
```

COMMENT L157:
```
# Test 7 — config load failure degrades to no-op (fail-open), never raises.
```

COMMENT L171:
```
# Test 8 — (a)+(b): first request pins the model_params entry it saw; a later config change
```

COMMENT L172:
```
# against the SAME fixated dict (same simulated proxy process) does NOT alter the result.
```

COMMENT L191:
```
# Test 9 — (c): a FRESH fixated dict (simulated fresh addon instance / hot-reload) picks up the
```

COMMENT L192:
```
# new config — proves fixation is scoped to the dict instance, not global module state.
```

COMMENT L203:
```
# Test 10 — (d): legacy path is pinned the SAME way, and stays byte-identical to unfixated legacy
```

COMMENT L204:
```
# behavior (model rewrite included) on the pinning (first) call.
```

COMMENT L217:
```
# Config now DISABLES the section — same fixated dict must still apply the pinned (enabled) snapshot.
```

COMMENT L225:
```
# Test 11 — a genuine MISS (config loads fine, model not in the table) pins "no injection" too —
```

COMMENT L226:
```
# a later config addition for that model id, against the SAME fixated dict, must NOT retroactively apply.
```

COMMENT L243:
```
# Test 12 — a genuine _load_config() exception on the FIRST call for a model id does NOT pin —
```

COMMENT L244:
```
# the very next call (config now loadable) resolves live and pins from there.
```

## Salvage from dev/proxy/model_params_test_infra.py

## Salvage from dev/proxy/p2_model_params_probe.py

DOCSTRING L1-51:
```

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

```

## Salvage from dev/proxy/p3_cache_breakpoints_probe.py

DOCSTRING L1-26:
```

Issue #63 live-verify, surface 1 — cache breakpoint placement (src/proxy/cache.py) across the two
recorded CC 2.1.223 sessions (api_requests_opus_posts_1786051932, 152 requests;
api_requests_opus_websearch_1786052022, 108 requests).

Replays every recorded request through a REAL ProxyAddon() instance, in chronological order, per
session (fresh addon per session — state carries across requests exactly as in a live proxy
process: prev_messages_by_model, fixated, prev_*_hashes_by_model). Extracts the actual bytes about
to be sent (flow.request.content) per request and inspects cache_control placement:

  BP1 — system[2] (cross-session anchor)
  BP2 — last non-defer tool
  BP3 — last message unchanged from the previous request (end of stable prefix)
  BP4 — last message (always)

Checks the interaction flagged by the 223 release research: 2.1.212 changed mid-conversation
system-block caching behind gateways, and 223 traffic now carries mid-conversation role=system
MESSAGES (nag/notice text) that our proxy either nukes to "." or (2026-08-07 fix,
_apply_role_system_strip's mid-turn-user-message guard) preserves whole. For every pair of
consecutive requests, diffs every message index PRESENT IN BOTH (cache_control stripped before
comparing — BP3/BP4 legitimately toggle it) to catch any already-existing (non-tail) message whose
content changed — a real prefix-cache bust, not the expected/designed tail growth.

Usage (from project root, real venv — imports mitmproxy via proxy.addon):
    ./venv/bin/python dev/native-model-start/p3_cache_breakpoints_probe.py

```

COMMENT L75:
```
# Load every recorded request's full original payload for one session, in file (chronological) order
```

COMMENT L97:
```
# Content of one message with cache_control stripped, for cross-request identity comparison.
```

COMMENT L98:
```
# Two independent normalizations collapse pure JSON-shape churn from the cache_control add/remove
```

COMMENT L99:
```
# cycle so only REAL content changes surface:
```

COMMENT L100:
```
#  (1) cache.py's own _normalize_user_content_shape (role='user' only, production behavior).
```

COMMENT L101:
```
#  (2) A single-text-block list <-> plain string collapse for EVERY role — not cache.py's own
```

COMMENT L102:
```
#      scope, but the mechanical cause of ALL remaining false positives observed in this probe's
```

COMMENT L103:
```
#      first two runs: _add_cache_control_to_message wraps a plain string into
```

COMMENT L104:
```
#      [{"type":"text","text":X,"cache_control":...}] to attach the marker (any role); once that
```

COMMENT L105:
```
#      position is no longer the BP3/BP4 target on a later request, the pass that regenerates that
```

COMMENT L106:
```
#      message (e.g. _apply_role_system_strip re-emitting a fresh bare "." every time it fires) has
```

COMMENT L107:
```
#      no reason to preserve the wrapper — semantically identical text, cosmetically different
```

COMMENT L108:
```
#      shape. Confirmed: after normalization (1) alone, EVERY remaining raw diff was exactly this
```

COMMENT L109:
```
#      wrap/unwrap pattern on non-user roles (system "." messages, mostly) — no case where the
```

COMMENT L110:
```
#      actual text differed while shapes also happened to differ.
```

COMMENT L125:
```
# Replay one session through a fresh real ProxyAddon; returns per-request records
```

COMMENT L155:
```
# Cross-request analysis: BP1/BP2 stability + BP3/BP4 prefix-bust detection
```

COMMENT L161:
```
# (seq, msg_idx) where a pre-existing message's content changed
```

COMMENT L194:
```
# For each prefix-bust index, classify: does the changed content match the mid-turn-user-message
```

COMMENT L195:
```
# marker (before and/or after) — the exact interaction this probe is checking for.
```

COMMENT L208:
```
# tail-adjacent: idx is the last or second-to-last message in BOTH requests — almost
```

COMMENT L209:
```
# certainly an in-flight draft edit/extension (user still typing before submit), not a
```

COMMENT L210:
```
# deep-history mutation of already-"stable" content. is_bootstrap: happens in the
```

COMMENT L211:
```
# session's first 3 requests — CC's own session-start message reshaping.
```

COMMENT L319:
```
# Overall verdict
```

## Salvage from dev/proxy/p4_dual_log_integrity_probe.py

DOCSTRING L1-25:
```

Issue #63 live-verify, surface 2 — dual_log integrity over ALL recorded requests of both CC
2.1.223 sessions (api_requests_opus_posts_1786051932, api_requests_opus_websearch_1786052022).

Part A — composition invariant, driven over REAL sessions (not the fixture corpus
dev/proxy_dual_log/test_composition_invariant.py uses). Calls the REAL
src/proxy/rules.py::apply_modification_rules on every recorded ORIGINAL payload (independent
per-request — the message-passes pipeline itself carries no cross-request state; only the
dual-log's cache-hash bookkeeping in ProxyAddon does, irrelevant to composition), and validates
its own returned `all_ops` (the real per-block edit-op list every op-recording pass appends to,
merged via `_merge_ops`) against the REAL `compose_block` (`src/proxy/diff_engine.py`, the same
function `strip_inject_delta.py` uses to build the dual-log's span data):

  Inv1: "".join(t for tag,t in spans if tag in ("equal","stripped")) == C0_block_text
  Inv2: "".join(t for tag,t in spans if tag in ("equal","injected")) == Cfwd_block_text

Part B — schema-drift scan: every top-level payload key, system-block key-set, and content-block
`type` value observed across BOTH sessions' original payloads, diffed against the sets this
pipeline's own code explicitly names/handles (found by reading message_summary.py /
_extract_forwarded_fields / diff_engine.py) — flags anything new CC 2.1.223 might have introduced
that the pipeline does not model.

Usage (from project root, real venv — imports mitmproxy transitively via src.proxy.rules):
    ./venv/bin/python dev/native-model-start/p4_dual_log_integrity_probe.py

```

COMMENT L46:
```
# Types this pipeline's own code explicitly branches on (message_summary.py::_summarize_message)
```

COMMENT L48:
```
# Top-level payload keys _extract_forwarded_fields / apply_modification_rules explicitly read
```

COMMENT L67:
```
# Part A — composition invariant over one request's real all_ops against the real compose_block
```

COMMENT L103:
```
# Part B — schema-drift scan over one payload
```

COMMENT L117:
```
# For each unmodeled top-level key, confirm the real pipeline forwards it byte-identical
```

COMMENT L118:
```
# (dict(payload) shallow-copy pattern used throughout apply_modification_rules/cache.py) rather
```

COMMENT L119:
```
# than silently dropping it — the difference between "not specially modeled" (fine, forward-
```

COMMENT L120:
```
# compatible by construction) and "silently lost" (a real functional bug: e.g. dropping the
```

COMMENT L121:
```
# top-level `thinking` config would disable extended thinking without any visible error).
```

## Salvage from dev/proxy/p5_strip_wordings_probe.py

DOCSTRING L1-19:
```

Issue #63 live-verify, surface 3 — strip wordings on CC 2.1.223, over both recorded sessions
(api_requests_opus_posts_1786051932, api_requests_opus_websearch_1786052022).

Part A — fn_map census: scans the REAL recorded `_stripped.jsonl`/`_injected.jsonl` dual-logs for
fn_map function-name occurrences, confirming `_apply_bg_launch_ack_strip` (bg-launch ack) and
`_apply_first_pass` (covers the TN branch) / `_apply_bg_exit_strip` (bg-completed/kill) actually
fired in both sessions' 223-era traffic — a historical record of what fired when these sessions
were captured.

Part B — unstripped-wording sweep: replays every recorded ORIGINAL payload through the REAL,
CURRENT `apply_modification_rules` (this worktree's code, not the possibly-stale historical fn_map
from Part A) and checks, for every message whose ORIGINAL content contains one of the known
bg-related marker strings, whether that marker text still appears in the corresponding FORWARDED
message content — a survival would mean a wording drift no strip pass currently matches.

Usage (from project root, real venv — imports mitmproxy transitively via src.proxy.rules):
    ./venv/bin/python dev/native-model-start/p5_strip_wordings_probe.py

```

COMMENT L40:
```
# Marker strings each bg-related strip pass anchors on (from the real source modules)
```

COMMENT L59:
```
# Part A — fn_map census over the real recorded stripped/injected dual-logs for one session
```

COMMENT L74:
```
# Part B — for one request, find messages whose ORIGINAL TOP-LEVEL content contains a marker, and
```

COMMENT L75:
```
# check if that marker text still appears in the corresponding FORWARDED message's TOP-LEVEL
```

COMMENT L76:
```
# content. TOP-LEVEL only (str content, or list blocks with type=='text') — deliberately excludes
```

COMMENT L77:
```
# tool_result content, matching the real strip passes' own `_top_level_content_contains` gate
```

COMMENT L78:
```
# (2026-07-28 FP-nuke fix, src/proxy/DOCS.md). Without this, rag-cli/gh-cli search results that
```

COMMENT L79:
```
# quote these marker strings as DATA (this repo's own process-docs discuss `<task-notification>`
```

COMMENT L80:
```
# and "Background command" at length, and get indexed/returned by rag-cli) produce massive false
```

COMMENT L81:
```
# "unstripped" counts — confirmed as the sole cause of this probe's first-run 421/2995 count
```

COMMENT L82:
```
# (spot-checked multiple hits: all were tool_result search-result content quoting the marker in
```

COMMENT L83:
```
# prose, never a live top-level notification).
```

COMMENT L122:
```
# Presence of the raw marker text in each session's ORIGINAL log — distinguishes "the strip
```

COMMENT L123:
```
# never fired because the wording never occurred" (fine) from "the wording occurred but the
```

COMMENT L124:
```
# strip didn't fire" (a real gap).
```

COMMENT L137:
```
# TN/bg-completion routes through _apply_bg_exit_strip for this traffic's dominant wording
```

COMMENT L138:
```
# (confirmed by direct fn_map inspection: flow 9f75f100/msg38 in websearch attributes to
```

COMMENT L139:
```
# _apply_bg_exit_strip, not _apply_first_pass) — either satisfies "the TN/bg-completed
```

COMMENT L140:
```
# replacement fired".
```

## Salvage from dev/proxy/thinking_context_management_tests.py

COMMENT L19:
```
# Load dev/proxy_dual_log/attribution_coverage.py by path (its module name has no package
```

COMMENT L20:
```
# context here, matching the same by-path load it itself uses for src/proxy/strip_vocab.py).
```

COMMENT L29:
```
# (a) thinking disabled + clear_thinking edit + a sibling edit -> only clear_thinking removed
```

COMMENT L30:
```
# (b) thinking disabled + ONLY the clear_thinking edit -> whole context_management key dropped,
```

COMMENT L31:
```
# not carried forward as an empty edits list (an empty edits list asks the API for "manage
```

COMMENT L32:
```
# context with zero edits", which is not the same as "no context_management at all" — dropping
```

COMMENT L33:
```
# the key is what Claude Code itself does when IT disables thinking, per the Haiku request in
```

COMMENT L34:
```
# the same capture).
```

COMMENT L62:
```
# (c) thinking NOT disabled (adaptive) -> context_management untouched, byte-identical (same
```

COMMENT L63:
```
# object, not just equal-by-value).
```

COMMENT L64:
```
# (d) thinking disabled, no context_management at all -> no-op
```

COMMENT L65:
```
# (e) thinking disabled, context_management has no clear_thinking edit -> untouched
```

COMMENT L91:
```
# (f) end-to-end: the exact observed shape — Claude Code sends thinking=adaptive plus its own
```

COMMENT L92:
```
# clear_thinking edit, the proxy's model_params injection (the menubar thinking-off toggle)
```

COMMENT L93:
```
# overwrites thinking to disabled, and the two functions together (as wired in
```

COMMENT L94:
```
# addon.py:_run_post_fixation_pipeline) must leave the payload self-consistent.
```

COMMENT L111:
```
# Test 13 — thinking/context_management self-consistency: a surviving clear_thinking_20251015
```

COMMENT L112:
```
# edit alongside a disabled thinking value is what produced the real 400 in
```

COMMENT L113:
```
# api_requests_worker_25c51a2e_cache-write-run_1789308787; _strip_clear_thinking_edit must remove
```

COMMENT L114:
```
# exactly that edit, no matter what disabled thinking, and never leave a dangling empty edits list.
```

COMMENT L122:
```
# Test 14 — the forwarded dual-log must show the forwarded 'thinking' value, so this exact failure
```

COMMENT L123:
```
# is readable straight off _forwarded.jsonl without cross-referencing the injected-fields delta.
```

COMMENT L144:
```
# Test 15 — follow-up review point: _strip_clear_thinking_edit can now remove a top-level field
```

COMMENT L145:
```
# (context_management) for the first time ever on the STRIP side. Establishes (a) the real fn_map
```

COMMENT L146:
```
# written to stripped/injected JSONL never attributes ANY top-level field, and that
```

COMMENT L147:
```
# src/proxy/strip_inject_delta.py's own _FIELD_STRIP_FN/_FIELD_INJECT_FN — proven dead code by
```

COMMENT L148:
```
# that fact — have since been removed from that module entirely; and (b) the tool that DOES
```

COMMENT L149:
```
# attribute fields_delta entries, dev/proxy_dual_log/attribution_coverage.py's own
```

COMMENT L150:
```
# _FIELD_STRIP_FN, now correctly names _strip_clear_thinking_edit instead of falling through to
```

COMMENT L151:
```
# UNATTR:context_management.
```

