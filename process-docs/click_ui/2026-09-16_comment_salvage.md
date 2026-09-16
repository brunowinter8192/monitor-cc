# process-docs/click_ui/2026-09-16_comment_salvage.md

Session: dev/click_ui/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/click_ui/*.py` during this milestone, copied
verbatim before deletion, plus the full pre-rewrite content of `dev/click_ui/DOCS.md`. Nothing
judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File count (9) and comment/docstring totals (87 comments, 5 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this time.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/click_ui/*.py` before
deletion: zero matches. The 5 module-level docstrings (in `p1_worker_selection_click_probe.py`
through `p5_proxy_message_copy_click_probe.py`) are plain narrative, never read at runtime. All 5
deleted outright, no constant-rewiring needed.

## Naming note (despite the directory name)

Every "click" in this directory is a synthetic in-process dispatch: each script calls a pane's
`_handle_*_mouse(button, col, row, ...)` function directly with fabricated coordinates against
module globals seeded with synthetic data. None of the 9 scripts drive the real macOS desktop,
send a real mouse/keyboard event, or automate a real tmux pane — confirmed by reading every file
in full and cross-checked against the pre-existing DOCS.md's own Gotchas section, which describes
the same synthetic-dispatch shape. All 9 were run before and after this session's edit.

Comment/docstring counts confirmed via AST + tokenize before deletion: 87 comments, 5 docstrings,
matching the task's stated measured state exactly.

## Salvage from dev/click_ui/DOCS.md

Full content of dev/click_ui/DOCS.md as it stood before this rewrite (183 lines), preserved
verbatim since the whole file is being replaced with the mandated leaner format (Role capped
at 50 words, Purpose capped at 25 words per module, no Gotchas section in the new format,
Public Interface / Flow / State sections added).

```markdown
# dev/click_ui/

## Role

Regression coverage proving every tmux-pane control is reachable by mouse, not just keyboard:
worker selection, copy-by-click, pane-chrome buttons (refresh), and per-server digit-key
parity in the gpu pane. Touch this area when adding or changing a click region, a chrome button,
or a `_handle_*_mouse` dispatcher in `src/proxy_display/`, `src/workers/`, `src/panes/`,
`src/gpu_pane/`, or `src/news_pane/`. `md/` holds every run's report.

## Modules

### p1_worker_selection_click_probe.py (313 LOC)

**Purpose:** Proves, after one real render pass, that BOTH worker panes' header click-region
tables (`_worker_proxy_header_regions`, `_worker_tokens_header_regions` — built by the shared
`workers.worker_switch_header.format_worker_switch_header`) each contain one entry per worker at
plausible coordinates, and that a synthetic click at those coordinates produces the same state
change (IPC selection file) as the corresponding digit key — including at pane widths that force
a marker to straddle a wrap boundary, swept down to worker_tokens_pane's real 34%-of-window share.
**Reads:** nothing external — seeds `src.proxy_display.worker_proxy_pane._worker_proxy_workers`
and `src.workers.worker_tokens_pane._worker_tokens_workers` directly with synthetic worker lists.
**Writes:** `md/p1_worker_selection_click_probe_<timestamp>.md`; throwaway IPC selection files
under `/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after each check.
**Called by:** none — run manually; re-run after any change to `workers.worker_switch_header`,
`_handle_worker_proxy_mouse`/`_handle_worker_proxy_key`, or
`_handle_worker_tokens_mouse`/`_handle_worker_tokens_key`.
**Calls out:** `src.proxy_display.worker_proxy_pane`, `src.workers.worker_tokens_pane` — loaded
via `importlib.import_module`.

---

### p2_copy_click_probe.py (269 LOC)

**Purpose:** Proves, per pane (tokens, warnings, worker-tokens), that after one real render pass the
copy-row registry contains an entry for every copyable row, and a synthetic click on the symbol
column copies exactly the same string the `y` key produces — both paths run through the real
serializer, compared against each other. Also a pure-function width-guard regression
(`utils.append_copy_symbol`) and a render-integration width-guard check per pane.
**Reads:** nothing external — seeds `_cache_turns`/`tool_errors`/`_worker_tokens_turns` with
synthetic data; `copy_to_clipboard` is monkeypatched to a capturing stub.
**Writes:** `md/p2_copy_click_probe_<timestamp>.md`; one throwaway IPC selection file under
`/tmp/monitor_cc_selected_worker_<hash>.txt`, removed after the check.
**Called by:** none — run manually; re-run after any change to `append_copy_symbol`,
`format_cache_tracker`, `_format_warnings_pane`, `_serialize_warnings`, or any pane's
`_handle_*_mouse`/`_handle_*_key`.
**Calls out:** `src.panes.token_pane`, `src.format.token_format`, `src.panes.warnings_pane`,
`src.panes.warnings_render`, `src.workers.worker_tokens_pane`, `src.utils` — loaded via
`importlib.import_module`.

---

### p3_button_click_probe.py (286 LOC)

**Purpose:** Proves, per pane (warnings refresh), that after one real render pass the
chrome-button region is registered at a plausible coordinate, a synthetic click produces the
same state change as the corresponding key (`r`), a too-narrow pane registers no region, and each
pane's pre-existing click handling (expand/copy) still works with the header-check ahead of it.
Also covers the proxy pane's permanent search-bar header: `_build_proxy_output` returns row 1
with the search bar baked in, row 1 is not a body key, and
expand/collapse/copy/scroll/`_undo_proxy_expand` all still work at the shifted rows. (2026-09) The
workers-pane freeze-badge test is DELETED, not retargeted — the 'f' freeze feature was tied to the
all-workers list pane, which is gone; see the module docstring for why it has no successor here.
**Reads:** nothing external — seeds `tool_errors`/`proxy_entries` directly.
**Writes:** `md/p3_button_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `_format_warnings_header`,
`_handle_warnings_mouse`/`_handle_warnings_key`, or
`_build_proxy_output`/`_handle_proxy_mouse`/`_undo_proxy_expand`.
**Calls out:** `src.panes.warnings_pane`, `src.panes.warnings_render`, `src.proxy_display.pane`,
`src.proxy_display.format` — loaded via `importlib.import_module`.

---

### p4_gpu_news_button_probe.py (333 LOC)

**Purpose:** Proves gpu's digit keys 1-9 need no dedicated button — the pre-existing per-server
button fires the identical `rag-cli` subprocess call as `_toggle_server(idx, presets)` (what the
digit key calls), for both a stopped and a running+healthy preset. Also proves the gpu/news
`[refresh]` header buttons: region registered on row 1, disjoint from every pre-existing button
region, dispatched before the pre-existing `_fire_button`/`_fire_pipeline` branch; narrow panes
get no `[refresh]` text/region; news's pre-existing `[run pipeline]` click still fires. Sweeps
pane widths across each pane's button-visibility crossover (gpu 27, news 38) to prove the
decorative rule shrinks before `[refresh]` is dropped.
**Reads:** nothing external — seeds synthetic gpu preset dicts and news status dicts;
`gpu_pane.status.PRESET_NAMES` is monkeypatched to a fixed list; `subprocess.Popen` is
monkeypatched to a capturing stub (no real `rag-cli`/news-pipeline process ever launched).
**Writes:** `md/p4_gpu_news_button_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `_render_pane` (either pane),
`_toggle_server`, `_fire_button`, `_fire_pipeline`, `utils.compute_header_rule_len`, or either
loop's inline mouse-dispatch snippet.
**Calls out:** `src.gpu_pane.pane`, `src.news_pane.pane` — loaded via `importlib.import_module`.

### p5_proxy_message_copy_click_probe.py (158 LOC)

**Purpose:** Entry script — orchestrates all three copy-granularity suites (message/thinking/
block) from their own modules and writes the combined report; carries the full milestone
docstring.
**Reads:** nothing external.
**Writes:** `md/p5_proxy_message_copy_click_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `render_messages.py`'s message-row,
thinking-block, or generic-block build sites, `proxy_pane_shared._serialize_proxy_message`/
`_serialize_proxy_block`/`_prepare_copy_text`/`_copy_feedback_key`,
`format._apply_row_backgrounds`, or either pane's `_handle_*_mouse`/`_handle_*_copy_click`.
**Calls out:** `proxy_copy_probe_shared.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.

---

### proxy_copy_probe_shared.py (60 LOC)

**Purpose:** Shared fixtures for the P5 suite — module handles (`mod_proxy`, `mod_worker_proxy`,
`mod_format`, `mod_shared`), `check()`/`_RESULTS`, `_patch_clipboard`, `_make_entry`,
`_render_expanded`.
**Reads:** nothing external.
**Writes:** nothing (mutates the shared `_RESULTS` list the entry script reads).
**Called by:** `p5_proxy_message_copy_click_probe.py`, `proxy_copy_message_probe.py`,
`proxy_copy_thinking_probe.py`, `proxy_copy_block_probe.py`.
**Calls out:** `src.proxy_display.pane`, `src.proxy_display.worker_proxy_pane`,
`src.proxy_display.format`, `src.proxy_display.proxy_pane_shared` — loaded via
`importlib.import_module`.

---

### proxy_copy_message_probe.py (118 LOC)

**Purpose:** Message-row copy granularity (P5.1-5.5) — `('msg', entry_idx, msg_idx)` key
registration, click/serializer parity, click/copy dispatch, width guard.
**Reads:** nothing external — seeds a synthetic multi-block assistant message plus a blockless
user message via the shared `_make_entry`.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_thinking_probe.py (131 LOC)

**Purpose:** Thinking-block copy granularity (P5.6-5.10) — `('think', entry_idx, msg_idx, bidx)`
key registration, click/serializer parity, the non-copy-click-still-toggles-expand regression
(the one behavior this granularity must NOT disturb), width guard.
**Reads:** nothing external — seeds a synthetic entry with an assistant thinking block followed by
a text block.
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

### proxy_copy_block_probe.py (132 LOC)

**Purpose:** Generic-block copy granularity (P5.11-5.15) — `('block', entry_idx, msg_idx, bidx)`
key registration, click/serializer parity nested in both message and REQ copies, the
non-copy-click-is-a-no-op regression (opposite of the thinking-block shape), width guard.
**Reads:** nothing external — reuses the shared `_make_entry` (multi-block assistant message).
**Writes:** nothing.
**Called by:** `p5_proxy_message_copy_click_probe.py`.
**Calls out:** `proxy_copy_probe_shared.py`.

---

## Gotchas

**Both gpu and news panes keep `_render_pane`'s own row numbering unshifted** (relative to its
own top); the search-bar row is prepended and `_button_regions` shifted externally, in each pane's
loop, after `_render_pane` returns. A probe calling `_render_pane` directly (as this suite does)
sees the unshifted numbering — dispatch-loop-level assertions must account for the external
shift separately.

**The worker-proxy header's row-1 slot is reserved for the search bar** — a header-marker click
probe must apply `_WP_SEARCH_BAR_LINES`'s shift itself when calling `_format_worker_proxy_header`
directly (bypassing `_build_worker_proxy_output`, which performs the shift internally).

**The proxy panes' own body row-1 slot is ALSO reserved for the search bar, one level below the
header-marker case above** — `_handle_proxy_mouse`/`_handle_worker_proxy_mouse` special-case
`row == 1` as "focus the search bar" BEFORE ever looking at `line_map`. A probe calling
`format_proxy_block` directly (the same unshifted-row style `dev/display/test_hover_map.py` and
this suite's other probes already use) gets body rows starting at 1 — dispatching a synthetic
click at a raw `format_proxy_block` row number can silently land on the search-bar branch instead
of the real copy/expand dispatch, `_handle_proxy_mouse`/`_handle_worker_proxy_mouse` still returns
truthy, and the click quietly does nothing to the thing you meant to test. Shift both `line_map`
and `copy_rows` by 1 with `proxy_pane_shared._shift_line_map_and_copy_rows` (the same shift
`_render_and_scroll_body` applies in the real event loop) before dispatching any synthetic click
through `_handle_proxy_mouse`/`_handle_worker_proxy_mouse`.
```

## Salvage from dev/proxy/p1_worker_selection_click_probe.py

DOCSTRING L1-34:
```

P1 -- worker-selection click parity probe (Milestone 1: worker selection clickable in both
worker panes; retargeted 2026-09 for the panesplit milestone -- the all-workers list pane
(worker_pane.py) is gone, replaced by worker_tokens_pane.py, a single-selected-worker cache
tracker carrying the SAME kind of switch header the worker-proxy pane already had).

Proves, per pane, that after ONE real render pass:
  1. the click-region table (the worker-switch header markers, built by the shared
     src/workers/worker_switch_header.py::format_worker_switch_header for BOTH panes) contains
     one entry per worker at plausible coordinates
  2. dispatching a synthetic mouse click at those exact coordinates produces the SAME state
     change (selected worker name written to the IPC selection file) as pressing the
     corresponding digit key, in EITHER pane

Also proves every rendered header marker stays clickable when the header wraps across physical
rows -- a marker straddling a wrap boundary gets one region PER row segment it occupies (never
zero), swept across pane widths from no-wrap to forced multi-straddle. worker_tokens_pane.py's own
sweep additionally includes width 34 -- the pane's real share of the window (34%/66% split with
worker-proxy) is narrow enough that 5 workers' name+status+context-% markers routinely wrap.

Covers:
  - src/workers/worker_switch_header.py :: format_worker_switch_header header regions
    (incl. wrap-straddle segmentation via _register_marker_regions) -- shared by both panes below
  - src/proxy_display/worker_proxy_pane.py :: _handle_worker_proxy_mouse vs _handle_worker_proxy_key
  - src/workers/worker_tokens_pane.py :: _handle_worker_tokens_mouse vs _handle_worker_tokens_key

No live tmux/terminal needed -- module globals are seeded directly with synthetic worker lists;
IPC selection files are written to throwaway, probe-specific project_filter paths (hashed into
/tmp/monitor_cc_selected_worker_<hash>.txt by the real get_selection_file_path), cleaned up after
each check.

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p1_worker_selection_click_probe.py

```

COMMENT L68:
```
# Remove a probe-scoped IPC selection file, if present
```

COMMENT L75:
```
# Read back a probe-scoped IPC selection file's content ('' if absent)
```

COMMENT L83:
```
# Worker-proxy pane: header-marker regions built one per worker; click == digit key
```

COMMENT L129:
```
# Worker-proxy pane: every rendered marker stays clickable when the header wraps -- a marker
```

COMMENT L130:
```
# straddling a wrap boundary must get >=1 region per row segment it occupies, never zero
```

COMMENT L140:
```
# (2026-08-18, rollout sub-milestone 3) _format_worker_proxy_header computes regions
```

COMMENT L141:
```
# RELATIVE to its own top (row 1 = its own first line); the real _build_worker_proxy_output
```

COMMENT L142:
```
# shifts them by _WP_SEARCH_BAR_LINES so the search bar owns physical row 1 and a header
```

COMMENT L143:
```
# marker never collides with it. This test calls the helper directly (bypassing that
```

COMMENT L144:
```
# production shift step), so it must replicate the shift itself before dispatching clicks.
```

COMMENT L176:
```
# worker_tokens_pane: header markers (built by the SAME shared format_worker_switch_header as
```

COMMENT L177:
```
# the worker-proxy pane) -- one region per worker; click == digit key (both write the IPC
```

COMMENT L178:
```
# selection file identically, no expand-state involved since this pane shows one worker only)
```

COMMENT L225:
```
# worker_tokens_pane: the pane's real window share is 34% -- narrow enough that 5 workers' own
```

COMMENT L226:
```
# name+status+context-% markers routinely wrap; every marker must stay clickable, and (unlike the
```

COMMENT L227:
```
# worker-proxy sweep above, which only sweeps widths that happen to force a straddle) this sweep
```

COMMENT L228:
```
# pins the pane's actual narrow width to prove the header wraps and clicks land correctly there,
```

COMMENT L229:
```
# not just at some width chosen to force the case
```

## Salvage from dev/proxy/p2_copy_click_probe.py

DOCSTRING L1-41:
```

P2 -- copy-by-click parity probe (Milestone 2: copy-by-click in the y-only panes).

Proves, per pane, that after ONE real render pass:
  1. the copy-row registry (phys_row set/dict populated by the pane's own build function) contains
     an entry for every row that carries a copyable unit, at plausible coordinates
  2. dispatching a synthetic mouse click on the symbol column of that row copies EXACTLY the same
     string the 'y' key produces for that same row -- both paths run through the REAL serializer,
     nothing hardcoded, the two outputs are compared against each other
  3. a too-narrow pane_width suppresses BOTH the visible symbol and the row registration (width
     guard) -- proven once at the pure-function level (append_copy_symbol) and once at the
     render-integration level (format_cache_tracker, tokens pane)

**(2026-09) The main pane was removed entirely** (window 0 is now the tokens pane at full width,
see `process-docs/main_pane/`) — `test_main_pane_copy_click` and its `mod_main_display`/
`mod_monitor` imports were dropped accordingly.

**(2026-09, panesplit) The all-workers list pane (worker_pane.py) is gone**, replaced by
`worker_tokens_pane.py` -- a single-selected-worker cache tracker with the exact same
`(turn_idx, call_idx)`-keyed copy-row shape `token_pane.py` already has (no more worker-header-row
copy case, since there is no worker header ROW anymore in this pane -- worker identity now lives
in the switch header's marker regions, covered by `p1_worker_selection_click_probe.py`, not here).
`test_workers_pane_copy_click` is retargeted at `worker_tokens_pane.py` accordingly, same shape as
`test_tokens_pane_copy_click`.

Covers:
  - src/panes/token_pane.py :: _build_tokens_output (cache_copy_rows), _handle_tokens_mouse,
    _handle_tokens_key
  - src/panes/warnings_pane.py :: _build_warnings_output (error_copy_rows), _handle_warnings_mouse,
    _handle_warnings_key -- plus a regression guard for the pre-existing _serialize_warnings
    int-vs-tuple key bug fixed as part of this milestone
  - src/workers/worker_tokens_pane.py :: _build_worker_tokens_output (worker_tokens_copy_rows),
    _handle_worker_tokens_mouse, _handle_worker_tokens_key

No live tmux/terminal needed -- module globals are seeded directly with synthetic data;
copy_to_clipboard is monkeypatched per module to a capturing stub (no real pbcopy calls, no OS
clipboard dependency) so both paths' output can be read back and compared.

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p2_copy_click_probe.py

```

COMMENT L76:
```
# Monkeypatch mod.copy_to_clipboard with a capturing stub; returns the capture list
```

COMMENT L83:
```
# Pure-function width guard: symbol appended when room, unchanged when not
```

COMMENT L91:
```
# Tokens pane: one copy region per API-call row; click vs 'y' parity; width guard end-to-end
```

COMMENT L131:
```
# Warnings pane: fixed int-key serializer bug regression guard + one copy region per error row
```

COMMENT L174:
```
# worker_tokens pane: one copy region per API-call row (same (turn_idx, call_idx)-keyed shape as
```

COMMENT L175:
```
# token_pane.py, since this pane shows exactly one worker's own cache tracker); click vs 'y'
```

COMMENT L176:
```
# parity; width guard end-to-end
```

## Salvage from dev/proxy/p3_button_click_probe.py

DOCSTRING L1-45:
```

P3 -- pane-chrome button click parity probe (Milestone 3: the remaining single-purpose keyboard
controls -- warnings 'r' refresh; proxy 'u' undo stays keyboard-only, see below).

Proves, per pane, that after ONE real render pass:
  1. the header/chrome button region is registered at a plausible (start_col,end_col,phys_row)
  2. dispatching a synthetic click on it produces the SAME state change as the corresponding key
  3. a too-narrow pane registers no region (and renders no button text either)
  4. the existing click handling each pane already had (warnings expand/copy) still works after
     adding the header check ahead of it

(2026-07-30) The proxy pane's [undo] button and the one-line header introduced solely to host it
were REVERTED per user decision after live-testing: 'u' is the only way to undo, and stays.
(2026-08-18) A DIFFERENT, permanent one-line header was added back for Milestone 2's search bar
-- not a revert candidate, this is the user's explicit "always visible" design principle, not a
hidden-feature button. The proxy-pane test now proves the NEW header+shift contract instead: row
1 is the search bar (not body, no `_proxy_header_regions`/`_format_proxy_header` leftover from
the button-era code), body rows start at row 2, and everything the header/body split touches --
expand/collapse clicks, copy symbols, scroll, auto-scroll-to-just-expanded, and 'u' itself --
still works at the SHIFTED rows.

**(2026-09, panesplit) `test_workers_freeze_button` is DELETED, not retargeted.** The 'f' freeze
badge was a control on the all-workers list pane specifically -- "pause the whole list so I can
read it while it churns" -- and that list is gone per the user's own decision (the switch header
replaces it; see `process-docs/workers/`). worker_tokens_pane.py, its successor, shows one
worker at a time; there is no "the whole list keeps scrolling under me" problem for freeze to
solve there, and freezing a single already-selected worker's own tracker was never asked for as
part of this milestone. This is a feature genuinely retired with the pane it belonged to, not an
oversight -- it has no successor test in this suite.

Covers:
  - src/panes/warnings_pane.py :: _build_warnings_output (_warnings_header_regions),
    _handle_warnings_mouse, _handle_warnings_key -- src/panes/warnings_render.py ::
    _format_warnings_header
  - src/proxy_display/pane.py :: _build_proxy_output (permanent search-bar header, row-shifted
    line_map/copy_rows), _handle_proxy_mouse (row==1 -> focus), _undo_proxy_expand --
    src/proxy_display/format.py (search-highlight priority in _apply_row_backgrounds)

No live tmux/terminal needed -- module globals are seeded directly with synthetic data;
copy_to_clipboard is monkeypatched where needed (reused from milestone 2's pattern) so the
existing-click regression checks don't touch the OS clipboard.

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p3_button_click_probe.py

```

COMMENT L77:
```
# Build a minimal synthetic proxy entry (same shape as dev/display/test_hover_map.py's _make_entry)
```

COMMENT L91:
```
# Warnings pane: [refresh] header button -- region, click/key parity, width guard
```

COMMENT L103:
```
# (2026-08-18, rollout sub-milestone 6) row shifted from 1 to 2 -- the search bar now owns
```

COMMENT L104:
```
# physical row 1, the [refresh] header (still exactly one row) shifts to row 2.
```

COMMENT L129:
```
# Proxy pane: Milestone 2 (2026-08-18) added a PERMANENT row-1 search bar -- unlike the
```

COMMENT L130:
```
# milestone-3 [undo] button (reverted 2026-07-30, see git history), this header is not a
```

COMMENT L131:
```
# revert candidate; it is the user's explicit "always visible, not hidden behind a keypress"
```

COMMENT L132:
```
# design principle. Proves the new header+shift contract: row 1 is the search bar (not body),
```

COMMENT L133:
```
# body rows start at row 2, clicking row 1 focuses the bar, and everything the header/body split
```

COMMENT L134:
```
# touches -- expand/collapse clicks, copy symbols, scroll, auto-scroll-to-just-expanded, and the
```

COMMENT L135:
```
# 'u' key itself -- still works at the SHIFTED rows.
```

COMMENT L170:
```
# Row 1 is the search bar now -- NOT in proxy_line_map (only body rows get keys)
```

COMMENT L172:
```
# Body content starts at row 2 (header_lines=1 shift)
```

COMMENT L180:
```
# Click on row 1 focuses the search bar, does NOT toggle any expand state
```

COMMENT L187:
```
# Expand/collapse click still works, at the SHIFTED row (row 2, not row 1)
```

COMMENT L192:
```
# re-render to pick up the new copy-row set post-expand
```

COMMENT L196:
```
# Copy-symbol click still fires, at its own (shifted) row
```

COMMENT L213:
```
# 'u' key (_undo_proxy_expand) keeps working, unchanged
```

COMMENT L222:
```
# Scroll wheel still works (row argument irrelevant to wheel handling)
```

COMMENT L230:
```
# Auto-scroll-to-just-expanded: the entry that was just expanded stays visible in the very
```

COMMENT L231:
```
# next render (item_positions_out/_proxy_just_expanded machinery, now operating on the
```

COMMENT L232:
```
# header-shifted line_map -- same mechanism the search-jump feature reuses)
```

## Salvage from dev/proxy/p4_gpu_news_button_probe.py

DOCSTRING L1-38:
```

P4 -- gpu + news pane button probe (Milestone 4: the last keyboard-only controls).

Proves:
  1. gpu digit keys 1-9 need NO new button -- the pre-existing per-server [start]/[stop]/
     [restart] button already registered in _button_regions computes the SAME action and fires
     the SAME rag-cli subprocess call as _toggle_server(idx, presets) (what the digit key calls).
     Asserted by comparing captured subprocess.Popen args + resulting _toggle_state entry between
     the two paths, for both a stopped preset (start) and a running+healthy preset (stop).
  2. gpu's new [refresh] header button and news's new [refresh] header button: region registered
     after a render, disjoint from every pre-existing button region (different phys_row), and the
     dispatch loop correctly special-cases action=='refresh' before falling into the pre-existing
     _fire_button/_fire_pipeline branch (verified by replicating run_gpu_loop's / run_news_loop's
     exact inline dispatch snippet, since neither loop factors mouse dispatch into a standalone
     function -- same documented boundary as milestone 2's main-pane 'y' key: the local `force_
     refresh`/`input_changed` variables inside the blocking loop are not independently reachable
     without running that loop for real).
  3. narrow pane: [refresh] gets no text and no region in both panes; the pre-existing per-row
     buttons are NOT touched by the width-guard fix (unrelated, out of scope) and are not asserted
     on for the narrow case.
  4. news pane's existing [run pipeline] click dispatch is unchanged by the new action=='refresh'
     branch (regression check).
  5. (2026-07-30 review fix) the decorative '═' rule yields to the button, not the other way
     round: a width sweep in both panes proves the [refresh] region survives down to widths well
     below today's live pane widths (gpu 215, news 107) -- the rule shrinks (asserted: fewer '═'
     chars than its cap) before the button is dropped -- and that the no-room case (even the rule
     minimum can't fit alongside the button) still registers nothing while the title text itself
     stays fully visible at every swept width, including the narrowest.

No live tmux/terminal, no real rag-cli or news pipeline subprocess: subprocess.Popen is
monkeypatched per module to a capturing stub (mirrors milestone 2/3's copy_to_clipboard pattern).
gpu_pane.status.PRESET_NAMES (resolved once at import time via a REAL `rag-cli server presets`
subprocess call) is monkeypatched to a fixed synthetic list so the probe is deterministic
regardless of what's actually running on this machine.

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p4_gpu_news_button_probe.py

```

COMMENT L68:
```
# Monkeypatch mod.subprocess.Popen with a capturing stub (no real process launched); returns the
```

COMMENT L69:
```
# capture list of Popen call (args, kwargs) tuples
```

COMMENT L81:
```
# Build a synthetic gpu preset status dict
```

COMMENT L90:
```
# Replicate run_gpu_loop's exact inline button-region dispatch (not a standalone function in the
```

COMMENT L91:
```
# real loop); returns 'refresh' | (action, target) | None -- same three outcomes the real loop's
```

COMMENT L92:
```
# local force_refresh/input_changed assignment produces
```

COMMENT L105:
```
# Replicate run_news_loop's exact inline button-region dispatch
```

COMMENT L118:
```
# gpu pane: digit-key vs existing per-server button -- same action, same subprocess call, same
```

COMMENT L119:
```
# _toggle_state entry (no new button needed for 1-9)
```

COMMENT L170:
```
# gpu pane: new [refresh] header button -- region, dispatch, width guard
```

COMMENT L199:
```
# gpu pane: decoration must yield to the button, not the other way round -- width sweep proving
```

COMMENT L200:
```
# the '═' rule shrinks (down to its minimum) BEFORE [refresh] is dropped, all the way down to a
```

COMMENT L201:
```
# width range well below today's live pane width (215), and that title text survives even where
```

COMMENT L202:
```
# the button itself no longer fits
```

COMMENT L207:
```
# crossover for '  GPU Servers' + '[refresh]' at rule_min=4, gap=1 is pane_width=27
```

COMMENT L230:
```
# news pane: new [refresh] header button -- region, dispatch, width guard, no collision with
```

COMMENT L231:
```
# [run pipeline]
```

COMMENT L249:
```
# Regression: [run pipeline] click still fires the pipeline (existing behavior unchanged)
```

COMMENT L265:
```
# news pane: decoration must yield to the button, not the other way round -- width sweep, same
```

COMMENT L266:
```
# shape as the gpu sweep, down to a range well below today's live pane width (107)
```

COMMENT L269:
```
# crossover for '  CoinDesk News Pipeline' + '[refresh]' at rule_min=4, gap=1 is pane_width=38
```

## Salvage from dev/proxy/p5_proxy_message_copy_click_probe.py

DOCSTRING L1-71:
```

P5 -- proxy pane message-row, thinking-block AND generic-block copy-by-click probe (Milestone 5:
message-level copy inside an expanded REQ; extended for the thinking-block-level copy milestone
right after it; extended again for the fourth granularity -- a copy affordance on every other
block row: text, tool_use, tool_result, anything else).

Proves, per proxy pane (main `pane.py`, worker `worker_proxy_pane.py`), that after one real
render pass of an expanded REQ:
  1. every plain message-summary row (the `[msg_idx] role  type  chars` / `[msg_idx] role  type`
     rows built by `render_messages._render_new_messages`/`_render_modified_messages`) gets a
     `('msg', entry_idx, msg_idx)` key and a copy-row registration, alongside the pre-existing
     `('req', entry_idx)` row
  2. a synthetic click on a message row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_message`'s real output for that key -- not hardcoded --
     and that output is a byte-exact match of the corresponding `--- msg[i] ... ---` segment(s)
     inside `_serialize_proxy_entry`'s own REQ-level output for the same message
  3. a click anywhere else on a message row (not the copy column) changes nothing -- no
     `expand_states` mutation, no clipboard write -- matching what these rows did before they had
     a key at all (key=None -> `_handle_proxy_mouse` returns immediately)
  4. copying one message row's flash timer is keyed by the message's own `('msg', ...)` key, not
     the shared `entry_idx` -- it must NOT flash the REQ header or a sibling message row
  5. the pre-existing whole-REQ copy path is completely unaffected (same key, same dispatch
     branch, same `_serialize_proxy_entry` output)
  6. a too-narrow pane renders no `⎘`/`✓` on a message row and registers no copy row for it
     (`utils.append_copy_symbol`'s existing width guard, inherited for free)
  7. a thinking block's own always-visible summary row (the `▶/▼ [bidx] thinking ...` row) gets a
     copy-row registration too, alongside its pre-existing `('think', entry_idx, msg_idx, bidx)`
     key
  8. a synthetic click on a thinking row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_block`'s real output -- a byte-exact substring of the
     same message's `_serialize_proxy_message` output
  9. a click anywhere ELSE on a thinking row still toggles `expand_states[think_key]`, exactly as
     it already did before this row had a copy affordance -- the one behavior this milestone must
     NOT change, proven by asserting the toggle actually flips, not just that nothing crashes
 10. copying a thinking block's flash timer is keyed by its own `('think', ...)` key -- it must
     NOT flash the sibling message row, the REQ header, or a different block
 11. a too-narrow pane renders no `⎘`/`✓` on a thinking row and registers no copy row for it
 12. every other block row (text, tool_use, tool_result -- anything reaching the non-thinking
     branch of `render_messages._render_block_spans`) gets a `('block', entry_idx, msg_idx, bidx)`
     key and a copy-row registration, alongside its sibling message/REQ rows
 13. a synthetic click on a block row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_block`'s real output for that key, and that output is a
     byte-exact substring of BOTH the owning message's own copy AND the REQ-level copy -- verified
     directly, not assumed via transitivity
 14. a click anywhere else on a block row changes nothing -- no `expand_states` mutation, no
     clipboard write -- the SAME shape as the message-row case (3), not the thinking-row case (9):
     a block row never toggled anything before it had a key, so it must not start now
 15. copying one block row's flash timer is keyed by its own `('block', ...)` key -- it must NOT
     flash the REQ header, the owning message row, or a sibling block row
 16. a too-narrow pane renders no `⎘`/`✓` on a block row and registers no copy row for it

`_serialize_proxy_block` is ONE function shared by both the `('think', ...)` and `('block', ...)`
key shapes, not two near-identical copies -- the pre-merge `_serialize_proxy_think` body had
nothing thinking-specific in it beyond its own guard (same `full_text`-with-`preview`-fallback
read, same header format, same block-index lookup), so widening the guard to
`_is_think_key(key) or _is_block_key(key)` was the deliberate choice over duplicating that body a
third time. The two key-shape predicates (`_is_think_key`, `_is_block_key`) stay SEPARATE from
each other and from the merged serializer, because they still drive a real fork elsewhere: each
pane's `_handle_*_mouse` non-copy-click dispatch treats a `('think', ...)` row and a `('block', ...)`
row oppositely (think falls through to the pre-existing expand-toggle branch, block returns a
no-op alongside `is_msg`) -- that fork is genuine and stays; only the serialization body, which
never varied, was collapsed.

No live tmux/terminal needed for parts 1-5/7-16 -- `format_proxy_block` and `_handle_*_mouse`
are called directly with synthetic entries, `os.get_terminal_size` is never invoked on that path.
`copy_to_clipboard` is monkeypatched per module to a capturing stub (no real pbcopy call, no OS
clipboard dependency).

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p5_proxy_message_copy_click_probe.py

```

## Salvage from dev/proxy/proxy_copy_block_probe.py

COMMENT L75:
```
# -- copy click on block row 0's copy column --
```

COMMENT L84:
```
# -- copy click on block row 1's copy column --
```

COMMENT L90:
```
# -- non-copy click on a block row: no-op, matching the message-row shape (never toggled anything before) --
```

COMMENT L97:
```
# -- copying the owning message row does not flash either block row --
```

COMMENT L104:
```
# -- REQ-level copy still works, unaffected --
```

## Salvage from dev/proxy/proxy_copy_message_probe.py

COMMENT L70:
```
# -- copy click on msg row 0's copy column --
```

COMMENT L78:
```
# -- copy click on msg row 1's copy column --
```

COMMENT L84:
```
# -- non-copy click on a msg row: no-op, matching pre-milestone (key=None) behavior --
```

COMMENT L91:
```
# -- REQ-level copy still works, unchanged shape, keyed by entry_idx --
```

## Salvage from dev/proxy/proxy_copy_probe_shared.py

COMMENT L45:
```
# Direct format_proxy_block call -- no os.get_terminal_size dependency, mirrors
```

COMMENT L46:
```
# dev/display/test_hover_map.py's existing pattern. Row numbers are then shifted by 1, the same
```

COMMENT L47:
```
# shift _render_and_scroll_body applies in the real event loop (row 1 is reserved for the
```

COMMENT L48:
```
# permanent search-bar header in both panes) -- without this shift a synthetic REQ landing on raw
```

COMMENT L49:
```
# row 1 would collide with _handle_*_mouse's "row==1 -> focus search bar" branch and never reach
```

COMMENT L50:
```
# the real copy/expand dispatch at all. Returns (line_map, copy_rows) already shifted.
```

## Salvage from dev/proxy/proxy_copy_thinking_probe.py

COMMENT L85:
```
# -- copy click on the thinking row's copy column --
```

COMMENT L93:
```
# -- non-copy click on the thinking row: MUST still toggle expand/collapse, exactly as before --
```

COMMENT L101:
```
# -- clicking again toggles it back, proving this is a real toggle, not a one-way flip --
```

COMMENT L106:
```
# -- copying the sibling message row does not flash the thinking row --
```

