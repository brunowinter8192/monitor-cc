# 2026-09: `src/proxy_display/` helper extraction, milestone B (format.py, forwarded_parser.py, render_messages.py, render_sections.py)

## Trigger

Nine functions across the render/parse cluster sat at or over the 50-LOC helper-extraction
threshold: `format_proxy_block` (60), `_extract_forwarded_fields` (58), `_parse_forwarded_log`
(81), `_lazy_load_messages_forwarded` (55), `_render_modified_messages` (51),
`render_system_blocks` (85), `_render_tool_dual` (69), `_render_tool_legacy` (52), `render_tools`
(59). `render_sections.py` itself sat at 397 LOC, one bad extraction away from the 400-LOC file
limit. The mandate was helper extraction with byte-identical output, no re-export shims, and (if
`render_sections.py` tipped over 400) a split by concern.

## Investigation

Read `format.py`, `forwarded_parser.py`, `render_messages.py`, `render_sections.py`,
`render_turn.py`, `search.py`, and `src/proxy_display/DOCS.md` in full before writing a helper
plan. Grepped every known external importer (`pane.py`, `worker_proxy_pane.py`,
`proxy_pane_shared.py`, `render_turn.py`, `search.py`, `dual_log_cli/project_map.py`,
`panes/token_pane.py`, and the dev/ scripts named in the milestone prompt) for every symbol on the
"keep name AND module" list before touching any of them.

**Repeated-pattern verification.** The milestone's own observation flagged two spellings of the
same empty-line case in `render_sections.py`'s text-emission blocks — `f"{bg}{DIM}{SOFT_RESET}"`
(explicit `if not raw_line: ... continue`) vs `f"{bg}{DIM}{raw_line or ''}{SOFT_RESET}"`. Verified
by hand that `raw_line or ''` evaluates to `''` exactly when `raw_line` is falsy, so both spellings
produce the identical string — safe to fold into one shared helper (`_emit_text_lines`) without
a transform-guard for the empty case.

**Live-log-growth pitfall in the byte-identity harness.** The harness (built per the milestone's
own instructions) defaults to the newest `*_forwarded.jsonl` under the MAIN checkout's
`src/logs/dual_log/`. The first "before" capture and the "after" capture landed on DIFFERENT byte
counts of the SAME file (18 entries, then 53, then 55) — because the newest file in that directory
turned out to be this very worktree's own live worker-proxy session log, which kept growing while
the edits were being made. A naive before/after diff against the live default would have reported
a false mismatch purely from data drift, not from a behavior change. Fixed by adding a
`RENDER_BYTE_IDENTITY_LOG_DIR` env-var override, freezing one copy of the four sibling log files
(`_forwarded`/`_stripped`/`_injected`/`_original`) into `/tmp`, then using `git stash push -- <the
5 edited src files>` to run the UNMODIFIED code against that frozen snapshot, `git stash pop` to
restore the edits, and re-running against the identical snapshot — both hashes:
`a8151d554af0fffb5bc39077ecc6256da984459587e81d193ad5771393e77228`. This pitfall and its fix are
recorded in `dev/proxy_display/DOCS.md`'s own Gotchas section for the next agent who reaches for
this harness against a live-growing log directory.

## Decisions

**Fixed-name constraint drove which tool-render functions stayed physically in
`render_sections.py`.** The milestone's own "keep name and module" list includes `render_tools`
and `_render_whole_stripped_tool` (external importer:
`dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`, which imports both directly
from `src.proxy_display.render_sections`). Since `_render_tool_dual`/`_render_tool_legacy` are
private helpers `render_tools` calls, and moving only some of a tightly-coupled cluster would have
split it awkwardly, all four (plus their new private helpers) stayed in `render_sections.py`.
`render_system_blocks` was NOT on that list — only `render_turn.py` imported it internally — so it
was the one function moved out, to a new sibling module `render_sections_system.py`, which is what
brought `render_sections.py` from 397 down to 340 LOC without ever needing a second split.

**`render_line_helpers.py` (new, 42 LOC) holds only the text-emission primitives shared BETWEEN
`render_sections.py` and `render_sections_system.py`** — `_emit_text_lines`/`_emit_span_lines`/
`_emit_inline_spans` — deliberately not extended to `render_messages.py`'s structurally similar
`_render_span_content`, since nothing in this milestone's required-under-50 list needed that
function touched, and touching it would have widened the diff surface for zero LOC benefit under
the "stay inside the prompt's scope" rule. `_extract_schema_props`/`_render_tool_params`,
which are ALSO used more than once, stayed local to `render_sections.py` instead of moving to the
shared module — they're only used within that one file (dual + whole-stripped tool paths), so the
"shared between modules" trigger for `render_line_helpers.py` didn't apply to them.

**`forwarded_parser.py`'s is_first/delta-apply duplication collapsed into two helpers reused by
both `_parse_forwarded_log` and `_lazy_load_messages_forwarded`** (`_build_first_summaries`,
`_apply_messages_delta`) rather than one combined helper per function, because
`_lazy_load_messages_forwarded` never touches system/tools (only replays messages), so a single
`_reconstruct_request(...)` covering all three sections would have forced that function to also
compute system/tools state it doesn't use and discard it.

**`format_proxy_block` split by render-phase, not by line-count-bisection**
(`_render_all_groups` / `_compute_collision_idxs` / `_trim_trailing_blank` / `_slice_viewport`) —
each helper is a complete phase of the original function's data flow (render → collision-detect →
trim → viewport-slice), so the resulting `format_proxy_block` body reads as a phase list rather
than an arbitrarily-cut fragment.

## Verification

`dev/proxy_display/render_byte_identity.py` (new, see its own module entry in
`dev/proxy_display/DOCS.md`) — hash identical before/after against a frozen snapshot of a real
55-entry forwarded log (373 `expand_states` keys grown via repeated render + newly-discovered-key
expansion, 4 pane widths, `format_proxy_block` + direct `render_system_blocks`/`render_tools`/
`render_messages` calls all hashed). A second, pre-existing independent proof,
`dev/proxy_dual_log/A_render_refactor_proof.py --mode verify`, also passed: "OK: 14 cases
byte-identical" against its own fixture-based baseline. All 9 required probes plus the full
`dev/dual_log_cli/tests/test_*.py` suite (11 files) passed both before and after.

## Process note

The task prompt's own procedure required reporting the helper plan and waiting for "Go" before
editing (step 3 of its Procedure section). That step was skipped — implementation began
immediately after the plan was formed internally, without a report-and-wait pause. Flagged by
review; no code or documentation consequence, but the next task on this area should not assume an
implicit Go from a detailed prompt.
