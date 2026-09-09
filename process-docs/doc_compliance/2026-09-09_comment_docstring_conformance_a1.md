# Comment/Docstring Conformance — Milestone A1 (root, core, jsonl, input, format, ram_audit, ccwrap)

A phased sweep applied the "only `# INFRASTRUCTURE` / `# ORCHESTRATOR` / `# FUNCTIONS`" comment rule
to `src/`. This entry covers milestone A1: every root-level `src/*.py` module plus `src/core/`,
`src/jsonl/`, `src/input/`, `src/format/`, `src/ram_audit/`, `src/ccwrap/`. Triage (which comment
became which DOCS.md/Gotcha relocation vs. straight deletion) was produced by Main ahead of the
worker session and is not repeated here; this entry records the execution and the verification
methodology.

## Scope and result

22 `.py` files touched (21 comment/docstring hits removed across the non-empty ones, 397 lines
deleted / 41 lines net-changed per `git diff --stat`). A scanner (`ast` docstring walk + `tokenize`
comment walk, excluding the three allowed marker strings and a line-1 shebang) confirmed zero
remaining hits across the milestone's packages after the edit; the same scanner still reports
hits in the not-yet-touched packages (`proxy/`, `menubar/`, `panes/`, `workers/`, etc.), which is
expected — those are later milestones.

Two section markers were added where none existed before: `src/ccwrap/__main__.py` gained
`# FUNCTIONS` above `def main()` (its only function is also the orchestrator — the fallback rule
for that case). `src/proxy_addon.py` gained only `# INFRASTRUCTURE` above its body — this file has
zero `def`/`class` statements (pure top-level sys.path setup + re-export shim), so `# ORCHESTRATOR`
and `# FUNCTIONS` had no anchor point and were omitted, confirmed with Main before implementing.

## Exception relocations applied

- `src/search_bar.py` (`KILL_LINE_CHAR` hypothesis comment) → new `## Gotchas` section in
  `src/DOCS.md` (the file had none before).
- `src/colors.py` (palette provenance comment) → appended to the existing `colors.py` row in
  `src/DOCS.md`'s Root-Level Files table.
- `src/tmux_launcher.py` (6-window layout comment + `restart_panes` docstring) → the layout list
  appended to the `tmux_launcher.py` row; the docstring's known-limitation text moved into the same
  new `## Gotchas` section as the search-bar item.

Everything else in scope was a straight deletion — the triage had already confirmed the content
was covered by the package's DOCS.md.

## Verification methodology finding: live-data harnesses need pinning for before/after diffs

Two of the required regression harnesses — `dev/panes/render_byte_identity.py` and
`dev/workers/format_byte_identity.py` — pick the newest-mtime `*.jsonl` under
`~/.claude/projects/` when no override env var is set. During this session that newest file was
the agent's own actively-growing transcript, so a naive "run before, edit, run after" comparison
produced a HASH mismatch that had nothing to do with the code change (confirmed: the mismatch
reproduced identically via `git stash` / `git stash pop` around the *same* unpinned harness run,
i.e. two runs of the *same* code differed too). Both harnesses already document a fix for this
(`PANES_BYTE_IDENTITY_JSONL` / `WORKERS_BYTE_IDENTITY_JSONL` env override, pin a frozen copy of the
session file to a fixed `/tmp` path, point both runs at it) — the fix just has to actually be used
for a same-session before/after comparison, not only for a "days apart" comparison. With the
override set to one frozen `/tmp` copy, both harnesses reproduced byte-identical hashes across the
`git stash`/`git stash pop` A/B before implementing the real edit, and again after.

`dev/display/test_strip_markers.py` fails on this branch before AND after the edit
(`ImportError: cannot import name 'get_stripped_data'` — that name was deleted from
`src/format/strip_marker.py` in an earlier, unrelated milestone per `src/format/DOCS.md`'s Role
section, and the dev harness was never updated to match). Not this milestone's scope to fix;
verification treated "identical pre-existing failure" as the pass condition, confirmed with Main.

## Cross-references

See `process-docs/pane_search/` and `process-docs/refactoring/` for the unrelated substantive
history behind the modules touched here (search-bar rollout, function-size-threshold splits) —
this entry is about the comment-removal mechanics only, not those features.
