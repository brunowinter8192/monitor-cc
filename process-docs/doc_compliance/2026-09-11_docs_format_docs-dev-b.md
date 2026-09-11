# Salvage — DOCS.md format cut, docs-dev-b, 2026-09-11

This file is the salvage of the format cut applied to the `dev/<area>/DOCS.md` files assigned to
worker docs-dev-b (native-model-start, pane_error_log, pane_search, panes, pipeline, proxy_display,
proxy_dual_log, proxy_instrumentation, proxy_tool_stripping, proxy, rag_helpfulness, ram_audit,
session_analysis, sleep_pattern_analysis, strip_fp_tool_result, thinking, timer-loop, tmux_launcher,
tool_injection, tool_use_analysis, tool_use_errors, ToolsSystemPrompts, verbosity,
worker_status_probes, workers), dated 2026-09-11. Every file below was rewritten from a
changelog-style history (dated iteration notes, "split out of X", verification narratives,
function-by-function detail) to the DOCS.md module-map format. The full pre-cut text of each file is
preserved here verbatim, grouped by its source path, for RAG retrieval — this file makes no claim
about which parts are still true of the current code; the rewritten DOCS.md files are the current
module map.

## Salvage from dev/ToolsSystemPrompts/DOCS.md

```
# dev/ToolsSystemPrompts/

## Role
Captured reference corpus of Claude Code's built-in tool definitions + a system-prompt segment, snapshotted to size the proxy-side tool-injection / tool-stripping budget (how many chars each tool description + schema costs, and which are strip candidates). Reference DATA + its analysis, not a script area — no `.py`, nothing produced at runtime. Touch when re-measuring tool-definition sizes against a new CC version; do NOT treat as live state (it is a point-in-time capture).

## Contents
- `_index.md` — size table: per-tool description chars, schema chars, totals, plus `sys[3]` and grand total.
- `_review.md` — strip analysis (Phase B): total tool-description chars, chars classified REDUNDANT/KNOWN and strippable.
- `<Tool>.md` (`Bash`, `Edit`, `Glob`, `Grep`, `Read`, `Skill`, `Write`) — the captured description + JSON schema text of each built-in tool, with its char count.
- `mcp__plugin_iterative-dev_iterative-dev__*.md` — captured MCP tool schemas (dev_sync, git_check, worker_send, worker_spawn).
- `sys3.md` — the captured `sys[3]` system-prompt segment (char count + content).

## Gotchas
Char counts are version-specific — a CC upgrade changes tool descriptions, so the numbers here are only valid for the capture's CC version. Re-capture rather than trust stale figures.
```

## Salvage from dev/native-model-start/DOCS.md

```
# dev/native-model-start/

## Role

Verification scripts for starting the orchestrator's main CC session natively on a chosen model
(`--fable`/`--opus` flags on `src/claude_proxy_start.sh`, `p1_`), the proxy-side per-model
parameter config that replaced the old model-rewrite override (`src/proxy/inject_helpers.py`,
`p2_`), and the CC 2.1.223 pin-bump live-verify (`p3_`/`p4_`/`p5_`, issue #63 — cache breakpoints,
dual_log composition integrity, strip-wording coverage, all driven over two recorded 223 sessions).
`md/` holds every script's report.

## Modules

### p1_arg_parse_dry_run.sh (148 LOC)

**Purpose:** Pure argument-parsing dry run for `src/claude_proxy_start.sh`'s `--fable`/`--opus`/
`--model` precedence — mirrors the exact parse loop verbatim (kept in sync manually, same
convention as `dev/hook_smoke/test_version_purge.sh`'s mirrored-function pattern). 8 cases: no flag
(byte-identical baseline), `--fable` alone, `--opus` alone, a shortcut then explicit `--model`
(explicit wins), explicit `--model` then a shortcut (explicit STILL wins — position-independence,
pinned as its own case), both shortcuts in each order (last one wins both ways), and a mixed case
with `--project` + another passthrough flag+value. Never starts the proxy or claude.
**Reads:** Nothing persistent — pure in-process argument simulation.
**Writes:** `md/p1_arg_parse_dry_run_<timestamp>.md`.
**Called by:** run manually — regression guard; re-run after any change to
`claude_proxy_start.sh`'s parse loop (keep both copies in sync).
**Calls out:** stdlib bash only.

---

### p2_model_params_probe.py (356 LOC)

**Purpose:** Verifies `src/proxy/inject_helpers.py::_inject_model_override`'s 2026-08-06 rework —
per-model `model_params` config path (exact model-id lookup, never writes `model`) vs the legacy
family-bucketed `model_override`/`model_override_worker` path (byte-identical fallback when
`model_params` is absent from config) — and its 2026-09 fixation extension. 12 test groups, 55
checks. Tests 1-7 (unchanged from the 2026-08-06 rework, all still called with only 2 positional
args): legacy-only config unchanged incl. the model rewrite (opus/sonnet/haiku); `model_params` hit
for each of the 3 snippet models with the model field verified untouched; miss leaves payload
untouched; a suffixed model-id variant (`claude-opus-4-8[1m]`) is a DELIBERATE miss — exact-match
only, no normalization, pinned so a future report of this is recognized as a known boundary, not a
fresh bug; `model_params` presence (both non-empty and empty `{}`) wins over legacy sections even
when both are in the config; empty vs partial per-model entries; `_load_config` raising fails open
— all proving the 2-arg call form (no fixation dict) is byte-unaffected by the rework, since the
default `fixated_model_override=None` creates a fresh, discarded dict per call. Tests 8-12 (new,
2026-09, model-params fixation): a caller-owned `fixated` dict pins the whole resolved unit
(model_params entry, or the legacy section) on the first call for a given exact model id — Test 8
proves a later config change against the SAME dict (simulated same proxy process) is ignored; Test
9 proves a FRESH dict (simulated fresh addon instance / hot-reload) picks up the new config; Test 10
proves the legacy path is pinned the same way and stays byte-identical to the unfixated Test 1 on
the pinning call, even surviving the legacy section later being disabled; Test 11 proves a genuine
miss (config loads fine, model not in the table) pins "no injection" too, not just a hit; Test 12
proves a genuine `_load_config()` exception on the first call does NOT pin — the very next call
retries live and pins from there. Config injected via `mock.patch.object(inject_helpers,
"_load_config", ...)` — no prior mocking precedent for `rules_config` existed anywhere in this repo
before this script.
**Reads:** Nothing persistent — builds all fixtures in-process.
**Writes:** `md/p2_model_params_probe_<timestamp>.md`.
**Called by:** run manually — regression guard for `inject_helpers.py`; re-run after any change to
`_inject_model_override`, its two path functions, or the fixation mechanics.
**Calls out:** `src/proxy/inject_helpers.py`.

---

### p3_cache_breakpoints_probe.py (311 LOC)

**Purpose:** Issue #63 live-verify, surface 1 — `src/proxy/cache.py` breakpoint placement across
both recorded 223 sessions. Replays every recorded request through a REAL `ProxyAddon()` instance
in chronological order (fresh addon per session, state carries across requests as in a live proxy)
and inspects the actual bytes about to be sent. BP1 (`system[2]`)/BP2 (last non-defer tool)
positional stability; message-level content diffs at common indices, classified
`session_bootstrap` / `tail_draft_edit` / `deep_history_mutation` / `mid_turn_marker` (the flagged
2026-08-07 preserve-guard interaction) after two normalizations that neutralize pure JSON-shape
churn from the cache_control add/remove cycle itself (both discovered empirically — first run: 83
raw diffs, all cache_control-list-vs-collapsed-string shape noise; confirmed the second
normalization needed to apply to EVERY role, not just cache.py's own user-only scope).
**Reads:** `src/logs/dual_log/api_requests_opus_{posts_1786051932,websearch_1786052022}_original.jsonl`.
**Writes:** `md/p3_cache_breakpoints_probe_report.md`.
**Calls out:** `src.proxy.addon` (`ProxyAddon`, `_derive_worker_context`).

---

### p4_dual_log_integrity_probe.py (237 LOC)

**Purpose:** Issue #63 live-verify, surface 2 — composition invariant + schema drift over both
recorded 223 sessions. Part A: calls the REAL `apply_modification_rules` (independent per-request
— the message-passes pipeline carries no cross-request state) and validates its own returned
`all_ops` against the REAL `compose_block` (`src/proxy/diff_engine.py`, same function
`strip_inject_delta.py` uses) — Inv1 (C0 reconstruction) / Inv2 (Cfwd reconstruction) over every
block with recorded ops. Part B: top-level payload keys / system-block shapes / content-block
`type` values observed vs the pipeline's explicitly-named sets; any unmodeled top-level key gets a
direct pass-through verification (not assumed) exploiting the `dict(payload)` shallow-copy pattern
`apply_modification_rules`/`cache.py` both use.
**Reads:** same two `_original.jsonl` files as `p3_`.
**Writes:** `md/p4_dual_log_integrity_probe_report.md`.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.diff_engine`
(`compose_block`, `_get_inner_text`).

---

### p5_strip_wordings_probe.py (207 LOC)

**Purpose:** Issue #63 live-verify, surface 3 — bg-launch-ack / bg-completed / TN strip coverage
on 223-era wordings. Part A: fn_map census over the REAL recorded `_stripped`/`_injected`
dual-logs (historical record of what fired at capture time). Part B: unstripped-wording sweep —
replays every request through the CURRENT `apply_modification_rules`, checking whether any known
bg-related marker string (bg-launch-ack ×2 wordings, bg-completed, `<task-notification>`) survives
unstripped into the forwarded payload — scoped to TOP-LEVEL content only via
`payload_helpers._top_level_content_contains`, matching the real passes' own tool_result-exclusion
gate (first run without this scoping: 421/2995 false "survivals", all rag-cli/gh-cli search
results quoting these marker strings as prose in this project's own indexed docs).
**Reads:** same two sessions' `_original.jsonl` + `_stripped.jsonl` + `_injected.jsonl`.
**Writes:** `md/p5_strip_wordings_probe_report.md`.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy.payload_helpers`
(`_top_level_content_contains`).

---

## Gotchas

**p1's ready-to-paste `model_params` values live in process-docs, not here.** The actual JSON
snippet for `~/.claude/shared-rules/proxy_rules.json` (fable-5/opus-5/sonnet-5, values read from
the live legacy config at write time) is in
`process-docs/native-model-start/2026-08-06_model_params_config.md` — that file is user config
outside the repo and is never edited by any script in this directory.

**p3/p4/p5's two recorded sessions are live/growing — counts are a lower bound, not final.** Same
caveat as `dev/timer-loop`'s p1 corpus note: `src/logs/dual_log/api_requests_opus_{posts,
websearch}_*_original.jsonl` can still be appended to by a concurrent live session while a probe
runs; re-running shifts denominators (observed: 4924 → 4999 composition blocks, 1810 → 1818 marker
occurrences across two runs in the same session) but the CLEAN/FINDING classification itself was
stable.

**p3's cache-content comparison needs TWO shape normalizations, not one.** cache.py's own
`_normalize_user_content_shape` (role='user' only) is production behavior and must be mirrored for
fidelity — but is NOT sufficient alone: `_add_cache_control_to_message` wraps a plain string into
a single-text-block list to attach `cache_control`, for ANY role, and once that position stops
being the BP3/BP4 target the pass regenerating it (e.g. `_apply_role_system_strip` re-emitting a
bare `"."`) has no reason to preserve the wrapper. Comparing content across requests without
collapsing this second shape difference (any role, not just user) produces large false-positive
"content changed" counts — went from 83 → 46 → 10 raw diffs across the two normalization passes
before landing on the real signal.
```

## Salvage from dev/pane_error_log/DOCS.md

```
# dev/pane_error_log/

## Role

Regression coverage for `src/pane_error_log.py` (shared exception-safe sink) and the
per-loop exception guard wrapping all 8 pane `run_*_loop()` functions
(`src/workers/worker_pane.py` + the 7 other modules retrofitted 2026-07-31, in two passes — 6 found
in the initial sweep, `news_pane/log_pane.py` found in a follow-up: it was missed because window 5
has two panes, so this one dying silently leaves pane 5.1 blank rather than killing the whole
tmux window, unlike the single-pane windows that motivated the original sweep). **(2026-09) The
main pane's `run_main_loop` (`src/core/monitor.py`) was removed along with the main pane itself**
— see `process-docs/main_pane/` — dropping the pane-loop count from 9 to 8; `test_main_pane` and
its `mod_main` import were removed from `p1_pane_loop_survives_exception_probe.py` accordingly.
Verifies catch+log+continue end to end without a live tmux session — cannot be tested by killing a
real pane process, so each loop is invoked directly with its I/O primitives monkeypatched. `md/`
holds every run's report.

## Modules

### p1_pane_loop_survives_exception_probe.py (429 LOC)

**Purpose:** For 7 of the 8 pane loops (all but `news_pane/log_pane.py`): injects a marker
exception on the loop's first `read_keypress()` call, forces a bounded exit after 3 ticks via a
`BaseException` stand-in (`_ProbeStop`), and asserts the injected exception was caught + logged
with the correct pane identifier + full traceback, that the loop survived past the crash
iteration, and that `finally: disable_mouse(); restore_terminal()` still ran. For the 8th
(`news_pane/log_pane.py::run_news_log_loop`, pane id `news_log`) — no keyboard/mouse and no
`finally:` (never had one, none invented) — the marker exception is injected via `find_log_file()`
instead, `time.sleep` is the tick counter, and only catch+log+continue is asserted, not cleanup.
Also verifies real `KeyboardInterrupt`/`SystemExit` still propagate (not swallowed by
`except Exception:`), that a failing log write (unwritable path, `_cap_log_size` seek-underflow
on an artificially tiny file) cannot raise out of `log_pane_error`, and that the sink truncates
to its tail once it exceeds the size cap.
**Reads:** Whatever real session/tmux/RAG state exists on the machine (each loop's real
data-refresh/render path runs unmocked past the injected first-call crash — any exception it
raises is caught by the same new guard and logged, harmless to the assertions, which only check
for the specific injected marker).
**Writes:** `md/p1_pane_loop_survives_exception_probe_<timestamp>.md`; redirects
`pane_error_log.PANE_ERROR_LOG_PATH` to `/tmp/_pane_error_log_probe.log` for the run (never
touches the real `/tmp/monitor_cc_error.log`).
**Called by:** run manually — regression guard for `pane_error_log.py` and all 8 pane-loop
guards; re-run after any change to a pane loop's `while True:` shape or to `pane_error_log.py`.
**Calls out:** `src.pane_error_log`, `src.workers.worker_pane`, `src.proxy_display.pane`,
`src.proxy_display.worker_proxy_pane`, `src.panes.token_pane`, `src.panes.warnings_pane`,
`src.gpu_pane.pane`, `src.news_pane.pane`, `src.news_pane.log_pane` — loaded
via `importlib.import_module` (package-qualified; these modules use `from ..constants import ...`
double-dot relative imports, so they cannot be path-inserted as bare top-level modules the way
self-contained packages like `proxy` can).
```

## Salvage from dev/pane_search/DOCS.md

```
# dev/pane_search/

## Purpose

Feasibility measurement + regression coverage for the pane-search rollout. `p1`-`p3` cover the
PROXY pane's search feature (`src/proxy_display/` — `pane.py`, `format.py`, `render_turn.py`,
`forwarded_parser.py`, `search.py`), the rollout's reference implementation. Milestone 1 (`p1_*`)
probed the cost of candidate message-reconstruction strategies on real forwarded-delta logs —
measurement only, no feature code. Milestone 2 (`p2_*`) is the regression suite for the
implemented feature: permanent row-1 search bar, one-sweep reconstruction, real-render-based
matching, the `flow_id`-based `_lazy_load_messages_forwarded` fix found during M2 investigation,
and (follow-up) the UTF-8 multi-byte keypress fix in `input.click_handler.read_keypress`.
Milestone 3 (`p3_*`) is drag-to-select on the search bar (press-anchors, motion-extends,
release-copies-to-clipboard). `p4_*` (rollout sub-milestone 2) covered the MAIN pane
(`src/core/monitor.py`, `core/monitor_display.py`) reaching full parity with the proxy-pane
reference — **removed 2026-09 along with the main pane itself** (window 0 is now the tokens pane
at full width, see `process-docs/main_pane/`).
`p5_*` (rollout sub-milestone 3) covers the WORKER-PROXY pane
(`src/proxy_display/worker_proxy_pane.py`) — the proxy pane's closest structural twin (same
`format_proxy_block`/`render_turn` pipeline, same forwarded-log data model) — reaching the same
parity, plus the NEW 2-row header composition (search bar row 1, the pre-existing
worker-switcher header shifted below) and a worker-switch search-state reset.
`p6_*` (rollout sub-milestone 4) covers the TOKENS pane (`src/panes/token_pane.py`,
`src/format/token_format.py`, new `src/panes/token_search.py`) — structurally simpler (single
expand level, data always fully loaded, no windowing) — reaching the same parity, plus fixing
the `ZEBRA_BG_A == ''` sentinel bug (same class the proxy pane hit) in this pane's own
hand-rolled row-background loop, and the two-key (`(turn_idx,call_idx)` vs `('turn',turn_idx)`)
match-container-marking design.
`p7_*` (rollout sub-milestone 5) covers the WORKERS pane (`src/workers/worker_pane.py`,
`src/workers/worker_format.py`) — the FIRST pane needing a genuine reconstruction step
(`worker_turns` only holds data for currently-EXPANDED workers, so Enter force-parses every
listed worker's own JSONL) — reaching the same parity, plus a THREE-tier match key (worker /
turn / call, composing with `format_cache_tracker`'s sub-milestone-4 kwargs via a per-worker
scoping derivation), a third occurrence of the sentinel fix, and a jump-to-match design that
respects the pane's dormant pane-level scroll while self-healing via a fresh re-parse at jump
time.
`p8_*` (rollout sub-milestones 6-8, BUNDLED — the final milestone, one plan/Go/commit stream)
covers WARNINGS (`src/panes/warnings_pane.py` + `warnings_render.py`), GPU
(`src/gpu_pane/pane.py`), and NEWS (`src/news_pane/pane.py` ONLY — `log_pane.py` explicitly
EXCLUDED per decision). Warnings: 1-level expand, a fourth sentinel occurrence — but the ONLY
pane in the rollout whose pre-existing row-bg detection needed ZERO collateral `.startswith()`
fix (verified by reading `warnings_render.py` at line level before assuming, per the milestone's
own explicit requirement — it already used the substring form). GPU/news: flat, small
live-fetched lists, NO scroll infra at all — HIGHLIGHT-ONLY, no jump-to-match, `n`/`N` cycles
`current_idx` with zero scroll call, no sentinel needed (no per-row background at either pane).
Both panes' mouse dispatch is inline (never factored into a standalone handler function, a
pre-existing characteristic unrelated to search) — `search_bar.py`'s functions are called
directly at the dispatch sites; `_render_pane`'s own row numbering in both panes stays
UNSHIFTED, the search-bar shift for `_button_regions` applied externally in the loop — verified
by `dev/click_ui/p4_gpu_news_button_probe.py` needing ZERO changes (it calls `_render_pane`
directly). Rollout complete as of this milestone — all 8 tmux panes now share `src/search_bar.py`.
See `process-docs/pane_search/` for the investigation trail.

## Scripts

### p1_full_sweep_cost_probe.py (403 LOC)

**Purpose:** Compares two reconstruction strategies on a real `_forwarded.jsonl` log:
per-entry lazy-load (replay-from-byte-0 per entry, O(N) replays) vs one-sweep reconstruction
(single pass, deque eviction removed, keeps messages for all entries).

dev/ scripts may not import `src/` — the delta-accumulation algorithm
(`_dict_to_list`/`_apply_delta_to_list`/family accumulator/deque-bound eviction) is
reimplemented locally, mirroring `src/proxy_display/forwarded_parser.py`'s
`_parse_forwarded_log`/`_lazy_load_messages_forwarded` (same per-line I/O + `json.loads` +
delta-apply work). Message summarization is simplified to chars-only — real
`src/proxy/message_summary.py` adds per-block-type detail irrelevant to the O(N) file-replay
cost measured here; both strategies share the same local summarizer, so the comparison is
apples-to-apples.

Measures: summed + per-entry wall time for lazy-load-ALL-entries (`_lazy_load_one`, linear-fit
slope quantifies the O(idx)-per-call / O(N^2)-total growth), one-sweep total wall time
(`_sweep_parse(fwd_path, keep_last=None)`), and peak/current traced RAM (`tracemalloc`,
`gc.collect()` + `clear_traces()` isolation) for one-sweep vs the keep-last-10 baseline.

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p1_full_sweep_cost_probe.py [fwd_log_path]
```
Defaults to the largest forwarded log available on the dev machine as of 2026-08-18
(`/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/api_requests_opus_wise2627_1786984319_forwarded.jsonl`,
main-repo path — gitignored, absent from worktrees). Pass an explicit path to measure a
different log.

**Output:** writes `dev/pane_search/md/p1_full_sweep_cost_report.md`; prints a one-line summary
(entries/lazy_sum_ms/sweep_ms/ram_delta_kb) to stdout.

**Reads:** `_forwarded.jsonl` dual-log (positional arg or default path).
**Writes:** `dev/pane_search/md/p1_full_sweep_cost_report.md`; stdout summary line.
**Called by:** manual invocation only.
**Calls out:** stdlib only (`json`, `tracemalloc`, `gc`, `collections.deque`) — no `src/` imports.

---

### p2_search_feature_regression_test.py (463 LOC)

**Purpose:** Regression guard for the implemented M2 search feature. Unlike `p1_*` (fully
reimplemented, no `src/` imports), this file DOES exercise real `src/` code — via
`importlib.import_module('src...')` (the sanctioned workaround for the dev-import-block hook,
precedent: `dev/timer-loop/test_abort_stamp_scope.py`), not a literal `from src.` line. Covers:
bar renders at row 1 (empty + populated query text); line_map/copy_rows shift correctness
(header row never gets a body key, body starts at row 2); collapsed-hit marks the REQ header row
only; expanded-hit marks BOTH the header AND the matching inner content line (decision: header
stays marked when expanded); `n`/`N` jump ordering (wraps both directions, no-ops with zero
matches); Esc clears query+matches but the bar itself is never hidden (it's a permanent row, not
a toggle); scroll-jump reuses the existing `_proxy_just_expanded`/`item_positions` clamp and is
idempotent across repeated renders at the same offset; the `flow_id`-based
`_lazy_load_messages_forwarded` fix, verified against a SELF-CONTAINED synthetic 2-batch
forwarded-delta JSONL fixture (not the real gitignored log) reproducing the exact
`_fwd_req_idx`-collision scenario found during investigation — portable, no dependency on any
one dev machine's log files.

**(2026-08-18, follow-up) Highlight-scope tightening.** `test_collapsed_hit_marks_req_row` /
`test_expanded_hit_marks_line` were widened beyond "marker present somewhere in the line" (which
kept passing even through the whole-row-hoist bug, since the marker WAS still present, just
scoped wrong) to also assert: the marker sits AFTER the leading indent (not at column 0, which a
whole-row prefix would produce), for content lines the marker is immediately ADJACENT to the
matched substring (proves substring-only wrapping, not whole-line), and no unsubstituted
`format._BG_RESTORE_SENTINEL` leaks into the final rendered output (proves
`_apply_row_backgrounds` always resolves it). See `process-docs/pane_search/` for the full
before/after mechanism writeup.

**(2026-08-18, second follow-up — live bug, exact repro) `test_sentinel_resolves_to_default_bg_
not_empty_string_on_zebra_a_rows`.** The FIRST highlight-scope fix above was verified only
against non-empty `chosen_bg` (`DIM_YELLOW_BG`) — `ZEBRA_BG_A = ''` (every second zebra row) was
missed: substituting the sentinel with `''` deletes it outright, leaving the gold highlight BG
flooding to the row's `\033[K` erase-to-EOL. This test is the EXACT byte-for-byte repro handed
down from a live user report + self-reproduction (`_apply_row_backgrounds` called directly with
a `('msg',5,0)` key at `initial_parent_count=0`, landing on `ZEBRA_BG_A`) — confirmed to FAIL
against the pre-fix code and pass post-fix (verified both ways while writing it, not assumed).
Asserts a real `\033[49m` appears between the matched text and `\033[K`, plus a sanity check
that the non-empty-`chosen_bg` (`ZEBRA_BG_B`) case stays unaffected by the fix.

**(2026-08-18, follow-up) UTF-8 multi-byte keypress fix.** `input.click_handler.read_keypress`
read exactly 1 byte and decoded it alone — a multi-byte character (em-dash, ä/ö/ü, emoji)
arrived as N separate invalid single-byte decodes, each replaced with U+FFFD (`'�'`) — reported
live as an em-dash rendering as `���` in the search bar. `test_utf8_multibyte_keypress` feeds
the literal UTF-8 byte sequences for an em-dash (3 bytes), ä/ö/ü (2 bytes each), and an emoji
(4 bytes) through a REAL `os.pipe()` fd into the real `read_keypress()` (not a mock), asserting
each returns exactly the correct single decoded character, plus a back-to-back
multi-byte-then-ASCII case (no over-consumption of the next character's byte).
`test_utf8_search_query_accumulation` feeds the same byte sequences through the full
`_handle_proxy_search_input` path and asserts `_proxy_search_query` accumulates the real
characters. The fix lives in `src/input/click_handler.py` (shared by every pane, see
`src/input/DOCS.md`) — confirmed (ad-hoc, not in this suite) to heal `core/monitor_display.py`'s
main-pane search bar too, since both route through the same `read_keypress`.

**(2026-08-18, follow-up) Kill-line after a real search run.** `test_kill_line_after_a_real_search_run`
runs an actual Enter-triggered search (via `_handle_proxy_search_input('\r')`, the real code
path, not a mock of `_run_proxy_search`), then feeds `pane._KILL_LINE_CHAR` and asserts the query
empties while the matches from that run stay untouched — matches are edit-independent, Enter is
the sole recompute trigger (unchanged M2 convention, confirmed — see `pane.py`'s module entry).
The fuller selection-delete + kill-line mechanics live in `p3_drag_select_regression_test.py`
below (same feature, drag-select is that file's primary subject).

Synthetic entries (`_make_entry`) use a per-index unique marker embedded in that entry's own NEW
message (`messages` list built CUMULATIVE — length == `message_count`, one filler message per
earlier index plus this entry's own marked one) — `render_messages._render_new_messages` finds
"new" messages via `range(prev_msg_count, len(messages))`, so a non-cumulative per-entry-only
messages list silently renders an EMPTY new-message range and the marker never appears (a mistake
made and caught while writing this test — see `process-docs/pane_search/`). The marker is
deliberately NOT placed in `system_blocks` — that section is a NESTED collapsible
(`('sys', entry_idx)`) not shown by `_render_req_expanded` unless that sub-toggle is ALSO
expanded, so it's a poor choice for asserting "found in the always-visible expanded view".

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p2_search_feature_regression_test.py
```

**Output:** PASS/FAIL per check to stdout; writes `dev/pane_search/md/p2_search_feature_regression_test_<timestamp>.md`; exits 1 if any check fails.

**Reads:** nothing external — seeds `src.proxy_display.pane` module state with synthetic
entries directly; the flow_id-fix test writes a throwaway forwarded-delta JSONL fixture under
`tempfile.mkdtemp()`, removed after the check; the UTF-8 keypress tests open a real `os.pipe()`
per case, closed after the check.
**Writes:** `dev/pane_search/md/p2_search_feature_regression_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the M2 search feature; re-run after any change
to `pane.py`'s search state/handlers, `format.py`'s `format_proxy_block`/`_apply_row_backgrounds`,
`render_turn.py`'s search-marker embedding, `search.py`, `forwarded_parser.py`'s
`_lazy_load_messages_forwarded`/`reconstruct_all_messages`, or `input.click_handler.read_keypress`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.format`, `src.proxy_display.search`,
`src.proxy_display.forwarded_parser`, `src.input.click_handler`, `src.constants` — loaded via
`importlib.import_module`.

---

### p3_drag_select_regression_test.py (396 LOC)

**Purpose:** Regression guard for drag-to-select on the search bar (row 1) — a NEW milestone
(not folded into `p2`, mirroring `dev/click_ui`'s own per-milestone `p1`/`p2`/`p3`/`p4` file
split rather than growing one file indefinitely). Covers: `_search_col_to_query_index`
boundary-mapping correctness for both plain ASCII (single-width, always snaps to the boundary
BEFORE the clicked char — the only possible relative offset within a 1-cell span) and a
wide-char/emoji query (2-cell, snaps to the nearer half); the full press
(`button==0,row==1`) → motion (`button==32`, the SGR "left button held" flag) → release
(`(-1,-1,-1)` sentinel, now routed to `_handle_proxy_search_release` instead of the previous
hard no-op) drag flow, asserting `copy_to_clipboard` (monkeypatched, not a real `pbcopy` call)
receives EXACTLY the selected substring; a plain click (press+release, NO motion) makes ZERO
clipboard calls (must never clobber the real clipboard with an empty string) and preserves the
pre-existing focus-only behavior; a release with no prior row-1 press is a no-op; a drag that
starts on a BODY row never arms search-bar dragging (motion after it falls through unchanged to
the generic hover bucket); click-elsewhere / new-keyboard-input / Esc-cancel / session-change
all clear a live selection; rendering wraps the selected substring in SGR reverse-video
(`\033[7m...\033[27m`) and only when a selection is actually active.

**(2026-08-18, follow-up) Editor-style deletion.** `test_backspace_deletes_active_selection` —
Backspace with an active selection deletes the SELECTED substring from the query (not just the
last char) and clears the selection. `test_backspace_without_selection_still_trims_last_char` —
regression guard: Backspace with no selection still does the pre-existing single-char trim.
`test_kill_line_empties_query` / `test_kill_line_ignores_active_selection` —
`pane._KILL_LINE_CHAR` (`'\x15'`, Ctrl-U — a documented HYPOTHESIS for what Ghostty maps
Cmd+Backspace to on macOS, not a confirmed capture; named constant so a rebind after live
testing is a one-line change) empties the WHOLE query unconditionally, independent of any active
selection. `test_kill_line_not_silently_swallowed_by_isprintable_fallthrough` — direct regression
guard for the exact bug being fixed: asserts `'\x15'.isprintable()` is `False` (confirming the
character would otherwise silently fall through every branch to a no-op) AND that the query
actually gets cleared, not silently ignored. `test_editing_never_clears_matches` — plain
backspace, selection-delete, and kill-line all leave `_proxy_search_matches` untouched (Enter
remains the sole recompute trigger — confirmed against actual pre-existing behavior, not
assumed, before this change: neither did plain backspace/typing).
**Reads:** nothing external — seeds `src.proxy_display.pane` module state directly; drives the
real `_handle_proxy_mouse`/`_handle_proxy_search_release`/`_handle_proxy_search_input`/
`_render_proxy_search_bar` with direct `(button, col, row)` calls (not simulated raw SGR bytes —
`read_mouse_event`'s own parsing is unchanged and out of scope; button 32 for a held-left-button
drag is a documented SGR protocol fact taken as given, not re-derived here).
**Writes:** `dev/pane_search/md/p3_drag_select_regression_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the drag-select feature; re-run after any
change to `pane.py`'s `_search_col_to_query_index`, `_handle_proxy_mouse` (press/motion
branches), `_handle_proxy_search_release`, `_clear_proxy_search_selection`, or
`_render_proxy_search_bar`.
**Calls out:** `src.proxy_display.pane` — loaded via `importlib.import_module`.

---

### p5_worker_proxy_pane_parity_test.py (543 LOC)

**Purpose:** Regression guard for the WORKER-PROXY pane (`src/proxy_display/worker_proxy_pane.py`)
reaching search-bar parity with the proxy pane (rollout sub-milestone 3). Covers the same
mechanics suite as `p3`/`p4` (drag-select press→motion→release, plain-click zero-copy,
selection-delete Backspace vs plain Backspace, kill-line, editing-never-clears-matches, `n`/`N`
wrap, Esc clears state while the bar stays visible, reverse-video selection render) retargeted at
this pane's own thin wrappers, PLUS what's genuinely new here: the 2-ROW HEADER (search bar row
1, `_format_worker_proxy_header`'s pre-existing click-region table shifted to row 2+ —
`test_two_row_header_composition_and_shifts` asserts `_worker_proxy_header_regions` rows are all
`>= 2` and `worker_proxy_line_map` body rows sit past BOTH header rows;
`test_header_marker_click_still_selects_worker_at_shifted_row` confirms a click at the shifted
row still selects the worker exactly as before), Enter always re-running (no unchanged-query
gate ever existed on this pane, unlike the main pane's now-removed one — nothing to correct),
the one-sweep `reconstruct_all_messages` merge specifically wired for this pane
(`test_enter_triggers_reconstruction_merge_when_log_path_set` — a self-contained 2-line
forwarded-delta JSONL fixture, mirrors `p2`'s `_fwd_line` fixture pattern — confirms an entry's
`messages` populates from `None` and the reconstructed content becomes findable), and the
WORKER-SWITCH reset (`test_worker_switch_resets_search_state` — drives the real
`_refresh_worker_proxy_data` with `get_selection_file_path`/`list_workers`/`find_worker_proxy_log`
monkeypatched to a synthetic worker-B selection, confirms `_worker_proxy_search` resets exactly
like `pane.py`'s session-change reset).

**Scope note — a companion fix landed alongside this suite, in `dev/click_ui/`, not here:**
`dev/click_ui/p1_worker_selection_click_probe.py::test_worker_proxy_header_wrap_straddle` calls
`_format_worker_proxy_header` DIRECTLY (bypassing `_build_worker_proxy_output`'s region-shift
step) — before this milestone that was harmless (no search bar, row 1 = the header's own top);
after, a raw unshifted row-1 region collided with the new search-bar press branch. Fixed by
replicating the same `+_WP_SEARCH_BAR_LINES` shift inside that test, right after the direct call
— see `dev/click_ui/DOCS.md`'s entry for that file. Confirmed via a full regression sweep (this
milestone touches shared mouse-dispatch code, not just this suite's own new coverage) that this
was the ONLY other suite affected — `p2`/`p3`/`p4`/`p3_button_click_probe`/`p2_copy_click_probe`/
`A_render_refactor_proof` all re-ran clean untouched.

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p5_worker_proxy_pane_parity_test.py
```

**Output:** PASS/FAIL per check to stdout; writes `dev/pane_search/md/p5_worker_proxy_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.

**Reads:** nothing external — seeds `src.proxy_display.worker_proxy_pane` module state (entries, workers list) directly; the reconstruction-merge test writes a throwaway 2-line forwarded-delta JSONL fixture under `tempfile.mkdtemp()`, removed after the check; the worker-switch test writes a throwaway IPC selection file, also removed after.
**Writes:** `dev/pane_search/md/p5_worker_proxy_pane_parity_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the worker-proxy pane's search bar; re-run after any change to `worker_proxy_pane.py`'s search/mouse handlers, `_build_worker_proxy_output`'s header composition, `_format_worker_proxy_header`/`worker_proxy_helpers.py`, or `src/search_bar.py`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.search_bar` — loaded via `importlib.import_module`.

---

### p6_tokens_pane_parity_test.py (514 LOC)

**Purpose:** Regression guard for the TOKENS pane (`src/panes/token_pane.py`, `src/format/token_format.py`, `src/panes/token_search.py`) reaching search-bar parity with the proxy pane (rollout sub-milestone 4). Structurally simpler than the proxy family — single expand level, turns never collapse, data always fully loaded (no windowing/reconstruction). Covers the same mechanics suite as `p3`/`p4`/`p5` (drag-select, editor-style deletion, `n`/`N`, Esc, reverse-video render) retargeted at this pane's own thin wrappers, PLUS what's genuinely new here:
- **Two-key match semantics** — `test_call_level_match_collapsed_container_marked` / `_expanded_substring_marked`: a `(turn_idx, call_idx)` match gets its WHOLE call-header line container-marked unconditionally, even when the match text lives in unrendered (collapsed) detail content invisible in the assertion's own rendered output; when expanded, the header stays marked AND the specific matching detail line gets browser-find substring-highlighted. `test_turn_level_match`: a `('turn', turn_idx)` match container-marks the turn's own prompt line; asserts the key never leaks into `cache_line_map` (turn headers stay non-interactive for clicks).
- **The sentinel bug, same class as the proxy pane** — `test_sentinel_resolves_to_default_bg_not_empty_string`: confirms `constants.ZEBRA_BG_A == ''`, then confirms an explicit `\033[49m` (not a raw leaked `_BG_RESTORE_SENTINEL`) appears right after a highlighted detail line in a real `_build_tokens_output()` call.
- **A collateral regression fix** — `test_light_red_bg_still_detected_when_call_is_also_a_match`: `_build_tokens_output`'s `LIGHT_RED_BG` (cc_broken row) detection changed from `.startswith()` to `in` (a search-match marker now precedes it in the string when both conditions co-occur); asserts the row's OUTER `chosen_bg` prefix is still `LIGHT_RED_BG` despite the marker.
- **Jump-to-match** — `test_jump_to_match_moves_scroll_offset`: real Enter-triggered search pushes `cache_scroll_offset` to bring an early (off-screen-by-default) match into view, via `_tokens_nav` (populated by `format_cache_tracker`'s new `nav_out` param on a prior render — the test renders once first, mirroring the live pane loop's own render cadence).
- **Session-change reset** — `test_session_change_resets_search_state`: drives the real `_refresh_tokens_data` with `core.monitor.get_main_session_files`/`proxy_display.parser.find_response_log_path`/`read_response_log` monkeypatched to a synthetic session switch; confirms `_tokens_search` AND `_tokens_nav` both reset — mirrors `pane.py`'s session-change reset and the fix applied to the main pane (sub-milestone 2) and the worker-proxy pane (sub-milestone 3).

**Not re-verified here:** `format_cache_tracker`'s byte-identity against its 4 real callers (default kwargs) — proven via a ONE-SHOT frozen-turns old-vs-new comparison during implementation (not committed; the live `dev/display/A_format_cache_tracker_proof.py` harness reads directly from `~/.claude/projects/.../*.jsonl`, the top-10-most-recently-modified REAL session files, which were actively growing during this milestone's own session and produced a false-positive mismatch on a naive capture-then-verify-later run — see `process-docs/pane_search/` for the full root-cause writeup). 0/60 mismatches confirmed against turns frozen in memory and held constant across both code versions in the same process.

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p6_tokens_pane_parity_test.py
```

**Output:** PASS/FAIL per check to stdout; writes `dev/pane_search/md/p6_tokens_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.

**Reads:** nothing external — seeds `src.panes.token_pane._cache_turns` with synthetic turns directly; the session-change test monkeypatches `core.monitor.get_main_session_files` and `proxy_display.parser.find_response_log_path`/`read_response_log` to point at nonexistent throwaway paths (never opened for real — `jsonl.read_new_lines` gracefully returns `[]` for a nonexistent file).
**Writes:** `dev/pane_search/md/p6_tokens_pane_parity_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the tokens pane's search bar; re-run after any change to `token_pane.py`'s search/mouse handlers, `token_format.py`'s `format_cache_tracker`/`_compute_cache_viewport`, `token_search.py`, or `src/search_bar.py`.
**Calls out:** `src.panes.token_pane`, `src.panes.token_search`, `src.format.token_format`, `src.search_bar`, `src.constants`, `src.core.monitor`, `src.proxy_display.parser` — loaded via `importlib.import_module`.

---

### p7_workers_pane_parity_test.py (535 LOC)

**Purpose:** Regression guard for the WORKERS pane (`src/workers/worker_pane.py`,
`src/workers/worker_format.py`) reaching search-bar parity with the proxy pane (rollout
sub-milestone 5) — the FIRST pane needing a genuine reconstruction step, since `worker_turns`
only holds data for currently-EXPANDED workers. Covers the same mechanics suite as
`p3`/`p4`/`p5`/`p6` (drag-select, editor-style deletion, `n`/`N`, Esc, reverse-video render)
retargeted at this pane's own thin wrappers, PLUS what's genuinely new here:
- **2-row header + freeze badge shift** — `test_search_bar_row1_and_freeze_badge_shifted`:
  `_worker_header_regions['freeze']` moves from row 1 to row 2; the shifted region is STILL
  clickable (real `_handle_workers_mouse` dispatch through it).
- **Three-tier match keys + per-worker scoping, the actual new design** —
  `test_worker_level_match_and_scoping` (bare `name` match, container-marks ONLY that worker's
  header, a second non-matching worker stays unexpanded) and
  `test_call_level_match_collapsed_container_marked_and_scoped` (a `(name,turn_idx,call_idx)`
  match container-marks the collapsed call row in the MATCHING worker, while a SECOND worker
  that's independently expanded with different (non-matching) content carries ZERO search
  highlight anywhere in its own rendered output — the critical cross-worker leak check that
  proves `_scope_matches_to_worker`/`_scope_current_key_to_worker` actually work). Both use REAL
  throwaway JSONL fixture files (`_setup_worker_jsonls`, `find_worker_jsonl` monkeypatched to
  resolve them) — the real `read_new_lines`→`parse_jsonl_lines`→`extract_cache_turns` pipeline
  runs unmocked, only the tmux-session→path resolution is stubbed.
- **The sentinel bug (third occurrence)** — folded into the two match tests above (asserts no
  raw `_BG_RESTORE_SENTINEL` leaks, and the marker's own presence/absence exactly where
  expected) rather than a separate dedicated test, since the real fixture-based match tests
  already exercise the exact rendering path that needed the fix.
- **The `LIGHT_RED_BG` collateral fix** — `test_light_red_bg_still_detected_when_call_is_also_a_match`:
  same `.startswith()`→`in` regression guard as the tokens pane, against a real cc_broken call
  that's ALSO a search match.
- **Jump-to-match respecting the dormant scroll** — `test_jump_never_touches_dormant_pane_scroll`
  (real Enter-triggered jump, asserts `worker_scroll_offset` — the pane-level int — stays
  exactly 0) and `test_jump_self_heals_stale_worker_turns` (simulates `_refresh_workers_data`'s
  own poll-tick `worker_turns.clear()` + un-expanding the worker between two jumps, confirms the
  SECOND jump re-populates `worker_turns` fresh rather than finding it empty) and
  `test_vanished_worker_jump_is_a_noop_not_a_crash` (a match for a worker absent from the
  current `workers` list — the self-healing no-op path, not an exception).

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p7_workers_pane_parity_test.py
```

**Output:** PASS/FAIL per check to stdout; writes `dev/pane_search/md/p7_workers_pane_parity_test_<timestamp>.md`; exits 1 if any check fails.

**Reads:** nothing external — seeds `src.workers.worker_pane` module state (workers list via each test's own construction) directly; `_setup_worker_jsonls`/`_cleanup_worker_jsonls` write/remove real throwaway JSONL fixture files under `tempfile.mkdtemp()`, with `find_worker_jsonl` monkeypatched to resolve worker `session` strings to them (removed after each test that uses them).
**Writes:** `dev/pane_search/md/p7_workers_pane_parity_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the workers pane's search bar; re-run after any change to `worker_pane.py`'s search/mouse handlers or jump-to-match, `worker_format.py`'s `format_workers_block`/`_scope_matches_to_worker`/`_scope_current_key_to_worker`, `panes/token_search.py`, or `src/search_bar.py`.
**Calls out:** `src.workers.worker_pane`, `src.workers.worker_format`, `src.search_bar`, `src.constants` — loaded via `importlib.import_module`.

---

### p8_warnings_gpu_news_parity_test.py (584 LOC)

**Purpose:** Regression guard for the FINAL three panes (rollout sub-milestones 6-8, bundled)
reaching search-bar parity: WARNINGS (`src/panes/warnings_pane.py` + `warnings_render.py`), GPU
(`src/gpu_pane/pane.py`), NEWS (`src/news_pane/pane.py` only). Covers the same mechanics suite
as `p3`-`p7` (drag-select, editor-style deletion, Esc, reverse-video render) retargeted at each
pane's own thin wrappers, PLUS what's genuinely new here:
- **`test_warnings_dim_yellow_bg_already_used_in_not_startswith`** — the milestone's own explicit
  verification requirement, made into a permanent regression guard: introspects the real source
  (`inspect.getsource`) of the function that carries the zebra/hover row-bg loop and asserts it
  contains `'DIM_YELLOW_BG in line'` and does NOT contain `'.startswith(DIM_YELLOW_BG)'` — proves
  the "no collateral fix needed here" finding stays true even if the function is refactored later.
  **(2026-09, panes-split milestone) re-pointed from `_format_warnings_pane` to
  `_render_warnings_rows`** — `warnings_render.py`'s split moved the row-bg loop itself into a new
  helper of that name (`_format_warnings_pane` became a thin orchestrator); this was the ONE
  literal-source-introspection check across every probe in this milestone's behavior-proof set
  (grep-confirmed), which is why the zebra/viewport loop's extraction target had to be decided
  around it — see `src/panes/DOCS.md`'s `warnings_render.py` entry for the full rationale.
- **`test_warnings_collapsed_container_mark_and_expanded_substring_mark`** — uses a MULTI-WORD
  Bash command (`'echo unique_marker_x'`) specifically because `warnings_render.py`'s
  PRE-EXISTING `first_word_of_call` already shows a one-word inline preview even when
  collapsed — a single-word marker would have made the "hidden while collapsed" assertion
  false for reasons unrelated to search (caught by a first failing run, not assumed correct).
- **`test_warnings_sentinel_resolves_to_default_bg_not_empty_string`** — the `ZEBRA_BG_A==''`
  repro, same shape as every prior pane, confirming the sentinel fix WAS still needed here
  despite the already-correct `DIM_YELLOW_BG` detection (two independent findings, not one).
- **`test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally`** /
  **`test_news_render_pane_stays_unshifted`** — build with synthetic data, confirm
  `_render_pane`'s own `_button_regions` row is relative to its own top (row 1), replicate the
  EXACT external shift snippet `run_gpu_loop`/`run_news_loop` use, confirm the shifted region
  still dispatches correctly via `_dispatch_gpu_click` (mirrors
  `dev/click_ui/p4_gpu_news_button_probe.py`'s own established "replicate the inline dispatch"
  convention, extended here with a row-1 search-bar-press branch).
- **`test_gpu_highlight_only_match_no_sentinel_needed`** / **`test_news_highlight_only_match`** —
  real Enter-triggered search (`_gpu_search_on_commit`/`_news_search_on_commit`) against
  synthetic presets/status, confirms the matched line is highlighted with `SEARCH_CURRENT_BG`
  and the exact substring is wrapped browser-find style — news's query targets
  `TARGET_COLLECTION` (a stable constant) specifically to stay independent of `_is_running()`'s
  real filesystem/subprocess check, which the on_commit callback also calls (mirroring the real
  per-tick render's own behavior) but which this test doesn't need to control.
- **`test_gpu_n_N_cycles_current_idx_no_scroll_infra`** / **`test_warnings_n_N_cycles_without_touching_scroll`**
  — the "highlight-only, no jump" decision as a permanent guard: gpu has no `error_scroll_offset`
  equivalent at all; warnings DOES have real scroll state (`error_scroll_offset`), and this test
  specifically asserts n/N leaves it COMPLETELY untouched (only `current_idx` cycles) — proving
  the reduced scope was a deliberate choice, not an accident of gpu/news lacking the infra to
  begin with.

**Usage (from project root):**
```bash
./venv/bin/python dev/pane_search/p8_warnings_gpu_news_parity_test.py
```

**Output:** PASS/FAIL per check to stdout; writes `dev/pane_search/md/p8_warnings_gpu_news_parity_test_<timestamp>.md`; exits 1 if any check fails.

**Reads:** nothing external — seeds `src.panes.warnings_pane.tool_errors` / synthetic `presets`/`status` dicts directly for gpu/news (no real `rag-cli`/subprocess calls — `_render_pane`/`_gpu_search_on_commit`/`_news_search_on_commit` all take data as plain parameters).
**Writes:** `dev/pane_search/md/p8_warnings_gpu_news_parity_test_<timestamp>.md`.
**Called by:** run manually — regression guard for the warnings/gpu/news panes' search bars; re-run after any change to `warnings_pane.py`/`warnings_render.py`'s search handling, `gpu_pane/pane.py`'s or `news_pane/pane.py`'s `_render_pane`/inline dispatch, or `src/search_bar.py`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.gpu_pane.pane`, `src.news_pane.pane`, `src.search_bar`, `src.constants` — loaded via `importlib.import_module`.
```

## Salvage from dev/panes/DOCS.md

```
# dev/panes/

## Role

Byte-identity regression harnesses for `src/panes/` module splits. Add a script here when a
`src/panes/` refactor (module split, helper extraction) needs a before/after correctness proof
that isn't already covered by `dev/pane_search/`, `dev/click_ui/`, or `dev/pane_error_log/`'s own
behavior probes.

## Modules

### render_byte_identity.py (214 LOC, new 2026-09, panes-split milestone; format_cache_tracker case added 2026-09 tokens-data-render-helpers milestone)

**Purpose:** Byte-identity harness for the panes-split milestone (`token_pane.py` /
`warnings_pane.py` / `warnings_render.py` concern split — `build_cache_turns` moved to
`cache_turns.py`, `_format_warnings_pane` split into 3 helpers). Three checks, hashed together:
(1) `build_cache_turns` fed incrementally in growing file-line chunks (mirrors real polling of a
growing session JSONL) over a frozen 300-line prefix of a real session JSONL under
`~/.claude/projects/`, hashing the resulting turns after EVERY chunk — this is what actually
exercises the duplicate-call merge path the function's own LOC-split touches, not just its final
state; (2) `_format_warnings_pane` over a synthetic 4-error `tool_errors` list (mixed
expanded/collapsed, one carrying `_pre_strip_text`/`_stripped_chunks`, one with a search match) at
two pane widths, hashing `(rendered_string, line_map)`; (3) **(2026-09, tokens-data-render-helpers
milestone)** `format_cache_tracker` (`src.format.token_format`) over a synthetic 1-turn/2-call
list (`_make_rate_limit_turns`) with `response_rid_map` populated for call 0 — rate-limit headers
carrying both 5h/7d utilization+reset (fixed, non-"now"-relative epochs so the same-day/other-day
`_fmt_rl_reset_time` branch taken doesn't depend on which day the harness runs), a non-`'allowed'`
status, and a non-`'allowed'` overage — plus every usage-extras group (`cache_creation_ttl`,
`server_tool_use`, `service_tier`/`speed`/`inference_geo`, `iterations`); `expand_states` both
calls `True`; `copy_feedback` on call 0 with a far-future expiry; a `search_query` matching text
inside the turn AND the expanded call's text block. This is the ONLY harness in the repo covering
the `rl:`/warn lines and the expanded content-blocks loop — the workers-pane harness's own
synthetic fixtures never populate `response_rid_map`, so `format_cache_tracker`'s "already covered
by the workers-pane harness" note (pre-2026-09) was only true for its non-rate-limit paths.
**Reads:** One real session `*.jsonl` — newest under `~/.claude/projects/*/`  by default, or
`$PANES_BYTE_IDENTITY_JSONL` when set (check (1) only — checks (2)/(3) are fully synthetic).
**Writes:** Nothing outside its own tempfile (cleaned up on exit) — stdout only (one `HASH: <hex>` line).
**Run:** `./venv/bin/python dev/panes/render_byte_identity.py`
**Calls out:** `src.panes.cache_turns` (`build_cache_turns`), `src.panes.warnings_render`
(`_format_warnings_pane`), `src.format` (`format_cache_tracker`) — all imported via a function
(`_import_panes`), not a module-level `from src.` line, per `block_dev_imports_src`.

**`PANES_BYTE_IDENTITY_JSONL` env var** overrides the source path — needed to pin a before/after
comparison to the exact same bytes when the default (newest `*.jsonl` under `~/.claude/projects/`)
can itself be an actively-growing session log; same pitfall class as
`dev/proxy/pipeline_byte_identity.py`'s `PROXY_PIPELINE_BYTE_IDENTITY_LOG` (see its own DOCS
entry). Snapshot a real session file's frozen 300-line prefix to a fixed `/tmp` path once, then
point both runs at it via the env var.

**`nav_out` dict-key normalization:** `format_cache_tracker`'s `nav_out` mixes tuple keys
(`(turn_idx, call_idx)`, `('turn', turn_idx)`) and a string key (`'total_lines'`) — `json.dumps`
with `sort_keys=True` can't compare a tuple key against a string key, so check (3) stringifies
every key (`{str(k): v for k, v in nav_out.items()}`) before hashing; check (1)/(2) don't hit this
since their own dict keys are already homogeneous.

Status (check (1)+(2), pre-2026-09 tokens milestone): hash
`b1161b3b00fe58b5edcd4b8f3aef79ff59eb7f0c3333cf30c68a6c4addc02679` — identical before and after
the panes-split milestone (pinned 300-line session-JSONL prefix). Combined 3-check hash as of
introducing check (3) (synthetic `frozen_session.jsonl` fixture, not the panes-split milestone's
real-session prefix — the two are not directly comparable): `bfa03b2520b1f9c3026d3414e1741235bf2a47d2a0b7b7d944cac5a65d4723e4`
(before check (3) existed) → `4de22c232aa61fdbf16e43fb3ddbe3cc28dd64f73e470b31b13562344c4df050`
(after adding check (3), unmodified `token_format.py`/`jsonl_cache_turns.py` — this is the
baseline the tokens-data-render-helpers milestone's own refactor must reproduce).
```

## Salvage from dev/pipeline/DOCS.md

```
# Pipeline Evaluation Suite

Dev scripts measuring Monitor_CC pipeline characteristics. Each suite measures one aspect and writes MD reports.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

## Suites

### memory_profile/
**Measures:** tool_use_cache and buffered_subagent_calls growth.
**Usage:** `python3 dev/pipeline/memory_profile/01_cache_growth.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md, process-docs/pipeline/pipe03_core_loop.md

### io_profile/
**Measures:** Filesystem calls per poll cycle (stat, iterdir, glob).
**Usage:** `python3 dev/pipeline/io_profile/01_poll_cycle_cost.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md

### parsing_profile/
**Measures:** Time per extract function, multi-pass overhead.
**Usage:** `python3 dev/pipeline/parsing_profile/01_multipass_cost.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md

### format_stability/
**Measures:** Message type coverage across all JSONL files.
**Usage:** `python3 dev/pipeline/format_stability/01_unknown_types.py`
**Decision:** process-docs/pipeline/pipe02_data_sources.md
```

## Salvage from dev/proxy/DOCS.md

```
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

### addon_hook_byte_identity.py (202 LOC, new 2026-09, proxy addon-split milestone)

**Purpose:** Byte-identity regression harness for the `ProxyAddon` HOOK METHODS themselves
(`request`, `responseheaders`, `response`) — `pipeline_byte_identity.py` above only exercises the
pure-function pipeline `request()` calls into; nothing else in `dev/` drives the hook methods on a
real `ProxyAddon()` instance end-to-end the way this does. Constructs a real `ProxyAddon` with
`MONITOR_CC_ROOT` pointed at a fresh temp dir, drives all three hooks with a minimal fake mitmproxy
flow (`_FakeHeaders`/`_FakeRequest`/`_FakeResponse`/`_FakeFlow` — request-side shape reused from
`dev/native-model-start/p3_cache_breakpoints_probe.py` / `dev/bg_wakeup_id_line/p2_bg_escape_probe.py`,
extended with a response side) over a bounded prefix (60 lines) of a real `*_original.jsonl`: every
payload gets a 2xx `request()`+`responseheaders()`+`response()` sequence, plus one dedicated 4xx
flow to exercise `_log_4xx_error`. `x-request-id` is pinned per request in the fake headers so
`uuid.uuid4()` is never invoked (no monkeypatch needed for that); `timestamp`/`ts` JSONL fields are
normalized to a fixed sentinel post-write, and the tempdir's own random path is stripped out of the
captured stderr before hashing (the `tool_injection` "schema store missing" warning embeds it
verbatim — the #1 source of accidental non-determinism found while building this harness). Hashes
the concatenated contents of all six dual-log files plus the normalized stderr.
**Reads:** One `*_original.jsonl` file — newest under `/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/`
by default, or `$ADDON_HOOK_BYTE_IDENTITY_LOG` when set.
**Writes:** Nothing outside its own tempdir (cleaned up on exit) — stdout only (`source`, `payloads`, one `HASH: <hex>` line).
**Run:** `./venv/bin/python dev/proxy/addon_hook_byte_identity.py`
**Calls out:** `src.proxy.addon` (`ProxyAddon`) — imported at module scope specifically because
`src/proxy/payload_helpers.py` resolves its own `sys.path` insert from `MONITOR_CC_ROOT` at import
time, so importing AFTER repointing `MONITOR_CC_ROOT` at the tempdir would break the `constants`
import; see the module's own comment on `_import_proxy_addon`.

**`ADDON_HOOK_BYTE_IDENTITY_LOG` env var** — same override convention and same pitfall class as
`pipeline_byte_identity.py`'s `PROXY_PIPELINE_BYTE_IDENTITY_LOG` (see its own entry above).

Status: hash `dd771ac18157443ff2a69ec067126bdc861dcd5fee3dff67a75a419d2345796a` — identical before
and after the addon-split milestone (17 real payloads + 1 synthetic 4xx flow, pinned snapshot).

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
```

## Salvage from dev/proxy_display/DOCS.md

```
# dev/proxy_display/

## Role

Development scripts for `src/proxy_display/` render-cluster changes — regression harnesses that
verify a refactor of `format.py`/`render_turn.py`/`render_sections*.py`/`render_messages.py`/
`forwarded_parser.py` changes zero observable output. Touch this directory when adding a new
render-cluster regression check; do not touch for `pane.py`/`worker_proxy_pane.py` event-loop
changes (see `dev/pane_search/`, `dev/click_ui/`, `dev/pane_error_log/` for those).

## Modules

### render_byte_identity.py

**Purpose:** Byte-identity regression harness for the proxy_display render cluster. Reconstructs
entries from a real forwarded dual-log (default: newest `*_forwarded.jsonl` under
`src/logs/dual_log/` in the MAIN checkout — reads only, never writes/commits log content),
attaches the stripped/injected/original overlays the same way `pane.py` does, then grows
`expand_states` by repeatedly rendering and flipping every newly-discovered key to expanded
(via `item_positions_out`, which — unlike `line_map` — captures every rendered key regardless of
viewport) until the key set stops growing. Hashes `format_proxy_block`'s full output at several
pane widths, plus `render_system_blocks`/`render_tools`/`render_messages` called directly per
entry per width (wider coverage than `format_proxy_block`'s own viewport can show even with a
huge `pane_height`, since those three are exercised identically regardless of scroll state).
Prints one `HASH: <hex>` line — run before and after a render-cluster change, the hash must match.

**`RENDER_BYTE_IDENTITY_LOG_DIR` env var** overrides the source directory (default: the live MAIN
checkout's `src/logs/dual_log/`). Needed because the default directory can itself grow between a
"before" and "after" run — e.g. this very worktree's own proxy session keeps appending to its
newest forwarded log while work is in progress. For a reproducible before/after comparison, copy
the newest `*_forwarded.jsonl` + its `_stripped`/`_injected`/`_original` siblings to a fixed `/tmp`
directory once, then point both runs at that directory via the env var. Never commit such a copy —
only the script and its hash output belong in this repo.

**Reads:** `*_forwarded.jsonl`/`*_stripped.jsonl`/`*_injected.jsonl`/`*_original.jsonl` under the
resolved log directory.
**Writes:** Nothing — stdout only (`source`, `entries`, `expand_states keys`, `HASH` lines).
**Called by:** Run manually from project root; imports are all local (inside functions), per the
`block_dev_imports_src` hook's indentation-based exemption.
**Calls out:** `src.proxy_display.forwarded_parser` (`_parse_forwarded_log`, `_infer_model_family`),
`src.proxy_display.dual_log_accumulator` (`accumulate_dual_log`, `accumulate_original_tools`),
`src.proxy_display.proxy_pane_shared` (`_attach_overlay_references`), `src.proxy_display.format`
(`format_proxy_block`, `_is_standalone_entry`), `src.proxy_display.render_turn`
(`_resolve_prev_same_family`), `src.proxy_display.render_sections` (`render_tools`),
`src.proxy_display.render_sections_system` (`render_system_blocks` — update the import path if
either function moves module again), `src.proxy_display.render_messages` (`render_messages`)

## Gotchas

**The default log source is live and growing.** Any script under this directory that reads
`src/logs/dual_log/` directly (rather than a frozen copy) can observe different data between two
runs in the same session, if that session's own worker/opus proxy log happens to be the newest
file. Use `RENDER_BYTE_IDENTITY_LOG_DIR` (or the equivalent pattern in a new script) to pin the
source when doing a before/after comparison.
```

## Salvage from dev/proxy_dual_log/DOCS.md

```
# dev/proxy_dual_log/

## Purpose

Verification suite for the `src/logs/dual_log/` log quartet written by `src/proxy/addon.py`.
Proves losslessness and self-consistency of the forwarded-delta log against the original log,
and completeness of the strip/inject diff engine (`src/proxy/diff_engine.py`).

## Modules

### verify_delta.py (272 LOC)

**Purpose:** Reads a `_original.jsonl` + `_forwarded.jsonl` pair, reconstructs the full forwarded
payload from the delta stream (per-model-family chain), and verifies two invariants:

- **Check 1 (hard):** Reconstructed element counts == counts declared in the delta entry. Pure
  delta self-consistency — must always hold. Violation = delta-builder bug → exit 1 + FAIL.
- **Check 2 (soft diagnostic):** `forwarded counts.messages` vs message count in the original.
  Mismatches are reported with context (request, delta indices, diff) but do NOT fail the script —
  the proxy legitimately changes message count (msg0-strip).

Output: per-request table (line, request_id, family, is_first, sys/tools/msgs counts, delta KB,
status, delta indices) + PASS/FAIL summary line.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/verify_delta.py \
    src/logs/dual_log/api_requests_<id>_original.jsonl \
    src/logs/dual_log/api_requests_<id>_forwarded.jsonl
```

**CLI flags:**

| Flag | Description |
|---|---|
| `original` (positional) | Path to `_original.jsonl` |
| `forwarded` (positional) | Path to `_forwarded.jsonl` |
| `--original` | Named alternative for original path |
| `--forwarded` | Named alternative for forwarded path |

**Exit codes:** 0 = all hard checks passed (soft mismatches possible); 1 = at least one hard-fail.

---

### tt_delta_skip_replay.py (282 LOC)

**Purpose:** Before/after proof for the read-side badge suppression of the per-request
`<total_tokens>N tokens left</total_tokens>` nuke, INCLUDING its claude-f trailing-nudge variant
(2026-09-05 — see `src/proxy_display/DOCS.md`'s `parser.py` entry for the full design). Replays a
recorded `_original.jsonl` through the REAL production pass pipeline
(`rules.apply_modification_rules`, the actual source of `all_ops`), feeds `(orig_payload,
fwd_payload, all_ops)` into the REAL `_build_stripped_injected_deltas` — the same call `addon.py`
makes — and runs the resulting dual-log lines through the REAL `parser.accumulate_dual_log`.
Unlike `verify_strip_inject.py` it therefore exercises the message delta path end to end, because
it supplies `all_ops`.

Reports two things separately: the WRITE side (entries carrying `messages_delta`, which must be
unchanged — the spans keep rendering) and the RENDERED BADGE, resolved through the real
`parser.badge_flags` (so the flow coordination between the stripped and injected side is exercised,
not just the per-line filter), under the old one-to-one rule vs the new one. The old rule is
reproduced in-process by monkeypatching `parser._msgs_delta_is_substantial` to
`bool(messages_delta)`, so both readings differ in nothing else. Classifies each request as `pure_total_tokens` / `mixed` / `real_strip` / `no_msg_delta` by
inspecting the original payload's messages via `_is_tt_msg`, which delegates to the REAL
`parser._is_total_tokens_nuke_text` (lazy-imported via `_shape_classifier()`) rather than keeping
its own copy of the shape test — updated 2026-09-05 alongside the production widening so this
script's own classification never drifts out of agreement with what it is verifying; before that
change this script's narrower bare-tag-only `_is_tt_msg` misclassified nudge-shaped messages as
`real_strip`/`mixed` and the `--compare` check FAILED on the claude-f sessions for that reason
alone (the widened production code was correct, the harness's classifier was stale).

**Verified:** PASS on `api_requests_opus_monitor_cc_1788011077`, one run of 88 requests on
2026-08-29 (that log was live during the work, so a later run shows larger absolute counts — the
script asserts per-class invariants, not fixed totals, and keeps passing as the log grows): write
side unchanged at 77 stripped / 76 injected entries with `messages_delta`; rendered badge 78 → 25
for `strip` and 78 → 25 for `inject`; 53/53 pure-total_tokens requests show NEITHER word while 53/53
still carry their stripped spans; 14/14 real-strip requests show `strip` and 13/13 of those with a
green message span show `inject`; 10/10 mixed requests show both words. **Re-verified 2026-09-05**
against all three current claude-f/opus corpus stems (`api_requests_opus_{wise2627_1788612045,
websearch_1788611995, monitor_cc_1788611156}`) after the trailing-nudge widening — PASS on all
three; the widened `pure_total_tokens` bucket on `monitor_cc` (which now correctly absorbs the
nudge-prefixed shapes) rose from 16 requests (old bare-only classification) to 119, and `strip`
dropped from 157 → 38 shown while every real-strip request kept showing both words.

**Check semantics note:** the inject check is an implication, not an equality — a green message span
MUST light `inject`, but the converse does not hold, because a system-section injection (proxy rules
into `system[2]`) legitimately lights `inject` with an empty injected `messages_delta`.

Recorded dual-logs are read from the MAIN checkout (`MAIN_REPO_ROOT`), since they are untracked
data not duplicated into worktrees; the code under test is imported from the worktree root.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py api_requests_opus_monitor_cc_1788011077 --compare
```

**CLI flags:**

| Flag | Description |
|---|---|
| `stem` (positional) | Log stem without the `_original.jsonl` suffix |
| `--compare` | Report the badge signal under the old rule vs the new one, with PASS/FAIL |

**Exit codes:** 0 = every class behaves as specified; 1 = at least one class regressed.

---

### diff_strip_inject.py (239 LOC)

**Purpose:** Span-level strip/inject diff of Original vs Forwarded proxy logs. Shows what the
proxy stripped (delete spans = yellow) and injected (insert spans = green) per request. Reads
a `_original.jsonl` + `_forwarded.jsonl` pair, reconstructs the full forwarded payload from
the delta chain (per-model-family), aligns blocks (system by index, tools by name, messages
by index + within-message by block position), and classifies spans as equal / stripped /
injected using difflib. One diff delivers both colors: delete spans = stripped, insert spans = injected.

Engine imported from `src/proxy/diff_engine.py` (via `sys.path.insert` — same engine used by
the runtime `_build_stripped_injected_deltas` in `logging.py`).

**Diff strategy:** Word-level when `SequenceMatcher.ratio() >= 0.1` (partial edits, e.g. a
cache_control suffix appended to a 55k base64 block — ratio ≈ 1.0, only the last few words
change). Whole-block 2-span replacement when `ratio < 0.1` (full replacements, e.g. sys[2]:
CC system prompt → proxy rules, ratio ≈ 0.004 — word-level would produce thousands of trivial
word-spans with zero information gain).

**Output:** Per-request sections with system / tools / messages blocks, per-block IDENTICAL /
REPLACED / STRIPPED / INJECTED tags, char counts, previews (120 chars), and a SPANS summary
line per request.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \
    src/logs/dual_log/api_requests_<id>_original.jsonl \
    src/logs/dual_log/api_requests_<id>_forwarded.jsonl
```

**CLI flags:**

| Flag | Description |
|---|---|
| `original` (positional) | Path to `_original.jsonl` |
| `forwarded` (positional) | Path to `_forwarded.jsonl` |
| `--original` | Named alternative for original path |
| `--forwarded` | Named alternative for forwarded path |

---

### span_inline_probe.py (625 LOC)

**Purpose:** Form A vs Form B inline-render data model probe. Validates that Form B (full
ordered span list per log) is the minimal enrichment that lets the read-side render
strip/inject inline without content duplication. Shows Form A's empirical failure via concrete
offset/substring mismatches on real data. Probes 3 blocks: sys[2] full-replace, sys[3]
strip-to-dot, and a word-level message block with cache_control diff.

Key finding: trailing equal span `'"is_error": false}'` from normalized diff NOT found in
`fwd_raw_text` (exact_in_raw=-1) — Form A's offset/text unusable as raw-text anchor.
Form B stores equal+stripped in `_stripped`, equal+injected in `_injected`; 3-color render
= read-side lock-step zip by equal anchors (trivial for all patterns in session 1780517466).

Imports `diff_engine._diff_text` via `importlib` (standalone load, no src/ package import).
Inlines `_strip_cache_control` (5-line mirror of `logging.py:_strip_cache_control`).

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/span_inline_probe.py
```

**Output:** `dev/proxy_dual_log/md/span_inline_probe_<YYYYMMDD>.md`

---

### main_log_elimination_probe.py (625 LOC)

**Purpose:** Feasibility probe for eliminating the main log (`api_requests_<id>.jsonl`).
Answers two questions on a real session using the `_forwarded` + `_original` quartet logs:

- **Question A (Forwarded reconstruction):** Accumulates `_forwarded` delta log per-model-family
  into full `{system, tools, messages}` payloads, diffs against main log `raw_payload` after
  stripping `cache_control`. Reports content losslessness, BP-count divergence table, and classifies
  every top-level payload field as: delta-covered / MUST-ADD / metadata-pane-only-irrelevant.
- **Question B (Error extraction):** Extracts `is_error=True` tool_result blocks from `_original`
  payloads, deduplicates by `tool_use_id`, compares against `tool_errors.jsonl` for the session.

Matching strategy: positional (request_ids are empty in quartet; both logs written serially).
Inlines `_strip_cache_control` + `_normalize_msg_shape_for_hash` verbatim from `src/proxy/logging.py`.

**Findings (session `opus_monitor_cc_1780602018`, 47 requests):**
- A: LOSSLESS — system/tools/messages reconstruct exactly after cache_control normalization
- A: BP-count diverges structurally (pre-ops 3 markers → post-ops grows +1/request)
- A: MUST-ADD `max_tokens` + `output_config` to `_build_forwarded_delta` for proxy-pane header fields
- B: EXACT MATCH — 1 unique error (by tool_use_id) matches tool_errors.jsonl entry

**Usage (from project root):**
```bash
MONITOR_CC_ROOT=/path/to/monitor-cc \
./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe.py <session_suffix>
```

Default session: `opus_monitor_cc_1780602018`

**Output:** `dev/proxy_dual_log/md/main_log_elimination_<YYYYMMDD>.md`

---

### green_overlay_probe.py (538 LOC)

**Purpose:** Reproduces the green-overlay false-injection bug in `_diff_text` (word-level path)
on real log data and validates the char-level candidate fix. The bug: when a JSON-serialized
tool_result block is diffed, the escaped `\n` sequences are NOT real whitespace, so tokens
containing both code content and `<system-reminder>…` are treated as single words by `.split()`.
SequenceMatcher tags them as 'replace' → common prefix `set()))\n\n` mis-tagged as stripped
(yellow) AND injected (green). Only `<system-reminder>…` was actually stripped.

Implements both variants inline (self-contained, no `src/` imports at module level):
- `diff_text_word` — exact copy of production `_diff_text` (word-level path)
- `diff_text_char` — candidate fix: char-level SequenceMatcher, keeps early-exit branches

Also runs 4 regression cases (R1–R3 real logs ratio >= 0.1; R4 synthetic whitespace-collapse
test) to confirm no span explosion and correct whitespace fidelity.

**Key findings (2026-06-05, session `badge-recap_1780678180`):**
- Bug case: word=4 spans (common prefix `set()))\n\n` wrongly split), char=6 spans (280-char
  common prefix correctly equal ✅, `<system-reminder>` stripped ✅, fidelity ✅)
- R1 (ratio=0.76): word=4, char=6 — no explosion
- R2 (ratio=0.99): word=3, char=3 — identical span count
- R3 (ratio=0.95): word=4, char=3 — char fewer spans ✅
- R4 synthetic whitespace: word collapses `  ` / `\t` / `   ` to single space; char preserves exactly ✅
- All 4 regression fidelity checks: orig_ok=True fwd_ok=True ✅

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/green_overlay_probe.py
```

**Output:** `dev/proxy_dual_log/md/green_overlay_probe.md`

---

### groundtruth_message_spans_probe.py (669 LOC)

**Purpose:** Validates `build_message_spans(orig_text, fwd_text, stripped_chunks)` — the
ground-truth span construction algorithm that replaces the blind `_diff_text` for messages.
Instead of diffing, builds spans from the exact stripped chunks recorded by
`apply_modification_rules` (`stripped_msg_removed`): split `orig_text` at chunk positions →
EQUAL + STRIPPED segments; walk `fwd_text` matching EQUALs; gaps in `fwd_text` = INJECTED
(the real replacement placeholder, if any). Proves: zero phantom green on pure-strip cases,
lossless fidelity (equal+stripped rebuilds orig, equal+injected rebuilds fwd), and correct
small injected spans for replace cases (`.` placeholder, wake-up text).

Data source: re-runs `apply_modification_rules` on `_original` dual-log payloads to regenerate
`stripped_msg_removed`; validates mod payload == fwd delta per case. Operates at inner-content
level (`block["text"]` / `block["content"]`) rather than `json.dumps(block)` — JSON structural
chars (`"is_error": false}`) are never coloured.

**Key findings (2026-06-05):**
- BUG case msg[18] blk[0] tool_result SR strip: GT 0 phantom ✅; diff_text_word at production
  JSON level: injected phantom `set()))\\n\\n",` ❌
- TEXT_REPLACE DEF-SR → `.`: GT injected=`.` correct small ✅; fidelity ✅
- BG_REPLACE TN→wakeup: GT injected=`background done…` correct small ✅; fidelity ✅
- LARGE_SR 5777-char: precision gap — trailing `\n` not in stripped_chunks; `fwd_ok=False`
- Recording gaps: ENV-context SR and trailing `\n` not captured in `stripped_msg_removed`

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/groundtruth_message_spans_probe.py
```

**Output:** `dev/proxy_dual_log/md/groundtruth_spans_<YYYYMMDD_HHMMSS>.md`

---

### composition_probe.py (547 LOC)

**Purpose:** Proves multi-pass span composition over C0. Models each proxy pass as an
`Op(offset_in_Ck, removed, injected)` derived from the pass's `(before, after)` block-text
pair via common-prefix/suffix. Composes all passes into a single span list over C0 by walking
the accumulated `(equal/stripped/injected)` span list and applying each op — "equal" bytes in
the removal range become "stripped"; prior "injected" bytes re-removed disappear. Models
`_dedup_wakeup_blocks` as a final composed op (Layer-1 payload modification, not a span-build hack).

**Stage 1A wiring:** `_REAL_OPS_PASSES = frozenset({"po_preview", "hook_prefix", "git_lock", "bd_noise"})` — for these 4 passes the probe reads `result[5]` (directly-recorded ops from `src/proxy/rules.py`) instead of the `(before, after)` stand-in. Remaining passes still use the stand-in; both paths verified byte-exact.

**Proved (9509/9509 blocks, 567 entries, 5 stems — 2026-06-09 with Stage 1A ops):**
- Both reconstruction invariants byte-exact: `equal+stripped == C0`, `equal+injected == Cfwd`
- 1134 multi-pass blocks (same block, ≥2 passes) — all pass
- 772 double-inject blocks — dedup op correctly reduces each to 1 injected wakeup
- Money shot (msg[100] TN+BG double-inject): span list = 1 stripped (full TN block) +
  1 injected wakeup; Cfwd (48 chars) reconstructed byte-exact from C0 (406 chars)

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/composition_probe.py
```

**Output:** `dev/proxy_dual_log/md/composition_probe_<YYYYMMDD>.md`

---

### attribution_coverage.py (479 LOC)

**Purpose:** Read-only function-attribution coverage analysis for `_stripped`/`_injected` dual-logs.
Answers: can every strip AND inject entry be attributed to a responsible proxy function?
Processes all available `*_stripped.jsonl`/`*_injected.jsonl` pairs in `src/logs/dual_log/`
and produces a coverage report with per-category attribution tables, RAW/ADJUSTED coverage
percentages, full residual listing, and false-positive evidence.

Key findings from first run (19 pairs, 2026-06-04):
- Strip ADJUSTED 100% / Inject ADJUSTED 100% — zero truly unattributed entries
- 6 residual gap categories in strip_vocab (ENV/HP/UI_PARTIAL/DATE_SR/SN/FM) — all attributable,
  need vocab additions before `fn` field can be materialised
- **json_reserialization bug**: 409 false positive entries from `_set_cache_breakpoints`
  format-normalisation not being mirrored in `_build_stripped_injected_deltas` diff setup;
  renders as false yellow/green in the monitor

Loads `strip_vocab` via `importlib.util.spec_from_file_location` (block_dev_imports_src safe).
Auto-detects main repo vs worktree path for dual_log directory.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/attribution_coverage.py
```

**Output:** `dev/proxy_dual_log/md/attribution_coverage_<YYYYMMDD>.md`
```

## Salvage from dev/proxy_instrumentation/DOCS.md

```
# dev/proxy_instrumentation/

## Role

Reconstructs/measures the proxy's real strip/inject pipeline output straight from recorded
dual-log payloads or `src/logs/dual_log/*_original.jsonl`, through the REAL production code
(`src/proxy/message_passes.py`, `rule_ops.py`, `diff_engine.py`, `proxy_display/render_messages.py`)
— no live proxy required. Touch when validating a pane-render or span-computation change against
real recorded data; not for live-session debugging (see `dev/proxy_dual_log/` for the dual-log
invariant/verification suite instead).

## Modules

### render_recorded_request.py (129 LOC)

**Purpose:** Reconstructs the pane render for one specific recorded request (by `request_id`)
straight from the on-disk dual-log, verifying a span-render fix for block-less messages.
`_render` takes `entry_idx` as of 2026-08-28 (thinking-expander milestone bumped
`render_messages`'s signature to `(entry_idx, entry, ...)`) — passes `target_line`/`control_line`,
mechanical update only, no behavior change to this script's own checks.
**Reads:** `src/logs/dual_log/api_requests_opus_posts_1785266871_{forwarded,stripped,injected}.jsonl`
(hardcoded stem/request_id — one-off verification, not parameterized).
**Calls out:** `src.proxy_display.{forwarded_parser,parser,render_messages}`.

### p4_blocklist_223_probe.py (140 LOC)

**Purpose:** Verifies the CC 2.1.223 `TOOL_BLOCKLIST` extension (Artifact, ReportFindings,
DeferredToolPlaceholder) end-to-end — runs the real `proxy.tools._strip_unused_tools` on the
session's actual original-log payload, asserts the post-strip set is exactly
`{Bash, Edit, Read, Write, Skill}` + any MCP-injected names present in the forwarded log; sanity
check for a live `tool_use` invocation of any newly-blocked name (would 400 the API if stripped);
confirms `Agent` (pre-existing blocklist entry) is absent from the forwarded tools list — the
drill-down's "Agent" sighting is the intentional whole-stripped yellow row
(`render_sections.py`), not a strip-path bug.
**Reads:** `src/logs/dual_log/api_requests_opus_websearch_1786052022_{original,forwarded}.jsonl`.
**Writes:** `md/blocklist_223_probe_report.md`.
**Calls out:** `proxy.tools` (`_strip_unused_tools`), `constants` (`TOOL_BLOCKLIST`),
`src.proxy_display.forwarded_parser` (`_parse_forwarded_log`).

### p5_mid_turn_user_msg_preserve_probe.py (132 LOC)

**Purpose:** Verifies the CC 2.1.223 mid-turn-user-message preserve-guard in
`src/proxy/message_passes.py::_apply_role_system_strip` (issue #61) — drives the REAL function on
the REAL recorded message list, not a synthetic fixture. Preserve case: session
`api_requests_opus_posts_1786051932`, flow `4b4d396b...`, msg 274 — the live incident itself (a
role='system' mid-turn user message body "jetzt") must survive byte-for-byte. Regression: session
`api_requests_opus_websearch_1786052022`, three unrelated role='system' noise messages
(deferred-tools, task-tools-nag, date-changed) must still strip to `"."` exactly as before.
**Reads:** `src/logs/dual_log/api_requests_opus_{posts_1786051932,websearch_1786052022}_original.jsonl`.
**Writes:** `md/mid_turn_user_msg_preserve_probe_report.md`.
**Calls out:** `src.proxy.message_passes` (`_apply_role_system_strip`).

### p6_no_flow_extra_prepend_probe.py (294 LOC)

**Purpose:** Verifies that an expanded request body is the request's payload delta and nothing
else, after the out-of-window prepend was removed entirely (2026-08-30). Replaces
`p6_flow_extra_suppress_probe.py`, which verified the earlier PARTIAL suppression of the same
mechanism by rendering each entry twice (once with the suppression disabled) — impossible now that
the mechanism is gone, so these invariants are self-contained instead: no entry's body carries a
`[N]` header below its own delta-window start (the window start is recomputed here from
`prev_msg_count`/`diff_start` rather than imported, so the probe cannot agree with the renderer by
construction); `_render_flow_extra_messages`/`_own_msgs` are absent from `render_messages`, the
parser no longer mentions `_msg_idx_sub_by_flow_id` and no entry carries a sub-lookup attachment
(reintroduction guard — a partial revert would otherwise pass the first check silently); every
entry whose out-of-window touch is SUBSTANTIAL still badges, substantiality read off the raw
dual-log lines via `parser._msg_delta_entry_is_substantial` because a total_tokens-only touch
deliberately badges nothing; and at least one entry still renders an in-window olive/green span, so
a regression that killed span rendering outright cannot pass as "no prepend". Reports, without
asserting, how many entries have an out-of-window touched index whose stripped original is
therefore invisible in the pane — the accepted cost, recoverable only from the `_stripped` stream. **Fifth check (2026-08-30):** the write-side lag correction is sound and effective — every coordinate re-attributed to the flow that stripped it carries the total_tokens marker (never a mid-conversation overwrite, which would be neighbour bleed), and every such coordinate inside its flow's delta window really renders olive+green. Guards the bare-`.` defect.
**Reads:** `src/logs/dual_log/api_requests_{opus_monitor_cc_1788091735,opus_gh_cli_1787995963}_{forwarded,stripped,injected}.jsonl` (override via argv).
**Writes:** `md/no_flow_extra_prepend_report.md`.
**Calls out:** `src.proxy_display.{forwarded_parser,parser,render_messages,render_turn}`.

### p7_blocklist_258_probe.py (145 LOC)

**Purpose:** Verifies the CC 2.1.258 `TOOL_BLOCKLIST` extension (SendFeedback, ListAgents)
end-to-end against the CURRENT full `src/logs/dual_log/*_original.jsonl` corpus, not one hardcoded
session — glob-driven, since the corpus rotates. Runs the real `proxy.tools._strip_unused_tools`
on the newest main-session log's original payload, asserts the post-strip set is exactly
`{Bash, Edit, Read, Write, Skill}` + any MCP-injected names; corpus-wide sanity check for a live
`tool_use` invocation of either newly-blocked name in ANY `_original.jsonl` file's messages (would
400 the API if stripped) — reports files-scanned count and hit count; confirms both names are in
`TOOL_BLOCKLIST`.
**Reads:** all `src/logs/dual_log/*_original.jsonl` files present at run time.
**Writes:** `md/blocklist_258_probe_report.md`.
**Calls out:** `proxy.tools` (`_strip_unused_tools`), `constants` (`TOOL_BLOCKLIST`).

### p1_measure_full_replacement_blast_radius.py (536 LOC)

**Purpose:** Measurement script (dev/ M1 "bg-ack-shapes" milestone, 2026-07-29) — drives real
recorded payloads through the real `message_passes.py` pass functions in `rules.py`'s actual
order, classifies each `_ops_from_content_change` call site as FULL (whole-block-independent
replacement) vs PARTIAL (excise-and-keep-remainder) vs STRUCTURAL (index-shift artifact) by
reading the underlying strip function — NOT by any ratio threshold — and quantifies how many
FULL-class ops are today recorded as a trimmed/split span due to `_extract_block_op`'s
prefix/suffix-trim. Report: `md/full_replacement_blast_radius_20260729.md`.
**Reads:** `src/logs/dual_log/api_requests_{opus_monitor_cc_1785336796,opus_posts_1785338463,
opus_wise2627_1785324012,worker_25c51a2e_tn-role-system_1785344818}_original.jsonl`.
**Writes:** `md/full_replacement_blast_radius_20260729.md`.
**Calls out:** `src.proxy.{message_passes,rule_ops,diff_engine,payload_helpers,content_strip}`,
`src.proxy_display.render_messages`.

---

## Gotchas

- `pN_*.py` scripts import from `src/` — filename MUST carry the `pN_` prefix (project convention:
  only `pN_*.py` dev scripts may `from src...`/`import src...`; unprefixed dev scripts must copy
  the logic or import from an existing `pN_` module).
- `proxy_display` has an internal `from ..constants` (2-level relative import in `pane.py`, pulled
  in transitively by `proxy_display/__init__.py`) — it must be imported with the project ROOT on
  `sys.path` (not `src/` directly, which is what the plain `src/proxy/*` imports use). Mixing both
  roots on `sys.path` in the same script is safe (verified in `p1_measure_full_replacement_blast_radius.py`)
  since `src.proxy_display` and the flat `proxy` package never collide.
- `p1_measure_full_replacement_blast_radius.py` feeds each pass function only the NEW-message
  delta per dual-log request (not the full cumulative message list) — safe because none of the
  11 pass functions read any OTHER message's content (verified by reading `message_passes.py`),
  so this reproduces the same per-message ops as the real pipeline without the dual-log's
  cumulative-snapshot duplication inflating counts. The 2026-07-29 corpus itself was NOT static
  during the scan — see `process-docs/proxy_instrumentation/2026-07-29_full_replacement_blast_radius_measurement.md`
  for the moving-snapshot caveat.
```

## Salvage from dev/proxy_tool_stripping/DOCS.md

```
# dev/proxy_tool_stripping/

## Purpose

Regression coverage and measurement probes for the proxy's strip/inject display area — how a
whole-stripped tool shows up in the tools drill-down (`TOOL_BLOCKLIST`, `src/constants.py` +
`src/proxy/tools.py`), and the REQ-header `strip`/`inject` badge's noise filters
(`src/proxy_display/parser.py`). Shares its name with `process-docs/proxy_tool_stripping/`, the
broader area covering both the write-side strip mechanism and the read-side display/logging of
what got stripped — not limited to the tool blocklist specifically, despite the directory name.

## Scripts

### tests/test_whole_stripped_tool_expand.py (216 LOC)

**Purpose:** Verifies the whole-stripped tool row expand feature (Milestone 2, 2026-09) — a
`TOOL_BLOCKLIST`-stripped tool's yellow drill-down row is now expandable, showing the original
description/schema sourced from the same session's `_original` dual-log (the last request's own
`tools` list), instead of a static non-expandable name-only row.
- `_render_whole_stripped_tool` (`src/proxy_display/render_sections.py`): collapsed-row bytes and
  key shape (`('stripped_tool', entry_idx, name)`), expanded body with a resolved `tool_def`
  (description lines + `name[*]: type — desc` params, all `DIM_YELLOW_BG`), expanded fallback
  (`(original definition unavailable)`) when `tool_def` is `None`.
- `render_tools`'s `use_dual` whole-stripped loop: wires `entry['_original_tools_by_name']`
  through to the new function; a forwarded-tool row (no whole-stripped tools present) renders
  identically to the pre-milestone shape.
- `parser._find_original_log_path` / `parser.accumulate_original_tools`: path derivation
  (`dual_dir / f'{stem}_original.jsonl'`), per-family latest-snapshot overwrite behavior
  (`_original` is NOT delta-encoded, so no merge — always the newest tools-bearing line wins),
  reference-preservation across incremental reads, missing-file no-op.
Placed under `tests/` (pytest-shaped filename) so `src.hooks.block_dev_imports_src`'s regression-
suite exemption applies — this file needs literal `from src.proxy_display....` imports, which the
hook otherwise blocks for any other `dev/` script (see that hook's own module for the exact rule).
**Reads:** Nothing from disk (synthetic fixtures only) except a `tempfile.TemporaryDirectory()`
JSONL file it writes itself for the `accumulate_original_tools` incremental-read tests.
**Writes:** Nothing persistent — prints PASS/FAIL to stdout.
**Usage:** `python3 dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`

### probe_trailing_message_shapes.py (121 LOC)

**Purpose:** Measurement probe (2026-09-05) backing the claude-f trailing-nudge badge-widening —
scans every `_stripped.jsonl` line's `messages_delta` in the three current corpus stems, collects
every individual stripped text ending with the `<total_tokens>N tokens left</total_tokens>` tag,
normalizes by replacing the digit run with `N`, and reports distinct shapes with counts per
session plus a union total. Pure text/regex measurement — no `src/` import needed (does not touch
the `from src.` block-dev-imports-src hook at all), so it lives at the top level of this directory
rather than under `tests/`. This is what established the 24-distinct-shapes finding and the
3-sentence nudge catalog now in `src/proxy_display/parser.py`'s `_TOTAL_TOKENS_NUDGE_PARAGRAPHS` —
re-runnable against the live corpus to check whether a NEW, uncatalogued nudge shape has appeared
(by design it would show up here as a new distinct shape with real content mixed in, or as a
growing "ending-with-tag but never matches any catalogued shape" bucket over time).
**Reads:** `src/logs/dual_log/api_requests_opus_{wise2627_1788612045,websearch_1788611995,
monitor_cc_1788611156}_stripped.jsonl` (hardcoded stems — measurement was run against a specific
corpus snapshot, not parameterized).
**Writes:** `md/trailing_message_shapes_report.md`.
**Usage:** `python3 dev/proxy_tool_stripping/probe_trailing_message_shapes.py`

## Gotchas

- The byte-identical regression for this milestone was NOT run from this directory — it reuses
  the existing `dev/proxy_dual_log/A_render_refactor_proof.py` harness (capture-before /
  implement / verify-after). 13 of its 14 fixture cases stayed byte-identical; the 14th
  (`expand_fixpoint`) legitimately gained one new line once its whole-stripped `read_file` row's
  new key got iterated to `True` by the fixpoint loop — inspected manually via `difflib`, confirmed
  the diff is exactly the new expanded content and nothing else. The refreshed baseline is
  `dev/proxy_dual_log/A_render_refactor_proof_reports/baseline_20260905.json`.
```

## Salvage from dev/rag_helpfulness/DOCS.md

```
# dev/rag_helpfulness/

## Role
Holds the 2026-05 rag-cli call inventory report — a scan of proxy JSONL logs for rag-cli invocations (query text, char count, ok/fail). The extraction logic that produced it was superseded by `dev/tool_use_analysis/rag_query_audit.py`; no producing script remains in this folder.

## Files
- `md/01_inventory.md` — rag-cli call inventory across 61 scanned proxy JSONL files (27 with calls).
```

## Salvage from dev/ram_audit/DOCS.md

```
# dev/ram_audit/

## Problem

Pane process RSS grows over long sessions. Investigation module to capture live RAM snapshots and identify the top allocators.

## Trigger a dump

```bash
# Send SIGUSR1 to a running pane process (e.g. warnings_pane):
kill -USR1 $(cat /tmp/.monitor_cc_pid_warnings)
```

- **PID file:** `/tmp/.monitor_cc_pid_<pane>` — written at startup by each pane's run loop, removed on exit.
- **Dumps land in:** `dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_<pane>.txt`
- The handler prints `[ram-dump] wrote <path>` to stderr (visible in the pane's tmux output).

## Dump format

Each dump contains four sections:

1. **Header** — `timestamp`, `pid`, `rss` (bytes + MB, sourced from `resource.getrusage` on macOS).
2. **Top-30 gc objects by class** — 2-column table: class name | count. Covers all live Python objects at snapshot time.
3. **Top-30 tracemalloc by lineno** — 3-column table: file:line | size_bytes | count. Requires `tracemalloc.start(25)` (called at module import). Shows which source lines hold the most memory.
4. **Pane module state** — len + sizeof for every module-level list/dict; scalar values for floats/ints/strings. Reveals unbounded growth in module-level event lists.

## Scripts

### dump_all.sh (44 LOC)

Triggers a SIGUSR1 RAM dump on every running monitor_cc pane in one shot.

**Usage (from project root):**
```bash
dev/ram_audit/dump_all.sh
```

**What it does:**
1. Iterates all `/tmp/.monitor_cc_pid_*` PID files.
2. For each, verifies the process is alive (`kill -0`), then sends `SIGUSR1`.
3. Sleeps 1 s for handlers to write their dumps.
4. Lists freshly created dump files in `dev/ram_audit/dumps/`.
5. Prints summary: `N dumps written, see dev/ram_audit/dumps/`.

**Graceful handling:** skips stale PID files (process no longer running); exits cleanly with "No active pane PID files found" when no panes are instrumented.

**Equivalent per-pane trigger:**
```bash
kill -USR1 $(cat /tmp/.monitor_cc_pid_<pane>)
# e.g.:
kill -USR1 $(cat /tmp/.monitor_cc_pid_proxy)
kill -USR1 $(cat /tmp/.monitor_cc_pid_warnings)
```

### dump_byte_identity.py (114 LOC, new 2026-09, remaining-thresholds milestone)

**Purpose:** Byte-identity harness for `register_ram_dump`/`_handle_ram_dump`'s function-LOC
split into module-level report-section helpers. Calls `register_ram_dump` with a fake pane name
and a fixed `module_state_provider` (one container, one scalar), sends `SIGUSR1` to itself, reads
the resulting dump file, then normalizes out every inherently-non-deterministic line (`timestamp:`/
`pid:`/`rss:` header lines; the actual gc object-count rows and tracemalloc size/count rows — real
process memory state varies run to run, kept only as section headers/structure) before hashing
what remains — the report's fixed structure plus the fully-deterministic module-state section.
Verified stable across 3 independent runs on the unmodified code before recording the baseline.
**Reads:** Its own freshly-written dump file under `dev/ram_audit/dumps/`.
**Writes:** `/tmp/.monitor_cc_pid_byteidentity` and `dev/ram_audit/dumps/<ts>_byteidentity.txt` —
both deleted before the script exits (dump-dir `*.txt` files are gitignored either way, but this
harness cleans up proactively so a full run leaves the directory untouched). Stdout: one
`HASH: <hex>` line (plus `register_ram_dump`'s own `[ram-dump] wrote <path>` line on stderr).
**Run:** `./venv/bin/python dev/ram_audit/dump_byte_identity.py`
**Calls out:** `src.ram_audit.instrument` (`register_ram_dump`) — imported via a dedicated function
(`_import_instrument`), not a module-level `from src.` line, per `block_dev_imports_src`.

Status: hash `7f7f0d224b2eb5b19ee5eae33471f60614d6def9c2a00c720e295e9e26a4322d` — identical before
and after the `register_ram_dump`/`_handle_ram_dump` split (remaining-thresholds milestone,
2026-09).
```

## Salvage from dev/session_analysis/DOCS.md

```
# dev/session_analysis/

Standalone forensic analysis suite for Claude Code session JSONL and proxy log data. Used to investigate cache behavior, token attribution, and cache rebuild root causes. Scripts are not part of the production pipeline — they read raw data files directly and write Markdown reports or print to stdout. All scripts assume CWD = `Monitor_CC/` (project root).

## 01_extract.py

**Purpose:** Multi-level extraction and summary of tool calls from session JSONL files. Supports four zoom levels: all projects (aggregate), single project, single session, single session filtered by tool name.

**Input:** `~/.claude/projects/**/*.jsonl` session files. Optionally filtered by `--project` (absolute path) and `--session` (JSONL file path).

**Output:** Markdown table of tool call counts and input/output token usage — printed to stdout.

**Usage:**
```bash
# All projects (aggregate)
python3 dev/session_analysis/01_extract.py

# Single project
python3 dev/session_analysis/01_extract.py --project /path/to/project

# Single session
python3 dev/session_analysis/01_extract.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session, single tool
python3 dev/session_analysis/01_extract.py --session <path> --tool Bash
```

| Flag | Description |
|------|-------------|
| `--project` | Absolute project path — filters to that project's sessions |
| `--session` | Path to a single session JSONL file |
| `--tool` | Tool name filter (requires `--session`) |

---

## 02_cache_timeline.py

**Purpose:** Visualizes cache and token behavior turn-by-turn or minute-by-minute across a session or project. Detects anomalies (large CC spikes, time gaps > TTL, drops in CR). Useful for spotting when and why cache rebuilds occur at a coarse granularity.

**Input:** `~/.claude/projects/**/*.jsonl` session files, optionally a full project path.

**Output:** Markdown table with per-turn CR/CC/D/Out metrics, anomaly flags, bar chart — printed to stdout.

**Usage:**
```bash
# Single session — turn-by-turn
python3 dev/session_analysis/02_cache_timeline.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session — anomalies only
python3 dev/session_analysis/02_cache_timeline.py --session <path> --anomalies-only

# Single session — per-minute aggregation
python3 dev/session_analysis/02_cache_timeline.py --session <path> --aggregate

# Project summary (one row per session)
python3 dev/session_analysis/02_cache_timeline.py --project /path/to/project

# Include worker sessions
python3 dev/session_analysis/02_cache_timeline.py --project /path/to/project --workers
```

| Flag | Description |
|------|-------------|
| `--session` | Path to session JSONL file |
| `--project` | Absolute project path — one summary row per session |
| `--aggregate` | Per-minute aggregation view (requires `--session`) |
| `--workers` | Include worker sessions (requires `--project`) |
| `--anomalies-only` | Show only turns with detected anomalies (requires `--session`) |

---

## 03_cache_rebuild_context.py

**Purpose:** Detects cache rebuilds (turns where CR drops and CC spikes disproportionately) and displays surrounding message context for root cause analysis. Outputs pattern summary (how many rebuilds, time-gap triggered vs payload-triggered) and delta statistics.

**Input:** `~/.claude/projects/**/*.jsonl` session files. Single session or all projects scan.

**Output:** Per-rebuild context blocks (N messages before/after) + pattern summary — printed to stdout.

**Usage:**
```bash
# Single session, full context
python3 dev/session_analysis/03_cache_rebuild_context.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session, wider context window
python3 dev/session_analysis/03_cache_rebuild_context.py --session <path> --context 10

# Single session, summary only (no context blocks)
python3 dev/session_analysis/03_cache_rebuild_context.py --session <path> --summary-only

# All sessions across all projects
python3 dev/session_analysis/03_cache_rebuild_context.py --all
```

| Flag | Description |
|------|-------------|
| `--session` | Path to session JSONL file |
| `--context N` | Messages before/after each rebuild (default: 5) |
| `--summary-only` | Print pattern summary only, no context blocks |
| `--all` | Scan all session JSONLs across all projects |

---

## 04_cache_validation.py

**Purpose:** Validates proxy-side cache breakpoint placement and stability. Reads a proxy JSONL log and shows per-request: CC's original breakpoint positions (system/tools/messages), which messages contain proxy-modified content, whether breakpoints are stable between consecutive requests, and potential invalidation risks from modified content before a breakpoint.

**Input:** A proxy JSONL log file (`src/logs/api_requests_*.jsonl`) as positional argument.

**Output:** Per-request breakpoint analysis table — printed to stdout.

**Usage:**
```bash
# All requests in proxy log
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl

# Limit to first N requests
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl --limit 20

# Only requests with modifications before a breakpoint
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl --rebuilds-only
```

| Flag | Description |
|------|-------------|
| `log_file` | *(positional)* Path to proxy JSONL log file |
| `--limit N` | Limit output to first N requests (0 = all, default: 0) |
| `--rebuilds-only` | Only show requests where modified content sits before a cache breakpoint |

---

## 05_req_breakdown.py

**Purpose:** Forensic per-segment token attribution for a specific API request. Uses tiktoken (cl100k_base) to tokenize each system block, tool definition, and message individually and compare against session JSONL ground truth (CR, CC, D, Out). Optional cross-session byte-diff (`--prev-proxy-log`) computes which prefix segments were cache-read vs newly created, enabling root cause attribution for cache rebuilds. Writes a timestamped Markdown report to `md/`.

**Input:** A proxy JSONL log (`--proxy-log`) + a session JSONL (`--session-jsonl`) for the same session. Optionally a previous session's proxy log (`--prev-proxy-log`) for byte-diff attribution when CR > 0.

**Output:** `md/<YYYYMMDD_HHMMSS>_req<N>.md` — report path printed to stdout.

**Usage:**
```bash
python3 dev/session_analysis/05_req_breakdown.py \
  --proxy-log src/logs/api_requests_<id>.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
  --req 5

# With cross-session byte-diff attribution
python3 dev/session_analysis/05_req_breakdown.py \
  --proxy-log src/logs/api_requests_<current>.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
  --req 5 \
  --prev-proxy-log src/logs/api_requests_<previous>.jsonl
```

| Flag | Description |
|------|-------------|
| `--proxy-log` | *(required)* Proxy JSONL log file for the session |
| `--session-jsonl` | *(required)* Session JSONL file for ground truth CR/CC/D/Out |
| `--req N` | Request number (1-based, Opus only, default: 1) |
| `--prev-proxy-log` | Previous session proxy log for prefix byte-diff attribution (enables CR breakdown) |

---

## 06_char_token_ratio.py

**Purpose:** Correlates message char counts with actual API token counts (CR, CC, D) to derive chars-per-token ratios for Claude's tokenizer. Supports single-file analysis and batch mode across all proxy logs with auto-pairing to session JSONLs. Generates persistent Markdown reports.

**Input:** Proxy JSONL log (positional arg) or `--batch <dir>` for all logs in a directory. Optionally `--session-jsonl` for single-file mode to pair with session JSONL for token data.

**Output:** Markdown table to stdout + persistent report to `md/` (batch mode).

**Usage:**
```bash
# Single proxy log (char counts only)
python3 dev/session_analysis/06_char_token_ratio.py src/logs/api_requests_<id>.jsonl

# Single proxy log + session pairing (adds CR/CC/D/ratio)
python3 dev/session_analysis/06_char_token_ratio.py src/logs/api_requests_<id>.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl

# Batch mode — all proxy logs, auto-paired with session JSONLs
python3 dev/session_analysis/06_char_token_ratio.py --batch src/logs/
```

| Flag | Description |
|------|-------------|
| `log_file` | *(positional, optional in batch mode)* Proxy JSONL log file |
| `--session-jsonl` | Session JSONL for token data pairing (single-file mode) |
| `--batch DIR` | Scan all `api_requests_*.jsonl` in DIR, auto-pair with session JSONLs |

**Ratio types in output:**
- `full-rebuild`: CR=0, ratio = total_chars / CC (entire payload tokenized)
- `delta`: CR>0 + CC>0 + Δchars>0, ratio = Δmsgs_chars / CC (incremental message tokens)

---

## 07_quartet_prefix_diff.py

**Purpose:** Forensic per-segment prefix-diff for cache rebuilds. Reconstructs full payload state (system/tools/messages) at each opus-family request by replaying the `_forwarded` dual-log delta chain, aligns it to session-JSONL ground-truth usage (CR/CC/D) by timestamp, and diffs consecutive requests segment-by-segment (system[0..3] individually / tools / messages, per-index) to find WHERE a cache-rebuild's byte divergence sits and WHAT changed there (chars added/removed, image blocks mutated — including images nested inside `tool_result.content` — per-row auto-classification note). Also auto-scans the whole log for CR-collapse points (CC > CR and CR < 0.2 x prior max CR). Optionally cross-checks each modified message index against the `_original` dual-log (full non-delta incoming payloads, matched by `flow_id`) to attribute a diff as CLIENT-SIDE (already present in the incoming request, before our proxy) vs PROXY-SIDE (introduced by our own modification pass) — the fix-vs-document decision.

Cache-control breakpoint markers are intentionally NOT reported: the forwarded delta chain hashes elements with `cache_control` stripped (`src/proxy/logging.py: _delta_hash` -> `_strip_cache_control`), so a marker-only change never enters the delta and a replayed message's `cache_control` can be stale. True sent breakpoint positions are not derivable from this reconstruction.

**Input:** `--forwarded-log` — a `_forwarded` dual-log JSONL (delta-encoded: `system_delta`/`tools_delta`/`messages_delta` per request, NOT the eliminated single-main-log `raw_payload` format read by 04/05/06). `--session-jsonl` — session JSONL for ground-truth CR/CC/D. `--req-range A-B` and/or `--auto-detect`. `--original-log` (optional) — the matching `_original` dual-log for client-vs-proxy attribution.

**Output:** `md/<YYYYMMDD_HHMMSS>_quartet_prefix_diff.md` — report path printed to stdout.

**Usage:**
```bash
./venv/bin/python dev/session_analysis/07_quartet_prefix_diff.py \
  --forwarded-log src/logs/dual_log/api_requests_opus_<id>_forwarded.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
  --original-log src/logs/dual_log/api_requests_opus_<id>_original.jsonl \
  --req-range 133-137 --auto-detect
```

| Flag | Description |
|------|-------------|
| `--forwarded-log` | *(required)* `_forwarded` dual-log JSONL path |
| `--session-jsonl` | *(required)* Session JSONL for ground-truth CR/CC/D |
| `--req-range` | Consecutive REQ pair range to analyze, e.g. `133-137` |
| `--auto-detect` | Also scan the whole log for CR-collapse points |
| `--original-log` | `_original` dual-log JSONL (full non-delta incoming payloads) for CLIENT-SIDE vs PROXY-SIDE attribution |

**REQ numbering:** ground-truth requests are grouped from session-JSONL `type=assistant` lines by identical `(cr, cc, inp, out)` usage tuple (one physical request can emit several content-block lines interleaved with `type=user` tool_result lines from mid-stream tool execution). Forwarded-log entries are aligned to these groups by timestamp (two-pointer, monotonic) — NOT a fixed line-position offset; retried/aborted forwarded sends are silently absorbed into the next group's match.

**Original-log matching:** the `_original` log (one line per request, full non-delta `payload`) is matched to a forwarded/ground-truth request via `flow_id` (shared field on both logs). Only lines whose `flow_id` is in the target set are fully JSON-parsed — a cheap regex peek at the first 300 chars of each raw line extracts `flow_id` first, avoiding a full parse of the ~9MB-average irrelevant lines in a 1.4GB file.

---

## md/

MD reports written by `05_req_breakdown.py` and `07_quartet_prefix_diff.py`. One file per run.

**Naming convention:** `<YYYYMMDD_HHMMSS>_req<N>.md` (05) / `<YYYYMMDD_HHMMSS>_quartet_prefix_diff.md` (07).

**05 report structure:**
1. **Header** — proxy log path, session JSONL path, timestamp
2. **Ground Truth** — CR, CC, D, Out, Total input from session JSONL (deduplicated streaming chunks)
3. **Segment Breakdown** — tiktoken token counts per system block, per tool definition, per message; totals and estimate vs ground truth delta
4. **Prefix Attribution** *(when `--prev-proxy-log` provided)* — byte-diff per segment: which segments are byte-identical to previous session (→ cache-read) vs changed (→ cache-creation)
5. **Rule Edits** — proxy modifications detected between current and previous request (system content changes, injected rules)

**07 report structure:**
1. **Methodology** — REQ mapping notes (forwarded-entry / ground-truth counts, absorbed retries)
2. **Auto-Detected CR-Collapse Points** — table of collapse REQs vs prior max CR
3. **Per-pair sections** — system blocks table, tools changed y/n, messages table (status/chars/image counts per index), breakpoint markers added/removed, segment attribution (first diverging segment, raw and excluding per-request `system[0]` churn), CR/CC reconciliation (tiktoken BP1 estimate, recovery-identity check)
4. **Findings Summary** — proven-from-bytes facts, separated from interpretation/hypotheses
```

## Salvage from dev/sleep_pattern_analysis/DOCS.md

```
# dev/sleep_pattern_analysis/

## Role

Empirical analysis of `block_chained_sleep` hook firing events — classifies the `cmd_before`
token (command that immediately precedes `sleep N` in a blocked Bash chain) as trivial-sync
(safe to strip) vs load-bearing (keep) vs mixed/unclear. Produces the data needed to design
`rewrite_chained_sleep.py`: a hook that rewrites violations instead of blocking them.

Touch this suite when: re-auditing hook events after rule or hook changes; expanding the
trivial/load-bearing token sets; adding per-subcommand inspection logic for mixed tokens.

## Modules

### analyze.py (361 LOC)

**Purpose:** Orchestrates the full audit — walks `~/.claude/projects/*/*.jsonl`, resolves
each BLOCKED event to its triggering Bash command, extracts per-sleep context records,
produces the markdown report.

**Reads:** `~/.claude/projects/*/*.jsonl` — two passes per file:
  1. Builds `tool_use_id → command` map + `uuid → entry` map
  2. Finds `BLOCKED` lines for `block_chained_sleep`, resolves command via tool_use_id

**Writes:** `--out` path (default `md/sleep_audit_<date>.md`).

**Called by:** CLI only.

**Calls out:** `classify.add_classification()` for the classification section.

---

### classify.py (92 LOC)

**Purpose:** Token classification rules — constant sets (`_TRIVIAL`, `_LOADBEAR`, `_MIXED_NOTES`)
and reasons prose, plus `add_classification()` which appends the four-section classification
table to an in-progress report line list.

**Reads:** nothing (pure constants + logic).

**Writes:** mutates the `lines` list passed in by `analyze._build_report()`.

**Called by:** `analyze._build_report()`.

**Calls out:** nothing.

---

## Output

`md/sleep_audit_<YYYY-MM-DD>.md` — sections:
1. Summary header (event count, sleep count, heredoc FP exclusions, date range)
2. cmd_before histogram (top 25 tokens, count, %, 3 example snippets each)
3. cmd_after histogram (top 15 tokens)
4. In-loop / Naked / Canonical breakdown
5. Sleep duration distribution (1s / 2–5s / 6–15s / 16–60s / 60s+)
6. Classification — trivial-sync / load-bearing / mixed / unclassifiable tail

## Usage

```bash
# From dev/sleep_pattern_analysis/ (required: classify.py must be on sys.path)
cd dev/sleep_pattern_analysis
../../venv/bin/python analyze.py --since 2020-01-01 \
  --out md/sleep_audit_$(date +%Y-%m-%d).md

# Or from project root:
cd dev/sleep_pattern_analysis && \
  /path/to/venv/bin/python analyze.py [--since YYYY-MM-DD] [--out PATH]
```

## CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--since YYYY-MM-DD` | 30 days ago | Earliest event timestamp to include. Pass `2020-01-01` for all-time. |
| `--out PATH` | `md/sleep_audit_2026-05-24.md` | Report output path. |

## Notes

- Must be run from `dev/sleep_pattern_analysis/` so `import classify` resolves. The project
  venv Python is required (stdlib only, but `./venv/bin/python` is the project convention).
- Heredoc body spans are detected and excluded from histograms (hook false positives — the
  regex scanner in `block_chained_sleep.py` sees `sleep` tokens inside heredoc strings).
- `cmd_before = (empty)` means sleep is the FIRST command in the chain (sleep-first pattern,
  not strippable — the sleep IS the timing intent).
```

## Salvage from dev/strip_fp_tool_result/DOCS.md

```
# dev/strip_fp_tool_result/

## Role

Measurement-only audit for the FP-nuke bug class (see `process-docs/message_strip_fp_nuke/`) as
it applies to `tool_result` content specifically: which strip passes remove text from INSIDE a
`tool_result` block, split into the SR strip family (`_apply_first_pass`'s SR branches,
`_apply_cumulative_sr_strips`, `_apply_final_sr_pass` — all matching via `strip_sr.py`'s
line-anchored `<system-reminder>` scan) vs. unrelated non-SR passes (`bg_launch_ack`,
`hook_prefix`, `po_preview` — each matching its own marker, no `strip_sr` dependency). Touch when
extending this measurement (more corpus, more passes) or building the fix milestone's regression
baseline; do NOT touch to change strip behavior — that lives in `src/proxy/`.

## Modules

### audit_tool_result_sr_strips.py (656 LOC)

**Purpose:** Streams every request payload in `src/logs/dual_log/*_original.jsonl`, threads it
through the 11 real `_apply_*` pass functions from `src.proxy.message_passes` in
`rules.py::apply_modification_rules`'s exact order, and — using each pass's own
`pass_ops_by_msg_blk` per-block diff (offset/removed/injected) — records every removal whose
pre-pass block `type == 'tool_result'`. Classifies template via the real `strip_sr.py` registry
(imported, not reinvented); non-SR passes get their fixed mod name. Quoted-data / genuine-CC-
injection verdicts are hand-written into `_MANUAL_VERDICTS` (keyed by `(file, msg_idx, blk_idx,
first_line_idx)`) after reviewing one run's raw context, then folded in on the next run.
**Reads:** `src/logs/dual_log/*_original.jsonl` (main checkout, not per-worktree — gitignored).
**Writes:** `dev/strip_fp_tool_result/md/audit_tool_result_sr_strips.md`.
**Called by:** none (standalone CLI: `python3 dev/strip_fp_tool_result/audit_tool_result_sr_strips.py`).
**Calls out:** `src.proxy.message_passes`, `src.proxy.strip_sr`, `src.proxy.content_strip`,
`src.proxy.rule_ops`, `src.proxy.strip_git_lock` (all via `importlib`, dodging
`block_dev_imports_src`).

---

## Gotchas

- **Self-session exclusion is by filename, not automatic.** Any file matching `SELF_SESSION_MARKER
  = 'sr-fp-audit'` is excluded — this worker's own dual-log is live-growing while the script runs
  and its own Read/Bash calls on this investigation would otherwise appear as fake "evidence".
- **The corpus is live.** Other sessions' dual-logs (`api_requests_opus_monitor_cc_...`, etc.) keep
  growing between runs (real concurrent Claude sessions) — occurrence counts are a snapshot at
  scan time, not a fixed total; re-running can surface new rows requiring new `_MANUAL_VERDICTS`
  entries (same reasoning as an already-classified sibling, not a reclassification).
- **`tool_result_list_joined` offsets are into the JOINED sub-block text**, not any single
  sub-block — `_block_inner_text` (imported from `rule_ops.py`) is what `_ops_from_content_change`
  computed the offset against; context slicing reuses the same function for consistency.
- **SR-family vs. non-SR split is load-bearing for the report's headline conclusion** — pooling
  `bg_launch_ack`/`hook_prefix`/`po_preview` (unrelated markers, correct-by-design tool_result
  descent) together with the actual SR-template passes produces a false "genuine injections
  found" conclusion. Keep the two aggregated and reported separately.
- **Ground-truth non-reproduction is a first-class result, not a bug in the script.** The
  task-stated `stripped_git_lock_advice` finding does not reproduce in this corpus snapshot — the
  literal 5-line block never appears with real newlines outside this worker's own excluded
  self-session (an artifact of investigating `strip_git_lock.py`'s escaped source, not production
  data). `_scan_ground_truth_git_lock` makes this check itself re-runnable.
- **This script also served as the fix-milestone's verification tool.** After
  `strip_sr.py::_strip_system_reminders` stopped descending into `tool_result` (2026-07-28), a
  re-run showed the SR-family aggregate going from 1 occurrence to 0, non-SR unchanged in kind —
  see `process-docs/message_strip_fp_nuke/2026-07-28_tool_result_sr_audit.md`. The report's
  "Genuine CC injection — found?" section has an explicit `elif not sr_occ:` branch for this
  post-fix state (distinct from the pre-fix "0 genuine, 1 FP" prose) — don't let the two states'
  wording collide if the corpus regresses.
```

## Salvage from dev/thinking/DOCS.md

```
# dev/thinking/

## Role

Verification tooling for the proxy pane's thinking-related display features: the per-request
"brain marker" (🧠 badge on the REQ header) and the thinking-block drill-down + wrapping inside
an expanded REQ. Touch this when changing `has_thinking_delta` computation
(`src/proxy_display/forwarded_parser.py`), the badge rendering
(`src/proxy_display/render_turn.py::_build_req_header_line`), or the thinking-block toggle/wrap
(`src/proxy_display/render_messages.py::_render_block_spans`/`_wrap_thinking_text`,
`src/utils.py::wrap_visible`).

## Scripts

### render_brain_badge.py (136 LOC)

**Purpose:** Renders a real `_forwarded` dual-log through the actual parse + render path
(`forwarded_parser._parse_forwarded_log` → `render_turn._build_req_header_line`, no
reimplementation of the badge logic) and reports, per request, whether `🧠` appears in the
rendered header. Also computes an independent CUMULATIVE cross-check (any `thinking` block
anywhere in the full accumulated message list) to demonstrate the delta variant is the narrower,
informative one — the milestone's stated rationale for delta-over-cumulative semantics.

**Usage:**
```bash
# defaults to src/logs/dual_log/api_requests_opus_monitor_cc_1787931850_forwarded.jsonl
python3 dev/thinking/render_brain_badge.py
python3 dev/thinking/render_brain_badge.py path/to/other_forwarded.jsonl
```

**Measured (2026-08-28, live runtime log — the file keeps growing across sessions, so absolute
counts drift; re-run for current numbers):** 48 opus / 13 haiku requests; 26/48 opus carry 🧠
under delta semantics, 0/13 haiku; cumulative cross-check gives 47/48 opus (only the very first
opus request, before any assistant turn exists, is cumulative-negative) — confirming delta is
meaningfully narrower than cumulative, same shape the milestone spec describes.

**Reads:** a `_forwarded` dual-log JSONL file (path arg or the default above; the log itself is
runtime-only, gitignored under `src/logs/`, not vendored in the repo).
**Writes:** `dev/thinking/md/render_brain_badge_<timestamp>.md` (per-request table + aggregate counts).
**Called by:** nobody — standalone verification script, run manually.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.format`, `src.utils` (all via `importlib.import_module`, per dev/ import convention).

---

### render_thinking_expander.py (256 LOC)

**Purpose:** Verifies the thinking-block drill-down + wrapping against a real `_forwarded` log,
through the REAL render path (`render_turn._render_req_expanded`, not a reimplementation).
Three checks, matching the milestone's own verification spec: (1) collapsed — a thinking block
occupies exactly one line and leaks no thinking text, proven by diffing a from-scratch collapsed
render against a single-key-expanded render (prefix/suffix around the header line must be byte
identical — the ONLY difference is the inserted content block); (2) expanded — the full text is
present (whitespace-normalized match against `blk['full_text']`, so re-wrapped whitespace can't
hide a false pass) and no content line exceeds `pane_width` cells, checked at 180 (the milestone's
own clipping example) and 60 (narrow stress width); (3) byte-identical — a non-thinking block's
`_render_block_spans` output is identical before and after this milestone's `render_messages.py`
edit, proven by loading the PRE-CHANGE file straight from git (`BEFORE_COMMIT_SHA`, pinned to the
commit preceding the edit) into an isolated `old_snapshot.src...` package under `/tmp` — a real,
separately-rooted package tree so the old file's relative imports (`from ..constants import
...`) resolve without colliding with the live `src` package already in `sys.modules` — and
calling its old-signature `_render_block_spans` against the same real block data the new one
renders, for one real block of each non-thinking type in the log (text, tool_use, tool_result,
image). Also determines which `(entry_idx, msg_idx, bidx)` thinking blocks are actually owned by
a given entry's own rendered delta empirically (`think_key` present in that entry's own
from-scratch render), not inferred — a message re-appears in every LATER entry's accumulated
`messages` too, but only the entry whose own delta introduced it renders it (same delta-vs-
cumulative distinction as `render_brain_badge.py`'s brain marker).

**Usage:**
```bash
# defaults to src/logs/dual_log/api_requests_opus_monitor_cc_1787931850_forwarded.jsonl
python3 dev/thinking/render_thinking_expander.py
python3 dev/thinking/render_thinking_expander.py path/to/other_forwarded.jsonl
```

**Measured (2026-08-28):** 26 owning thinking blocks found in the log — collapsed 26/26 ok,
expanded 52/52 ok (26 blocks × 2 pane_widths), byte-identical 4/4 non-thinking types ok. Exits 1
if any check fails.

**KNOWN LIMITATION the probe does NOT cover (unmeasured, not ruled out):** `_render_span_content`
ignores `full_text` entirely when `i_blk` is new-format span data — a thinking block carrying its
own strip/inject spans would render them unwrapped, bypassing this milestone's wrap. This script's
`check_non_thinking_byte_identical` never exercises that coordinate for a thinking block (it only
runs the byte-identical check on non-thinking types), and no thinking block in the sampled log
carried spans either — the absence is a property of this one log, not a proof the coordinate is
unreachable. See `process-docs/thinking/` for the full note.

**Reads:** a `_forwarded` dual-log JSONL file (path arg or the default above), plus `git show` of
`BEFORE_COMMIT_SHA` for the byte-identical check (requires the commit to exist in the local repo).
**Writes:** `dev/thinking/md/render_thinking_expander_<timestamp>.md` (three result tables +
aggregate counts); a throwaway package tree under a `tempfile.mkdtemp` `/tmp` dir (not cleaned up
— harmless, same as any other `/tmp` scratch artifact).
**Called by:** nobody — standalone verification script, run manually.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.render_messages`, `src.proxy_display.format`, `src.utils`, `git` (subprocess,
`show` only) — all Python imports via `importlib.import_module`, per dev/ import convention.
```

## Salvage from dev/timer-loop/DOCS.md

```
# dev/timer-loop/

## Role

Measurement + verification scripts for the (now-removed, Milestone 3) proxy-side
pending-background-task tracking design: what background-task completion/kill notices actually
look like in the recorded corpus (`p1_`, feeding the design — independent of the removed
mechanism, still runs), the proxy-side state mechanism that used to arm/clear a pending tombstone
from them (`p2_`, `src/proxy/pending_bg_state.py` — REMOVED, see `process-docs/timer-loop/`), and
the 2026-08-07 project-scoping fix spanning that writer and its enforcement hook,
`src/hooks/block_timer_pending_bg.py` (`p3_` — hook removed Milestone 2, writer removed Milestone
3; the whole chapter is closed, `p2_`/`p3_` kept only as historical record). `md/` holds every
script's report. `test_abort_stamp_scope.py` is a live regression-guard for the 2026-08-18
menubar-side abort-scoping fix (`src/menubar/bg_timer.py`) — a different mechanism in the same
wake-up chain, not related to the removed pending-state machinery above.

## Modules

### p1_scan_bg_completion_wordings.py (466 LOC)

**Purpose:** Inventories distinct background-task completion/kill notice wordings in the recorded
corpus (`src/logs/dual_log/*_original.jsonl`), split main vs worker session, dedups cumulative
dual-log duplication via a per-session exact-raw-text `seen` set (not a positional delta — robust
to the non-monotonic message-count resets observed in some worker sessions), evaluates the real
`payload_helpers._extract_task_notification_task_id` extraction against each wording.
**Reads:** `src/logs/dual_log/*_original.jsonl` (corpus dir overridable via `sys.argv[1]`).
**Writes:** `md/bg_completion_wordings_<date>.md`.
**Called by:** run manually — measurement only, not a regression guard.
**Calls out:** `src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_completed.py`,
`src/proxy/payload_helpers.py` (imports the real markers/regexes/extractors).

---

### p3_project_scope_incident_probe.py (243 LOC)

**SUPERSEDED (Milestone 2, 2026-08, hook family rework — updated Milestone 3):**
`src/hooks/block_timer_pending_bg.py` was removed in Milestone 2 (hook-subprocess sections
stopped running); `src/proxy/pending_bg_state.py` itself was removed in Milestone 3 (its own
probe, `p2_pending_bg_state_probe.py`, deleted with it), so this probe's writer-side sections are
ALSO non-runnable now — the whole script is a dead import. Left as-is, historical record only. See
`process-docs/timer-loop/` for the removal.

**Purpose:** Replays the 2026-08-07 ~01:10 cross-project false-block incident verbatim — the
websearch project's main session armed its canonical timer and was blocked by a POSTS-project
pending entry (task `b4z5fzzao`) in the one global `pending_bg_tasks.json`. Drives the REAL
`block_timer_pending_bg.py` hook via `subprocess` with a seeded state file and a real named cwd
directory (`.../Websearch`, `.../Posts`) — not injected strings — so `_current_project_slug()`'s
actual cwd-basename derivation runs end-to-end: foreign-project pending → now ALLOWS (the incident
itself); same-project pending → still BLOCKS; legacy no-project entry → still BLOCKS regardless of
cwd (backward compat); expired same-project entry → ALLOWS (expiry independent of project match).
Also verifies the writer side directly — real `ProxyAddon.request()` stamps the project slug from
`PROXY_PROJECT_PATH`.
**Reads:** Nothing persistent — seeds its own state file per case under a `tempfile.TemporaryDirectory()`-scoped `MONITOR_CC_ROOT`.
**Writes:** `md/p3_project_scope_incident_probe_report.md`.
**Called by:** does not run — historical incident record only (see SUPERSEDED note above; both the
hook-subprocess sections and the writer-side sections are now dead imports).
**Calls out:** `src/hooks/block_timer_pending_bg.py` (removed, path now dead),
`src/proxy/pending_bg_state.py` (removed, path now dead), `src/proxy/addon.py` (`ProxyAddon`,
`_derive_worker_context` — still live).

---

### test_abort_stamp_scope.py (122 LOC)

**Purpose:** Integration regression guard for the 2026-08-18 abort-stamp scoping fix
(`src/menubar/bg_timer.py:_abort_bg_sleep_timers`/`_resolve_pid_output_file`). Spawns two REAL
subprocesses (`sleep 20`) with stdout+stderr redirected straight to fake `.output` files —
mirrors CC's own background-launch fd shape — plus one plain 0-byte file with no associated
process. Calls the REAL `_abort_bg_sleep_timers` with only one of the two PIDs, asserts: (1) the
killed PID's own file gets stamped `aborted\n`; (2) the killed PID's process actually terminates;
(3) the foreign 0-byte file (no associated PID) is untouched; (4) the OTHER live process's file
AND its process are both untouched (still running) — the exact "a live wait's file in another
session" shape from the confirmed 2026-08-17 incident; (5) the `[abort]` menubar.log line lists
only the stamped file, not the untouched ones. `importlib.import_module` used for the
`src.menubar` imports (`block_dev_imports_src.py` forbids a literal `from src.` line in `dev/`).
**Reads:** nothing persistent — spawns its own subprocesses + tempdir.
**Writes:** tempdir under system temp (removed in `finally`); appends to the REAL
`APP_SUPPORT/menubar.log` (same file the live menubar app uses — append-only, no isolation
needed, verified via before/after size diff rather than a fresh file).
**Called by:** run manually — `python3 dev/timer-loop/test_abort_stamp_scope.py`.
**Calls out:** `src.menubar.bg_timer` (`_abort_bg_sleep_timers`, dynamic import),
`src.menubar.paths` (`_APP_SUPPORT`, dynamic import); `subprocess`, `lsof` (via the module under
test), `sleep` (fixture processes).

---

## Gotchas

**p1's corpus is a moving target — counts are a lower bound, not final.** Same caveat as
`dev/bg_wakeup_id_line`'s p1: `src/logs/dual_log/*_original.jsonl` keeps growing from concurrent
live sessions while the scan runs; a rescan can only add deduped occurrences, never remove them.
```

## Salvage from dev/tmux_launcher/DOCS.md

```
# dev/tmux_launcher/

## Role

Byte-identity regression harness for `src/tmux_launcher.py`. Add a script here when a
`tmux_launcher.py` refactor (helper extraction, LOC split) needs a before/after correctness proof
of the exact `subprocess.run` argv sequence it issues — this package never invokes real tmux.

## Modules

### argv_byte_identity.py (177 LOC, new 2026-09, remaining-thresholds milestone)

**Purpose:** Byte-identity harness for `launch_split_screen`/`restart_panes`'s function-LOC split.
Monkeypatches `subprocess.run` to record every argv list issued (real tmux never runs) and to
return scenario-appropriate canned stdout/returncode via a stateful `_FakeTmux` that tracks
`new-window`/`split-window` calls so a LATER `list-panes` call in the same run reflects them
(exactly like real tmux would — this is what exercises `restart_panes`'s own "refresh pane list so
subsequent iterations see the new pane" comment). Three scenarios, hashed together:
(1) `launch_split_screen` — session doesn't pre-exist (`has-session` returncode != 0, so
`kill_session` is never called), `attach-session` stubbed (the fake never blocks).
(2) `restart_panes` — all 6 windows + every layout pane already present → pure respawn path, zero
`new-window`/`split-window` calls.
(3) `restart_panes` — window 2 entirely missing (recreate-from-scratch path, exercises the
`pane_specs[1:]` split-after-create loop) AND window 5 present but missing its second pane
`'news-log'` (single-missing-pane split path).
**Reads:** Nothing external — all fixtures are constructed inline.
**Writes:** Nothing — stdout only (`HASH: <hex>`).
**Run:** `./venv/bin/python dev/tmux_launcher/argv_byte_identity.py`
**Calls out:** `src.tmux_launcher` (`launch_split_screen`, `restart_panes`) — imported via a
dedicated function (`_import_tmux_launcher`), not a module-level `from src.` line, per
`block_dev_imports_src`.

Status: hash `f3cc235e20ff81eb2193791f70f2e776555e448617932f7f8f1bb25f79cf5cb6` — identical before
and after the `launch_split_screen`/`restart_panes` LOC split (remaining-thresholds milestone,
2026-09).
```

## Salvage from dev/tool_injection/DOCS.md

```
# dev/tool_injection/

Extracts and manages MCP tool schemas for proxy-side tool injection.

## Purpose

Proxy needs stable, deterministic `tools[]` arrays in every API request to prevent cache invalidation caused by Claude Code's alphabetical tool insertion mid-session (ToolSearch / deferred-builtin lifecycle). These scripts provide the schema store that `src/proxy/tool_injection.py` reads at runtime.

## 01_extract_schemas.py

**Purpose:** Extract tool schemas from FastMCP plugin servers and write them as JSON files to `src/proxy/schemas/`.

**Input:**
- `/Users/brunowinter2000/Documents/ai/Meta/blank/server.py` — iterative-dev server (24 tools)
- `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/server.py` — github-research server (20 tools)

Each server is loaded in an isolated subprocess using its own Python venv. If the venv doesn't exist, the script bootstraps it from `requirements.txt`.

**Output:** `src/proxy/schemas/<plugin>/<tool_name>.json` — one JSON file per tool, Anthropic API format:
```json
{
  "name": "mcp__plugin_<plugin>_<server>__<tool>",
  "description": "...",
  "input_schema": { ... }
}
```

**MCP prefix pattern** (verified against `src/logs/api_requests_opus_monitor_cc_1776092124.jsonl`):
- `iterative-dev` → `mcp__plugin_iterative-dev_iterative-dev__<tool_name>`
- `github-research` → `mcp__plugin_github-research_github__<tool_name>`

**Usage:**
```bash
./venv/bin/python dev/tool_injection/01_extract_schemas.py
```

Re-run whenever plugin tools change. Output is gitignored (lives in `src/logs/`).

## Stage 2 context

See `src/proxy/tool_injection.py` for how the schema store is loaded and injected into API requests at proxy time. The proxy reads from `src/proxy/schemas/` on first request (cached), then appends iterative-dev tools unconditionally and active plugin tools in activation order.
```

## Salvage from dev/tool_use_analysis/DOCS.md

```
# dev/tool_use_analysis/

Forensic extraction and analysis of tool_use blocks from Claude Code sessions. `extract_long_calls.py` for full Markdown reports; `extract_zeros.py` for zero-result search detection. Each script is standalone (no shared library — helpers inlined per script). Error/failure analysis and rule-compliance scoring have moved to `dev/tool_use_errors/`.

## Report Convention

- **Script docstring (mandatory):** every script opens with a module docstring — one-sentence purpose + `Input:` (JSONL source/pattern) + `Output:` (report path under `md/`, or stdout).
- **Report Source block (mandatory):** every generated report opens, right after its title, with a `## Source JSONLs` block — one line per JSONL passed to `load_proxy()`, each with its event count (lines with `raw_payload != null`) and deduplicated tool_use-block count, then a total sessions/blocks line. Glob patterns are expanded to the individual files.
- **No shared library:** each script is standalone; 10–30 LOC of inlined helpers (JSONL parse, tool_use extraction, char counting) is acceptable — do not extract a shared forensic module.

## extract_long_calls.py

**Purpose:** Reads one or more Proxy JSONL files from `src/logs/`, collects every `tool_use` block from `raw_payload.messages[].content[]`, deduplicates by `tool_use.id` (each unique call counted once), measures the JSON-serialized `input` dict in characters, and outputs a Markdown report ranked by input size. Used to identify which tool calls burn the most context budget.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: summary by tool, char-bucket distribution, top-N detail entries.

**Usage:**
```bash
# Single file → stdout
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  src/logs/api_requests_opus_monitor_cc_1776615410.jsonl

# All proxy logs → file
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  /path/to/src/logs/api_requests_*.jsonl \
  --output dev/tool_use_analysis/md/20260419_baseline.md

# Top 10 only, threshold 1000 chars
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  src/logs/api_requests_*.jsonl \
  --top 10 --min-chars 1000
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--tool NAME` | Filter by tool name (e.g. `Bash`, `Read`, `Grep`) | all tools |
| `--ratio` | Ratio mode: match tool_use with tool_result, report input/output ratio; excludes Edit/Write/worker_send | off |
| `--top N` | Top-N entries in detail section (char-sorted normally, ratio-sorted in `--ratio` mode) | 30 |
| `--min-chars N` | Min input chars filter; ignored in `--ratio` mode | 500 |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Modes:**
- Default: all tools, char-sorted, `--min-chars` filter applies
- `--tool Bash`: adds **Command-Prefix Clustering** section (extract_prefix per call, aggregated by prefix → total_chars)
- `--ratio`: input/output ratio per matched pair; summary table shows mean/median/max ratio per tool
- `--tool NAME --ratio`: combined — ratio mode for one specific tool (exclusion list bypassed)

## extract_zeros.py

**Purpose:** Reads one or more Claude Code session JSONL files, detects every Grep / Glob / Read call that returned a zero result, and outputs a Markdown report with each call's tool name, input parameters, raw result, and preceding assistant text (context for the search intent).

**Input:** One or more session JSONL paths (positional, variadic) under `~/.claude/projects/<encoded>/<session>.jsonl`.

**Output:** Markdown report to stdout by default, or a file via `--output`.

**Usage:**
```bash
# Single session → stdout
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<session>.jsonl

# Multiple sessions — parent + worker sessions combined
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<parent>.jsonl \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<worker1>.jsonl

# Write to file
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py <session.jsonl> --output /tmp/zeros.md
```

| Flag | Description |
|------|-------------|
| `session_jsonl` | *(positional, variadic)* One or more session JSONL file paths |
| `--output FILE` | Output markdown file path (default: stdout) |

**Zero-result detection logic:**
- Grep: result contains `"No matches found"` or `"No files found"`
- Glob: result contains `"No files found"`
- Read: result contains `"File does not exist"` or `"does not exist"` AND does not start with a line-number prefix (`\d+\t`)

**Preceding text extraction:** walks the `parentUuid` chain from the tool_use event back to the nearest preceding assistant text block — gives context for what Opus was trying to accomplish.

## rs_truncation_preserve_replay.py

**Purpose:** Replay-verifies the `_apply_role_system_strip` preserve-guard (`src/proxy/message_passes.py`) — asserts every logged `role='system'` message whose content starts with `[Truncated:` (Read-truncation notice) passes through the pass UNCHANGED, while all other `role='system'` noise (deferred-tools, date-changed, etc.) is still reduced to `"."`.

**Input:** One dual-log `_original.jsonl` path (positional, optional — defaults to `src/logs/dual_log/api_requests_opus_trading_1784579551_original.jsonl`, worktree copy if present else the main-checkout absolute path). Payload key: `payload.messages`.

**Output:** Console PASS/FAIL one-liner (`truncation_preserved=N noise_stripped=M failures=K`) + verbose per-failure table to `dev/tool_use_analysis/md/rs_truncation_preserve_replay_detail.md`.

**Usage:**
```bash
./venv/bin/python dev/tool_use_analysis/rs_truncation_preserve_replay.py
```

## extract_transcript.py

**Purpose:** Chronological tool_use/tool_result transcript from a proxy-log JSONL snapshot — renders WHAT calls a session made, in order, to trace the workflow and spot redundant call sequences (10 calls where 2 would do). No waste/ratio scoring — a plain timeline dump. Marks `(ERROR)` on tool_results with `is_error` (surfaces skill-load / blocked-call failures directly). Built 2026-06-01 to analyse a capture-worker run.

**Input:** One or more proxy-log JSONL paths under `src/logs/` (positional, variadic). Uses the entry with the highest `message_count` (cumulative snapshot) per file; entries with `raw_payload == null` skipped. Pure stdlib — no venv needed.

**Output:** Markdown report to stdout by default, or a file via `--output`. CONVENTION Source-block header + per-file `--- msg[i] <role> tool_use/tool_result ---` blocks in message order.

**Usage:**
```bash
./venv/bin/python3 dev/tool_use_analysis/extract_transcript.py \
  src/logs/api_requests_worker_<id>_<name>_<ts>.jsonl \
  --output /tmp/worker_transcript.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) | required |
| `--max-input-chars` | Truncate tool_use input JSON | 4000 |
| `--max-result-chars` | Truncate tool_result content | 1500 |
| `--with-text` | Also include assistant/user text blocks | off (tool blocks only) |
| `--output FILE` | Output markdown path | stdout |

## extract_patterns.py

**Purpose:** Reads one or more Proxy JSONL files, pairs every `tool_use` block with its `tool_result`, applies ratio + input-size filtering (ratio≥3, input≥50 chars) to identify waste calls, normalizes tool inputs to grouping signatures (paths→`<PATH>`, log filenames→`<LOG>`, bead IDs→`<BEAD_ID>`, hex IDs→`<HEX>`, epoch timestamps→`<TS>`, long strings→`<TEXT>`), aggregates by `(tool_name, signature)`, and outputs a 6-section Markdown report: per-source summary, tool breakdown, Bash pattern groups (top 15), other tool patterns (Grep/Glob/Read), failed-call groups, wrapper candidates.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: Source JSONLs block (CONVENTION.md), per-source summary, tool breakdown, Bash pattern groups, other-tool patterns, failed calls, wrapper candidates.

**Usage:**
```bash
./venv/bin/python dev/tool_use_analysis/extract_patterns.py \
  src/logs/api_requests_opus_monitor_cc_1776797402.jsonl \
  src/logs/api_requests_worker_extract-tool-defs_1776798488.jsonl \
  --output dev/tool_use_analysis/md/20260422_session_waste_patterns.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Waste filter:** `ratio = input_chars / max(output_chars, 1) >= 3.0` AND `input_chars >= 50`. Failed calls (`is_error=True`) tracked separately regardless of ratio. `CONTENT_TRANSFER_TOOLS = {'Write', 'Edit'}` plus Bash(`bd *`) and `worker_send`/`worker_merge` MCP calls are excluded from waste pairs (large input by design) and reported in Section 2b instead.

**Normalization order:** paths → log filenames → bead IDs → hex IDs → epoch timestamps → long double-quoted strings → long single-quoted strings → worker session names (context-anchored after `worker-cli`).

**Section 6 (Wrapper Candidates):** Write/Edit/worker_send excluded (content-driven); heredoc/`python3 -c` patterns classified as `structural`; other Bash patterns classified by presence of `|`/`&&`/`bd`. Sorted by `total_input_chars / complexity_weight` (trivial=1, medium=2, structural=4).

## waste_repetition.py

**Purpose:** Reads a single Proxy JSONL file, finds the entry with the highest `message_count` (the cumulative session snapshot), extracts all deduplicated Bash `tool_use` blocks from that entry, and analyzes waste along two independent dimensions:

1. **Repetition Signature Groups** — normalizes each command to a stable signature (home paths → `<HOME>/`, log filenames → `<LOG>`, quoted strings → `<STR>`, hex/digit runs → `<HEX>`/`<N>`, worker names → `<WORKER>`), groups by signature, ranks by `count × avg_chars` descending, reports all groups with `count ≥ --min-count`.

2. **Known-Shortcut Path Fragments** — scans every command for replaceable path fragments using a four-rule table (`KNOWN_SHORTCUTS`): (a) any `abs-path ~/Documents/ai/<project>` in a worker-cli/git-check/dev-sync argument → `c`; (b) same for `~`-form; (c) `/Users/brunowinter2000/Documents/ai/Monitor_CC` in any context → `~/…`; (d) generic `/Users/brunowinter2000/` → `~/`. Per-rule counts are independent; the grand total deduplicates overlapping matches (best/highest-savings rule wins per fragment position).

**Input:** Single Proxy JSONL path (positional). Entries with `raw_payload == null` skipped. The entry with the most messages is used as the cumulative session snapshot.

**Output:** Markdown report to stdout (redirect recommended). Sections: summary line (total calls, distinct sigs, total chars, repeated-sig chars, path-shortcut-saveable), Family Overview (per first-token family with sum counts/chars), Repetition Groups table (top K), Replaceable Path Fragments table with grand total, Full Samples (top 10 expanded commands).

**Usage:**
```bash
./venv/bin/python dev/tool_use_analysis/waste_repetition.py \
  src/logs/api_requests_opus_monitor_cc_1776855140.jsonl \
  > /tmp/waste_rep.md 2>&1
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional)* Single Proxy JSONL path | required |
| `--min-count N` | Minimum occurrence count for a repetition group | 2 |
| `--top K` | Show top K groups in the signature table | 20 |

## cc_injection_audit.py

**Purpose:** CC injection catalog via proxy-log / session-JSONL cross-reference. For each user-role message in the delta range of each opus REQ, checks whether the message content appears as a real user event in the matching CC session JSONL. Unmatched messages are CC-injected; classified by `startswith` pattern. Produces a Markdown catalog of injection types and frequencies, revealing which injections inflate the context budget.

**Input:** One or more proxy log paths (positional, optional). Default: newest 5 `src/logs/api_requests_opus_monitor_cc_*.jsonl`. CC session JSONL auto-discovered by mtime proximity (max 90 min); override with `--cc-session`.

**Output:** `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_cc_injection_catalog.md`. Path printed to stdout.

**Usage:**
```bash
# Auto-pick newest 5 proxy logs
./venv/bin/python3 dev/tool_use_analysis/cc_injection_audit.py

# Explicit proxy log + explicit CC session JSONL
./venv/bin/python3 dev/tool_use_analysis/cc_injection_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl \
  --cc-session ~/.claude/projects/-Users-.../session.jsonl
```

---

## tag_presence_audit.py

**Purpose:** Per-REQ, delta-scoped forensic audit for leftover tag occurrences (`<SR>`, `<TN>`, `<ND>`, `<PO>`) in `raw_payload.messages`. Complements `sr_bypass_audit.py` (which is aggregate and multi-counts persistent messages) and `strip_audit.py` (which is delta-scoped but truncated and mixed with EFF/INERT noise). This audit emits only REQs with tag occurrences, shows full content without truncation, and pairs each REQ with its `stripped_msg_removed` delta entries so the reader can answer per-REQ: "tag X was in delta msg[N] — was it stripped (visible in `stripped_msg_removed[N]`) or did it bypass?"

**Input:** Single Proxy JSONL path (positional, optional). Auto-picks newest `api_requests_opus_monitor_cc_*.jsonl` from `src/logs/`.

**Output:** `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_tag_presence_audit.md`. Path printed to stdout. Sections: per-REQ blocks (only for REQs with tag occurrences) + `## Aggregate (delta-scoped)` footer with tag-type count table and SR template bypass_rate table.

**Usage:**
```bash
# Auto-pick newest log
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py

# Explicit log
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py \
  src/logs/api_requests_opus_monitor_cc_1777294641.jsonl

# Explicit output path
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py \
  src/logs/api_requests_opus_monitor_cc_1777294641.jsonl \
  --output /tmp/my_audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `jsonl` | *(positional, optional)* Proxy JSONL path | auto-picks newest in `src/logs/` |
| `--output FILE` | Output markdown file path | `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_tag_presence_audit.md` |

**Per-REQ block format:** header line with timestamp + message counts + delta_start; one occurrence block per tag found (label: `<SR>/template_id`, `<TN>`, `<ND>`, or `<PO>`; full content indented 4 spaces); then `STRIPPED` blocks from `stripped_msg_removed` for all delta-range indices. Layer labels: `text`, `tool_result_str`, `tool_result_nested`, `tool_use`, `plain_str`. SR blocks starting with `_PRESERVE_PREAMBLE` (claudeMD context) are silently skipped. Unmatched SR blocks labeled `/?`.

---

## sr_bypass_audit.py

**Purpose:** SR bypass audit — per-template count of bypassed vs captured SR blocks. Scans `raw_payload.messages` for SR blocks still present after proxy processing (bypassed) and `stripped_msg_removed` for SR blocks successfully removed (captured). Reports `bypass_rate` per template per log file + aggregate summary table. Designed to identify which SR templates the proxy strip pipeline is missing.

**Methodology note:** The proxy `stripped_all_sr_msg0` final-pass strips all templates from `msg[0]` but does NOT write to `stripped_msg_removed`. SR blocks captured only by the final pass show as `(captured=0, bypassed=0, n/a)`. SR blocks in `msg[N>0]` that bypass the elif chain are counted as bypassed.

**Input:** JSONL paths (positional, optional). Default: newest 3 `api_requests_opus_monitor_cc_*.jsonl`.

**Output:** `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_sr_bypass_audit.md`. Path printed to stdout.

**Usage:**
```bash
# Auto-pick newest 3 proxy logs
./venv/bin/python3 dev/tool_use_analysis/sr_bypass_audit.py

# Explicit log
./venv/bin/python3 dev/tool_use_analysis/sr_bypass_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl
```

---

## strip_audit.py

**Purpose:** Reads a single Proxy JSONL file, filters to claude-opus-* entries only (skips Haiku subagents and null-model `sent_meta` entries), iterates requests in order, and classifies each REQ into five buckets using rule-counter deltas and marker-based chunk attribution from `src/proxy/strip_vocab.py`. Solves four flaws in the old format: (1) index-diff NEW-STRIP detection missed mc=1 secondary calls where `smi=[0]` in both prev and curr; (2) chunk attribution used template `startswith` instead of the proxy's actual capture marker, misattributing "As you answer…" claudeMd blocks; (3) `pass_mods` inert firings were indistinguishable from real strips; (4) pauschal FP flag on any tool_result was too broad.

**Input:** Single Proxy JSONL path (positional, optional). Auto-picks newest `src/logs/api_requests_opus_monitor_cc_*.jsonl` when no path is given.

**Output:** `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_strip_audit.md`. Report path is also printed to stdout. Four sections:

1. **Legend** — generated by `strip_vocab.legend_markdown()`. Three sub-tables: Buckets (EFF/INERT/IDX/LEAK/SUS with descriptions), Rules (code → full modifications[] name → attribution markers), Tag Literals (PO/SR/TN/ND → raw tag). Compact notation note at the bottom.
2. **Rule Catalog** — deeper reference: SR Templates table (`_SR_TEMPLATES` → `modifications[]` rule name, identifier, mode); Non-SR Rules table (`trimmed_task_notification`, `stripped_rejection_message`, `<persisted-output>` no-rule marker); Attribution Note explaining the marker-inversion logic.
3. **Delta Log** — one block per opus REQ in compact `BUCKET:RULE` notation:
   - `EFF:CODE  msg[idx] [tool_result:Name]  N chunk(s)  Xc` — rule newly fired + chunks attributed. Followed by `chunk[i] "head..."` per chunk.
   - `INERT:CODE` — rule newly fired, 0 attributable chunks (phantom firing from `pass_mods` sibling).
   - `IDX  msg[idx] [tool_result:Name]` — index newly in `smi` but `stripped_msg_removed[idx]` empty/missing (Final-Pass tracking gap; rules.py:197-208 updates `stripped_msg_indices` but not `stripped_msg_removed`).
   - `LEAK:<SR>/CODE  "head"` — SR tag in raw_payload after rule fired. `LEAK:<TN>` for TN tag.
   - `SUS:<PO>` / `SUS:<SR>/CODE  "head"` / `SUS:<TN>` — tag in raw_payload, no rule fired.
4. **Summary** — total REQs, REQs with EFF strips, INERT count, IDX count, SUS/LEAK occurrences.

**Attribution:** Chunk→rule attribution (`strip_vocab.attribute_chunk`) inverts the proxy's capture logic. `_find_system_reminder_blocks(content, MARKER)` captures SR blocks containing MARKER anywhere. Attribution checks each chunk for the MARKER substring; first match in `RULES` order wins. `TN` uses starts-with check (chunks always begin with `<task-notification>`). `ALL` (Final-Pass) has no markers and never appears in EFF — always INERT or triggers IDX.

**Usage:**
```bash
# Auto-pick newest log
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py

# Explicit JSONL path
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl

# Explicit output path
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl \
  --output dev/tool_use_analysis/md/202604221808_strip_audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `jsonl` | *(positional, optional)* Proxy JSONL path | auto-picks newest in `src/logs/` |
| `--output FILE` | Output markdown file path | `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_strip_audit.md` |

**LEAK vs SUSPECT classification:**
- `LEAK` — known tag found in `raw_payload.messages` AND the relevant strip rule appears in `modifications[]`: rule fired but tag survived (strip missed the occurrence, e.g. embedded in tool_result content not at line-start).
- `SUSPECT` — known tag found in `raw_payload.messages` AND no relevant rule fired: no rule applies (new tag type, or rule disabled). `<persisted-output>` is always SUSPECT (rule rolled back, no replacement).
- Unrecognized SR blocks (inner text matches no `_SR_TEMPLATES` identifier) are intentional non-strips and are NOT flagged.

**False-positive heuristic:** removed. The old pauschal `⚠ SUSPECT FALSE POSITIVE` flag was emitted on any stripped message with `tool_result` content — too broad (legitimate task-tools-nag strips in Read tool_results were misflagged). Tool_result context (`[tool_result:Read]`) is now shown inline in `EFF:*` and `IDX` lines for information, without attaching a suspect label.

---

## sr_session_audit.py

**Purpose:** Longitudinal SR audit across all Claude Code session JSONLs under `~/.claude/projects/*/*.jsonl`. For each user-role message, extracts `<system-reminder>` blocks (linestart-anchored, mirror of `_STANDALONE_SR_RE` in `src/proxy/strip_sr.py`), classifies against the live strip catalog imported from `_SR_TEMPLATES` in `src/proxy/strip_sr.py` + `_PRESERVE_PREAMBLE` (no duplication), and reports known/preserved/unknown buckets with per-bucket layer split (text vs tool_result), date timeline (first/last seen), and CC version attribution. Designed to surface (a) which catalog templates have empirical hits in modern CC versions, (b) which SR templates are leaking through (gap candidates for catalog extension).

**Input:** `~/.claude/projects/*/*.jsonl` (all CC project session files). Optional positional substring filter on project directory name.

**Output:** Markdown report at `dev/tool_use_analysis/md/<YYYYMMDDHHMM>_sr_session_audit.md` (auto-generated, override via `--output`). Path printed to stdout. Sections: header (run metadata), Scan Parameters (incl. noise filter description), Known Templates table, Preserved table, Unknown / Gap Candidates table (top N), Top-N Unknown sample text (full inner text up to 600 chars per bucket).

**Usage:**
```bash
# Default: all projects, since 2026-04-16 (Opus 4.7 / CC 2.1.x cutoff)
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py

# All sessions (pre-cutoff included)
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py --since 2026-03-01

# Single project
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py Monitor-CC --since 2026-04-16

# Custom output path
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py --output /tmp/audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `project_filter` | *(positional, optional)* Substring match on project dir name | `''` (all projects) |
| `--since YYYY-MM-DD` | Skip messages older than this date | `2026-04-16` |
| `--output FILE` | Output Markdown path | `dev/tool_use_analysis/md/<ts>_sr_session_audit.md` |
| `--top N` | Show top-N Unknown buckets in detail tables | `30` |

**Noise filters:**
- **code-heuristic** — drops SR matches whose inner text starts with regex syntax (`.*?`, `\s*`, `(.*`, `...`, `\n`, `\d+\t` line-number prefix) or contains code markers (`re.compile`, `re.escape`, `_SR_TEMPLATES`, `_TAG_`, `_STRIP_`, ` def `). Applies to ALL classifications. Counted under `n_code_noise`.
- **data-file-noise (Option A)** — UNKNOWN-bucket only. Drops SR when the 120 chars of context BEFORE the `<system-reminder>` tag contains `\d+\t` (Read-tool line-number prefix). Indicates the SR was read FROM a data file (e.g. old session JSONL excerpts in `/tmp/`, audit reports referencing the SR text) rather than INJECTED by CC. Known/Preserved templates are never filtered by this rule. Counted under `n_data_file_noise`.

**Classification logic (mirrors `_match_template()` in `src/proxy/strip_sr.py`):**
1. Inner stripped of leading/trailing whitespace.
2. If matches `_PRESERVE_PREAMBLE` (`"As you answer the user's questions, you can use the following context:"`) → `PRESERVED`.
3. For each template in `_SR_TEMPLATES`, identifier(s) checked via `inner.startswith(ident)`. List identifiers tried with OR semantics (e.g. `claudemd-contents` has `["As you answer the user's questions", "Contents of "]`). First match wins. → `KNOWN:<template_id>`.
4. Otherwise → `UNKNOWN` (after data-file-noise check).

**CC version extraction:** session JSONL entries carry top-level `version` field (e.g. `"2.1.114"`). Per-bucket `versions` set tracks all distinct CC versions where the SR appeared. Entries lacking `version` field are recorded as `unknown`.

---

## Generated Reports

### 202604221808_strip_audit.md
Per-REQ strip delta audit (`strip_audit.py`) for session `api_requests_opus_monitor_cc_1776871226.jsonl`. 38 opus REQs. 8 REQs with new strips. Key signals: `trimmed_task_notification` leaking `<task-notification>` into `raw_payload` on every REQ from #6 onward (rule fires but TN blocks survive in tool_result content). `<persisted-output>` present in every REQ from #2 (no active rule). False-positive strips: 5 (Read/Bash/Write tool_results containing SR tags from source code or docs).

### 20260422_session_waste_patterns.md
Signature-normalized analysis (`extract_patterns.py`) across 6 JSONLs (4 from 2026-04-21 evening + 2 from 2026-04-22). 528 unique tool_use blocks. Content-transfer excluded: Write (30 calls, 176k chars), Edit (38 calls, 46k chars), Bash(`bd*`) (19 calls, 12k chars), worker_send (15 calls, 9k chars). Actionable waste: Bash 99.3% (89 calls, 51k chars), Grep 0.7% (2 calls). Top Bash patterns: heredoc-python (structural) + `worker-cli status` (8 calls, 1k, trivial). 9 failed-call patterns; 11 failed calls total.

## Older Reports (in md/)

### 20260418_github_cli_failures.md

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`

Documents four categories of GitHub CLI (`gh-cli` Skill / `grep_repo` / `grep_file`) failures encountered during the warnings-pane-fixes session: missing `repo:` qualifier in `search_code`, POSIX `\|` vs Python `|` regex escaping confusion, wrong file path argument to `grep_file`, and wrong constant names (`WheelUp` vs `MOUSE_WHEEL_UP`). Includes root-cause analysis and fix directions for each failure.

### 20260419_baseline.md
Baseline run on all 17 Proxy JSONLs (default mode, `--min-chars 500`). Top offenders: Write (Ø 6,775 chars), Edit (Ø 1,854 chars), Bash (Ø 1,391 chars).

### 20260419_bash_deepdive.md
Bash-only deep-dive (`--tool Bash --top 50 --min-chars 500`) on all 17 Proxy JSONLs. Includes Command-Prefix Clustering. Top clusters by total_chars: `python3 [heredoc]` (35 calls, 69k chars), `bd` (36 calls, 59k chars), `python3` inline (39 calls, 52k chars).

### 20260419_ratio_analysis.md
Ratio analysis (`--ratio --top 50`) on all 17 Proxy JSONLs — 1,207 matched pairs. Bash leads with max ratio 191.62 (3k chars input → 16 chars output). Read is most efficient (median ratio 0.02).
```

## Salvage from dev/tool_use_errors/DOCS.md

```
# dev/tool_use_errors/

## Role

Empirical audit suite for `src/logs/tool_errors.jsonl`. Determines which error patterns
are agent-relevant (KEEP) vs strippable CC-wrapper noise, and verifies that
`strip_hook_prefix.py` strips the hook-error prefix before it reaches Anthropic.

## Scripts

### A_error_cluster_audit.py (365 LOC)

Loads `tool_errors.jsonl` → clusters by error shape → classifies each bucket → cross-checks
via available proxy logs whether `strip_hook_prefix.py` modifications reach Anthropic.

```bash
./venv/bin/python dev/tool_use_errors/A_error_cluster_audit.py
# Output: dev/tool_use_errors/md/YYYY-MM-DD_error_cluster_audit.md
```

**Buckets produced:**

| Bucket | Match rule | Verdict |
|--------|-----------|---------|
| `hook_prefixed` | `^PreToolUse:\w+ hook error: \[python3 ` | HISTORICAL (pre-strip-hook) |
| `tool_use_error` | `^<tool_use_error>` | KEEP |
| `exit_code_nonzero` / `exit_code_0` | `^Exit code \d+` | KEEP |
| `rejection` | contains `doesn't want to proceed` | ALREADY_STRIPPED by proxy |
| `bare_guidance` | residual (hook guidance text + CC tool errors without wrapper) | KEEP |

**Cross-check:** Scans `src/logs/api_requests_*.jsonl` for `stripped_hook_error_prefix`
modification entries to confirm the proxy strip reaches Anthropic. Also compares
`hook_prefixed` timestamps against the first strip occurrence to verify historical status.

## Reports

Output: `md/2026-05-30_error_cluster_audit.md` (first run; subsequent runs add `YYYY-MM-DD_error_cluster_audit.md`)

**Key findings (2026-05-30 run):**
- 495 entries total; no new strippable patterns found
- 59 hook_prefixed entries are historical (pre-strip-hook, 2026-05-24T20:59 – 2026-05-25T01:26)
- `strip_hook_prefix.py` confirmed active in 2,970 requests across 65 proxy log files
- All content after stripping is agent-relevant (KEEP) — `strip_hook_prefix.py` is sufficient
```

## Salvage from dev/verbosity/DOCS.md

```
# dev/verbosity/

## Role
Holds analysis of redundancy in this assistant's own chat output, transferring the
process-efficiency measurement from Chen et al., "Do NOT Think That Much for 2+3=?" from
LLM solution-rounds to Opus turn-exchanges, plus the frozen extraction the analysis was run
against. `extract_turns.py` is the only producing script, and it produces the corpus, not
the analysis: the clustering itself is a manual, per-exchange semantic judgment against a
fixed criterion (does a later exchange add a decision-relevant fact not already present in
an earlier exchange of the same turn), not a reusable pipeline — a future pass over new
turns would need a fresh manual read, not a re-run of code.

## Files
- `extract_turns.py` — reads every `~/.claude/projects/-Users-brunowinter2000-Documents-ai-monitor-cc/*.jsonl`
  session file, reconstructs Opus turns (one user message followed by consecutive
  Opus-model assistant text blocks), splits each turn's text into numbered exchanges on
  bold-point / 🛑 lines, keeps only turns with 4+ exchanges, and writes the result to
  `/tmp/k2_turns.md`. Path and output location are hardcoded (`/tmp/k2_turns.md`), not a
  CLI argument.
- `corpus/sessions/*.jsonl` — frozen copies, dated 2026-08-27, of the 7 raw Claude Code
  session JSONL files `extract_turns.py` was actually run against (originals live under
  `~/.claude/projects/-Users-brunowinter2000-Documents-ai-monitor-cc/`, not in this repo).
  Original basenames kept so the 8-char session-id prefixes in the report's turn headers
  stay resolvable to a file: `451ad7c7`, `96699adf`, `defdd334`, `16cd91af`, `587284d6`,
  `04ca8d8c`, `80b146dd`. 20 MB total on disk — a real, deliberate cost, not an accident;
  see "Raw session logs" below for why they were brought in anyway.
- `corpus/k2_turns.md` — the exact output `extract_turns.py` produced on 2026-08-27 (126
  turns, 626 exchanges, 306 KB), copied byte-for-byte from `/tmp/k2_turns.md` into the repo
  for persistence. This is what `md/20260827_k2_distinctness.md` was actually clustered
  against — verify the report's numbers against this file, not against a fresh run.
- `md/20260827_k2_distinctness.md` — per-turn distinctness table for 126 turns (626
  exchanges), a per-exchange-index aggregate (Chen Figure 6 analog), and the ten
  lowest-distinctness turns quoted in full with per-exchange cluster labels. States the
  measured corpus-wide distinctness (0.952) against a pre-registered prediction and flags
  the turns that required a judgment call beyond the stated criterion. Section 2a re-runs
  the position aggregate indexed from the END of each turn instead of the start, with the
  full 30-row list of redundant exchanges (turn, index, end-offset) that both distribution
  tables are computed from — this discriminates a "redundancy grows with depth" reading
  from a "redundancy is a closing-exchange role effect" reading; the probe rules out the
  former (see `process-docs/verbosity/` for the write-up).

## Relation between the files, and why `corpus/` is frozen

`corpus/sessions/*.jsonl` (raw) → `extract_turns.py` (filter: Opus-authored text only, no
tool calls or tool output) → `corpus/k2_turns.md` (126 turns, 626 exchanges) → manual
clustering → `md/20260827_k2_distinctness.md`. Every stage from raw log to published report
is now checkable from files committed in this directory, none of it from `/tmp`.

**Both `corpus/sessions/` and `corpus/k2_turns.md` are frozen snapshots, not regenerated on
every run.** Re-running `extract_turns.py` today would read the *live* session JSONL files
under `~/.claude/projects/...` in their current (further-grown) state, not the frozen copies
under `corpus/sessions/` — the script's source path is hardcoded to the live location, it
does not read from this directory. A fresh run is therefore not guaranteed to reproduce the
same 126 turns byte-for-byte: the live sessions can gain lines between runs (session
`04ca8d8c` in particular is still an active session and grew between the original extraction
and the later raw-log copy). Do not re-run the script to "refresh" the corpus without a new
dated report — the existing report's per-turn table and quoted exchanges are checked against
the specific frozen `corpus/k2_turns.md` and `corpus/sessions/` committed here, and
regenerating either would silently break that correspondence.

## Raw session logs: why they're here, and the secret-scan result

The 7 files under `corpus/sessions/` are full session transcripts, meaning they include tool
calls and tool output, not just Opus's prose (unlike `corpus/k2_turns.md`, which is filtered
to prose only). Full transcripts can carry secrets surfaced by tool output — API keys,
tokens, `.env` contents, credentials in command lines — so before committing them they were
scanned in place (unmodified, pre-copy) against 15 targeted patterns (AWS keys, Anthropic
`sk-ant-`, OpenAI `sk-`, GitHub tokens, Slack tokens, Bearer headers, JWTs, PEM private-key
headers, `.env`-style KEY=VALUE assignments, password assignments, basic-auth-in-URL,
`ssh-rsa`/`ssh-ed25519`, `BEGIN CERTIFICATE`) plus a broad word-frequency pass and a
high-entropy-string sweep (1,357 candidates ≥32 chars, entropy >4.5 bits/char, all
individually classified). Result: zero credential material found. The only findings were
benign — 430 base64 blobs are Claude's own extended-thinking signature tokens (standard,
opaque, present in every Claude Code session log), 26 are pasted-screenshot image data, the
rest are long filesystem paths and URLs. One `.env` file's *existence* (not contents) was
visible via an `ls -la` listing in one session; its contents were never displayed in any of
the 7 files. Full scan write-up: `process-docs/verbosity/`.
```

## Salvage from dev/worker_status_probes/DOCS.md

```
# dev/worker_status_probes/

Probe suite for empirically evaluating three candidate tmux activity sensors as replacements
for the JSONL-mtime demote rule in `_worker_detect_status` (iterative-dev plugin: `tmux_spawn.sh`, bash — not in `src/`). Produces raw CSVs and a
side-by-side comparison report.

## Usage

From project root:
```bash
./venv/bin/python dev/worker_status_probes/run_all.py [--duration N]
```
`run_all.py` discovers the Opus main session dynamically and launches all three probes
concurrently. The comparison report lands in `md/`; raw per-probe CSVs land in `csv/`.

## Modules

### run_all.py (121 LOC)

**Purpose:** Orchestrator. Discovers Opus main session (most recently active non-worker
window), launches probe_a/b/c as concurrent subprocesses with a shared timestamp.
**Reads:** tmux `list-windows` to find Opus session.
**Writes:** nothing directly — delegates to probe scripts.
**Called by:** user / Opus directly.
**Calls out:** `probe_a.py`, `probe_b.py`, `probe_c.py` via subprocess.

---

### probe_a.py (80 LOC)

**Purpose:** Polls `#{window_activity}` (Unix timestamp) for each target session every
1 second. Logs delta=1 when the window received bytes since the last sample, delta=0
when silent.
**Reads:** tmux `display-message -t <session>:0 -p '#{window_activity}'` per tick.
**Writes:** `csv/raw_probe_a_<ts>.csv` (cols: elapsed_sec, session, window_activity_ts, delta).
**Called by:** `run_all.py`.
**Calls out:** tmux CLI only.

---

### probe_b.py (135 LOC)

**Purpose:** Activates `tmux pipe-pane` for each target session; routes pane output through
`byte_touch.py` which touches an activity file and logs cumulative byte count. Samples both
every 1 second.
**Reads:** `/tmp/probe-b-<name>.activity` mtime; `/tmp/probe-b-<name>.bytecount` total.
**Writes:** `csv/raw_probe_b_<ts>.csv` (cols: elapsed_sec, session, activity_mtime, bytecount_total, bytes_last_sec).
**Called by:** `run_all.py`.
**Calls out:** tmux `pipe-pane`; spawns `byte_touch.py` via pipe-pane.

---

### byte_touch.py (51 LOC)

**Purpose:** stdin reader helper for probe_b. On each non-empty read: `os.utime(state_file)`
+ overwrites bytecount_file with cumulative total. Invoked by tmux pipe-pane; uses system
python3 (stdlib only).
**Reads:** stdin (pane output piped by tmux).
**Writes:** state_file mtime (touch); bytecount_file (overwrite with total).
**Called by:** tmux `pipe-pane` command, not directly.
**Calls out:** stdlib `os` only.

---

### probe_c.py (169 LOC)

**Purpose:** Spawns `tmux -C attach-session` per target session (no PTY needed on macOS).
Reader threads parse `%output` / `%extended-output` events filtered to window 0 pane IDs.
Samples event+byte counters each second.
**Reads:** `proc.stdout` line-by-line per session (control mode protocol stream).
**Writes:** `csv/raw_probe_c_<ts>.csv` (cols: elapsed_sec, session, events_last_sec, bytes_last_sec).
**Called by:** `run_all.py`.
**Calls out:** tmux `-C` subprocess; `threading.Thread` per session.

---

## Output

```
csv/
├── raw_probe_a_<ts>.csv    — window_activity timeseries (360 rows for 3 sessions × 120s)
├── raw_probe_b_<ts>.csv    — pipe-pane byte timeseries
└── raw_probe_c_<ts>.csv    — control-mode event timeseries
md/
└── comparison_<ts>.md      — side-by-side analysis + per-sensor verdicts + recommendation
```

## Gotchas

- Probe B leaves `tmux pipe-pane` active if the process is SIGKILL'd without running atexit.
  Recovery: `tmux pipe-pane -t <session>:0` (no args) stops piping. Verify with
  `tmux display-message -t <session>:0 -p '#{pane_pipe}'` == `0`.
- Probe C `bytes_last_sec` is tmux escaped-payload length, NOT actual byte count (~1.65×
  larger than pipe-pane byte count due to octal escaping). Use `events_last_sec` as the
  primary signal for Probe C.
- `run_all.py` targets window 0 of non-worker sessions to avoid bead-tracker noise from
  windows 3–4 of monitor_cc_* sessions.
```

## Salvage from dev/workers/DOCS.md

```
# dev/workers/

## Role

Development scripts for `src/workers/` changes — regression harnesses that verify a refactor of
`worker_pane.py`/`worker_format.py`/its sibling modules changes zero observable output. Touch
this directory when adding a new workers-pane regression check; do not touch for
`src/proxy_display/` changes (see `dev/proxy_display/`, `dev/pane_search/` for those).

## Modules

### format_byte_identity.py

**Purpose:** Byte-identity regression harness for `src.workers.worker_format.format_workers_block`.
Builds a synthetic 3-worker list (varied status/tokens/context_pct/purpose), expands one of them
with turns loaded from a real worker JSONL under `~/.claude/projects/` when one exists (bounded to
its first 200 lines and the first 10 extracted turns — a stable prefix even if the source file
keeps growing; falls back to synthetic turns otherwise), renders across a matrix of
`(frozen, selected_name, copy_feedback, search_match_set/search_current_key/search_query)`
argument combinations at two pane widths (`os.get_terminal_size()` monkeypatched —
`format_workers_block` detects width internally, no width parameter), and hashes every rendered
`(all_lines, line_keys, regions_out)` triple.

**`WORKERS_BYTE_IDENTITY_JSONL` env var** overrides the source JSONL path — needed to pin a
before/after comparison to the exact same bytes when the default "newest JSONL under
`~/.claude/projects/`" pick can itself be a different file across two runs, or (rarer, since the
harness already bounds to a fixed-size prefix) a session actively growing during the comparison
window. Same pitfall class as `dev/proxy_display/render_byte_identity.py`'s
`RENDER_BYTE_IDENTITY_LOG_DIR` — see that module's own Gotcha. Snapshot a real JSONL to a fixed
path once, then point both runs at it via the env var for full reproducibility.

**Reads:** One worker JSONL file under `~/.claude/projects/*/` (or `$WORKERS_BYTE_IDENTITY_JSONL`).
**Writes:** Nothing — stdout only (one `HASH: <hex>` line).
**Called by:** Run manually from project root; imports are all local (inside functions), per the
`block_dev_imports_src` hook's indentation-based exemption.
**Calls out:** `src.jsonl` (`read_new_lines`, `parse_jsonl_lines`, `extract_cache_turns`),
`src.workers.worker_format` (`format_workers_block`)

## Gotchas

**The default JSONL source can be a live, actively-growing transcript.** Any script under this
directory that reads `~/.claude/projects/` directly (rather than a frozen copy) risks picking THIS
very agent's own session file as "newest". `format_byte_identity.py` mitigates this by bounding to
a fixed-size prefix of whatever file it reads (append-only growth past that point never changes
the read content) — for a fully pinned before/after comparison across a longer work session, still
prefer `WORKERS_BYTE_IDENTITY_JSONL` pointed at a one-time snapshot.
```

