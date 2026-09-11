# 2026-09-11 — iterative-dev-refactor Phase 3 on src/: docs-drift check and DOCS.md format cut

Main session file. Continues the scan recorded in this area's 2026-09-09 summary (Phase 1 and 2
done, Phase 3 and 4 open). The doc-and-structure audit task (formerly its own issue) was folded
into this line of work at session start.

## Starting point

`docs-drift-check` on the main checkout reported 59 findings: 39 path, 6 LOC, 14 symbol.
Seventeen touched `src/` DOCS.md, eighteen `dev/` DOCS.md, the rest the gitignored `dist/`
bundle (ignored). About a third of the `src` findings were tool false positives (`/dev/null`,
`~/.claude/projects`, prose about removed symbols); four were real (a removed `queue.py`, a
moved `log_janitor.py`, a nonexistent `_clear_proxy_search_selection`, a file-prefix written as
a path).

The drift numbers were not the real finding. The 16 `src` DOCS.md files held 4,514 lines
(dual_log_cli 1,213, hooks 745, menubar 581, proxy_display 506, proxy 420); the 44 `dev` DOCS.md
files 4,784. Read against the DOCS.md Format of the documentation rules, the content was a
changelog: 38 dated iteration notes in dual_log_cli alone, module headings carrying "split out
of X 2026-09", Flow sections of 58 lines narrating every function, Purpose paragraphs explaining
why a docstring became a constant. Git history of dual_log_cli/DOCS.md showed 40 commits, nearly
all net-additive (one +381/−103).

## Root cause and rule change

The worker recap rule (Step 2 of `shared-rules/worker/worker-rules.md`) made the DOCS.md update
mandatory and phrased as "bring every place you touched in sync with what you did", while the
process-docs entry was optional ("when substantial"). Appending a delta to DOCS.md was the
cheapest way to satisfy it, so every worker did. Decision with the user: the documentation rule
is right and the docs are wrong; the rule that leaked was the worker recap.

Changed on 2026-09-11, in the GlobalRules repo (uncommitted there at the time of writing, next
to unrelated pending edits):

- Worker recap Step 2: progress goes into process-docs only; DOCS.md gets a currency check
  against the format, never a progress note; dates, "replaced X", "split out of Y", verification
  notes and function-level narrative are named as forbidden content.
- Documentation rule, process docs: one file per author session — a worker writes exactly one
  process-docs file across its lifetime (first recap creates it, later recaps append), a main
  session writes exactly one, and no other process-docs file is ever touched regardless of
  content. Write-once now means "closed when the author's session ends".

## Execution

Eight workers in parallel, one per DOCS.md block (dual_log_cli, hooks, menubar, proxy,
proxy_display, the eleven small src files, dev a–m, dev n–z), each ordered to derive the DOCS.md
from the code (full read of every `.py` in the package, grep for every importer) rather than
from the old prose, to write everything removed into its own single process-docs file under
`process-docs/doc_compliance/` before cutting, and to verify LOC per heading and zero
drift-check findings on its files.

Five of the eight skipped the report-first gate and implemented directly; their diffs were
reviewed after the fact and passed. One format deviation (dual_log_cli listing project modules
under `Calls out`) was corrected on review. The menubar worker stalled twice (an API mid-stream
error, then the account session limit) after writing the salvage and the rewrite but before
committing; Main verified the worktree (one LOC heading off by 22, corrected), committed and
merged, and wrote that worker's recap section.

## Result

| Surface | Before | After |
|---|---|---|
| `src` DOCS.md (16 files) | 4,514 lines | 2,663 lines |
| `dev` DOCS.md (44 files) | 4,784 lines | 3,214 lines |
| drift-check findings outside `dist/` | 53 | 0 |

`src/DOCS.md` grew (86 → 166) because a one-line-per-module table became full module entries;
everything else shrank, dual_log_cli by two thirds. Nine salvage files under
`process-docs/doc_compliance/2026-09-11_docs_format_*.md` hold the cut text verbatim, one per
worker. Every `Called by` list was grep-verified; module-level dead code was found nowhere in
`src`; in `dev`, `timer-loop/p3_project_scope_incident_probe.py` imports two removed `src`
modules and is flagged DEAD CODE in its DOCS.md.

Three residual drift findings after merge were the tool's inability to read the cross-project
marker when the project name sits outside the backticks, and a gitignored log path; all three
were reworded in plain words by Main.

## Left open

- `docs-drift-check` (`~/.local/bin`, outside any repo, dated 2026-05-23) still globs
  `decisions/**/*.md` for its doc scope, so process-docs entries are not path-checked at all.
  Decision with the user: not touched this session.
- The process-docs layer itself (101 area folders, 450 entries) was not audited; the doccheck
  skill's Step 1 per-folder verdict remains undone.
- Phase 4 (control-flow integrity) follows this entry in the same session.
