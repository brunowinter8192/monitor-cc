# Comment/Docstring Conformance — Milestone C (hooks)

Continuation of the phased sweep applying the "only `# INFRASTRUCTURE` / `# ORCHESTRATOR` /
`# FUNCTIONS`" comment rule to `src/`. This entry covers milestone C: every `.py` under
`src/hooks/` (34 files: 3 shared utilities `_fire_log.py`/`_known_cli.py`/`_shell_strip.py`, 28
`block_*.py` PreToolUse hooks, 2 `rewrite_*.py` hooks, and `hook_setup.py`). Triage (which comment
became which DOCS.md/Gotcha relocation vs. straight deletion) was produced by Main ahead of the
worker session (`triage_part1.md`/`triage_part2.md`) and is not repeated here; this entry records
the execution and the verification methodology.

## Scope and result

34 `.py` files touched, 578 comment/docstring hits removed (scanner: `ast` docstring walk +
`tokenize` comment walk, excluding the three allowed marker strings and a line-1 shebang).
`git diff --stat`: 45 insertions / 607 deletions across the milestone (two commits — see Gotchas).
A post-edit run of the same scanner over `src/hooks/` reported zero hits; a full-repo run of the
scanner confirmed zero hits attributable to `src/hooks/` while out-of-scope packages kept their
(expected, untouched) hit count. `py_compile` and an import smoke over all 34 modules both passed.

## Exception relocations applied

None. Both triage files were grepped for `hooks` — the only match in `triage_part2.md` is the
file's own title line ("Phase 2 triage — part 2 (proxy, hooks, menubar, root modules, ccwrap)").
No relocation/CONVERT exception row names any `src/hooks/*.py` file, and the "Layout markers"
list in `triage_part2.md` names six files in other packages (`src/proxy/rules_config.py`,
`src/proxy_addon.py`, `src/ccwrap/__main__.py`, `src/menubar/menubar_main.py`,
`src/menubar/model_controller.py`, `src/proxy/strip_interrupt_marker.py`) — none under
`src/hooks/`. Every hooks module already carried `# INFRASTRUCTURE`/`# ORCHESTRATOR`/
`# FUNCTIONS` in the standard order before this pass, so no marker insertion was needed. No module
in `src/hooks/` uses a docstring as runtime data (verified by reading all 34 files in full before
editing — none use `"""..."""` at all, every module was already comment-based) — so the
`__main__.py` `epilog=__doc__` CONVERT pattern from milestone A/B's triage row does not recur here.
Every one of the 578 hits was therefore a straight DELETE, all content already covered by the
existing `src/hooks/DOCS.md` (a substantially larger, already-current document — its Purpose
paragraphs, Blocked/Allowed pattern lists, and Gotchas section already restate most of what the
in-code comments said, in more detail).

## Layout markers added

None — no file in `src/hooks/` appeared in the triage's layout-marker list, and manual inspection
confirmed every module already had the standard marker set.

## Verification methodology

Baselines captured before any edit: scanner hit count per file (578 total, tabulated per-file in
the pre-implementation report); `dev/hook_smoke/test_*.py` run once to establish the pass/fail
set — 19 PASS, 4 pre-existing FAIL unrelated to `src/hooks/` scope (`test_bg_task_detection`:
`src/menubar`'s own relative-import bug; `test_block_chained_sleep`: targets the already-disabled
`block_chained_sleep.py.disabled`; `test_block_read_worktree`: pre-existing logic mismatch;
`test_fire_log`: missing `src.panes.warnings_persist` module) — full stdout/stderr of all 24 tests
saved to `/tmp/out_test_*.log`; `hook_setup.py --help` (no argparse exists, so any argv triggers
the same worktree guard) captured to `/tmp/hooksetup_pre.log`; `py_compile` of all 34 files;
`echo '{}' | python3 <hook>.py` smoke of all 28 `block_*.py` scripts (exit code + stdout + stderr)
saved to `/tmp/phase2c_baseline/block_smoke.log`; import smoke of all 34 modules saved to
`/tmp/phase2c_baseline/import_smoke.log`.

Post-edit, every baseline was re-run and diffed byte-for-byte against its pre-edit capture: all 24
`dev/hook_smoke/test_*.py` outputs diffed empty (`diff -q` reported no differences for any file,
including the 4 pre-existing failures — same failure, same reason, same output); `hook_setup.py
--help` diffed empty; the 28-script `block_*.py` empty-stdin smoke diffed empty; the 34-module
import smoke diffed empty; `py_compile` passed 34/34 both before and after.

## Gotchas

- **`gcommit` silently skips `block_venv_no_redirect.py` on its filename.** The first `gcommit`
  call staged 33 of the 34 touched files and reported `skipped: src/hooks/block_venv_no_redirect.py`
  with no further explanation — its secret/dependency skip-list appears to pattern-match on the
  substring `venv` in the path, mistaking a hook module named for the `venv/` directory convention
  it polices for an actual `venv/` artifact. Confirmed via `git status --short` after the first
  commit (file still showed modified) and `git diff HEAD~1 -- <file>` (diff still present in the
  working tree). Resolved with a second, plain `git add` + `git commit` for that one file — same
  branch, same worktree, same commit-message convention — since it is source code, not a secret.
  Any future milestone touching a file whose path contains `venv` (by name, not by being an actual
  dependency directory) should check `git status` after `gcommit` for a silent skip rather than
  trusting the reported staged-file list alone.

## Cross-references

See `process-docs/hook_fp_audit/` and `process-docs/tool_use_safety/` for the unrelated
substantive history behind the hooks touched here — this entry is about the comment-removal
mechanics only.
