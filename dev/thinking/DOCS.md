# dev/thinking/

## Role
Verification tooling for the proxy pane's thinking-related display: the per-request brain badge
on the REQ header, and thinking-block drill-down + wrapping inside an expanded REQ. Touch when
changing badge computation, its rendering, or the thinking-block toggle/wrap logic.

## Public Interface
No `__init__.py` in this directory. Each script is its own entry point, run directly with an
optional log-path argument, e.g. `python3 dev/thinking/render_brain_badge.py [path]`.

## Flow
A forwarded dual-log JSONL path (arg, or a default under `src/logs/dual_log`) goes in. Each
script parses it through the real parser and renders through the real render path — no
reimplementation of the logic under test. Output is stdout counts plus a timestamped report
under `md/`.

## Modules

### render_brain_badge.py (122 LOC)

**Purpose:** Renders a real forwarded dual-log through the real parse/render path and reports,
per request, whether the brain badge appears; cross-checks against a cumulative computation.
**Reads:** a `_forwarded` dual-log JSONL (path arg, or a default under `src/logs/dual_log` —
gitignored runtime data, absent from a fresh worktree).
**Writes:** `md/render_brain_badge_<timestamp>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.format`, `src.utils` — via `importlib.import_module`.

---

### render_thinking_expander.py (249 LOC)

**Purpose:** Verifies thinking-block drill-down + wrapping through the real render path:
collapsed/expanded correctness, and non-thinking-block output byte-identical to pre-change.
**Reads:** a `_forwarded` dual-log JSONL (path arg, or a default under `src/logs/dual_log`), plus
`git show` of a pinned pre-change commit for the byte-identical check.
**Writes:** `md/render_thinking_expander_<timestamp>.md`; an uncleaned throwaway package tree
under the system temp directory.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.render_turn`,
`src.proxy_display.render_messages`, `src.proxy_display.format`, `src.utils`, `git` (subprocess,
`show` only) — via `importlib.import_module`.

---

## State
No persistent state lives in this directory. Each script parses its input fresh on every run and
writes a new timestamped report; `render_thinking_expander.py`'s throwaway `/tmp` package tree
(a pinned pre-change snapshot of `render_messages.py` and its deps) is the one artifact that
outlives a single run, left uncleaned by design for inspection.
