# 2026-09-16 — Comment/docstring salvage for dev/pane_search/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/pane_search/` (26 `.py` files) into conformance with the project's
three-marker comment standard (`# INFRASTRUCTURE` / `# ORCHESTRATOR` / `# FUNCTIONS`, nothing
else). Every comment and docstring below was relocated here verbatim before deletion from the
code, per the "relocate then delete" rule — nothing was judged and dropped.

Counts: 73 non-marker comment lines, 7 module docstrings, 0 function/class docstrings, 0
load-bearing docstrings (`grep -n "__doc__\|argparse" *.py` in the directory returns nothing).

**One correction to the predecessor's notes (their notes said "p1 to p5 do not need a pty"):**
that is wrong for `p2_search_feature_regression_test.py` and
`p5_worker_proxy_pane_parity_test.py` — both call `mod_pane._build_proxy_output()` /
`mod_wp._build_worker_proxy_output()` directly (not behind an `os.get_terminal_size` monkeypatch)
in several test cases, and `_build_proxy_output` calls the real
`src/proxy_display/proxy_pane_shared.py::_terminal_size()`, which calls bare
`os.get_terminal_size()`. Under the plain Bash tool (no tty) this raises
`OSError: [Errno 25] Inappropriate ioctl for device`. I ran ALL seven entry scripts (`p1`
through `p8`) inside `tmux new-session -x 220 -y 50` + `send-keys` + `capture-pane` uniformly,
and used `clear` before each run inside the same pane so `capture-pane -S -200` outputs don't
bleed together. Redirecting stdout to a file inside tmux (`... > file.out 2>&1`) reintroduces the
same `OSError` — confirmed this myself, matches the predecessor's warning exactly. Only
`p3_drag_select_regression_test.py` happens to avoid any unguarded `_build_proxy_output` call (its
one call to it is inside a test that first monkeypatches `os.get_terminal_size`), so it passes
under plain Bash too — but running everything through tmux uniformly is simpler than
re-deriving which suite needs it.

**Verification method:** ran every one of the 7 runnable entry scripts (`p1_full_sweep_cost_probe.py`
plus the six `_test.py` files) via tmux before making any edit, recorded PASS/FAIL counts, then
re-ran all 7 after the comment/docstring removal and diffed. All identical:
`p1`: entries=15 (synthetic fixture, see below) — sweep/lazy numbers jitter run-to-run (expected,
tracemalloc/perf_counter timing) but N/report structure identical. `p2`: 48/48 both runs. `p3`:
62/62 both runs. `p5`: 77/77 both runs. `p6`: 78/78 both runs. `p7`: 83/83 both runs. `p8`: 82/82
both runs.

`p1_full_sweep_cost_probe.py`'s hardcoded default log
(`src/logs/dual_log/api_requests_opus_wise2627_1786984319_forwarded.jsonl`) does not exist in this
worktree (rotated off, as the predecessor warned) — I generated a throwaway 15-line synthetic
`forwarded_delta` JSONL fixture at `/tmp/p1_synth_fwd.jsonl` (type=forwarded_delta, one is_first
entry + 14 delta-continuations, flow_id per line) and passed it as the positional arg. The
tracked `md/p1_full_sweep_cost_report.md` was backed up to `/tmp/p1_report_backup.md` before the
before/after runs and restored from that backup afterward (`git status --short md/` showed zero
diff after restore). Every other entry script's timestamped report under `md/` was deleted by
explicit filename after diffing (never a wildcard, per the predecessor's warning about the 14
tracked files a wildcard `rm` destroyed for them).

---

## Salvage from dev/pane_search/p1_full_sweep_cost_probe.py

Module docstring (was lines 1-32):

```
p1_full_sweep_cost_probe.py — Milestone 1 measurement probe for the proxy-pane search feature.

Core cost question: the pane keeps `messages=None` for all entries outside the last-10
window (`PROXY_MESSAGES_KEEP_LAST` in `src/constants.py`); searching ALL requests' content
requires reconstructing every entry's messages. Two candidate strategies, measured on a real
forwarded-delta log:

  1. Per-entry lazy-load: replay the forwarded delta stream from byte 0 per entry (mirrors
     `forwarded_parser._lazy_load_messages_forwarded`) — timed for ALL entries, summed + curve.
  2. One-sweep reconstruction: a single pass over the forwarded log that reconstructs and
     KEEPS messages for every entry (mirrors `forwarded_parser._parse_forwarded_log` with its
     deque eviction removed — the parser already walks the whole file for delta accumulation;
     the sweep variant just doesn't discard).

dev/ scripts must not import from src/ — the delta-accumulation algorithm
(`_dict_to_list`/`_apply_delta_to_list`/family accumulator/deque-bound eviction) is
reimplemented locally in p1_full_sweep_reconstruct.py, mirroring
`src/proxy_display/forwarded_parser.py`. Message summarization is simplified to a chars-only
count (real `src/proxy/message_summary.py` adds per-block-type detail — irrelevant to the O(N)
file-replay cost this probe measures, which is dominated by repeated file I/O + json.loads, not
summarizer detail). Both candidate strategies below share this SAME local summarizer, so the
relative comparison is apples-to-apples.

RAM measured via tracemalloc (traced current/peak bytes), isolated per scenario via
gc.collect() + tracemalloc.clear_traces().

Writes dev/pane_search/md/p1_full_sweep_cost_report.md.

Usage (from project root):
    ./venv/bin/python dev/pane_search/p1_full_sweep_cost_probe.py [fwd_log_path]
```

## Salvage from dev/pane_search/p1_full_sweep_reconstruct.py

(no comments or docstrings in this file beyond the three section markers)

## Salvage from dev/pane_search/p1_full_sweep_report.py

(no comments or docstrings in this file beyond the three section markers — the `#`-prefixed
strings inside this file, e.g. `f"""# P1 — Full-Sweep Reconstruction Cost Probe`, are markdown
report-body content returned by the functions, not Python comments; they are untouched)

## Salvage from dev/pane_search/p2_search_feature_regression_cases.py

Was lines 98-99 (inside `test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows`):
```
    # key=('msg', 5, 0) with initial_parent_count=0 lands on ZEBRA_BG_A (empty string) — the
    # exact scenario the live bug needs to reproduce (ZEBRA_BG_B rows always restored fine).
```

Was lines 112-113 (same function):
```
    # Sanity: a NON-empty chosen_bg (ZEBRA_BG_B, via initial_parent_count=1) must still resolve
    # to the real color as before — this fix must not regress the already-correct case.
```

Was line 160 (inside `test_scroll_jump_clamps`):
```
        # Many entries so total_lines exceeds a small terminal height, forcing real scrolling
```

Was line 163, trailing on a statement (same function):
```
    mod_pane._proxy_search.matches = [2]  # near the TOP of the (chronological) list
```

Was line 174 (same function):
```
        # A second render at the same (already-clamped) offset must not push it further out of range
```

Was line 196 (inside `test_flow_id_lazy_load_fix`):
```
    # Ground truth: fresh byte-0 parse, matched by flow_id
```

Was lines 200-202 (same function):
```
    # Simulate 2 incremental polling batches (batch1 = first 2 lines only, batch2 = rest) —
    # this is what reproduces the call-local _fwd_req_idx collision: batch2's req_idx restarts
    # at 0, colliding with batch1's flow-A/flow-B at the SAME local indices.
```

Was lines 238-239 (inside `test_utf8_multibyte_keypress`):
```
    # Back-to-back multi-byte + ASCII in the SAME pipe write — continuation-byte reads must not
    # over-consume into the next character
```

Was line 278, trailing on a statement (inside `test_kill_line_after_a_real_search_run`):
```
    mod_pane._handle_proxy_search_input('\r')  # Enter -> real _run_proxy_search via the real path
```

## Salvage from dev/pane_search/p2_search_feature_regression_fixtures.py

Was lines 39-46 (above `_make_entry`):
```
# Synthetic proxy entry with a UNIQUE, always-visible marker in its OWN new message (message
# index == idx, "unique_marker_<idx>") — messages list is CUMULATIVE (length == message_count,
# one prior filler message per earlier idx + this entry's own new one), matching how
# render_messages._render_new_messages finds "new" messages: range(prev_msg_count, len(messages))
# — a non-cumulative per-entry-only messages list renders as an EMPTY new-message range and the
# marker never appears (found while writing this test; see process-docs/pane_search/).
# Base shape otherwise matches dev/display/test_hover_map.py's _make_entry, extended with
# flow_id (search's merge key).
```

Was line 91 (above `_fwd_line`):
```
# Build a synthetic 2-request forwarded_delta JSONL line (is_first or delta-continuation)
```

Was lines 105-106 (above `_read_keypress_from_bytes`):
```
# Write byte_seq into a real os.pipe(), point click_handler._stdin_fd at the read end, call the
# REAL read_keypress() once. Real os.read/select.select through the actual function — not a mock.
```

## Salvage from dev/pane_search/p2_search_feature_regression_test.py

Module docstring (was lines 1-34):

```
p2_search_feature_regression_test.py — Regression guard for the M2 proxy-pane search bar
(process-docs/pane_search/).

Covers, per the M2 spec:
  - search bar renders at row 1 (always visible)
  - line_map shift correctness (body rows start at row 2, header row never gets a body key)
  - collapsed-hit marks REQ row; expanded-hit ALSO highlights the matching inner line (header
    stays marked when expanded — decision: uniform, keeps orientation when scrolling)
  - n/N jump ordering (wraps both directions)
  - Esc clears the query (matches cleared, bar stays — it's a permanent row, not a toggle)
  - scroll-jump respects the existing max_scroll clamp
  - the flow_id-based _lazy_load_messages_forwarded fix (the _fwd_req_idx collision bug found
    during M2 investigation — verified against a self-contained synthetic 2-batch fixture, not
    the real gitignored log, so this guard is portable)
  - (follow-up, 2026-08-18) UTF-8 multi-byte keypress decoding in input.click_handler.read_keypress
    — em-dash/ä-ö-ü/emoji fed through the REAL byte-wise reader via a real os.pipe() fd (not a
    mock), asserting a single correctly-decoded character comes out (not N replacement chars),
    and that the full search-bar input path accumulates the real characters into the query

(2026-08-18, sub-milestone 1 of the pane-search rollout) pane.py's search state is now ONE
search_bar.SearchState instance (`_proxy_search`) instead of 8 separate flat globals — this
file's state-pokes were mechanically updated to the new attribute path
(`mod_pane._proxy_search_query` -> `mod_pane._proxy_search.query`, etc.); all function-call
shapes (`_handle_proxy_search_input`, `_search_col_to_query_index`, `_render_proxy_search_bar`,
`_KILL_LINE_CHAR`, ...) are UNCHANGED — pane.py keeps thin compat wrappers over search_bar.py's
generic functions specifically so this suite (and any other caller) needed no other changes.

Uses REAL render_turn.py / format.py / search.py / forwarded_parser.py / pane.py functions
against synthetic data — not mocks. importlib.import_module used throughout (dev/ scripts may
not use a literal 'from src.' import line).

Run: ./venv/bin/python dev/pane_search/p2_search_feature_regression_test.py
```

(the `f"# P2 search feature regression — {ts}"` string later in this file is report-body markdown
content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/p3_drag_select_regression_cases.py

Was line 24, trailing on a statement (inside `test_col_to_index_wide_char`):
```
    q = 'a😀b'  # a(1w) emoji(2w) b(1w)
```

Was line 26 (same function):
```
    # cols: label_w+1='a', label_w+2..3=emoji(2 cells), label_w+4='b'
```

Was line 45, trailing on a statement (inside `test_drag_select_copies_to_clipboard`):
```
        press_changed = mod_pane._handle_proxy_mouse(0, label_w + 2, 1)  # anchor at index1 ('e')
```

Was line 51, trailing on a statement (same function):
```
        motion_changed = mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # extend to index6 ('w')
```

Was line 99, trailing on a statement (inside `test_body_row_drag_never_arms_search_selection`):
```
    press_changed = mod_pane._handle_proxy_mouse(0, 5, 2)  # press on a body row, not row 1
```

Was line 101, trailing on a statement (same function):
```
    motion_changed = mod_pane._handle_proxy_mouse(32, 40, 2)  # motion after a body-row press
```

Was line 145, trailing on a statement (inside `test_backspace_deletes_active_selection`):
```
    mod_pane._handle_proxy_mouse(0, label_w + 2, 1)   # anchor at index1 ('e')
```

Was line 146, trailing on a statement (same function):
```
    mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # extend to index6 ('w') -> selects 'ello '
```

Was line 242, trailing on a statement (inside `test_render_reverse_video_bracket`):
```
    mod_pane._handle_proxy_mouse(0, label_w + 2, 1)   # index1
```

Was line 243, trailing on a statement (same function):
```
    mod_pane._handle_proxy_mouse(32, label_w + 7, 1)  # index6
```

Was line 251, trailing on a statement (same function):
```
    _reset_state('hello world')  # no selection
```

Was line 266, trailing on a class attribute (inside `test_session_change_clears_selection`,
`_FakeMonitor` class):
```
    active_project_filter = None  # keeps parse_proxy_log_forwarded/find_proxy_log_path as safe no-ops
```

Was line 274, trailing on a statement (same function):
```
    mod_pane._proxy_current_main_session = None  # force the session-change branch to fire
```

## Salvage from dev/pane_search/p3_drag_select_regression_fixtures.py

(no comments or docstrings in this file beyond the three section markers)

## Salvage from dev/pane_search/p3_drag_select_regression_test.py

Module docstring (was lines 1-37):

```
p3_drag_select_regression_test.py — Regression guard for drag-to-select on the proxy pane's
search bar (row 1), process-docs/pane_search/.

Covers, per the milestone spec:
  - button-0 press on row 1 anchors a selection at the char under the pointer (col->char-index
    mapping, _cell_width-aware for wide chars — em-dash/emoji land in queries per the UTF-8 fix)
  - motion (button 32 = left button held, the 0+32 SGR flag) extends the selection; row is
    ignored while dragging, so vertical drift during a fast drag doesn't break it
  - release finalizes: copies the selected substring to the clipboard via the real
    copy_to_clipboard (monkeypatched to a capturing stub, no real pbcopy call)
  - a plain click (press+release, NO motion in between) does NOT copy anything (must never
    clobber the real clipboard with an empty string) and preserves today's focus-only behavior
  - selection renders as SGR reverse-video (\033[7m...\033[27m) bracketing the exact substring
  - click elsewhere, new keyboard input, Esc-cancel, and session-change all clear a live
    selection's highlight
  - a drag that starts on a BODY row (not row 1) never arms search-bar dragging — button-32
    motion after a body-row press falls through to the unchanged generic hover bucket
  - editor-style deletion: Backspace with an active selection deletes it; kill-line (Cmd+Backspace
    hypothesis) empties the whole query; neither clears _proxy_search.matches

(2026-08-18, sub-milestone 1 of the pane-search rollout) pane.py's search state is now ONE
search_bar.SearchState instance (`_proxy_search`) instead of 8 separate flat globals — this
file's state-pokes were mechanically updated to the new attribute path
(`mod_pane._proxy_search_dragging` -> `mod_pane._proxy_search.dragging`, etc.); all function-call
shapes (`_handle_proxy_mouse`, `_search_col_to_query_index`, `_render_proxy_search_bar`,
`_KILL_LINE_CHAR`, ...) are UNCHANGED — pane.py keeps thin compat wrappers over search_bar.py's
generic functions specifically so this suite needed no other changes.

Uses REAL src.proxy_display.pane functions against direct (button, col, row) calls — not a
mock of the mouse-event layer itself (read_mouse_event's own SGR parsing is unchanged and out
of scope here; these tests exercise everything downstream of it, matching the milestone's
own investigation: button 32 for a held-left-button drag is a documented SGR protocol fact,
not something this suite re-derives from raw bytes).

Run: ./venv/bin/python dev/pane_search/p3_drag_select_regression_test.py
```

(the `f"# P3 drag-select regression — {ts}"` string later in this file is report-body markdown
content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/p5_worker_proxy_pane_parity_cases_mechanics.py

Was line 121, trailing on a statement (inside `test_body_row_click_clears_selection`):
```
    changed = _click(0, 5, 10)  # unmapped body row, no header regions registered
```

## Salvage from dev/pane_search/p5_worker_proxy_pane_parity_cases_search.py

Was line 114, trailing on a statement (inside `test_worker_switch_resets_search_state`):
```
    mod_wp._worker_proxy_last_worker_name = 'workerA'  # pretend we're currently on workerA
```

## Salvage from dev/pane_search/p5_worker_proxy_pane_parity_fixtures.py

Was lines 36-37 (above `_make_wp_entry`):
```
# Synthetic worker-proxy entry — same shape as p2/p3's _make_entry (proxy pane fixtures),
# required by build_search_matches/_render_req_expanded regardless of which pane calls them.
```

Was lines 93-94 (above `_build_output_with_worker`):
```
# Runs _build_worker_proxy_output with a real (temp-file-backed) selection, monkeypatching only
# get_selection_file_path — every other real function (format_proxy_block, _format_worker_proxy_header, ...) runs unmocked.
```

Was lines 109-110 (above `_fwd_line`):
```
# Build a synthetic forwarded_delta JSONL line (mirrors p2_search_feature_regression_test.py's
# _fwd_line — same fixture shape, reconstruct_all_messages is the shared function under test)
```

## Salvage from dev/pane_search/p5_worker_proxy_pane_parity_test.py

Module docstring (was lines 1-36):

```
p5_worker_proxy_pane_parity_test.py — Regression guard for the worker-proxy pane reaching
search-bar parity with the proxy pane (rollout sub-milestone 3, process-docs/pane_search/).

worker_proxy_pane.py is the proxy pane's closest structural twin — same format_proxy_block/
render_turn pipeline (search kwargs already threaded through, previously defaulted off for this
pane specifically), same forwarded-log data model, same one-sweep reconstruct_all_messages
strategy, same flow_id-fixed _lazy_load_messages_forwarded. The NEW work this milestone covers:

  - 2-ROW HEADER: the search bar takes row 1 (uniform rule); the existing worker-switcher header
    (_format_worker_proxy_header, variable height, click-region table) shifts to row 2+.
    _worker_proxy_header_regions (rows relative to the header's OWN top, computed by the pure
    helper worker_proxy_helpers.py — untouched) get shifted by +_WP_SEARCH_BAR_LINES in
    _build_worker_proxy_output, same rebuild-then-shift pattern already used for
    worker_proxy_line_map/_worker_proxy_copy_rows. content_height/body_hover use
    total_header_lines = _WP_SEARCH_BAR_LINES + worker_header_lines, not the old header_lines
    alone.
  - row-1 press/motion/release drag-select, editor-style deletion (selection-delete Backspace,
    kill-line), n/N jump reusing the EXISTING _wp_just_expanded/worker_item_positions/
    scroll-clamp mechanism (same anchor for collapsed and expanded matches)
  - Enter (_worker_proxy_search_on_commit) always re-runs (no unchanged-query gate — proxy's
    convention, no main-pane-style gate ever existed here to correct); one-sweep
    reconstruct_all_messages merge by flow_id when _worker_proxy_log_path is set
  - WORKER-SWITCH RESET: _refresh_worker_proxy_data's existing worker-change branch (fires for
    BOTH digit-key and header-marker selection, same selection-file + force_reload convergence
    point) now also calls search_bar.handle_search_cancel(_worker_proxy_search) — mirrors
    pane.py's session-change reset and the same fix just landed on the main pane. A stale
    .matches list of entry_idx values would otherwise point into the log just switched away
    from.

Uses REAL src.proxy_display.worker_proxy_pane functions against synthetic entries/workers —
not mocks. importlib.import_module used throughout (dev/ scripts may not use a literal
'from src.' import line).

Run: ./venv/bin/python dev/pane_search/p5_worker_proxy_pane_parity_test.py
```

(the `f"# P5 worker-proxy pane parity regression — {ts}"` string later in this file is
report-body markdown content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/p6_tokens_pane_parity_cases_matching.py

Was line 96 (inside `test_light_red_bg_still_detected_when_call_is_also_a_match`):
```
    # cache_creation > cache_read triggers cc_broken -> LIGHT_RED_BG prefix in _format_cache_call
```

Was lines 112-115 (inside `test_jump_to_match_moves_scroll_offset`):
```
    # _tokens_nav is populated by the LAST render (mirrors core/monitor_display.py's
    # ensure_match_visible reading _search_all_line_offsets) — one render must happen first,
    # exactly as it would in the live pane loop (the pane is always rendering independently of
    # search actions).
```

## Salvage from dev/pane_search/p6_tokens_pane_parity_cases_mechanics.py

Was line 88, trailing on a statement (inside `test_body_click_clears_selection`):
```
    changed = mod_tp._handle_tokens_mouse(0, 5, 10)  # unmapped body row
```

## Salvage from dev/pane_search/p6_tokens_pane_parity_fixtures.py

Was lines 34-36 (above `_make_turn`):
```
# Synthetic turn — one call, optionally carrying a marker in its own prompt (turn-level match
# surface) and/or a content_blocks text preview (call-level match surface, only found by the
# matcher's force-expand, invisible when collapsed in a real render).
```

## Salvage from dev/pane_search/p6_tokens_pane_parity_test.py

Module docstring (was lines 1-48):

```
p6_tokens_pane_parity_test.py — Regression guard for the tokens pane's search bar reaching
parity with the proxy pane (rollout sub-milestone 4, process-docs/pane_search/).

token_pane.py is structurally simpler than the proxy family: single expand level
(cache_expand_states[(turn_idx, call_idx)], turns themselves never collapse), data ALWAYS
fully loaded incrementally (no windowing, no reconstruction step — on_commit just builds
matches over what's in memory via token_search.build_token_search_matches). Three genuinely
new pieces this milestone had to build:

  - THE SENTINEL BUG, SAME CLASS AS THE PROXY PANE: ZEBRA_BG_A == '' (confirmed in
    constants.py) is the chosen_bg for every non-hovered/non-error row and every detail line.
    Search highlights are embedded with search_bar._BG_RESTORE_SENTINEL at construction time
    (token_format.py) and resolved via search_bar.resolve_bg_restore(line, chosen_bg) in
    token_pane.py's own hand-rolled row loop, right after chosen_bg is chosen — exact same
    fix shape as process-docs/pane_search/2026-08-18_highlight_flood_empty_bg_fix.md.
  - 2-ROW HEADER: format_cache_tracker's optional sticky_header (row 1 when scrolled, before
    this milestone) now shifts to row 2 — the search bar (_TOKENS_SEARCH_BAR_LINES=1, fixed)
    always wins row 1. format_cache_tracker's own internal viewport reservation (-1, for the
    sticky-header slot) is UNTOUCHED; _build_tokens_output now passes pane_height -
    _TOKENS_SEARCH_BAR_LINES as format_cache_tracker's own pane_height argument instead.
  - TWO-KEY MATCH SEMANTICS: a match key is either (turn_idx, call_idx) [found in that call's
    own header or force-expanded detail content] or ('turn', turn_idx) [found in the turn's
    own prompt/timestamp line — turns have no expand state]. BOTH get an UNCONDITIONAL
    whole-line "container mark" (not a literal-substring-only wrap) regardless of expand
    state — mirrors proxy's REQ-header "text extent" marking, since the actual matching text
    may be buried in unrendered (collapsed) detail. An EXPANDED matching call additionally
    gets its specific matching detail line(s) browser-find substring-highlighted. ('turn', idx)
    keys are deliberately kept OUT of line_keys/cache_line_map (turn headers stay
    non-interactive for clicks, exactly as before) — see format_cache_tracker's new nav_out
    param, populated separately for jump-to-match scroll math only.

format_cache_tracker's signature grew (search_match_set/search_current_key/search_query/
nav_out, all optional, all default to a no-op) WITHOUT changing its return arity — verified
byte-identical against all 4 real callers (token_pane.py, workers/worker_format.py,
dev/click_ui/p2_copy_click_probe.py, dev/display/A_format_cache_tracker_proof.py) via a
frozen-turns old-vs-new comparison (the live dev/display/A_format_cache_tracker_proof.py
harness reads directly from ~/.claude/projects/.../*.jsonl — the top-10-most-recently-modified
REAL session files — which turned out to be actively growing during this session, producing a
false-positive mismatch on a naive capture-then-verify-later run; the frozen-snapshot
comparison, held constant across both code versions in the same process, is the reliable
evidence and is not re-run here — see process-docs/pane_search/ for the full writeup).

Uses REAL src.panes.token_pane / src.format.token_format / src.panes.token_search functions
against synthetic turns — not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p6_tokens_pane_parity_test.py
```

(the `f"# P6 tokens pane parity regression — {ts}"` string later in this file is report-body
markdown content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/p7_workers_pane_parity_cases_matching.py

(no comments or docstrings in this file beyond the three section markers)

## Salvage from dev/pane_search/p7_workers_pane_parity_cases_mechanics.py

Was line 102, trailing on a statement (inside `test_body_click_clears_selection`):
```
    changed = mod_wt._handle_worker_tokens_mouse(0, 5, 10, _MONITOR)  # unmapped body row
```

## Salvage from dev/pane_search/p7_workers_pane_parity_fixtures.py

Was lines 68-71 (above `_setup_one_worker_jsonl`):
```
# Write a real throwaway JSONL fixture (one user prompt + optional one assistant tool_use call)
# for a single worker, monkeypatch find_worker_jsonl to resolve it. Real reconstruction pipeline
# (read_new_lines -> parse_jsonl_lines -> extract_cache_turns, via panes.cache_turns.build_cache_turns)
# runs unmocked -- only the tmux-session -> path RESOLUTION is stubbed.
```

## Salvage from dev/pane_search/p7_workers_pane_parity_test.py

Module docstring (was lines 1-38):

```
p7_workers_pane_parity_test.py -- Regression guard for the worker-tokens pane's search bar and
worker-switch header (rollout sub-milestone 5 originally targeted the all-workers list pane,
worker_pane.py; RETARGETED 2026-09 for the panesplit milestone, since that pane is gone -- the
workers list was replaced with worker_tokens_pane.py, a single-selected-worker cache tracker
carrying a switch header, mirroring worker_proxy_pane.py's own shape).

worker_tokens_pane.py is now structurally the tokens pane's closest twin (single cache-tracker
view, `format_cache_tracker`, two-tier match keys) PLUS the worker-proxy pane's own switch-header
mechanics (2-row header: search bar row 1, worker-switch markers row 2+, IPC-file-driven
worker-switch reset). This suite covers both halves:

  - THE SAME MECHANICS SUITE AS p6_tokens_pane_parity_test.py: drag-select press/motion/release,
    editor-style deletion (selection-delete Backspace, kill-line), n/N jump, Esc, the
    `ZEBRA_BG_A == ''` sentinel-resolution bug (now a 4th occurrence, same fix each time), the
    `LIGHT_RED_BG` detection regression (`.startswith()` -> `in`) -- because only ONE worker is
    ever visible at a time now, match keys are the plain `(turn_idx, call_idx)` / `('turn',
    turn_idx)` two-tier shape `token_pane.py` already uses -- NOT the old three-tier
    worker-wrapped shape (`(name, turn_idx, call_idx)`) the deleted worker_pane.py needed, since
    there is no second, simultaneously-visible worker's content left to accidentally leak into.
  - THE 2-ROW HEADER + WORKER-SWITCH MECHANICS OF p5_worker_proxy_pane_parity_test.py: search bar
    row 1, worker-switch header row 2+ (built by the SAME shared
    `workers/worker_switch_header.py::format_worker_switch_header` the worker-proxy pane uses),
    and a NEW worker-switch reset. This is a deliberate behavior CHANGE from the deleted
    worker_pane.py, which explicitly had NO worker-switch reset (documented there as "no single
    current worker to switch away from" -- true for a list showing every worker at once, false
    for this pane, which now has exactly one current worker, same as worker-proxy). Switching
    worker resets search AND scroll to 0 -- the real successor to the old, vacuous
    `test_workers_scroll_reset_on_expand` in dev/display/test_hover_map.py (which never called
    real code to begin with).

Uses REAL src.workers.worker_tokens_pane / src.format.token_format / src.panes.token_search
functions against synthetic turns, plus real throwaway JSONL fixture files (find_worker_jsonl
monkeypatched to point at them) for the match-search tests -- not mocks of the reconstruction
pipeline itself. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p7_workers_pane_parity_test.py
```

(the `f"# P7 worker-tokens pane parity regression -- {ts}"` string later in this file is
report-body markdown content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/p8_warnings_gpu_news_parity_cases_gpu.py

Was line 26 (inside `test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally`):
```
    # Replicate run_gpu_loop's own external shift snippet
```

## Salvage from dev/pane_search/p8_warnings_gpu_news_parity_cases_news.py

(no comments or docstrings in this file beyond the three section markers)

## Salvage from dev/pane_search/p8_warnings_gpu_news_parity_cases_warnings.py

Was lines 23-25 (inside `test_warnings_dim_yellow_bg_already_used_in_not_startswith`):
```
    # (2026-09, panes-split milestone) the zebra/hover row loop that carries this check moved out
    # of _format_warnings_pane into its own _render_warnings_rows helper — re-pointed here, same
    # assertion, same target concern.
```

Was line 92, trailing on a statement (inside
`test_warnings_plain_click_no_clipboard_and_body_clears_selection`):
```
    changed = mod_wpane._handle_warnings_mouse(0, 5, 20)  # unmapped body row
```

Was lines 127-130 (inside `test_warnings_collapsed_container_mark_and_expanded_substring_mark`):
```
    # first_word_of_call (warnings_render's OWN pre-existing collapsed-row inline preview) shows
    # only the Bash command's FIRST WORD even when collapsed -- 'echo' here, never the marker
    # itself -- so a multi-word command is needed to prove the match was found in HIDDEN content
    # (the matcher checks the full tool_call_input value; the collapsed render does not show it).
```

## Salvage from dev/pane_search/p8_warnings_gpu_news_parity_fixtures.py

Was line 32 (above `_make_error`):
```
# Synthetic tool_errors entry
```

Was lines 49-51 (above `_dispatch_gpu_click`):
```
# Mirrors run_gpu_loop's inline row-1/button dispatch (dev/click_ui/p4_gpu_news_button_probe.py's
# own established convention for these two panes -- mouse dispatch is inline, not a standalone
# function).
```

## Salvage from dev/pane_search/p8_warnings_gpu_news_parity_test.py

Module docstring (was lines 1-34):

```
p8_warnings_gpu_news_parity_test.py -- Regression guard for the FINAL three panes reaching
search-bar parity (rollout sub-milestones 6-8, bundled, process-docs/pane_search/): warnings
(src/panes/warnings_pane.py + warnings_render.py), gpu (src/gpu_pane/pane.py), and news
(src/news_pane/pane.py ONLY -- log_pane.py is EXCLUDED per the approved decision).

WARNINGS: 1-level expand (error_expand_states[idx]), full data always loaded. The verification
this milestone explicitly required: warnings_render.py's row-bg loop was read at line level
before assuming anything -- it ALREADY used `DIM_YELLOW_BG in line` (substring), not
`.startswith()`, so no collateral fix was needed there (unlike every prior pane). ZEBRA_BG_A==''
DOES still apply (same shared constant) -- search_bar.resolve_bg_restore is threaded into this
same (already-correct) loop. Match key is a bare int err_idx (no nesting -- one expand level).
Two-stage marking: collapsed error container-marks its whole header row; expanded ADDITIONALLY
substring-highlights the matching detail line(s). header_lines param generalizes the previously
hardcoded single-header-row offset (default 1, warnings_pane.py passes 2 for search bar +
[refresh]).

GPU + NEWS: flat, small live-fetched lists, NO scroll/viewport infra at all (pane_height is
accepted by _render_pane but never read -- confirmed by grep before implementing). Per the
approved decision: full bar mechanics (drag-select, editor-style deletion, kill-line) but
HIGHLIGHT-ONLY -- no jump-to-match. n/N still cycles current_idx (which on-screen match gets
SEARCH_CURRENT_BG vs SEARCH_MATCH_BG, and the N/M counter) with ZERO scroll call. No sentinel
needed in either pane -- neither has a per-row background/zebra/hover loop at all, so
utils.highlight_query_in_line's default restore_bg is directly correct (same simple case as the
main pane). _render_pane's OWN row numbering stays UNSHIFTED/relative to its own top in both
panes -- the search-bar row shift for _button_regions happens externally, in the loop, exactly
mirroring worker_proxy_pane's precedent -- verified by dev/click_ui/p4_gpu_news_button_probe.py
needing ZERO changes (it calls _render_pane directly).

Uses REAL src.panes.warnings_pane / warnings_render / src.gpu_pane.pane / src.news_pane.pane
functions against synthetic data -- not mocks. importlib.import_module used throughout.

Run: ./venv/bin/python dev/pane_search/p8_warnings_gpu_news_parity_test.py
```

(the `f"# P8 warnings + gpu + news panes parity regression -- {ts}"` string later in this file is
report-body markdown content written to disk, not a Python comment — untouched)

## Salvage from dev/pane_search/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas
- `ZEBRA_BG_A` is the empty string (`''`) — substituting a background sentinel with it (instead of
  the SGR reset `\033[49m`) silently deletes the sentinel rather than clearing the background,
  flooding a highlight color to end-of-line. Every pane's parity suite (`p2_`, `p6_`, `p7_`, `p8_`)
  re-checks this because each pane's row-background loop is a separate hand-rolled implementation.
- `format_cache_tracker`'s `nav_out` dict mixes tuple keys (`(turn_idx, call_idx)`, `('turn',
  turn_idx)`) with a string key (`'total_lines'`) — anything hashing or JSON-serializing it with
  `sort_keys=True` needs every key stringified first.
- Synthetic fixture entries must build a CUMULATIVE `messages` list (length == `message_count`, one
  filler message per earlier index) — `render_messages._render_new_messages` finds "new" messages via
  `range(prev_msg_count, len(messages))`, so a non-cumulative per-entry-only list silently renders an
  empty new-message range and a placed marker never appears.
- The `pN_*_fixtures.py`/`_cases*.py` split modules are never run directly — always invoke the
  `pN_..._test.py` (or `p1_full_sweep_cost_probe.py`) entry file at its documented path; the split
  exists purely to keep each file under the 400-LOC/50-line-function code-standard thresholds.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
