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

## Phase 4 — control-flow integrity (same session, appended)

### Scans

Main's textual pass over `src/`: zero comment hits for the keyword list, five function names
(`_check_legacy_files`, `_inject_legacy_model_override`, `_dedup_wakeup_blocks`,
`_render_legacy_tool_params`, `_render_tool_legacy`). Main's structural pass (AST: `except`
handlers returning non-`None` without re-raise): 87 handlers, 39 of them in `src/hooks/`. Two
scan workers (proxy side, pane side) confirmed all 87, added 18 handlers the AST walk missed
(default-assign-and-fall-through shapes, `or` chains, a whole-body `except: sys.exit(0)`), and
produced 9 cross-module findings. Combined: 121 findings in six groups.

### Classification with the user

- Hooks fail-open (45): kept. A hook that blocks on its own failure would stop every Bash call
  machine-wide.
- Config load swallowed to `{}`/defaults (12: proxy `rules_config`, `inject_helpers`,
  `tool_injection`; menubar `app_settings`, `model_selection`, `rag_controller`,
  `hook_writer`, `monitor_sweep_scheduler`): kept, by the evidence rule. Measured over 22 sessions
  and 2,265 non-haiku requests in the dual logs: every first request carried
  `context_management` and a full system delta, so a swallowed config load never happened; the
  menubar log held zero `hook_writer` errors; `proxy_rules.json` had 21 commits, none a breakage.
  A real tripwire for the proxy would need new code (mitmproxy's `safecall` swallows addon
  exceptions and forwards the request; `mitmdump` runs with `-q 2>/dev/null`), so deleting the
  `except` blocks alone would not surface anything. Decision: not built without an observed
  failure; the design (kill the flow, write `api_errors.jsonl`) is recorded here for the day one
  is observed. The user also raised the semantic case — a syntactically valid but unknown model
  id — which no local check can judge; the response stream's `message_start` model would be the
  arbiter, and it is not logged today. Left as a candidate for a separate milestone.
- Terminal-size defaults on `OSError` (12, one more than the scan found): eliminated. Every
  call site sits inside a pane loop's `except Exception: log_pane_error(...)`.
- Log-read `OSError` returning the unchanged position (7): kept, with a `log_pane_error` call
  added so a persistent failure shows in `/tmp/monitor_cc_error.log`.
- CLI validation exits (8, dual_log_cli): tripwires, kept.
- Cross-module: `_infer_model_family` (three copies) now lives once in
  `proxy/message_summary.py`; `is_main_session` once in `proxy/rules_config.py`; marker-file
  `log_id` resolution once in `forwarded_parser._resolve_log_id` with the lone `OSError` swallow
  removed; the project-path hash is now `normpath(expanduser())` in `claude_proxy_start.sh` and
  `forwarded_parser` as it already was in `tmux_launcher`/`worker_selection` (a trailing slash
  used to give `92a32869` vs `394da8fb` for the same project). The duplicated
  kill/send-while-working hooks stay (hook convention: small independent scripts). The two
  unlocked writers of `~/.claude/settings.json` stay (no observed clobber).
- Deletions: `render_sections` legacy tool path (no producer builds an entry without
  `_stripped_spans`), `get_proxy_session_start_ts`'s 24h `time.time()` branch, the shell
  marker's "old format, mtime-only" branch (every marker on disk has the PID line),
  `utils._iso_to_float` (zero callers), the 26 `HOOK_*` names in `constants.py` (zero
  importers; the byte-identity harness list and baseline updated), `src/metadata/` and
  `src/subagents/` (pycache-only dirs).
- `gpu_pane/status._check_legacy_files` ("delete after Phase 5"): the user could not say whether
  Phase 5 of the rag project is over; kept.

### Verification on `integration`

148 `src` modules import clean; `dev/proxy/test_strip_fix.py` and
`dev/proxy_dual_log/test_composition_invariant.py` ALL PASS; gpu_pane and constants
byte-identity hashes unchanged; all 13 `dev/dual_log_cli/tests` ALL PASS; `docs-drift-check`
zero findings outside `dist/`. Each fix worker proved its normal path byte-identical against a
pinned baseline and demonstrated every changed error path once with a throwaway script.

### Also found and fixed

Seven `dev/` areas had never had a DOCS.md (`dual_log_cli`, `proxy_forensics`, `grid_probe`,
`proxy_analysis`, `bead_tracker`, `menubar_per_project`, `coteditor`); they were outside every
Phase 3 worker's list because that list was built from existing files. Written by a worker from
the scripts. `dev/bead_tracker/smoke.py` targets a hook that no longer exists and is flagged
DEAD CODE there.
