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
