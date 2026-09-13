# dev/panes/

## Role
Regression harnesses for `src/panes/` and its `src/format/` render helpers. Byte-identity harnesses
belong here for a `src/panes/` refactor (module split, helper extraction) needing a before/after
correctness proof not already covered by `dev/pane_search/`, `dev/click_ui/`, or
`dev/pane_error_log/`'s own behavior probes; plain assert-based correctness tests for a specific new
render behavior (not a refactor) belong here too when the behavior lives in `src/format/token_format.py`
or a `src/panes/` module.

## Flow
A byte-identity check renders a function's output over a fixed real or synthetic input, hashes the
result, and prints one `HASH:` line to stdout — run once before and once after a refactor and compare
hashes. An assert-based check calls the real render function over synthetic input and asserts the
exact returned lines.

## Modules

### render_byte_identity.py (221 LOC)

**Purpose:** Byte-identity harness for the panes-split module boundaries: `build_cache_turns`
(`src.panes.cache_turns`) fed incrementally in growing file-line chunks over a frozen session-JSONL
prefix; `_format_warnings_pane` (`src.panes.warnings_render`) over a synthetic mixed-state
`tool_errors` list at two pane widths; `format_cache_tracker` (`src.format.token_format`) over a
synthetic turn/call list covering every usage-extras group, the rate-limit header paths, and the
answering-model line (M2 milestone: `response_rid_map` values are full `_response` dual-log entries,
not flat headers dicts — see `src/proxy_display/side_logs.py`). Hashes all three checks together into
one value.
**Reads:** one real session JSONL — newest under the user's Claude Code projects directory by
default, or the path in `PANES_BYTE_IDENTITY_JSONL` when set (check 1 only; checks 2/3 are fully
synthetic).
**Writes:** nothing outside its own temp file (cleaned up on exit) — stdout only (one `HASH:` line).
**Called by:** none — manual regression harness, run before and after a `src/panes/` refactor.
**Calls out:** `src.panes.cache_turns` (`build_cache_turns`), `src.panes.warnings_render`
(`_format_warnings_pane`), `src.format` (`format_cache_tracker`) — imported via a function, not a
module-level `from src.` line, per the `block_dev_imports_src` hook.

---

### answering_model_line_test.py (132 LOC)

**Purpose:** Assert-based correctness test for `format.token_format._render_answering_model_line`
(M2 milestone) and the updated `_render_rate_limit_lines`/`read_response_log` full-entry shape —
covers equal/mismatch/missing-field/missing-entry cases and the exact rendered ANSI line for each.
**Reads:** no on-disk data — synthetic `call`/`response_rid_map` dicts defined in the module.
**Writes:** stdout (pass/fail via assert).
**Called by:** none — manual regression guard, re-run after any change to `_render_answering_model_line`,
`_render_rate_limit_lines`, or `src/proxy_display/side_logs.py::read_response_log`.
**Calls out:** `src.format.token_format`, `src.colors` — imported via a function, not a module-level
`from src.` line, per the `block_dev_imports_src` hook.

---

## Gotchas
- `PANES_BYTE_IDENTITY_JSONL` overrides the default session-JSONL source — needed because the
  default (newest session file under the projects directory) can itself be actively growing during a
  before/after comparison. Snapshot a session file's frozen line-prefix to a fixed path once, then
  point both runs at it via the env var.
- `format_cache_tracker`'s `nav_out` mixes tuple keys and a string key — check 3 stringifies every
  key before hashing (`json.dumps` with `sort_keys=True` cannot compare a tuple key against a string
  key); checks 1/2 don't hit this since their own dict keys are already homogeneous.
