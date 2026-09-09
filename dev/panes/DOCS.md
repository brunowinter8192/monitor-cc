# dev/panes/

## Role

Byte-identity regression harnesses for `src/panes/` module splits. Add a script here when a
`src/panes/` refactor (module split, helper extraction) needs a before/after correctness proof
that isn't already covered by `dev/pane_search/`, `dev/click_ui/`, or `dev/pane_error_log/`'s own
behavior probes.

## Modules

### render_byte_identity.py (146 LOC, new 2026-09, panes-split milestone)

**Purpose:** Byte-identity harness for the panes-split milestone (`token_pane.py` /
`warnings_pane.py` / `warnings_render.py` concern split — `build_cache_turns` moved to
`cache_turns.py`, `_format_warnings_pane` split into 3 helpers). Two checks, hashed together:
(1) `build_cache_turns` fed incrementally in growing file-line chunks (mirrors real polling of a
growing session JSONL) over a frozen 300-line prefix of a real session JSONL under
`~/.claude/projects/`, hashing the resulting turns after EVERY chunk — this is what actually
exercises the duplicate-call merge path the function's own LOC-split touches, not just its final
state; (2) `_format_warnings_pane` over a synthetic 4-error `tool_errors` list (mixed
expanded/collapsed, one carrying `_pre_strip_text`/`_stripped_chunks`, one with a search match) at
two pane widths, hashing `(rendered_string, line_map)`. `format_cache_tracker`'s own output is
already covered by the workers-pane byte-identity harness — skipped here.
**Reads:** One real session `*.jsonl` — newest under `~/.claude/projects/*/`  by default, or
`$PANES_BYTE_IDENTITY_JSONL` when set.
**Writes:** Nothing outside its own tempfile (cleaned up on exit) — stdout only (one `HASH: <hex>` line).
**Run:** `./venv/bin/python dev/panes/render_byte_identity.py`
**Calls out:** `src.panes.cache_turns` (`build_cache_turns`), `src.panes.warnings_render`
(`_format_warnings_pane`) — both imported via a function (`_import_panes`), not a module-level
`from src.` line, per `block_dev_imports_src`.

**`PANES_BYTE_IDENTITY_JSONL` env var** overrides the source path — needed to pin a before/after
comparison to the exact same bytes when the default (newest `*.jsonl` under `~/.claude/projects/`)
can itself be an actively-growing session log; same pitfall class as
`dev/proxy/pipeline_byte_identity.py`'s `PROXY_PIPELINE_BYTE_IDENTITY_LOG` (see its own DOCS
entry). Snapshot a real session file's frozen 300-line prefix to a fixed `/tmp` path once, then
point both runs at it via the env var.

Status: hash `b1161b3b00fe58b5edcd4b8f3aef79ff59eb7f0c3333cf30c68a6c4addc02679` — identical before
and after the panes-split milestone (pinned 300-line session-JSONL prefix).
