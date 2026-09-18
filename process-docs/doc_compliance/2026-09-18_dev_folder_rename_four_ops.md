# Doc-Compliance Sweep — Four dev/ Folder Renames onto process-docs Areas (2026-09-18)

A follow-up pass to the 2026-07-25 dev-folder-rename sweep (see `process-docs/doc_compliance/`
for that entry). Aligned the four remaining `dev/<area>/` directories whose name did not match
their `process-docs/<area>/` counterpart. Confirmed via `comm -23` on sorted directory-name lists
(`dev/*/` vs `process-docs/*/`) that these were the complete set — no fifth mismatch exists.

## Old-path to new-path mapping

Read this table first. Roughly thirty `process-docs/` files outside `doc_compliance/` still cite
the OLD paths below — per the hard rule that closed process-docs files are never edited, none of
them were touched, so they are permanently stale on this point. Resolve any stale `dev/` path you
encounter in another process-docs file against this table, then move on.

| Old path | New path |
|---|---|
| `dev/grid_probe/` | `dev/nsgridview_migration/` |
| `dev/desktop_detection/` | `dev/desktop_allocation/` |
| `dev/strip_fp_tool_result/` | `dev/message_strip_fp_nuke/` |
| `dev/ToolsSystemPrompts/` | `dev/tool_injection/ToolsSystemPrompts/` (moved INTO an existing area as a subdirectory, not renamed onto a sibling area — `ToolsSystemPrompts` has no `process-docs/` area of its own) |

All four moves used `git mv`, so file history survived intact under the new paths.

## What else changed beyond the four `git mv` calls

- Each moved `DOCS.md` had its own heading line and its "run it like this" entry-path example(s)
  rewritten to the new path (`dev/nsgridview_migration/DOCS.md`, `dev/desktop_allocation/DOCS.md`,
  `dev/message_strip_fp_nuke/DOCS.md`, `dev/tool_injection/ToolsSystemPrompts/DOCS.md`).
- `dev/DOCS.md` line 29 — the only per-area bullet in its (deliberately partial) map that named
  one of the four old paths — updated `desktop_detection/` to `desktop_allocation/`. The other
  three old names were never in that bullet list to begin with (the list explicitly scopes itself
  to a subset and says "Other `dev/` areas exist outside this map's scope; see their own
  `DOCS.md`") — confirmed by grep before touching anything, so no other bullet needed a change.
- `dev/tool_injection/DOCS.md` — added a one-line `ToolsSystemPrompts/` pointer in its `## Modules`
  section (`### ToolsSystemPrompts/ (reference corpus, no .py modules — see its own DOCS.md)`,
  mirrored from the existing `attribution_coverage/` pointer pattern in
  `dev/proxy_dual_log/DOCS.md`) plus one clause in `## Public Interface` noting the subdirectory is
  a captured corpus, not a script.
- `.gitignore` line 63 hardcoded `dev/desktop_detection/02_bundle_stub.app/Contents/_CodeSignature/`
  — updated to `dev/desktop_allocation/...`. This was found only by grepping the whole repo for the
  four old strings, not by reading `.gitignore` on suspicion; it is the one touch-point outside
  `dev/`/`process-docs/` that this rename required.
- No `.py` file inside any of the four moved directories needed a content change. Verified by
  direct grep against every `.py` file in each old directory before moving: none contained a
  hardcoded string of their own directory name. All output-directory constants in
  `dev/desktop_allocation/*.py` (`_REPORTS_DIR = Path(__file__).parent / "NN_reports"`, one per
  `probeNN_*.py`) and in `dev/message_strip_fp_nuke/audit_report.py`
  (`os.path.join(os.path.dirname(__file__), 'md', ...)`) are built from `__file__`, not from a
  literal directory-name string, so a pure rename cannot break them.

## The .app bundle stubs — a separate, pre-existing dead-artifact finding (not fixed here, flagging for a future task)

`dev/desktop_allocation/02_bundle_stub.app/` and `03_bundle_stub.app/` were `git mv`d as opaque
directories, nothing inside was edited. Read both `Contents/MacOS/launcher` scripts and both
`Contents/Info.plist` files before deciding this. What is actually inside:

- Both `launcher` scripts hardcode an absolute path into a `.claude/worktrees/<name>/` directory
  that no longer exists — `probe02-context` for the 02 bundle, `probe03-fields` for the 03 bundle.
  `ls .claude/worktrees/` on this machine at the time of this pass shows only `arearename`,
  `waste-repetition`, `winsplit` — neither `probe02-context` nor `probe03-fields` is present.
- Both hardcoded paths additionally use the OLD, differently-cased repo root name `Monitor_CC`
  (e.g. `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/probe02-context/...`),
  while the actual current repo root on this machine is the lowercase `monitor-cc`
  (`/Users/brunowinter2000/Documents/ai/monitor-cc`). The repo itself was renamed at some point
  after these bundles were captured.
- `03_bundle_stub.app` is ad-hoc code-signed — `codesign -dv` on it reports
  `CodeDirectory ... flags=0x2(adhoc)` and `codesign -v` passes. `02_bundle_stub.app` is NOT signed
  (`codesign -dv` reports "code object is not signed at all") — there is no `_CodeSignature/`
  directory inside it, matching the defensive (currently inert) `.gitignore` rule for that path.

Conclusion: both bundles were already fully non-functional before this rename, for two reasons
that have nothing to do with the directory name — a worktree that no longer exists, and a repo
root whose casing already changed. Editing the `dev/desktop_detection` segment inside `launcher`
to say `dev/desktop_allocation` would not have restored anything (the worktree and the casing are
still wrong), and editing `03_bundle_stub.app`'s `launcher` in place would have invalidated its
existing ad-hoc signature for zero functional gain. Decision: leave both bundles' internals
untouched, `git mv` the parent directory only. A future task that wants a working bundle stub
again should treat this as a from-scratch re-capture (new worktree path, new signature), not a
one-line path fix.

## Forensic .md files that still quote the old paths — named here so a successor does not have to search

Three `dev/` files (not `process-docs/`, so nominally in-scope, but the same write-once rule
applies) quote an old `dev/` path inside captured, timestamped analysis prose rather than as a
live doc reference. Left untouched, same precedent as the German-artifact write-once rule in the
2026-07-25 sweep:

- `dev/tool_use_analysis/md/20260422_session_waste_patterns.md:89` — a captured Bash tool-call
  string that literally runs `ls .../dev/ToolsSystemPrompts/` as part of a quoted historical
  session transcript.
- `dev/verbosity/corpus/k2_turns.md` (lines 1287, 1295, 1531, 1541, 1586) and its rendered twin
  `dev/verbosity/md/20260827_k2_distinctness.md` (lines 438, 450) — German analysis prose from a
  captured K2 turn, discussing the `strip_fp_tool_result` dev-folder name explicitly as something
  that "does not exist as a process-docs folder" (which was true at capture time and is the exact
  gap this pass just closed) and quoting `dev/strip_fp_tool_result` as a path inside that
  discussion.
- `dev/hook_error_correlation/md/hook_block_analysis_2026-05-22.md:169` — a table row quoting a
  historical hook-block log line that contains the literal shell command
  `./venv/bin/python3 dev/grid_probe/p` (truncated in the original log line itself).

None of these are doc references that need to resolve — they are quotes of what was literally
typed/logged at the time, and rewriting them would falsify the forensic record.

## Two confirmed false leads (do not re-walk this path)

An initial broad `grep -rl` sweep with multiple `--include` globs at once surfaced
`src/hooks/block_dev_imports_src.py`, `src/hooks/hook_setup.py`, and
`dev/tool_use_errors/error_cluster_report.py` as apparent hits. A direct `grep -n` against each of
those three files individually found zero matches for any of the four old strings — the broad
`-l` pass's result set does not correspond to real content in those files (a tool-call artifact of
that particular grep invocation, not a real signal). Also: `src/menubar/discover.py` and
`src/menubar/desktop_detection.py` DO contain the substring `desktop_detection`, but it is an
unrelated, real production module (`src/menubar/desktop_detection.py`, imported via
`from .desktop_detection import detect_main_desktop_numbers`) and a same-named timing dict key
(`timings['desktop_detection']`) that predates and has nothing to do with the `dev/desktop_detection/`
probe folder — confirmed no change needed. The `dev/hotkey_latency/md/latency_report_*.md` and
`dev/refactoring/md/2026-09-16_src_control_flow_scan.md` files that mention `desktop_detection`
are citing this same real `src/menubar` module/metric, not the moved `dev/` folder.

## Verification

- `python3 -m py_compile` on every `.py` file in all three code-bearing moved directories (32 files
  in `dev/desktop_allocation/`, 4 in `dev/message_strip_fp_nuke/`, 1 in
  `dev/nsgridview_migration/`) — all compiled cleanly post-move.
- `dev/nsgridview_migration/probe.py` was deliberately never run or imported — it calls `main()`
  unconditionally at module scope (no `if __name__ == "__main__":` guard), so any import opens a
  real floating `NSPanel` and blocks in `app.run()`. `py_compile` proves syntactic survival of the
  move without executing that module-level call.
- `dev/desktop_allocation/`'s 24 entry/helper scripts use bare sibling imports
  (`from probe01_bridge import ...`, not path-string based), so a directory rename cannot break
  them by construction; confirmed anyway with a static `ast`-based check that every
  `from probeNN_x import ...` / `import probeNN_x` target across all 32 files resolves to a sibling
  file that still exists post-move. None of these scripts were executed — per the area's own
  `DOCS.md`, 4 of 6 top-level entry scripts mutate the real desktop (move/open/close real windows)
  and the other 2 still drive live AppleScript/CGS queries; none of that is worth triggering just
  to prove a rename.
- `dev/message_strip_fp_nuke/audit_tool_result_sr_strips.py` was actually run post-move
  (`./venv/bin/python3 dev/message_strip_fp_nuke/audit_tool_result_sr_strips.py`) — the one script
  among the four areas that is genuinely safe to execute (read-only against the real dual-log
  corpus at the main checkout's `src/logs/dual_log`, no GUI, no desktop mutation). It completed
  without error and wrote a fresh `md/audit_tool_result_sr_strips.md`. The fresh report's content
  differs completely from the pre-move committed report (`md5` differs, `diff` shows thousands of
  changed lines) — NOT because of the rename, but because `src/logs/dual_log` is a live, growing
  corpus (the report's own text warns of this: "other sessions in this corpus are ALSO live"; the
  main checkout held 293 dual-log files at verification time vs. the 5-6 the committed report was
  generated against). Since this task is a rename, not a re-audit, the fresh report was discarded
  and the pre-move committed content restored byte-for-byte at the new path (`md5` before restore:
  `f790965...`; after restore: `d9d789f...`, matching the original) — confirmed via `git status`
  that the file still shows as a clean `R` (rename, zero content delta) after the restore, not as
  a modified-content rename.
- `docs-drift-check` run before and after the full change set: identical totals both times — 45
  findings (41 path-drift, 0 LOC-drift, 4 symbol-drift). The only line-level difference between the
  two runs is that the two pre-existing `dev/logs/dual_log`-not-found path-drift findings that used
  to cite `dev/strip_fp_tool_result/DOCS.md:14`/`:34` now cite `dev/message_strip_fp_nuke/DOCS.md:14`/`:34`
  — the same two pre-existing findings, relabeled to the new path, not new findings. Zero new
  findings were introduced.
- `comm -23 <(ls -d dev/*/ | sed 's|dev/||; s|/$||' | sort) <(ls -d process-docs/*/ | sed 's|process-docs/||; s|/$||' | sort)`
  returns empty after the change — every top-level `dev/<area>/` now has a matching
  `process-docs/<area>/`.
