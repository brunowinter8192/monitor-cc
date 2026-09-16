# process-docs/thinking/2026-09-16_comment_salvage.md

Session: dev/thinking/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/thinking/*.py` during this milestone, copied
verbatim before deletion, plus the full pre-rewrite content of `dev/thinking/DOCS.md`. Nothing
judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File count (2) and comment/docstring totals (39 comments, 2 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/thinking/*.py`
before deletion: zero matches. The 2 module-level docstrings are plain narrative, never read at
runtime. Both deleted outright, no constant-rewiring needed.

## Execution-safety note for this session

Both scripts default to reading `src/logs/dual_log/api_requests_opus_monitor_cc_1787931850_forwarded.jsonl`,
which does not exist on disk in this worktree (gitignored runtime data, rotated out of the live
corpus — same pattern observed in several other dev/ areas this cycle). Both scripts check
`log_path.exists()` first and exit cleanly (`sys.exit(1)`, no report written, no git-show, no
temp package materialized) when it's missing. Both were run before and after this session's edit
against that same missing-file path, verifying the early-exit behavior is unchanged — neither
script's report-writing or `git show`/temp-package code paths were exercised in this session.

Comment/docstring counts confirmed via AST + tokenize before deletion: 39 comments, 2
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/thinking/DOCS.md

Full content of dev/thinking/DOCS.md as it stood before this rewrite (54 lines), preserved
verbatim since the whole file is being replaced with the mandated leaner format (Role capped
at 50 words, Purpose capped at 25 words per module, no Gotchas section in the new format,
Public Interface / State sections added).

```markdown
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

### render_thinking_expander.py (285 LOC)

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
```

## Salvage from dev/proxy/render_brain_badge.py

DOCSTRING L1-18:
```

render_brain_badge.py — Verifies the proxy-pane REQ header's 🧠 badge (milestone: brain marker
for thinking in the proxy pane REQ header) against a real forwarded dual-log.

Parses the log through the REAL parser (forwarded_parser._parse_forwarded_log) and renders each
entry's header through the REAL render function (render_turn._build_req_header_line) — not a
reimplementation of the badge logic. For every entry it reports model, a request label, and
whether '🧠' is present in the ANSI-stripped rendered header line.

Also cross-checks against CUMULATIVE semantics (any 'thinking' block anywhere in the entry's full
accumulated message list, computed independently here for comparison only — NOT the code path
under test) to confirm the DELTA-driven badge is the narrower, informative variant per the
milestone's stated rationale.

Run: ./venv/bin/python dev/thinking/render_brain_badge.py [path/to/_forwarded.jsonl]
Default log: src/logs/dual_log/api_requests_opus_monitor_cc_1787931850_forwarded.jsonl (real
runtime log, gitignored — must be present on disk; not vendored in the repo).

```

COMMENT L48:
```
# Parse the entire forwarded log via the real parser (keep_last=None keeps every entry's
```

COMMENT L49:
```
# messages populated, so the cumulative cross-check below has full data to look at).
```

COMMENT L54:
```
# Render each entry's real header line and record (model, family, label, delta_brain,
```

COMMENT L55:
```
# cumulative_brain) — delta_brain comes from the actual render path; cumulative_brain is an
```

COMMENT L56:
```
# independent local check, kept separate to prove the delta variant is the narrower one.
```

COMMENT L77:
```
# Independent cumulative check (any thinking block anywhere in the FULL accumulated message
```

COMMENT L78:
```
# list) — used only as the cross-check the milestone spec calls out, never as the render path.
```

COMMENT L86:
```
# Write the per-request table plus the aggregate counts (delta-positive / total, per family)
```

COMMENT L87:
```
# the milestone's verification deliverable is checked against.
```

## Salvage from dev/proxy/render_thinking_expander.py

DOCSTRING L1-23:
```

render_thinking_expander.py — Verifies the thinking-block drill-down + wrapping (milestone:
thinking-text expander with wrapping in the expanded REQ view) against a real forwarded log.

Renders through the REAL render path — render_turn._render_req_expanded (the actual function
that builds an expanded REQ's body) — not a reimplementation of the toggle/wrap logic. Reports,
per verification point from the milestone spec:

  1. COLLAPSED: a thinking block occupies exactly one line, and no thinking text leaks into it.
  2. EXPANDED: the full text is present (whitespace-normalized match against blk['full_text'])
     and no content line exceeds pane_width cells — checked at a realistic width (180, the
     milestone's own clipping example) and a narrow stress width (60).
  3. BYTE-IDENTICAL: a non-thinking block's rendered output is identical before and after this
     milestone's change to render_messages.py — proven by loading the PRE-CHANGE
     render_messages.py from git (BEFORE_COMMIT_SHA below) into an isolated package under /tmp
     and calling its (old-signature) _render_block_spans directly against the same real block
     data the NEW _render_block_spans renders, for one real block of each non-thinking type
     found in the log (text, tool_use, tool_result, image).

Run: ./venv/bin/python dev/thinking/render_thinking_expander.py [path/to/_forwarded.jsonl]
Default log: src/logs/dual_log/api_requests_opus_monitor_cc_1787931850_forwarded.jsonl
(gitignored runtime log — copy it into the worktree; not vendored in the repo).

```

COMMENT L46:
```
# The commit immediately preceding this milestone's render_messages.py changes (tip of
```

COMMENT L47:
```
# integration merged into this branch before the thinking-expander edits started) — the "before"
```

COMMENT L48:
```
# snapshot for the byte-identical check. Not a live ref: pinned so the check is reproducible.
```

COMMENT L65:
```
# Parse the entire forwarded log via the real parser (keep_last=None — every entry needs its
```

COMMENT L66:
```
# own accumulated 'messages' so _render_req_expanded can find the delta that introduced a block).
```

COMMENT L71:
```
# Every (entry_idx, msg_idx, bidx) whose message is part of THAT entry's OWN rendered delta —
```

COMMENT L72:
```
# i.e. the entry whose expanded view actually shows this block (a message reappears in every
```

COMMENT L73:
```
# LATER entry's accumulated 'messages' too, but only the entry that introduced it renders it —
```

COMMENT L74:
```
# same delta-vs-cumulative distinction as milestone 1's brain badge). Determined empirically via
```

COMMENT L75:
```
# the real render (think_key present in a from-scratch collapsed render's keys), not inferred.
```

COMMENT L89:
```
# Verification points 1+2: for every owning thinking block, render collapsed and (that one
```

COMMENT L90:
```
# block) expanded via the real _render_req_expanded, and check:
```

COMMENT L91:
```
#   - collapsed contributes exactly one line (prefix/suffix around the header line are byte
```

COMMENT L92:
```
#     identical between the collapsed and single-expanded render — the only delta is the header
```

COMMENT L93:
```
#     line's own symbol plus the inserted content block)
```

COMMENT L94:
```
#   - the header line itself never contains the block's own thinking text
```

COMMENT L95:
```
#   - expanded content, whitespace-normalized, matches blk['full_text'] exactly (proves no text
```

COMMENT L96:
```
#     lost/duplicated by wrapping)
```

COMMENT L97:
```
#   - no expanded content line exceeds pane_width cells, at WIDTH_CASES
```

COMMENT L140:
```
# Verification point 3: load the PRE-CHANGE render_messages.py from git into an isolated
```

COMMENT L141:
```
# package (so its relative imports resolve) and compare its _render_block_spans output against
```

COMMENT L142:
```
# the current one, for one real block of each non-thinking type found in the log.
```

COMMENT L159:
```
# First real block of each non-thinking type with non-trivial size, one sample per type.
```

COMMENT L173:
```
# Fetch one file's content at commit_sha via `git show`.
```

COMMENT L179:
```
# Materialize the pre-change render_messages.py (+ its non-stdlib deps: constants.py,
```

COMMENT L180:
```
# proxy/strip_vocab.py) as a real package tree under /tmp, rooted at a name distinct from the
```

COMMENT L181:
```
# live 'src' package so both can be imported in the same process without collision. Real
```

COMMENT L182:
```
# on-disk files are required for relative imports ('from ..constants import ...') to resolve —
```

COMMENT L183:
```
# an in-memory exec would need the same package machinery anyway.
```

COMMENT L199:
```
# Write the report: per-check pass/fail tables + the deliverable summary counts.
```

