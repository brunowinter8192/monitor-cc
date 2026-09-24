# Main session 2026-09-24/25 — iterative-dev-refactor over monitor-cc (with websearch and trading in parallel)

Orchestrator-level record. One Main agent ran the refactor-scan skill (Phases 0-6) over three projects at once, fully autonomous by user instruction. Worker-level details live in the worker entries of this area and of the component areas dated 2026-09-24/25.

## Starting state, measured 2026-09-24

- `.py` scan (own AST/tokenize scanner, excludes venv/build/dist/repo/logs): 4 files over 400 LOC (`src/menubar/panel.py` 412, three dev tests), 2 functions at or over 50 lines, 65 comment lines in `setup_py2app.py` and `workflow.py`.
- `docs-drift-check`: 600 findings (593 rule violations = function/constant names in DOCS.md).
- DOCS.md over 400 lines: `src/menubar` 516, `src/dual_log_cli` 435, `src/proxy` 418.
- The 253-entry control-flow list from 2026-09-16 was still unclassified.

## Ending state, measured 2026-09-25

- 0 files over 400 LOC, 0 functions at or over 50 lines, 0 comments/docstrings outside the three markers and line-1 shebangs (`.py`). Shell launcher and `.githooks` are comment-free too.
- `docs-drift-check`: 0 / 0 / 0.
- `python -c "import src.menubar"` succeeds; `dev/hook_smoke/run_all.py` 23/23 strands; `dev/menubar/p5_run_all.py` 8/8.
- `src/menubar/DOCS.md` 452 lines, deliberately not split (see below).

## Phase 0 decision

No contact layer. Everything in scope except third-party/build output: `repo/` (vendored tmux C source), `build/`, `dist/`, `venv/`.

## What changed, by phase

- Phase 1: `panel.py` split (`panel_views.py`), three dev tests split into fixtures/case modules, `run_sequence` split. Phase 6 added: `src/claude_proxy_start.sh` 402 lines split into the launcher plus `proxy_start_janitor.sh` and `proxy_start_markers.sh`, with a sandbox equivalence harness (12 cases, stubbed mitmdump/claude, pinned to base commit 0c837c41).
- Phase 2: comment salvage for `setup_py2app.py` (area menubar_build) and `workflow.py` (area pipeline); shell and githook comments salvaged by the Phase 6 worker (this area).
- Phase 3: shared runner `dev/refactoring/strand_runner.py`; hook tests anchored to the repo root and isolated from the live firing log; private tmux sockets for sweep tests; frozen fixtures instead of live session files. `dev/bead_tracker/` deleted (hook and bd gone).
- Phase 4: every DOCS.md rewritten at module level; gotchas and function-level detail moved to process-docs of this area.
- Phase 5: classification rule used for every unobserved fallback: search git history and process-docs for a recorded observation; if found, keep and make the path traceable; if not, remove the second path (tripwire). Prior user decisions (hooks fail-open, config loads swallowed, log-read OSError, CLI validation exits) were kept and only made traceable.
- New shared pieces: `src/monitor_root.py` (single MONITOR_CC_ROOT resolver, replaced 16 copies), `src/proxy/proxy_error_log.py` (proxy stderr goes to /dev/null in production, so every proxy error now lands in `src/logs/proxy_error.log`), `src/jsonl/jsonl_reader.py` (stops before an unterminated last line), hook decision value `trace` in the firing log.

## Defects found on the way (observed, fixed)

- Live `TypeError` in the worker proxy pane: 166 traces between 23:18 and 23:19 on 2026-09-24. Entries outside the keep-last window carried `messages=None`, an expanded state rendered them every frame. Fixed: absent key instead of None, loader raises, reparse clears expand states.
- Import cycle introduced by the resolver commit: `menubar_log -> paths -> monitor_root -> root_report -> menubar_log`. `import src.menubar` failed; the running menubar was the py2app bundle from 2026-09-24 22:36 and was not affected. Found only by the Phase 6 four-eyes worker. Lesson: after any change to an import-time module, import every package module in a fresh interpreter, in more than one order.
- A test fixture used the model id `claude-fable-5-1`; after the family classifier stopped mapping unknown ids to opus it failed. Observed ids in the dual logs: `claude-opus-5-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`.

## Decisions taken autonomously

- `src/menubar/DOCS.md` (452 lines) not split: the import graph has one real unit (entry `menubar_main` via `__init__`), plus the standalone scripts `hook_writer.py` and `hook_setup.py`, whose absolute paths are registered in `~/.claude/settings.json`. Same reasoning as the `src/proxy` exception recorded 2026-09-16.
- Module-layout findings from the four-eyes review (section order in 27 files, orchestrators containing logic, 422 relative imports in `src/`) are outside the skill's Phase 2 (comments/docstrings) and were left for a separate issue.
- Production emojis in the panes were replaced by plain-text markers of equal width (tool `tl`, thinking `th`, warning `!`).
- Shebang lines stay (functional).

## Known open points (not fixed in this cycle)

- The Models-tab apply success flash calls `setFrame_display_` on an NSButton; the error is now visible in `menubar.log` instead of the `.err` file.
- All 270 lines of `api_errors.jsonl` carry a `ts` like `...+00:00Z`, which `fromisoformat` rejects; the janitor keeps them forever and now reports that.
- `dev/pipeline` has two imports of a removed `src.jsonl_parser`.

## Orchestration notes for the next Main

- Workers spawned from another project land in that project's repo; create the target worktree with `worker-cli worktree <name> <repo>` right after spawn and tell the worker to cd there.
- 13 parallel workers on one repo produce merge conflicts mostly in DOCS.md LOC headings; the clean way was: abort the merge in the main checkout, send the worker `git merge integration` in its own worktree, merge again.
- `worker-cli status` can say idle while the pane is still working; `worker-cli capture` shows the truth.
- One worker hit a permission prompt for `rm -rf *` after a `cd`; answer No and demand `mktemp -d` sandboxes.
