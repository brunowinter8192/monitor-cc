This file is the salvage of the format cut for the DOCS.md files brought into compliance by
worker docs-dev-a, dated 2026-09-11: `dev/DOCS.md` and every `dev/<area>/DOCS.md` for
bg_wakeup_id_line, cc_injection_inventory, cc_internals, click_ui, constants, cursor_edges,
desktop_detection, display (+ display/jsonl_exploration), gpu_pane, hook_error_correlation,
hook_smoke, hotkey_latency, jsonl, menubar_nspanel, menubar, model_selector, monitor_lifecycle.
Every paragraph, dated note, "split from"/"renamed"/"reverted" narrative, function-by-function
walkthrough, and hash/verification-status line removed from these files during the rewrite to the
DOCS.md Format is captured below, grouped by the DOCS.md it came from and the module it described,
before being cut. Nothing here is maintained after this entry closes.

## Salvage from dev/DOCS.md

The pre-rewrite file was a single flat index over ~50 dev/ areas (most out of this worker's
scope). The full pre-rewrite body, including entries for areas NOT in this worker's scope (left
untouched on disk, salvaged here only because they lived in the same file that got rewritten):

```markdown
# Dev Scripts

Development and testing scripts for Monitor_CC pipeline components.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

```bash
cd Monitor_CC/
```

## Documentation Tree

- [display/DOCS.md](display/DOCS.md) — Display layer tests + format_cache_tracker differential proof
- [jsonl/DOCS.md](jsonl/DOCS.md) — extract_cache_turns differential proof harness
- [hook_error_correlation/DOCS.md](hook_error_correlation/DOCS.md) — Hook-caused tool-error overlay analysis (`hook_firing.jsonl` × `tool_errors.jsonl`); `md/` also holds the historical 2026-05-22 hook block-event snapshot
- [pipeline/DOCS.md](pipeline/DOCS.md) — Pipeline evaluation suite (memory, I/O, parsing, format stability)
- [session_analysis/DOCS.md](session_analysis/DOCS.md) — Forensic session JSONL + proxy log analysis (cache behavior, rebuild detection, token attribution)
- [tool_injection/DOCS.md](tool_injection/DOCS.md) — MCP tool schema extraction for proxy-side tool injection
- [tool_use_analysis/DOCS.md](tool_use_analysis/DOCS.md) — Tool-use input size extraction (Proxy JSONL) + zero-result detection (Session JSONL)
- [tool_use_errors/DOCS.md](tool_use_errors/DOCS.md) — Empirical audit of `src/logs/tool_errors.jsonl` — cluster analysis + strip_hook_prefix.py cross-check (2026-05-30)
- [cursor_edges/DOCS.md](cursor_edges/DOCS.md) — NSPanel cursor-rect investigation probe — edge hover ↔/↕ blockers (NonactivatingPanel, subview coverage, mask conflicts)
- [menubar_nspanel/DOCS.md](menubar_nspanel/DOCS.md) — NSPanel sticky-toggle probe suite — persistent menubar panel replacing NSMenu auto-dismiss behavior
- [cc_internals/DOCS.md](cc_internals/DOCS.md) — CC binary + source research artifacts — env-var inventory from npm binaries, cross-referenced against community decompiles
- [ToolsSystemPrompts/DOCS.md](ToolsSystemPrompts/DOCS.md) — Captured CC built-in tool definitions + sys[3] segment — char-count corpus for proxy tool-injection/stripping budget analysis
- [ram_audit/DOCS.md](ram_audit/DOCS.md) — Pane RAM snapshot investigation — SIGUSR1 dump handler + `dump_all.sh` for live RSS/allocator capture across all panes
- [sleep_pattern_analysis/DOCS.md](sleep_pattern_analysis/DOCS.md) — Empirical audit of `block_chained_sleep` firing events; classifies cmd_before tokens as trivial-sync / load-bearing / mixed to inform `rewrite_chained_sleep.py` design
- [hook_smoke/DOCS.md](hook_smoke/DOCS.md) — Hook blocking/rewrite smoke tests — one test script per hook (block_dangerous_kill, block_read_worktree, rewrite_chained_sleep; block_chained_sleep preserved for reference; test_fire_log added 2026-05-24); also holds `test_bg_task_detection.py` + `probe_bg_task_live.py` for `proc_cache.py::_has_active_bg` (menubar background-task predicate, not a hook — added 2026-07-30)
- `bead_tracker/` — `smoke.py`: end-to-end smoke for `bead_tracker_hook` per-subcommand processing (4 cases: single, chained `;`, cross-project skip, pipe non-split); creates/deletes real test beads; no own DOCS.md
- [strip_fp_tool_result/DOCS.md](strip_fp_tool_result/DOCS.md) — Audit: which strip passes remove content from inside `tool_result` blocks, split SR strip family vs. unrelated non-SR passes; measurement only
- [proxy/DOCS.md](proxy/DOCS.md) — Per-pass unit tests + targeted replay proofs for individual proxy strip/inject passes (message_passes.py sub-passes, rules_config.py) and a bash regression for the proxy marker-file lifecycle (claude_proxy_start.sh)
- [proxy_dual_log/DOCS.md](proxy_dual_log/DOCS.md) — Verification suite for the dual-log quartet written by src/proxy/addon.py — losslessness/self-consistency of the forwarded-delta log against the original, and completeness of the strip/inject diff engine
- [proxy_instrumentation/DOCS.md](proxy_instrumentation/DOCS.md) — Reconstructs/measures the proxy's real strip/inject pipeline from recorded dual-log payloads through the real production code, no live proxy required
- [bg_wakeup_id_line/DOCS.md](bg_wakeup_id_line/DOCS.md) — CC background-launch-ack wording inventory (`p1_`) + tmux-Escape-on-launch-ack mechanism verification (`p2_`, `src/proxy/bg_escape.py`); `md/` holds both scripts' reports
- [pane_error_log/DOCS.md](pane_error_log/DOCS.md) — Regression coverage for the shared exception-safe pane-error sink (`src/pane_error_log.py`) and the exception guard on all 9 pane event loops — catch+log+continue, `KeyboardInterrupt`/`SystemExit` passthrough, failing-log-write safety, sink size-capping
- [click_ui/DOCS.md](click_ui/DOCS.md) — Click-UI milestone series (every pane control mouse-clickable) — Milestone 1: worker-selection click-region parity vs. digit keys, worker-proxy header + workers pane
- [hotkey_latency/DOCS.md](hotkey_latency/DOCS.md) — Menubar hotkey-lag investigation tooling: `GetEventTime`/`GetCurrentEventTime` probe + `menubar.log` `[latency]` line parser/report generator; measurement only, no `src/` behavior change
- [thinking/DOCS.md](thinking/DOCS.md) — Verification for the proxy pane's thinking display features: the per-request 🧠 brain-marker badge (`has_thinking_delta`, delta vs. cumulative cross-check) and the thinking-block drill-down + wrapping in the expanded REQ view (collapsed/expanded/byte-identical checks against a pre-change git snapshot) — both render through the real parse+render path against a real `_forwarded` dual-log
- [monitor_lifecycle/DOCS.md](monitor_lifecycle/DOCS.md) — Load probe for `monitor_cc_*` tmux sessions (per-pane mode/PID/age/CPU snapshot, `reports/` holds dated baselines) + regression test for `src/monitor_janitor.py`'s daily sweep (`tests/`, real throwaway tmux sessions) + gate test for `src/menubar/monitor_sweep_scheduler.py`'s at-most-once-per-24h tick trigger (`tests/`, isolated temp state, no real tmux)
- `menubar_per_project/` — `test_open_or_focus_monitor.py`: unit tests for the per-project menubar monitor button's pure/branch logic (`src/menubar/system.py:_open_or_focus_monitor`) — session-name reuse from `tmux_launcher.py` (never re-derived), the focus-vs-launch branch given `check_session_exists`, and launch-command quoting for a cwd containing a space; no own DOCS.md

## session_analysis/

See [session_analysis/DOCS.md](session_analysis/DOCS.md).

6 standalone analysis scripts (01–06) + `md/` for `05_req_breakdown.py` output. No pipeline mapping.
```

---

## Salvage from dev/bg_wakeup_id_line/DOCS.md

### p1_scan_launch_ack_wordings.py
Original purpose prose: "Inventories distinct CC background-launch-ack wordings in the recorded
corpus (`src/logs/dual_log/*_original.jsonl`), dedups cumulative dual-log duplication, evaluates
the 3 real recognition mechanisms (`src/proxy/strip_bg_launch_ack.py`) against each wording."
"Called by: run manually — measurement only, not a regression guard."

### p2_bg_escape_probe.py
Full original purpose text: "Verifies `src/proxy/bg_escape.py` — the tmux-Escape-on-launch-ack
mechanism. 8 test groups: dedup across repeated acks (real 142/169 shape), two distinct task ids
→ two Escapes, both CC wordings trigger, a `main` (non-worker) context never triggers, tmux
session name derivation from `PROXY_LOG_ID` + `PROXY_PROJECT_PATH` (including a hyphenated worker
name), a fire writes one JSONL trace line to `bg_escape_events.jsonl` under a
`MONITOR_CC_ROOT`-scoped temp dir (task id, tmux session, send result), a main-context skip logs
`reason='main_context'`, and a request with no ack chunk at all never creates the log file
(2026-07-30), a real tmux round trip (throwaway session, real `send-keys`, `capture-pane` proof),
and failure isolation (dead/missing tmux session, missing `tmux` binary — both at the unit level
and through a real `ProxyAddon.request()` call with the binary simulated absent)."
"Called by: run manually — regression guard for `bg_escape.py`; re-run after any change to
`strip_bg_launch_ack.py`'s detection or `addon.py`'s worker-context derivation."

### p3_strip_interrupt_marker_probe.py
Full original purpose text: "Verifies `src/proxy/strip_interrupt_marker.py` and its full wiring
through `message_passes.py` / `rules.py` / `strip_vocab.py` / `strip_inject_delta.py`. 7 test
groups: the real measured 3-block shape (`tool_result` / marker(+trailing `\n`) / injected
wake-up) with byte-identical neighbors after strip, all 4 content shapes, the 2nd real wording
("for tool use"), the false-positive class (marker embedded inside longer text left untouched,
incl. a real corpus-derived 180-char quote), message-pass role-gating + mod naming,
`strip_vocab`/`_MSG_CODE_TO_FN` attribution (`IM` code, both wordings), and a full-pipeline check:
real `apply_modification_rules` → real `_build_stripped_injected_deltas`, asserting
`fn_map['msg.0.1'] == '_apply_interrupt_marker_strip'` (not `'unknown'`)."
Original Reads note (measurement provenance, not currently reproducible): "The 2026-07-30
header's '1791 occurrences' figure was an uncorrected per-request-log count and never
reproduced; the 2026-07-31 re-measurement (last/fullest line per
`src/logs/dual_log/*_original.jsonl` session file) found 11 real occurrences across 5 session
files, all trailing-`\n`-terminated, in 2 wordings — reproduced here as synthetic fixtures, not
re-scanned (no real dual-log corpus in this worktree)."

### Gotchas (kept nearly verbatim in the rewrite, salvaged here for the cut framing sentence)
Original framing sentence dropped: "see `process-docs/escape_idle_worker/2026-07-30_tmux_escape_edge_trigger.md`
for the original diagnosis of this failure mode" — a single-entry cross-reference, replaced with
an area-level cross-reference per the docs rules (cross-references point at areas, not files).

---

## Salvage from dev/cc_injection_inventory/DOCS.md

Original heading was `## Purpose` (kept as prose, folded into Role in the rewrite). Full original
paragraph: "Reusable audit tool that produces a COMPLETE INVENTORY of every distinguishable text
class present in the raw request payloads Claude Code sends, as captured in
`src/logs/dual_log/`. An inventory, not a top-N filter: every class found is listed regardless of
frequency or size. Answers 'what text classes exist and are any of them unhandled?' — complements
`dev/proxy_dual_log/attribution_coverage.py`, which answers 'does every entry our proxy already
strips have a named function?' (that tool never sees content our proxy does NOT touch; this one
does, by classification rather than log-diff)." (The comparison to `attribution_coverage.py`
stays in the rewrite's Role — it's a boundary statement, not history.)

### Methodology notes section (fully removed as function-level/rationale detail)
- "Dedup key: `(file, role, section, block_type, exact segment text)` — segment-granularity
  refinement of the prior `(file, exact full message content)` convention, so a message combining
  one repeated block with one new block credits only the new block as a new distinct occurrence."
- "tool_result vs top-level text. `tool_result.content` is OUR tool's own return value — a
  `<system-reminder>` or CLAUDE.md-preamble literal appearing INSIDE it is quoted DATA (a fetched
  issue body, a `strings` dump, source containing the tag as a string), never a CC wrapper. The
  CLAUDE.md-preserve and leftover-SR extraction passes (`_extract_claudemd_blocks`,
  `_extract_leftover_sr_blocks`) therefore only run on top-level shapes (`_TOP_LEVEL_SHAPES` =
  `plain_string`/`text`) — anything matching inside `tool_result` content stays part of that
  segment's `OURS` residual instead of being pulled out as `KEEP`/`UNCLASSIFIED`."
- "INJECTED — ground truth is the pipeline's OWN output, not a heuristic. `apply_modification_
  rules` returns `injected_msg_added` alongside `stripped_msg_removed` — chunks it actually ADDS.
  Every non-empty chunk found there (still present verbatim in the residual — subtracted out
  before further OURS/UNCLASSIFIED classification) becomes an `INJECTED` hit, grouped by
  normalized-template signature like the COVERED-ALL fallback. Currently the only message-level
  source is `strip_bg_completed.py`'s wake-up replacement text (fired via `_apply_first_pass`'s
  task-notification branch or `_apply_bg_exit_strip`)."
- "Grouping: COVERED = one rule code; KEEP = one known wrapper; OURS = one tool name or the
  single user/assistant-text bucket; INJECTED/UNCLASSIFIED = one normalized-template signature
  (paths/IDs/numbers -> placeholders). Top-level user text uses a two-phase pass: a normalized
  signature needs >=2 SUBSTANTIVELY DISTINCT variants at >=40 chars to count as a recurring CC
  template (`UNCLASSIFIED`). Distinctness is containment-collapsed (`_distinct_variant_count`):
  whitespace-only differences (a trailing-newline shape artifact observed mid-corpus) AND one
  variant being a verbatim substring of another (prefix/suffix/mid-string extension — one human
  message edited/resent as it grew, not a template recurring) both collapse to a single variant.
  Everything that doesn't clear the bar (singletons, short acks, collapsed pairs) folds into one
  `OURS` aggregate."
- "Known simplification: `role=user` segments are tested independently per block, not as part
  of the full multi-block message — every strip pass gates only on a single block's own content,
  so this does not change any COVERED/KEEP decision, but is a deliberate divergence from
  production's whole-message pass loop."
- "Self-scan exclusion: the default glob excludes THIS session's own worker log — any file
  matching `api_requests_worker_*` that also embeds the current task/worktree name
  (`_current_task_name`, detected from the `.claude/worktrees/<name>/` path) — since that file is
  written live while the script runs and would make the corpus non-reproducible mid-scan. Other
  (past/unrelated) worker session logs are NOT excluded. An explicit `--logs-glob` bypasses this
  entirely. Excluded files are listed in the report's Corpus section." (This one's calibration —
  that the exclusion depends on worktree nesting — was kept as a Gotcha in the rewrite.)

### Runtime note (removed as a one-time measurement, not a calibrated limit)
"Runtime: ~11s for the full corpus (~730 entries, ~4GB total, one file 3.9GB) on the reference
run — dominated by JSON parsing; classification itself is cheap because exact-text dedup means
the (expensive) real strip-pipeline call only runs once per distinct segment, never per raw
occurrence."

### Report shape note (removed — describes report structure, not the module)
"Report shape: opens with a 'Strip Candidates' summary (the `UNCLASSIFIED` rows only —
Class/Distinct occ./Cum. chars, sorted by cost — the direct answer to 'what should we strip that
we don't today') before Methodology/Corpus, then the full 5-section breakdown (one section per
origin, every row from the summary repeated there with full role/section/block-type/sample
context — the summary never drops or filters a row present in the full sections)."

---

## Salvage from dev/cc_internals/DOCS.md

Original "Touch this directory when adding new binary extracts or updating the env-var
inventory. Area pairs with `process-docs/cc_internals/`." — kept the area cross-reference framing
in the rewrite's Role, dropped "Touch this directory when..." editorializing (redundant with the
Role's own "when to touch it" guidance already required by the format).

Provenance table kept verbatim per Main's direction (not salvaged — see rewritten file).

---

## Salvage from dev/click_ui/DOCS.md

### Area-level Role (original, full milestone-by-milestone narrative)
"Regression coverage for the click-UI milestone series (making every tmux-pane control reachable
by mouse, not just keyboard). Milestone 1 covers worker selection in the worker-proxy pane header
and the workers pane. Milestone 2 covers copy-by-click in the tokens/warnings/workers panes (the
main pane's own copy-by-click case was removed 2026-09 along with the main pane itself, see
`process-docs/main_pane/`). Milestone 3 covers two of three remaining single-purpose keyboard
controls (workers freeze, warnings refresh) as pane-chrome buttons — the third (proxy undo) got a
button too but it was reverted 2026-07-30 per user decision after live-testing; `u` stays the
only way to undo. Milestone 4 covers gpu (digit keys 1-9 already covered by existing buttons; new
`[refresh]`) and news (new `[refresh]`). (2026-08-18, unrelated proxy-pane search feature
milestone: the proxy pane now HAS a permanent one-line header again — a search bar, not a
button, see `p3_button_click_probe.py`'s entry below.) (2026-08-18, rollout sub-milestone 3: the
worker-proxy pane also gained a permanent row-1 search bar, shifting
`_worker_proxy_header_regions` down by one row — `p1_worker_selection_click_probe.py`'s
wrap-straddle test calls `_format_worker_proxy_header` directly, bypassing the production shift
step, so it now replicates that shift itself before dispatching clicks; see that module's entry
below.) `md/` holds every run's report."

### p1_worker_selection_click_probe.py
"(2026-08-18, rollout sub-milestone 3) The wrap-straddle test calls `_format_worker_proxy_header`
directly (regions computed RELATIVE to the header's own top) rather than through
`_build_worker_proxy_output` (which shifts them by `_WP_SEARCH_BAR_LINES` for the new row-1
search bar) — the test now replicates that same shift itself right after the direct call, before
dispatching clicks, so the synthetic coordinates match what `_handle_worker_proxy_mouse` actually
expects (row 1 is reserved for the search bar; a header marker click at the OLD unshifted row 1
would otherwise be swallowed by the search-bar press branch instead). The click-parity test
(`test_worker_proxy_header_click`) needed no change — it already goes through the real
`_build_worker_proxy_output`, which performs the shift itself."

### p2_copy_click_probe.py
"(2026-09) `test_main_pane_copy_click` and its `mod_main_display`/`mod_monitor` imports removed
— the main pane it covered was deleted entirely (window 0 is now the tokens pane at full width,
see `process-docs/main_pane/`). Regression guards for two bugs found and fixed in an earlier
milestone: (1) `warnings_render._serialize_warnings` expected a `('error', idx)` tuple but
`error_line_map` stores a bare `int` — `y` silently copied `''` for every warnings row until
fixed; (2) `worker_pane._handle_workers_key`'s `y`-branch resolution order made the
`worker_cache_line_map` fallback dead code — hovering an expanded cache-call row always resolved
to the parent worker's identity instead of the specific call, fixed via
`_resolve_workers_hover_key` (closer-ancestor-wins)."

### p3_button_click_probe.py
"(2026-07-30) Proxy pane: `[undo]` button reverted — `u` stays the only way to undo. (2026-08-18)
Proxy pane: PERMANENT search-bar header added (Milestone 2, unrelated to the button revert — a
deliberate 'always visible' design principle, not a hidden-feature button).
`test_proxy_pane_permanent_search_bar_header` (renamed from `test_proxy_pane_reverted_no_header`,
whose assertions were the OPPOSITE of the new contract) asserts the new header+shift contract...
(2026-08-18, rollout sub-milestone 6) `test_warnings_refresh_button`'s row assertion updated.
`warnings_pane.py` gained its own permanent row-1 search bar — the pre-existing `[refresh]`
header region shifts from row 1 to row `1 + mod_warnings._WARNINGS_SEARCH_BAR_LINES` (row 2). The
ONE hardcoded `next(iter(regions))[2] == 1` assertion was updated to reference the constant
instead of a bare literal — same 'update the dependent test when a pane's row contract changes'
pattern as the worker-proxy wrap-straddle fix (sub-milestone 3) and identical to the shift every
other pane in this rollout applied; every OTHER assertion in this test already resolved `(sc, ec,
er)` dynamically and needed no change. `dev/click_ui/p4_gpu_news_button_probe.py` needed ZERO
changes for the gpu/news milestone (sub-milestones 7-8) — see that file's own DOCS entry below."

### p4_gpu_news_button_probe.py
"(2026-07-30 review fix) `test_gpu_refresh_button_width_sweep` / `test_news_refresh_button_width_
sweep`: sweep pane widths on both sides of each pane's button-visibility crossover (gpu 27, news
38 — both far below the panes' live widths of 215/107) proving the `'═'` decoration shrinks (fewer
chars than its cap, asserted directly) before `[refresh]` is dropped, that the button is
registered at every swept width at/above the crossover, and that the title text stays fully
visible even below it, closing the priority inversion where the fixed-length decorative rule ate
the space `[refresh]` needed first. (2026-08-18, rollout sub-milestones 7-8) Needed ZERO changes
for the gpu/news search-bar migration. Both panes' `_render_pane` kept its OWN row numbering
UNSHIFTED (relative to its own top) by design — the new search bar's row is prepended and
`_button_regions` shifted EXTERNALLY, in each pane's loop, AFTER `_render_pane` returns (mirrors
`worker_proxy_pane.py`'s sub-milestone-3 precedent) — so every assertion in this file (which calls
`_render_pane` directly) kept working unmodified. This is the doc trail for why: confirms the
'keep the pure render function reusable/testable, shift externally' design choice paid off exactly
as intended."

---

## Salvage from dev/constants/DOCS.md

Module heading originally carried: "(104 LOC, new 2026-09, constants-split milestone)" — date/
milestone tag cut, LOC kept.

Full original Purpose paragraph (module-split rationale, kept in spirit but trimmed of the
per-module-destination narrative in the rewrite): "Byte-identity harness for `src/constants.py`'s
split into `src/colors.py` (ANSI colors + backgrounds, `PASTEL_*` cluster), `src/core/modes.py`
(`MODE_*` cluster), `src/pane_error_log.py` (`PANE_ERROR_LOG_*` cluster, absorbed into the module
that already owns that concern), and the residual `src/constants.py` (timing/size limits,
`TOOL_BLOCKLIST`, and the `HOOK_*` cluster — left in place per Main's direction: it has zero
importers anywhere in `src/`/`dev/`, so a dedicated module would be dead code on arrival, and it's
the only cluster left in `constants.py` once the other three leave, which satisfies the split rule
on its own). Hardcodes the exact 70 top-level UPPER_CASE names that existed in `constants.py` at
the moment this harness was built (frozen as a literal list — dynamic discovery via `vars()` would
only find the 35 or so still there post-split), resolves each through a `_NEW_LOCATIONS` map
(defaults to `src.constants`; updated in the same commit as the split for every name that actually
moved), and hashes `{name: repr(value)}`."

Removed closing line: "Status: hash `fa6f42c25ef89eb9d6d5bd9e90ad66697c29e6d1d950bd670e0eda8d7fd60bc3`
— identical before and after the constants-split milestone."

---

## Salvage from dev/cursor_edges/DOCS.md

Full original file was an investigation log (Problem / Investigation History / Scripts / Test
Plan / Findings), not a module map. Salvaged in full below since nearly all of it is cut:

### Problem section
"`_PanelContentView.resetCursorRects` installs 4 cursor zones on the production NSPanel (bottom
↕, left ↔, right ↔, interior →). Bottom-edge I-Beam→Arrow transition worked in Iteration 3. Sides
have never shown `↔`. As of 2026-05-20 even the bottom edge may have regressed.

Iteration 4 hypothesis (REFUTED by probe): Footer, TopBarView, and StackView *cover* the exact
pixel strips where cursor rects should fire. AppKit's cursor-rect merge gives the *deepest* child
view priority.

Iteration 5 hypothesis (PARTIALLY CONFIRMED, 2026-05-20): `NSWindowStyleMaskNonactivatingPanel`
blocks cursor-rect dispatch entirely. `enableCursorRects()` was missing — confirmed by visual
evidence: I-Beam→Arrow transition on panel entry NOW works with `--fix`. Resize `↔` at edges still
does not appear → a second blocker remains.

Iteration 6 hypothesis (REFUTED, 2026-05-20): Subview coverage IS the remaining blocker —
leaf-rects on covering views. Tested with `--leaf-rects` flag. Visual result: still no resize
cursors. Subview coverage is NOT the blocker.

H7 hypothesis (active): `NSWindowStyleMaskResizable` causes WindowServer to claim the edge regions
for native resize handling. For NonactivatingPanel it neither shows resize cursors itself nor
allows our cursor rects to fire. Removing the resizable mask should let our rects take effect.
`--no-resizable` flag tests this. Trade-off: no native drag-resize if H7 is confirmed and that
approach is adopted."

### Investigation History
"`process-docs/menubar_build/menubar_overhaul_2026-05-19.md` § 'NSPanel Cursor Rabbit Hole (4
Iterationen, DEFERRED)' — full iteration log."

### probe.py subclass table and startup-observation narrative
"Startup observation: `resetCursorRects` fires in child-first order on every subview: 1.
ContentView (installs 4 rects) 2. FooterView → Button('Restart') → Button('Kill') 3. TopBarView →
Button('Auto-Jump: ON') 4. StackView → 3 session row buttons. This confirms child views DO install
cursor rects via super. The race is visible in the log."
"Smoke run output (2026-05-20): Panel starts, logs startup hierarchy, `resetCursorRects` cascade
fires immediately. No crashes."

### Test Plan (full 9-row hover table) — investigation methodology, not module map
Positions 1-9 (left/right/bottom/top edges, Kill/Restart/session-row/Auto-Jump buttons, interior)
with expected-cursor / expected-winner columns and the framing question "which class name appears
after `cursorUpdate_` in the log?".

### Findings
"Iteration 4 baseline (interactive run, 2026-05-20): Left edge (x<8), ~280 mouseMoved_ fires, 0
cursorUpdate_, correct hitTest view. `resetCursorRects` cascade: all 10 subviews, correct order.
Conclusion: cursor-rect dispatch is not engaged at all. Iteration 4's child-view-race hypothesis
was wrong — the race never runs.

Iteration 5 --fix smoke (automated, 2026-05-20): `enableCursorRects()` called —
`areCursorRectsEnabled=True`; cursor-rect dispatch enabled confirmed; interactive hover needed to
verify `cursorUpdate_` fires.

Iteration 5b — --fix partial confirm (interactive, 2026-05-20): I-Beam→Arrow transition NOW works
on panel entry (`enableCursorRects()` was genuinely missing — confirms NonactivatingPanel
hypothesis); Resize `↔` at left edge still does NOT appear (a second blocker remains);
`cursorUpdate_` logged 0 times — NOT a valid signal (see note). `cursorUpdate_` is NOT the right
metric for cursor-rect verification: it's the NSTrackingArea callback mechanism, while
`addCursorRect_cursor_` dispatches directly at AppKit window level without firing `cursorUpdate_`.
The correct visual signal is whether the cursor shape changes at the edge — it did (I-Beam→Arrow),
confirming dispatch works; the `↔` shape is still missing → ContentView's left-edge rect is
shadowed by covering subviews.

Iteration 6 — Leaf-Rect Test (REFUTED, 2026-05-20): `probe.py --fix --leaf-rects` installed
resize cursor rects on each leaf subview at their portion of the panel edges (super first, then
leaf rects). Result: still no `↔`/`↕` resize cursors at edges, only the I-Beam→Arrow transition
remained. Conclusion: subview coverage is NOT the blocker — the blocker is upstream of cursor-rect
dispatch itself.

Iteration 7 — H7 No-Resizable Test (pending user verification): Hypothesis — WindowServer claims
edge regions for native resize under `NSWindowStyleMaskResizable`; for NonactivatingPanel it
neither shows its own resize cursors nor allows `addCursorRect_cursor_` rects to fire there;
removing the resizable mask removes the WindowServer claim. `probe.py --fix --no-resizable`
creates the panel with only `NSWindowStyleMaskNonactivatingPanel`. Smoke (2026-05-20): all flag
combos start clean, `areCursorRectsEnabled=True`, correct MODE line, `[--no-resizable]` log line
confirming mask removed. Pending: user runs the combined flag set and hovers edges — `↔`/`↕`
appearing confirms H7 (trade-off decision is user's call); still Arrow/I-Beam refutes H7,
remaining candidates H8 (custom resize handler) / H9 (`sendEvent_` override), both expensive,
deferred."

---

## Salvage from dev/desktop_detection/DOCS.md

Full original file was a Problem/Investigation(Code Analysis+External Research+Hypotheses)/
Scripts/write-up. Salvaged in full below:

### Problem
"What happens: Monitor_CC Menubar displays arbitrary slot-numbers `[1]` `[2]` `[3]` instead of
user-visible Mission Control Desktop numbers for each Main CC session. Worker windows spawn on
random desktops. `show <file>` opens apps on wrong desktops.
Manifestation: No production impact yet (Menubar shows slot-based order, not spatial order).
Detection pipeline missing — this investigation builds it.
Production code status: No changes yet. Detection probe only. See
`process-docs/desktop_allocation/` for design and iteration history."

### Code Analysis table
`src/menubar/ghostty.py` (cwd → UUID via OSC-2 title-probe; writes `ghostty_cwd_uuid.json`),
`src/menubar/proc_cache.py:_cc_proc_cache` (pid → (tty, cwd) cache for CC processes),
`src/menubar/discover.py:list_alive_sessions()` (returns `SessionInfo` including cwd for Mains),
`~/Library/.../ghostty_cwd_uuid.json` (live {cwd: uuid} map written by Menubar at 1.5s cadence).
"Pipeline gap: UUID is Ghostty-internal; macOS CGS APIs need `CGWindowID` (kCGWindowNumber). No
direct Ghostty → CGWindowID link exposed."

### External Research table (9 rows)
AppleScript `bounds of terminal id "UUID"` → -1728 error, primary bounds-match strategy not
available; `window of terminal id "UUID"` → -1728, direct UUID→window nav not exposed; `working
directory of terminal` → returns Monitor_CC for ALL terminals, bug in Ghostty AS dictionary
(always reflects app launch dir, not tab cwd); `id of terminal of tab of window` → works, UUID→
window_id mapping; `CGWindowListCopyWindowInfo(0,0)` (option=0) → 279 windows incl. off-screen,
`kCGWindowListOptionAll=0` = all spaces, `1` = OnScreenOnly; `CGWindowListCopyWindowInfo(1,0)`
(option=1) → 26 windows on-screen only, NOT "all"; `CGSCopyManagedDisplaySpaces` dict keys →
`Display Identifier`/`Spaces`/`ManagedSpaceID`, not `DisplayIdentifier`/`id`;
`CGSCopySpacesForWindows(cid,0x7,arr)` → returns [space_id] per WID, mask=0x7 works, [] for
invalid WIDs.

### Hypotheses table (8 rows)
AppleScript bounds→bounds-match→CGWindowID: Excluded (-1728 at every geometry level). AppleScript
tab traversal→UUID→window_id→kCGWindowName match: Confirmed. CGS space detection pipeline
(CGSCopyManagedDisplaySpaces + CGSCopySpacesForWindows): Confirmed, correct desktop_no for all
tested WIDs. OSC-2 injection required for ambiguous window names: Active, fires when CC tab is
not the focused tab in its Ghostty window. TCC blocks window enumeration
(kCGWindowOwnerPID) in launchd/bundle: Excluded — 02_context_comparison_probe: all 3 contexts
return 17 Ghostty windows with correct PID. TCC strips kCGWindowName in launchd/bundle context:
Confirmed — null for all Ghostty+Finder windows, CC-Bash has full titles. kCGWindowBounds
available without Screen Recording: Confirmed — 03_field_availability_probe: 280/280 populated in
launchd and bundle contexts. AX/_AXUIElementGetWindow viable in launchd context: Pending — next
probe, different TCC surface.

### Per-script narrative (dates, "Requires:", "Key finding(s):" paragraphs, three-strategy
resolution list for 01_probe.py, bundle-stub descriptions for 02/03, key implementation notes for
04_space_move_probe.py including the two CFUNCTYPE definitions and the inheritance note, key
design + key findings for 06_move_sweep_probe.py including all 4 primitive names (A/B/C/D) and the
"5/5 move APIs tested on 26.5, 0/5 functional" combined-with-G2 conclusion, window-types +
ground-truth + two-methods + space-signals + key-findings tables for 05_window_detection_probe.py
including the 12/12 all_agree and the per-method pass/fail breakdown) — all removed as
investigation narrative / historical measurement results. The current-shape mechanics that
survive as Gotchas in the rewrite: TCC strips `kCGWindowName` but not `kCGWindowOwnerPID`/
`kCGWindowNumber`/`CGSCopySpacesForWindows` in launchd/bundle contexts; AppleScript returns -1728
for all window-geometry queries in Ghostty's AS dictionary (not a TCC gap); all tested
CGS/SkyLight window-move primitives were no-ops on the tested macOS version.

---

## Salvage from dev/display/DOCS.md

### scan_jsonl_rules.py
"Status: Concluded — confirmed that Session-JSONL contains NO rules/instructions data (Contents
of: 0, system-reminder: 0, claudeMd: 0). InstructionsLoaded hook is the only viable
Claude-infrastructure source. Superseded by jsonl_exploration/ suite for detailed structure
analysis." (The underlying finding — that session JSONL carries no rules data — is preserved in
the rewrite as a Gotcha since it explains why the script still exists despite being "concluded".)

### test_tmux_layout.sh
"Originally 3-pane, now 5-window / 10-pane (main+tokens | proxy+metadata | rules+hooks |
workers+worker-proxy+worker-metadata | warnings)." — history of the pane count changing, cut;
current pane count kept in the rewrite.
"Source: tmux man page (github.com/tmux/tmux `tmux.1` L3591-3648) — `-l size%` = percentage of
target pane's available space." — citation, folded into a Gotcha in the rewrite without the
line-number citation.

### A_format_cache_tracker_proof.py
"Exercises `_render_expanded_call_lines`, `_compute_cache_viewport`, and `_fmt_rl_reset_time`
transitively." — function-level detail, cut.

### test_hover_map.py
"`render_messages()` call passes `entry_idx` as of 2026-08-28 (thinking-expander milestone
signature bump: `render_messages(entry_idx, entry, ...)`), mechanical update only." — dated
signature-change history, cut.
Full note on `test_stripped_msg_pair_alignment`: "sources real entries from
`src/logs/dual_log/*_forwarded.jsonl` + sibling `*_stripped.jsonl` (newest-first glob, not a
hardcoded filename) — reconstructs entries via `_parse_forwarded_log(..., keep_last=None)`,
builds the stripped-span accumulator via `accumulate_dual_log`, and attaches
`_stripped_spans`/`_injected_spans` + ownership-lookup dicts to entries exactly as `pane.py`'s
`_refresh_proxy_data` does, so `render_messages` runs its real dual-color (`use_dual=True`) path.
Gracefully skips (PASS, not FAIL) when no dual-log pair with stripped content exists in
`src/logs/dual_log/` — an environment/data availability gap, not a code issue." — kept the
graceful-skip behavior as a Gotcha in the rewrite (real trap: a green run can mean "skipped", not
"passed"), cut the rest as function-level narrative.

### test_strip_markers.py — was entirely undocumented in the pre-rewrite file, added now.

---

## Salvage from dev/gpu_pane/DOCS.md

Module heading originally: "(131 LOC, new 2026-09, gpu-pane-split milestone)" — tag cut.
Full original Purpose: "Byte-identity harness for the gpu-pane-split milestone (`pane.py` concern
split into `gpu_actions.py` / `gpu_render.py`). Calls `_render_pane` with synthetic
presets/arbitrary/anomalies/today_errors/error_counts/collections — 3 preset scenarios (running+
healthy, running+unhealthy, stopped), one arbitrary server, a fresh `'starting'` toggle_state
overlay and an old/expired-looking one (both set directly on `_toggle_state`, not via
`_toggle_server`/`_fire_button`), 3 errors, 2 collections, 1 anomaly — at two pane widths (100,
40), with and without a search query (query matched against the baseline render's own lines,
mirroring `_gpu_search_on_commit`'s own approach), hashing the rendered output AND the resulting
`_button_regions` dict for every one of the 4 calls per width." — module-split rationale and
per-scenario enumeration, cut to a one-sentence Purpose in the rewrite.
Removed closing line: "Status: hash `e33158d622d325e1ece673c5afbfc79217c7dd3842b4243225a338df58a14a52`
— identical before and after the gpu-pane-split milestone."

---

## Salvage from dev/hook_error_correlation/DOCS.md

Original heading structure (`## Problem`, `## Data Sources`, `## Scripts`, `## Reports`) folded
into Role/Modules/Gotchas. Nothing substantive cut beyond the `md/YYYY-MM-DD.md` placeholder
literal — resolved to plain-word phrasing per Main's known-drift note. The Data Sources table
content (session join yields 0 results — errors predate `_fire_log.py` or come from a
cross-project RAG session) is a real, current mechanics note and was kept as a Gotcha.

---

## Salvage from dev/hook_smoke/DOCS.md

The pre-rewrite file listed 24 of the 27 `.py`/`.sh` scripts actually present; missing entirely
were `test_block_broad_find.py`, `test_block_manual_worker_cleanup.py`,
`test_block_rag_corpus_read.py`, `test_block_rag_docs_layer.py`,
`test_block_worker_kill_while_working.py`, `test_block_worker_send_while_working.py`, and
`test_fire_log.py` — all added in the rewrite.

### Per-module case-by-case enumerations removed (kept only the case COUNT + hook name in the
rewrite's one-sentence Purpose):
- test_block_broad_grep.py: "5 blocked cases (broad recursive, piped to non-head), 5
  head-bounded exemptions (piped to `head`/`head -N`, with redirect before head, further pipe
  after head), and 6 existing-exemption passes (--include, file-targeted, non-recursive, git
  grep, quoted, heredoc)."
- test_block_gh_cli_local_path.py: full case enumeration incl. "the `--dest` false-positive trap
  in both flag positions", dated "(2026-08-07)" tag on the module heading.
- test_block_rag_cli_index_isolated.py: full 37-case enumeration including the 2026-08-01 and
  2026-08-02 "holes" narrative (env-prefixed index preceded by tail, multi-assignment-prefixed
  index piped to tee, command/backtick substitution cases, etc.).
- test_block_dangerous_kill.py: "pkill -f patterns, pipe-kill chains, heredoc/quote exemptions,
  and allowlist cases."
- test_block_git_destructive.py: full 21-case enumeration incl. the two named FP-regression
  cases (minimal repro + "actual recap command").
- test_log_janitor.py: path written as `src/panes/log_janitor.cleanup_old_jsonl` (drift, resolved
  to `src/panes/log_janitor.py` in the rewrite, function name kept in prose only). "Uses
  `sys.path.insert` on `src/panes/` + `from log_janitor import` to avoid the `from src.` import
  restriction." — kept as a Gotcha (real mechanism, not history).
- test_rewrite_background_sleep.py: heading tag "(184 LOC, Milestone 2 rewrite target change
  2026-08; orchestrator-only guard cases 2026-08 Milestone 3b)" cut. Full case narrative
  (6 positive-rewrite cases incl. "the OLD canonical `sleep 3300 && echo done` (now also a stale
  habit)", 5 negative no-op cases, 3 negative worktree-cwd cases) cut to case counts. The
  explicit-cwd-per-case mechanism (never inherited, because the suite's own on-disk path already
  contains `.claude/worktrees/`) was kept as a Gotcha — it's a real trap for anyone adding a case.
- test_block_unauthorized_background.py: heading tag "(96 LOC, Milestone 2 worker-cli wait
  exemption 2026-08)" cut. Full case enumeration (3 sleep-only ALLOW, 4 worker-cli wait ALLOW, 6
  FORCE, 1 PASS) cut to case count.
- test_version_purge.sh: "Mirrors the production functions inline — keep in sync with
  `src/claude_proxy_start.sh` when editing either." — kept as a Gotcha (real maintenance trap).
- test_header_capture.py: "Does NOT require a live mitmproxy process — uses minimal mock headers
  objects." and "Imports `_filter_response_headers` directly from `src/proxy/addon` via
  `sys.path.insert` on `src/`." — path drift (`src/proxy/addon` → `src/proxy/addon.py`) resolved;
  no-live-process note kept as a Gotcha.
- test_bg_task_detection.py: full 6-case enumeration (3 unit cases, 1 integration case with real
  subprocess + real `lsof`, 1 fail-open case, 1 TTL-gate case) cut to case count; the "Creates/
  removes a scratch dir under the real `_TASKS_BASE`" note kept as a Gotcha.
- probe_bg_task_live.py: full purpose paragraph including the benchmarking detail (per-tick cost
  of batched `lsof` cache) and the entire "Gotcha" paragraph about CC's own tracked-wrapper
  mechanism causing a 14-minute stuck run when a live probe targets its own session, plus both
  mitigations (`--snapshot`-driven external loop; `lsof <path>` scoped to the specific file) —
  the mechanism and both mitigations were kept as a Gotcha in the rewrite (real, calibrated trap),
  the "14 minutes" incident framing and "not CI-safe" framing were trimmed to the mechanism only.
- test_block_po_read.py: full 16-case enumeration cut to case count; "Expected output: `All 14
  tests passed.`" note (mismatched against the actual 16-case count) flagged as stale in the
  rewrite rather than propagated.
- test_block_cli_chained.py: heading tag "(168 LOC, new 2026-09 chain-hook unification;
  interpreter-path-bypass + stale-subcommand-name cases added 2026-09-06)" cut. Full rule-class
  enumeration (rule 1/2/3, all 8 CLI names, the "no allowlist of chain segments" thesis cases) and
  the entire "2026-09-06 additions (6 cases, two independent holes against websearch)" paragraph
  (the `scrape_url` → `scrape_url_chromium` stale-name correction, the 5 interpreter-path-bypass
  cases) — cut to a case count + one-sentence purpose; the fact that `block_cli_chained.py`
  replaced 7 named hooks is kept as a single clause since it's still true of the current file, not
  a change description.
- probe_replay_cli_chained.py: full purpose paragraph including "As of the 2026-09 rewrite: 115
  historical block fires total, 49 still block, 66 now pass" measurement result and "the
  milestone's own pre-implementation estimate was 'about 83/32'" comparison — cut as a one-time
  measurement result, not current-state fact.
- test_block_rag_cli_document_repeat.py: full 7-case enumeration cut to case count; the
  per-case fresh-tempfile-state-isolation note kept as a Gotcha.
- test_hook_setup_main_branch_gate.py: full 10-case enumeration (stub `git_query_fn`/
  `tree_query_fn` behavior, mirror-image conditions) cut to case count; the two-condition gate
  mechanism (must be both on `main` AND in the working tree) kept as a one-line Gotcha.

---

## Salvage from dev/hotkey_latency/DOCS.md

Full original Purpose: "Measurement tooling for the menubar hotkey-lag investigation (Cmd+K/L/
1..9 intermittent slow response). Verifies the Carbon `GetEventTime` technique and parses the
`[latency]` instrumentation `src/menubar/app.py`, `hotkey_controller.py`, `discover.py`,
`system.py`, `discovery_worker.py` write to `menubar.log` into a distribution report.
`analyze_latency.py` is measurement-only (reads the log, never touches `src/`); the M3
milestone's `src/` fix itself (discovery moved off the main thread + ghostty TTL re-arm) lives in
`src/menubar/`, not here." — "M3 milestone" framing and the fix-narrative sentence cut; the list
of instrumented modules kept in the rewrite's Role.
"Background: `process-docs/hotkey_latency/`." — kept as the area cross-reference.
analyze_latency.py: "`tick` and `bg_refresh` lines share one grammar (`<label> total=Nms
phase=Nms ...`), parsed by a single `_TICK_LIKE_RE` and rendered via one shared
`_tick_like_section()` for both." — function-level detail, cut. "Imports real menubar code via
the `sys.path.insert(0, WORKTREE_ROOT / 'src')` + `from menubar....` pattern (see
`dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py` for the established
precedent) — NOT `from src.menubar...` (blocked by the same hook)." — cross-file precedent
citation cut, the import-pattern mechanism itself kept as a Gotcha.

---

## Salvage from dev/jsonl/DOCS.md

Nearly compliant already. No substantive history to salvage — the Usage block's `--mode
capture`/`--mode verify --baseline <path>` flags were folded into the module's Purpose/entry-point
description rather than kept as a separate fenced Usage block, per module-level-only.

---

## Salvage from dev/display/jsonl_exploration/DOCS.md

Nearly compliant already. "Key Finding" section content (Session-JSONL contains NO rules/
instructions data; the InstructionsLoaded hook via `hook_outputs.jsonl` is the only
Claude-infrastructure source) was kept as a Gotcha in the rewrite since it's a current fact
future scripts in this area need, not a change description.

---

## Salvage from dev/menubar_nspanel/DOCS.md

`menubar_debug.py` was present on disk but entirely undocumented in the pre-rewrite file — added
in the rewrite.
Full original "Verification Checklist" (8 manual interactive steps: Cmd+L open, outside-click
persistence, second Cmd+L close, bar-icon toggle, `@rumps.timer` firing while panel open,
correct positioning, no focus steal, Quit) — removed as a step-by-step manual test script
(function/procedure-level, not module-map material); the underlying claims (panel does not
auto-dismiss on outside click, unlike NSMenu's `NSEventTrackingRunLoopMode` behavior; timer
keeps firing while panel is visible) kept as one Gotcha line in the rewrite.
"Background and design rationale: `process-docs/menubar_nspanel/A1.md`. Build narrative:
`process-docs/menubar_nspanel/A2.md`." — per-file process-docs references, replaced with the
area-level `process-docs/menubar_nspanel/` cross-reference.

---

## Salvage from dev/menubar/DOCS.md

Module headings originally carried: "(196 LOC, new 2026-09, menubar milestone A; fake-app
`.settings` re-point 2026-09 menubar milestone B)", "(211 LOC, new 2026-09, menubar milestone B)",
"(177 LOC, new 2026-09, menubar milestone C)" — all date/milestone tags cut, LOC kept.

### model_controller_byte_identity.py
Full original two-check enumeration (Persistence check: 4x model/3x effort/3x max_tokens cycle
sequence for both main and worker, seeded from a copy of the real
`~/.claude/shared-rules/proxy_rules.json`; UI check: fake app `.settings` SimpleNamespace,
`_panel_controller` NSObject subclass, `open()` then 6 `handle_cycle_*` calls, dumping every
arranged subview's class/frame/title/attributedTitle/tag/action) — cut to a one-sentence Purpose.
"Falls back to an import + `open()` smoke check if headless AppKit view creation fails (not
observed in this environment — both checks ran against real AppKit objects successfully)." — the
fallback-exists fact kept as a Gotcha, the "not observed" run-result framing cut.
"Determinism note: the UI check's `open()` reads the REAL `MODEL_SELECTION_FILE`/
`PROXY_RULES_FILE` (no override mechanism exists for that specific code path in production) — the
before/after hash comparison is only reliable if those files don't change between the two runs
(i.e. nobody clicks Apply on a live running menubar app in between). No writes ever happen in the
UI check itself." — kept as a Gotcha (real trap), trimmed of "before/after hash" framing.
Removed closing line: "Status: `PERSISTENCE_HASH: 650d5b77aafc3c718a08a033b5a56530336a9308552eb842499d5c12d3bc8b06`,
`UI_HASH: 52efdd84205e590eedd0663ee8b21d2bb0db8cd386e48907d865071832e1f2d7` — both identical before
and after the split."

### panel_manager_byte_identity.py
Full original scenario enumeration (`rebuild(sessions, bg_by_project)` with a synthetic 5-session/
3-project list: alpha two mains sharing desktop_no=2 → conflict `[!2]` rendering; beta one main +
one worker; gamma one main with desktop_no=None + a bg timer; walks every arranged subview
drilling into the one `NSGridView`; then `update_inplace` with one session's status flipped) — cut
to one sentence.
"Determinism note: this harness's own accessor code targets `PanelManager`'s CURRENT internal
attribute layout — it was updated in the same commit as the split (pre-split baseline hash
`0efc9d390506a6e17c5b33958074e44d6ae5831ddd898ae82c9bd8b008876d42`, re-confirmed identical against
the post-split `_widgets`/`_lookups` layout)... A future `PanelManager` change must re-verify this
hash still matches, updating the accessor code first if the internal attribute names move again."
— the maintenance obligation (accessor code must track PanelManager's internal attribute names)
kept as a Gotcha, the specific hash values and the milestone-A cross-reference cut.

### discover_byte_identity.py
Full original scenario enumeration (4 named scenarios: `worker_fresh_working_stale_activity`,
`worker_no_worktree_old_mtime`, `main_fresh_hook`, `main_idle_proxy_override`, each with its own
one-clause description) — cut to one sentence naming the function under test.
"Determinism note: the same top-level entry point (`_process_project_dir`) is called regardless
of how its internals are decomposed, so this harness needs no accessor-code update across the
milestone C split — unlike `panel_manager_byte_identity.py`'s `_widgets`/`_lookups` rename.
Baseline hash (pre-split) and post-split hash both matched:
`0395eddc436c042aea4b5fa2ca313f207248dc6efc70679e15520ecf6c636a37`." — hash values and milestone
comparison cut.
"`detect_main_desktop_numbers` (`desktop_detection.py`) and `_refresh_ghostty_tty_to_id`
(`ghostty.py`) have no equivalent harness — both call CGS/AppleScript/tty I/O with no clean
monkeypatch seam comparable to `discover.py`'s plain-function boundaries (CGS is `ctypes` CDLL
calls, not overridable Python names in the same way); import smoke (`IMPORT_OK` in the behavior
proof) plus `discover.py:list_alive_sessions`'s existing caller check (both functions are called
from there on every discovery cycle) were used instead, per this milestone's own scope." — kept
the substance (no monkeypatch seam exists for those two functions, so only import-smoke coverage
exists) as a Gotcha in the rewrite; cut the literal `IMPORT_OK` implementation-variable name and
"per this milestone's own scope" framing (known drift item — resolved).

---

## Salvage from dev/model_selector/DOCS.md

### verify_model_cycle_and_io.py
"Milestone 2, extended 2026-09 for the model-ID + per-model effort/max_tokens rows" — heading/
opening tag cut.
"(2026-09 menubar milestone A: moved out of `model_controller.py`'s own former location in the
same concern split that also produced `model_panel_ui.py` — see `src/menubar/DOCS.md`'s
`model_controller.py` entry)" — cut as history; current location (`src/menubar/model_selection.py`)
kept.
"milestone 2's review correction — an unrecognized-but-valid on-disk value is preserved verbatim,
never silently replaced, with an Apply-without-cycling round-trip proving it; unchanged behavior,
re-verified after the 4-value cycle change" — review-correction narrative cut; the current
behavior (unrecognized value preserved verbatim) kept as a one-clause Purpose fact.
"Loads the real module via `importlib.import_module('src.menubar.model_selection')`
(package-relative imports require real package context, unlike `hook_writer.py`) —
`_load_model_selection_module()` (renamed from `_load_model_controller()`, and the loaded module
variable renamed `mc`→`ms` throughout, 2026-09) re-pointed here rather than re-exported from
`model_controller.py`, since every symbol this script touches is a `model_selection.py` symbol
`model_controller.py` no longer calls directly post-split." — rename narrative (known drift item)
cut in full; resolves per Main's instruction.

### verify_three_tab_ring.py
"**(2026-09, menubar milestone B):** `_FakeApp`'s flat `_panel_width`/`_panel_min_height`/
`_auto_focus`/`_panel_backgrounded` attrs replaced with `.settings` (a `SimpleNamespace` with
`panel_width`/`panel_min_height`/`auto_focus`) — `PanelManager`/`RagController`/`ModelController`
now read `app.settings.*` instead of flat `app.*` attrs; `_panel_backgrounded` dropped entirely
from `_FakeApp` since it moved onto `PanelManager` itself, which now initializes its own copy." —
migration narrative cut; current fixture shape (`.settings` SimpleNamespace) kept in Purpose.

### verify_launcher_model_precedence.sh
"the narrower, config-unaware `dev/native-model-start/p1_arg_parse_dry_run.sh` still covers
tiers 1-2 in isolation and remains accurate for what it tests" — cross-script comparison kept as
a boundary note in the rewrite (explains why both scripts coexist, not history).

### Gotchas
"See `process-docs/model_selector/` for the full trace." — kept as the area cross-reference.

---

## Salvage from dev/monitor_lifecycle/DOCS.md

Module heading originally carried: "— new 2026-09" on `test_monitor_sweep_scheduler.py` — cut.
"(the sweep's own dedicated LaunchAgent was removed 2026-09, blocked by a TCC Full Disk Access
wall under launchd; see `process-docs/monitor_lifecycle/`)" — date cut, underlying fact (no
dedicated LaunchAgent; TCC Full Disk Access wall under launchd was the reason) kept as a Gotcha
without the date, area cross-reference kept.
"the daily sweep's dedicated LaunchAgent was removed the same milestone — see
`process-docs/monitor_lifecycle/`" (repeated on test_monitor_sweep_scheduler.py's own Purpose) —
same treatment, de-duplicated into the single Gotchas-section statement in the rewrite.
