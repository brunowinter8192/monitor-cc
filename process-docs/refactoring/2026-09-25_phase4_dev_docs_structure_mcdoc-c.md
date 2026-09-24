# Phase 4 (docs structure) for dev/ DOCS.md files, worker mcdoc-c, 2026-09-25

## Scope and result

All 70 DOCS.md files under `dev/` were checked against the DOCS.md format template. Every file was rewritten or trimmed so that no function, method, class or constant name remains; module names and file paths stay. The largest DOCS.md after the rewrite is `dev/desktop_allocation/DOCS.md` at 358 lines; none reaches 400.

Verification: `docs-drift-check` run from the worktree root reports 0 findings for `dev/` files (the remaining 452 rule findings are in `src/` DOCS.md files, out of scope for this worker). The tool must be run with the untracked symlinks `venv` -> main checkout venv and `src/logs` -> main checkout logs present in the worktree. Without them it reports about 50 false path drifts (`./venv/bin/python`, `src/logs/dual_log`) because the worktree has neither the venv nor the gitignored logs. The symlinks were removed before committing.

## Method that worked

- A small checker script (Role word count, Flow line count, Purpose word count, missing template sections, LOC heading versus `wc -l`, `.py` files without a module heading) found the format issues the drift tool does not: 20 files had Purposes over 25 words, 10 had Roles over 50 words, `dev/DOCS.md`, `dev/cc_internals`, `dev/rag_helpfulness`, `dev/verbosity`, `dev/tool_injection/ToolsSystemPrompts` lacked template sections, `dev/proxy/test_strip_fix_cases_pasted_content.py` had no module entry.
- Large repetitive files (`hook_smoke`, `dual_log_cli`, `pane_search`) were regenerated from a small Python table instead of hand-edited, then verified with the checker.
- LOC headings are written with no padding (`(102 LOC)`); older files had `(     102 LOC)`.

## Details removed from DOCS.md that a successor may need

These were in DOCS.md as Gotchas, State or Purpose prose and are not recoverable from the code. The pre-rewrite text of every file is in git history (the integration branch before this branch's docs commits).

dev/cache:
- The classification the extractor matches against lives in `src/constants.py` and is shared with a later `src/hooks/` consumer; hooks must never import from `dev/`.
- Matching is text-pattern based, not a shell parse. Observed false hits: a `duallog search "sed -i"` call and prompt text quoting `sed -i` both produced a `sed -i` match with no sed invoked; several `<>`, `>|`, `gawk -i inplace`, `tee` matches came from exploratory Bash calls that built those regex substrings as Python literals. `matched_forms` and the verbatim `command` are stored so a downstream reader decides; the extractor does not filter.
- Deliberately excluded families (can overwrite content as a side effect but primary job is different): `cp`, `install`, `dd`, `patch`, `git apply`, `truncate`, `mv`, `rsync`, `curl -o`, `tar -x`, `unzip -o`, `git checkout --`. Kept frame: redirection operators, canonical in-place editors (`sed -i`, `perl -pi`/`-ni`, `gawk -i inplace`), `tee`, interpreter one-liners with an explicit write-mode `open()`. Reason: with "overwrite-capable" as the bar the list has no stopping point. Anyone extending the classification for a hook needs a completeness guarantee and should re-litigate each excluded entry.
- The output file is opened with exclusive create; a second run in the same second raises `FileExistsError` by design (tripwire, not fallback).
- `dev/cache/jsonl/bash_file_mods_20260915T142910Z.jsonl` (210 records) was renamed from the old fixed-name file, not regenerated; its timestamp is the file mtime at creation, verified against commit `51d156b9` within ten seconds.
- The dual-log directory is gitignored live-growing data, so record counts shift between runs.

dev/tmux_launcher:
- History: before the two-window split of the workers window, the "everything present" restart fixture had a mode-string typo (`workers` instead of `worker-tokens`). Presence is matched by the mode value in the pane start command, so the restart silently emitted one extra split while the docs claimed zero create calls. A single combined hash changed with every real refactor and hid it. Lesson: assert named invariants (zero creates) explicitly instead of hashing the whole argv stream.

dev/hook_error_correlation:
- Replaying a blocking hook runs the real hook script from `src/hooks/` as a subprocess; a hook that blocks appends to the production hook-fire log. That is a live side effect on shared state. Replay must use the main project directory as cwd, not the worktree: the cd-drift hook exits 0 whenever the cwd contains `.claude/worktrees/`, which would make every replay look non-blocking.

dev/hook_smoke:
- The header-capture test failed 9 of 13 checks against the then-current proxy addon and is excluded from the runner.
- The replay probe and the corpus report renderer write tracked reports that are historical snapshots; regenerating them against the live corpus can drift without being a code regression.
- The corpus verification script targets a retired hook and cannot run.

dev/verbosity:
- `corpus/sessions/*.jsonl` and `corpus/k2_turns.md` are frozen; the extractor hardcodes the live session directory, so a re-run does not reproduce the same turns. Do not regenerate without a new dated report. The session files were scanned for credential material before commit (cloud/API keys, private-key headers, `.env` assignments, basic-auth URLs, SSH keys, certificate headers, plus a high-entropy sweep) and contained none; the only base64 blobs are extended-thinking signatures and pasted screenshot data.

dev/tool_injection/ToolsSystemPrompts:
- Char counts are valid only for the CC version of the capture; re-capture instead of trusting stale numbers.

dev/cc_internals:
- Sources of the env-var inventory: npm binary `@anthropic-ai/claude-code-darwin-arm64@2.1.121` (strings via `grep -oa "CLAUDE_[A-Z][A-Z_]*"`), decompile repos `thepono1/claude-code-source` (INSIGHTS.md, v2.1.88) and `alanisme/claude-code-decompiled` (docs/en, v2.1.88), and issues #33949, #25979, #49500 of `anthropics/claude-code`. Related area: `process-docs/cc_internals/`.

dev/proxy_dual_log (root and subareas):
- Every script finds the area root by walking up from its own file until a directory named `proxy_dual_log` appears; the project or worktree root is two levels above it. Scripts that need the gitignored corpus also derive the main-checkout root by stripping a trailing `.claude/worktrees/<name>`, and try the direct path first (except the span-inline probe, which always uses the main checkout). Report directories stay at the area root even for scripts in subfolders.
- The main-log elimination probe's root fallback (env var unset) is the project or worktree root; it was never main-checkout-aware and that scope was preserved deliberately.
- The composition corpus module lists five fixed stems, all rotated off disk. The corpus run skips missing stems, but the money-shot loader has no guard and raises; the probe catches that and embeds an error block in its report.
- The green-overlay probe's hardcoded stem is rotated off disk; case loading fails per section and is embedded as an error block. The ground-truth spans probe has two rotated stems; each loader failure is caught and reported as an error line. The span-inline probe raises on load, uncaught.
- One replay script patches and restores an accumulator predicate for one baseline comparison call.

dev/proxy_analysis:
- The flat single-file log schema it reads (total input chars, diff from previous, message count, cache breakpoints) is produced by no current writer; the dual-log split replaced it. The script resolves the logs directory via the monitor root env var, else script-relative, else cwd-relative.

dev/proxy_display:
- Byte-identity default input is the newest live forwarded log, which grows during a session; pin it with the log-dir env var on a copied corpus. `verify_req_numbering.py` reads hardcoded live paths with no seam, results change as logs rotate.

dev/sleep_pattern_analysis:
- The entry script's default report path points to a report that no longer exists; always pass `--out`.

dev/pipeline:
- Two scripts import `src.jsonl_parser`, which now lives under `src/jsonl/`; both are broken and dead by import graph. Not fixed (docs-only task).

dev/timer-loop:
- The p3 probe is dead: the hook module and pending-state module it imports no longer exist, it raises before completing.

dev/proxy:
- `replay_strip_v2.py` and `scan_sr_catalog.py` read a log directory under the project's pre-rename casing; a glob on the missing directory yields zero entries, no error. Non-functional against the current tree.
- Byte-identity harnesses default to the newest live original log; pin it via the harness env vars.

dev/proxy_tool_stripping:
- The trailing-shapes probe reads three fixed corpus stems that are rotated out; a run raises.

dev/native-model-start:
- p3, p4 and p5 replay two pinned pin-bump-era sessions that are rotated out; they raise before writing, their reports are historical snapshots.

dev/hotkey_latency:
- The interactive probe duplicates the Carbon boilerplate instead of importing the production hotkey controller because dev-imports-src is blocked repo-wide; its callback is kept alive on the app instance as a GC anchor.

dev/session_analysis:
- Two scripts write into a `04_reports/` directory that does not exist (the tracked directory is `md/`); pre-existing inconsistency, not fixed.

dev/desktop_allocation:
- `json/`, `png/`, `txt/` hold artifacts of an earlier pre-split version of the probes; no current module writes there.

dev/jsonl:
- The proof script writes baselines to its own reports directory, which differs from the tracked `json/` folder (pre-existing path drift).

## Decisions for a successor

- Function-level content moved out of DOCS.md means DOCS.md now says "verification aid, asserts nothing" or "manual test" per module instead of naming the function under test. If a reader needs the function, the module's `Calls out` line points to the `src` package.
- `dev/DOCS.md` keeps its area list under a Modules heading (subdirectories, not `.py` files) because the template has no other place for a map; it covers 21 of about 60 areas, the rest have their own DOCS.md.
- Not done (out of scope): fixing broken imports in `dev/pipeline`, adding a producing script for `dev/rag_helpfulness`, splitting any directory.
