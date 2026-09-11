# dev/thinking/

## Role
Verification tooling for the proxy pane's thinking-related display features: the per-request "brain"
badge on the REQ header and the thinking-block drill-down + wrapping inside an expanded REQ. Touch
when changing `has_thinking_delta` computation (`src/proxy_display/forwarded_parser.py`), the badge
rendering (`src/proxy_display/render_turn.py::_build_req_header_line`), or the thinking-block
toggle/wrap (`src/proxy_display/render_messages.py`, `src/utils.py::wrap_visible`).

## Flow
Each script parses a real forwarded dual-log through the real parse+render path and reports, per
request or per thinking block, whether the feature under test produced the expected output — no
reimplementation of the logic being verified.

## Modules

### render_brain_badge.py (136 LOC)

**Purpose:** Renders a real forwarded dual-log through `forwarded_parser._parse_forwarded_log` →
`render_turn._build_req_header_line` and reports, per request, whether the brain badge appears.
Cross-checks against a cumulative (any-thinking-block-anywhere) computation to demonstrate the
delta-scoped badge is the narrower, more informative variant.
**Reads:** a `_forwarded` dual-log JSONL (path arg, or a default under src/logs/dual_log — gitignored
runtime data, absent from a fresh worktree).
**Writes:** `dev/thinking/md/render_brain_badge_<timestamp>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.format`, `src.utils` — all via `importlib.import_module`.

---

### render_thinking_expander.py (256 LOC)

**Purpose:** Verifies the thinking-block drill-down + wrapping against a real forwarded log through
the real render path: collapsed state occupies exactly one line and leaks no thinking text; expanded
state shows the full text with no content line exceeding pane width; a non-thinking block's render
output is byte-identical before and after the change that introduced thinking-block wrapping (proven
by loading the pre-change file straight from git into an isolated package tree).
**Reads:** a `_forwarded` dual-log JSONL (path arg, or a default under src/logs/dual_log), plus
`git show` of a pinned pre-change commit for the byte-identical check.
**Writes:** `dev/thinking/md/render_thinking_expander_<timestamp>.md`; an uncleaned throwaway package
tree under the system temp directory.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.render_messages`, `src.proxy_display.format`, `src.utils`, `git` (subprocess,
`show` only) — Python imports via `importlib.import_module`.

---

## Gotchas
- `render_thinking_expander.py`'s byte-identical check never exercises a thinking block that also
  carries its own strip/inject spans — `_render_span_content` ignores `full_text` entirely for
  new-format span data, so such a block would render unwrapped. No thinking block in any sampled log
  has carried spans, so this coordinate stays unmeasured, not ruled out.
