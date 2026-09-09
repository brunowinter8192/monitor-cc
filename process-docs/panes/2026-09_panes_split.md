# src/panes/ concern split (2026-09)

## Task

`token_pane.py` was 424 LOC (over the 400 ceiling) with 3 functions over 50 LOC
(`run_tokens_loop` 67, `build_cache_turns` 53, `_build_tokens_output` 53); `warnings_pane.py` had
one over-50 function (`run_warnings_loop` 71); `warnings_render.py` had one (`_format_warnings_pane`
97). Goal: split by concern under the same limits as the proxy addon-split milestones, with
byte-identical behavior.

## Investigation before implementing

Read every `.py` in `src/panes/`, `src/panes/DOCS.md`, `src/workers/worker_render.py`,
`src/proxy_display/proxy_pane_shared.py` (both cited as precedent for a prior "helper-extraction
milestone" pattern of pulling pure render/logic helpers into sibling modules), and all 9 probes
named in the behavior-proof command.

**Monkeypatch constraint, confirmed by reading the probes, not assumed from the brief:**
`dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` and `dev/pane_search/p6`/`p7`
monkeypatch `read_keypress`, `setup_keyboard_input`, `enable_mouse`, `disable_mouse`,
`restore_terminal`, `wait_for_input`, `copy_to_clipboard` as MODULE ATTRIBUTES of the pane module
itself, then rely on functions physically defined in that module resolving those names via bare
lookup against the module's own (now-patched) globals. A function moved to another module and
re-imported back would resolve those names against the OTHER module's globals instead, silently
breaking the monkeypatch. This is why `_poll_tokens_input`/`_poll_warnings_input` (extracted from
the two loop functions) had to stay physically in `token_pane.py`/`warnings_pane.py` rather than
move to a shared helper module, and why `_handle_tokens_mouse`/`_handle_tokens_key`/
`_handle_tokens_search_release` (all reference `copy_to_clipboard` bare-name) stayed too.

**A genuine conflict found before Go, not discovered mid-implementation:**
`dev/pane_search/p8_warnings_gpu_news_parity_test.py::test_warnings_dim_yellow_bg_already_used_in_not_startswith`
does `inspect.getsource(mod_wrender._format_warnings_pane)` and asserts the literal substring
`'DIM_YELLOW_BG in line'` is present inside THAT function's own compiled source — the only
`inspect.getsource` check across all 9 probes (grep-confirmed). The milestone brief's default plan
(extract the per-error rendering AND the viewport/zebra row loop out of `_format_warnings_pane`)
would have moved that literal check-line into a different function's source, failing the probe on
a pure implementation-detail assertion despite identical runtime behavior. Flagged in the pre-Go
report rather than worked around silently; the proposed default was to leave the zebra/viewport
loop inline and extract only the per-error-line rendering. Main's Go instruction overrode this:
extract the zebra/viewport loop too (for a firmer margin under 50 LOC), and re-point the probe's
`inspect.getsource` target to the new helper (`_render_warnings_rows`) instead — an explicit,
Main-approved dev-script edit, not a default the worker chose unilaterally.

## What moved and why

`build_cache_turns` → new `src/panes/cache_turns.py`. Unlike every other extraction in this
milestone, this one had an independent justification beyond LOC: it is a pure JSONL-turn
accumulation function with zero pane-loop/module-state coupling, imported by two OTHER real
modules (`proxy_display/pane.py`, `proxy_display/worker_proxy_pane.py`) — a genuine data concern,
not a pane concern. Its own over-50-LOC fix (`_merge_duplicate_turn` helper for the duplicate-call
merge branch) happened in the new module. Re-pointed both real importers plus `token_pane.py`'s
own usage; grep confirmed no other importer existed before the move.

`_poll_tokens_input`/`_poll_warnings_input` — extracted from the two loop functions, stayed local
per the monkeypatch constraint above.

`_render_tokens_rows` — extracted from `_build_tokens_output`, stayed in `token_pane.py` (no
cross-module reuse case; the milestone brief's own "Optional" note said explicitly not to fold
this loop with `warnings_render._render_warnings_rows` / `workers/worker_render._render_workers_rows`
this round, despite the three being structurally near-identical — they differ in the
search-match-substring-bg constant checked (`LIGHT_RED_BG` in two, `DIM_YELLOW_BG` in the third)
and in key handling shape). A real 3-way fold is flagged as a plausible future milestone, not
attempted here.

`_format_warnings_pane` split into `_build_one_warning_lines` (one error's header + optional
detail lines), `_build_warnings_lines` (loops the above over `tool_errors`), and
`_render_warnings_rows` (the viewport-clipped zebra/hover loop) — `_format_warnings_pane` itself
kept its name and became a thin orchestrator (97 LOC → 31 LOC).

## Verification

New harness `dev/panes/render_byte_identity.py`: (1) feeds `build_cache_turns` a frozen 300-line
session-JSONL prefix in growing chunks (not just a single final call — this is what actually
exercises the duplicate-call merge path the LOC-split touches), hashing turns after every chunk;
(2) runs `_format_warnings_pane` over a synthetic 4-error list (mixed expanded/collapsed, one
with a strip overlay, one with a search match) at two pane widths, hashing `(output, line_map)`.
Hash `b1161b3b00fe58b5edcd4b8f3aef79ff59eb7f0c3333cf30c68a6c4addc02679` — identical before and
after the split.

All 9 named probes (`p6`/`p7`/`p8` pane-search parity, `p2` search-feature regression, `p2`/`p3`
click-UI probes, `p1` pane-loop exception-survival, `test_hover_map.py`, `test_log_janitor.py`)
passed unchanged after the split, including the re-pointed `p8` `inspect.getsource` check.
