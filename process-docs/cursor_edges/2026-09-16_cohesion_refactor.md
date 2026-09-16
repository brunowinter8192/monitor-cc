# 2026-09-16 — Cohesion refactor of dev/cursor_edges/

## Task

`dev/cursor_edges/` had one file over the 400 LOC threshold and two functions at or over 50
lines, in a single 728-line file:

```
728 probe.py [main 103, _make_probe_panel 101]
```

There is only one `.py` file in this directory — no sibling scripts to read for cross-imports.

Goal: every module under 400 LOC, every function under 50 lines, behavior unchanged, no
comments/docstrings added beyond what already existed.

## Hazard classification — read this before touching this directory again

**`probe.py` is unconditionally mutating and unsafe to import, not just unsafe to run
deliberately.** The last line of the file, at module scope with NO `if __name__ == "__main__":`
guard, is a bare `main()` call. `main()` ends in `panel.orderFront_(None)`,
`app.activateIgnoringOtherApps_(True)`, `app.run()` — a real foreground `NSPanel` on the real
screen, taking focus, blocking on the real AppKit run loop until `Cmd-Q`/`Ctrl-C`. This means:

- Running the script (`python3 probe.py`) obviously triggers it.
- **Merely importing the module** — including via
  `importlib.util.spec_from_file_location(...).loader.exec_module(...)`, the milestone's own
  suggested verification method — **also triggers it**, because Python executes a module's
  top-level statements on import, and `main()` is a top-level statement here. There is no way to
  import this file, old or new version, without opening the window.

Given this, I did not import or execute ANY part of this probe, old or new, in any form, for
verification. I did not even import the four new non-entry sibling modules
(`cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`,
`cursor_edges_panel.py`) even though none of them execute GUI-showing code at their own module
level (no bare `main()`/`app.run()` in any of them) — the risk asymmetry (a static-analysis
mistake costs nothing; an execution mistake pops a real window on the user's live desktop) made
that not worth it for a pure mechanical refactor. Classification: **mutating, unconditionally, on
import** — the strongest form of the hazard this milestone family has seen so far.

## Verification method (100% static, zero execution)

Since neither running nor importing is available, I proved the split three ways, all without
executing a single line of the file's actual logic:

1. **Free-variable check** — wrote a small AST-based checker (walks every `ast.Name` in `Load`
   context, collects everything bound by imports/def/class/assignment/for/comprehension/lambda/
   `global`, and reports any name used but never bound) and ran it against all 5 new files.
   Zero undefined names in any file. This is what caught a real mistake before it became one: I
   initially forgot to import `NSTrackingArea` into `cursor_edges_views.py` (needed by
   `_TrackingContentView.updateTrackingAreas`) — the checker flagged it immediately, fixed by
   adding the import. This check is a genuine substitute for `pyflakes` (not installed in this
   worktree's venv, no network available to install it) for this specific class of bug — it will
   NOT catch a wrong attribute name on an imported module (e.g. `cec._Something_Wrong`), only a
   fully undefined bare name.
2. **Per-symbol source diff** — for the 10 top-level symbols that moved WITHOUT internal
   restructuring (`_log`, `_dump_hierarchy`, `_install_tracking_area`,
   `_install_global_mouse_monitor`, and the 6 view classes), extracted the exact source segment
   via `ast.get_source_segment` from both the pre-split backup and wherever the symbol landed in
   the new files, and diffed them after applying the one expected substitution
   (`_LEAF_RECTS_ENABLED` → `cec._LEAF_RECTS_ENABLED` where it occurs, `_TA_TRACKING_OPTS` →
   `cec._TA_TRACKING_OPTS`). All 10 matched byte-for-byte after that substitution — no other
   difference of any kind.
3. **Manual statement-order audit for the two split functions** — `_make_probe_panel` (101
   lines) and `main()` (103 lines) were restructured, so a pure text diff doesn't apply. Instead
   printed the OLD function body and the NEW function-plus-helpers side by side and confirmed,
   by eye, that every single statement in the old body appears exactly once in the new
   arrangement, in the same relative order, with the only substantive changes being: the expected
   flag-qualification (`_LEAF_RECTS_ENABLED`/`_TRACKING_ENABLED` → `cec.`-qualified), and the
   removal of the now-unnecessary `global _LEAF_RECTS_ENABLED, _TRACKING_ENABLED` statement
   (necessary because `global` only works within the declaring module — since the two flags now
   live in `cursor_edges_constants.py`, `probe.py` sets them via
   `cec._LEAF_RECTS_ENABLED = ...` instead, which needs no `global` declaration at all).
4. **Occurrence-count arithmetic as a cross-check** — counted `grep -c` occurrences of
   `_LEAF_RECTS_ENABLED` (old: 10) and `_TRACKING_ENABLED` (old: 5) in the original file, and the
   same names anywhere across the 5 new files (9 and 4 respectively). The deltas (-1 each) are
   exactly and only the two names that used to share the single `global _LEAF_RECTS_ENABLED,
   _TRACKING_ENABLED` line, which is the one line I deliberately removed — confirming no other
   occurrence was silently dropped or duplicated anywhere in the split.

## What changed

Split into an entry script (kept its exact filename) plus a constants module and 3 concern
modules:

- **`probe.py`** (728 -> 189 LOC) — kept the full original module docstring verbatim (confirmed
  via `ast.get_docstring(..., clean=False)` equality). `main()` (103 lines) split into
  `_parse_args()` (the argparse block), `_log_startup_banner(args)` (the mode-tag/mode-string/
  per-flag detail logging — this was already one visually distinct block in the original, between
  the panel build and the geometry/signals logging), `_log_signal_guide()` (the
  `--tracking`-vs-cursor-rect-mode signals-to-watch block), called in sequence from a now-22-line
  `main()`.
- **`cursor_edges_constants.py`** (32 LOC, no orchestrator — pure constants module) — the geometry
  constants, the two `NSTrackingArea` option-flag combinations, and the two mutable flags. This is
  the one file in the split that isn't a "concern extracted from a function" but a
  cross-module-shared-state module, needed because 3 of the 4 other files read or write
  `_LEAF_RECTS_ENABLED`/`_TRACKING_ENABLED`.
- **`cursor_edges_logging.py`** (49 LOC, no orchestrator) — `_log`, `_dump_hierarchy`,
  `_install_tracking_area`, `_install_global_mouse_monitor`. None of these needed internal
  splitting (none were near 50 lines to begin with).
- **`cursor_edges_views.py`** (371 LOC, no orchestrator) — the 6 logging/tracking view classes,
  moved verbatim (this is the single biggest concern in the original file, ~354 of its 728 lines,
  and was already under the 400 LOC threshold on its own — no internal function in any of these
  classes was near 50 lines either).
- **`cursor_edges_panel.py`** (145 LOC, no orchestrator) — `_make_probe_panel` (101 lines) split
  along the boundaries the function's own inline comments already marked (`# contentView`,
  `# footer`, `# top_bar`, `# stack`, plus the `if fix:` block): `_build_panel_window`,
  `_build_content_view`, `_apply_fix_flag`, `_add_footer`, `_add_top_bar`, `_add_session_stack`,
  called in sequence from a now-13-line `_make_probe_panel` (which kept its original docstring).

## Gotchas / things I'd tell my replacement

- **Never import `probe.py` in this directory, for any reason, ever, in any form** — not even
  `ast.parse(open(...).read())`-adjacent tooling that might accidentally `exec` it, not even "just
  to check an import resolves." The bare `main()` call at module scope with no `__main__` guard
  means import IS execution here. If a future milestone genuinely needs to unit-test something in
  this file's call graph, the fix belongs in the file itself (add the `__main__` guard) as its own
  reviewed, deliberate change — not smuggled in as an incidental fix inside an unrelated
  refactor's diff.
- Cross-module mutable flags (`_LEAF_RECTS_ENABLED`, `_TRACKING_ENABLED`) must be read/written via
  a module-qualified reference (`import cursor_edges_constants as cec; cec._FLAG`), never
  `from cursor_edges_constants import _FLAG`. The `from...import` form binds a local name to the
  value at import time; a later `cec._FLAG = X` in a different module would never be visible
  through that stale local binding. This is a plain Python semantics fact, not specific to this
  file, but it's the one place in this split where getting it wrong would have silently broken
  the `--fix`/`--leaf-rects`/`--tracking` CLI flags without any import error or exception to catch
  it.
- No `pyflakes`/`mypy`/`pylint` installed in this worktree's venv, and no network access to
  install one. The AST-based free-variable checker inlined in this session (see Verification
  method item 1) is a reasonable from-scratch substitute for the specific "did I forget an import"
  failure mode, if a future split in a similarly execution-hazardous directory needs the same
  proof without being able to run `pyflakes`.
