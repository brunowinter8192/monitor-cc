# dev/panes/

## Role
Byte-identity regression harnesses for `src/panes/` module splits. Add a script here when a
`src/panes/` refactor (module split, helper extraction) needs a before/after correctness proof not
already covered by `dev/pane_search/`, `dev/click_ui/`, or `dev/pane_error_log/`'s own behavior
probes.

## Flow
Each check renders a function's output over a fixed real or synthetic input, hashes the result, and
prints one `HASH:` line to stdout — run once before and once after a refactor and compare hashes.

## Modules

### render_byte_identity.py (214 LOC)

**Purpose:** Byte-identity harness for the panes-split module boundaries: `build_cache_turns`
(`src.panes.cache_turns`) fed incrementally in growing file-line chunks over a frozen session-JSONL
prefix; `_format_warnings_pane` (`src.panes.warnings_render`) over a synthetic mixed-state
`tool_errors` list at two pane widths; `format_cache_tracker` (`src.format.token_format`) over a
synthetic turn/call list covering every usage-extras group and the rate-limit header paths. Hashes
all three checks together into one value.
**Reads:** one real session JSONL — newest under the user's Claude Code projects directory by
default, or the path in `PANES_BYTE_IDENTITY_JSONL` when set (check 1 only; checks 2/3 are fully
synthetic).
**Writes:** nothing outside its own temp file (cleaned up on exit) — stdout only (one `HASH:` line).
**Called by:** none — manual regression harness, run before and after a `src/panes/` refactor.
**Calls out:** `src.panes.cache_turns` (`build_cache_turns`), `src.panes.warnings_render`
(`_format_warnings_pane`), `src.format` (`format_cache_tracker`) — imported via a function, not a
module-level `from src.` line, per the `block_dev_imports_src` hook.

---

## Gotchas
- `PANES_BYTE_IDENTITY_JSONL` overrides the default session-JSONL source — needed because the
  default (newest session file under the projects directory) can itself be actively growing during a
  before/after comparison. Snapshot a session file's frozen line-prefix to a fixed path once, then
  point both runs at it via the env var.
- `format_cache_tracker`'s `nav_out` mixes tuple keys and a string key — check 3 stringifies every
  key before hashing (`json.dumps` with `sort_keys=True` cannot compare a tuple key against a string
  key); checks 1/2 don't hit this since their own dict keys are already homogeneous.
