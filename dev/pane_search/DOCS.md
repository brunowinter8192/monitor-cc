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
