# 2026-09: `src/workers/` split by concern (worker_pane.py, worker_format.py)

## Trigger

`worker_pane.py` sat at 546 LOC (limit 400) with three functions over the 50-LOC
helper-extraction threshold (`run_workers_loop` 74, `_handle_workers_mouse` 62,
`_build_workers_output` 74); `worker_format.py`'s `format_workers_block` sat at 121 LOC (flagged
HARD against the repo's 100-LOC ceiling). The mandate was a split by CONCERN — selection IPC,
clipboard serialization, mouse/key handling, search-bar reconstruction, data refresh, output
build — with zero output/behavior change and no re-export shims, following the same methodology
`process-docs/proxy_display/` already used for `parser.py`/`pane.py`/`worker_proxy_pane.py`.

## Investigation

Read every `.py` file in `src/workers/`, `src/workers/DOCS.md`, the seven required dev probes,
and `src/proxy_display/proxy_pane_shared.py` (for the established shared-helper style) in full
before writing a plan. Grepped every `mod_wp.<name>` / `mod_workers.<name>` / `wpane.<name>`
attribute access across all seven probes plus a broader `src/`+`dev/` sweep to build the
definitive "must stay exactly named, exactly in this module" list before touching any code.

**The load-bearing constraint carried over from the prior proxy_display milestone, restated
precisely for scalars.** `dev/pane_error_log/p1_pane_loop_survives_exception_probe.py`
monkeypatches `read_keypress`/`copy_to_clipboard`/etc. as attributes of `worker_pane` — any
function performing the literal `find_worker_jsonl(...)` (or `copy_to_clipboard(...)`,
`read_keypress()`) call must be DEFINED in `worker_pane.py`, because a bare-name lookup resolves
against the DEFINING module's own `__dict__`, not the caller's. This milestone additionally
identified a SECOND, distinct constraint the previous one didn't need to name explicitly: any
function that reassigns a **scalar** module global via `global` (`worker_selected_name`,
`worker_hover_row`, `_worker_pane_width`) must ALSO stay physically defined in `worker_pane.py` —
moving it and importing it back would rebind the WRONG module's copy of the name, silently
desyncing the in-memory value from what dev probes read directly off `worker_pane.<name>` (a real
behavior change no assertion might catch, not just a monkeypatch break). Dict/set *mutations*
(not rebinds) were confirmed safe to relocate, since Python passes/imports containers by
reference — this distinction (rebind vs. mutation) drove most of the split's shape.

**Reproducing a real worker JSONL in the byte-identity harness hit the same live-log-growth
pitfall as the prior milestone's forwarded-log harness**, but manifested differently: two
consecutive runs of the initial `dev/workers/format_byte_identity.py` (picking the newest file
under `~/.claude/projects/`) produced DIFFERENT hashes even seconds apart, because the newest
JSONL was this very agent's own actively-growing transcript. Fixed two ways: (1) bounded the read
to a fixed-size prefix (`lines[:200]`, `turns[:10]`) — an append-only file's own prefix never
changes regardless of how much more gets appended, so this alone made two consecutive runs
stable; (2) added `WORKERS_BYTE_IDENTITY_JSONL` (mirroring `RENDER_BYTE_IDENTITY_LOG_DIR`) for a
fully pinned before/after comparison spanning the whole implementation window, via a frozen
`/tmp` snapshot copied once. Baseline and post-implementation hashes matched exactly:
`be0580dbfa07a9fba182cdc871234a67d51e97036fd061cfe932fd4c002631ac`.

## Decisions

**`worker_pane.py` split into four sibling modules, chosen by which constraint each function's
own body was free of.** `worker_selection.py` (`get_selection_file_path`, `_write_selection`) —
pure, never monkeypatched, never referenced by exact name in any probe (only through
`worker_pane.py`'s own re-import). `worker_clipboard.py` (`_serialize_workers`) — gained an
explicit `worker_turns: dict` parameter in the move (was a bare module-global read before),
mirroring `proxy_pane_shared._serialize_proxy_entry(key, entries)`'s own explicit-argument shape.
`worker_render.py` — every genuinely pure viewport/row-render/jump-scroll computation
(`_workers_terminal_size`, `_compute_viewport`, `_render_workers_rows`,
`_resolve_workers_hover_key`, `apply_scroll`, `compute_jump_scroll_offset`); confirmed
`apply_scroll` (extracted from `_handle_workers_mouse`'s wheel branch) has NO scalar rebind
before moving it — it only mutates `worker_scroll_offsets` in place and reads `selected_name` —
so it was safe to relocate even though its sibling branch (`_handle_workers_body_click`, which
DOES rebind `worker_selected_name`) had to stay local. `worker_search.py`
(`workers_search_on_commit`) — the search bar's on_commit body, which itself never touched a
scalar global; its ONE monkeypatch-sensitive dependency (`find_worker_jsonl`, via the JSONL-load
chain) was resolved by INJECTING `worker_pane._load_worker_turns` as a callable parameter rather
than importing `find_worker_jsonl` independently — the same established pattern already used for
`copy_to_clipboard` in `search_bar.handle_search_mouse_release`. This avoided a circular import
between `worker_pane.py` and `worker_search.py` that a naive "just import `_load_worker_turns`
into `worker_search.py`" approach would have hit (the reverse direction — `worker_pane.py`
importing `workers_search_on_commit` from `worker_search.py` — has no such cycle since
`worker_search.py` needs nothing from `worker_pane.py` at its own import time).

**`_load_worker_turns`/`_parse_worker_turns` consolidate a chain that was repeated three times
inline** (`find_worker_jsonl` → `read_new_lines` → `parse_jsonl_lines` → `extract_cache_turns`,
in the pre-split `_workers_search_on_commit`, `_jump_to_workers_match`, and
`_refresh_workers_data`) — split into two functions specifically so `_refresh_workers_data`
(which already has `jsonl_path` resolved for two OTHER calls in the same loop iteration) can
reuse just the parse half (`_parse_worker_turns`) without a redundant second
`find_worker_jsonl` call, while the two match-driven callers use the full
`_load_worker_turns(session)` chain.

**`worker_pane.py` landed at 398 LOC after the four-module split plus one further internal
extraction** (`worker_render.compute_jump_scroll_offset`, pulling the `format_cache_tracker(...,
nav_out=...)` call + its scroll-math out of `_jump_to_workers_match`'s tail, which had no scalar
rebind of its own) — the first pass at the split (selection + clipboard + hover-key-resolve +
render-loop moved out) landed at 415 LOC, still over the limit; this additional extraction plus
trimming two verbose multi-line comments closed the remaining gap. `worker_format.py`'s
`format_workers_block` split followed the task's own explicit hint (header line / expanded view /
freeze-badge region as separate helpers) without complication — none of its extracted pieces
touch module state at all, since `worker_format.py` has none.

## Verification

`dev/workers/format_byte_identity.py` (new) — hash identical before/after
(`be0580dbfa07a9fba182cdc871234a67d51e97036fd061cfe932fd4c002631ac`) across a 3-variant ×
2-pane-width matrix (frozen/selected/copy_feedback/search on and off), against a frozen real
worker JSONL snapshot. All 7 required probes (`p7_workers_pane_parity_test`,
`p5_worker_proxy_pane_parity_test`, `p1_worker_selection_click_probe`, `p2_copy_click_probe`,
`p3_button_click_probe`, `p1_pane_loop_survives_exception_probe`, `test_hover_map`) plus
`IMPORT_OK` passed both before and after; `p6_tokens_pane_parity_test` (not required, touches
`worker_format` only in prose) run as an extra sanity check, also passed.
