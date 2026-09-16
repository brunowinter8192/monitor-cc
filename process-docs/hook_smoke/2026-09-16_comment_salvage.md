# process-docs/hook_smoke/2026-09-16_comment_salvage.md

Session: dev/hook_smoke/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/hook_smoke/*.py` during this milestone, copied
verbatim before deletion, plus the full pre-rewrite content of `dev/hook_smoke/DOCS.md`. Nothing
judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File-count note: the milestone prompt stated "26 .py files" as the measured state; the actual
count in `dev/hook_smoke/` is 29 `.py` files. The comment/docstring totals it stated (277 comments,
4 docstrings) match exactly what AST+tokenize measured across all 29 files, so the file-count
figure in the prompt is treated as approximate/stale and all 29 files were processed. 3 of the 29
(`test_block_non_canonical_edit.py`, `verify_block_non_canonical_edit_corpus.py`,
`verify_block_non_canonical_edit_report.py`) already had zero comments and zero docstrings before
this milestone touched them.

Grep for `__doc__` across `dev/hook_smoke/*.py` before deletion: zero matches. One file
(`probe_bg_task_live.py`) uses `argparse.ArgumentParser()` but never passes `description=` or
`epilog=`, and never has a module docstring at all (0 docstrings measured in that file) — so no
load-bearing docstring exists anywhere in this directory. All 4 docstrings deleted outright, no
constant-rewiring needed.

Comment/docstring counts confirmed via AST + tokenize before deletion: 277 comments, 4 docstrings,
matching the task's stated measured state exactly (despite the file-count note above).

## Salvage from dev/hook_smoke/DOCS.md

Full content of dev/hook_smoke/DOCS.md as it stood before this rewrite (407 lines), preserved
verbatim since the whole file is being replaced with the mandated leaner format (Role capped
at 50 words, Purpose capped at 25 words per module, no Gotchas section in the new format,
Public Interface / Flow / State sections added).

```markdown
# dev/hook_smoke/

## Role

Smoke-test suite for `src/hooks/` — one test script per hook, verifying positive (blocks/rewrites)
and negative (pass-through) cases. Unless noted otherwise below, each script invokes its hook via
`subprocess` with a JSON payload on stdin and checks the exit code (`0` = allow, `2` = block) plus
stdout/stderr against expected text, printing `All N tests/cases passed.` and exiting 1 on any
failure. Touch this suite when adding a new hook (add a matching test script) or changing hook
logic (extend the existing one).

## Modules

### test_block_chained_sleep.py (67 LOC)

**Purpose:** 13-case smoke for the retired `block_chained_sleep.py.disabled` — the canonical
`sleep N && echo done` form, chained/non-canonical sleep placements, heredoc/quoted-string/
ANSI-C-quote stripping, and command-substitution/backtick sleeps kept shell-active. `HOOK` now
points at the `.disabled` path (it used to point at the pre-rename name and silently test nothing
— see the Gotcha below for that history and its fix) and the suite genuinely executes the retired
hook's real code again: 13/13 pass, unchanged from what this test always asserted, since only the
path was ever wrong, never the hook's own logic.
**Called by:** none — run manually.

---

### test_block_broad_grep.py (84 LOC)

**Purpose:** 16-case smoke for `block_broad_grep.py` — blocked broad-recursive-piped-to-non-head
cases, head-bounded exemptions, and pre-existing exemptions (`--include`, file-targeted,
non-recursive, git grep, quoted, heredoc).
**Called by:** none — run manually.

---

### test_block_broad_find.py (99 LOC)

**Purpose:** 19-case smoke for `block_broad_find.py` — blocked broad-root `find` calls (`~`,
`$HOME`, filesystem root, no `-maxdepth`), allowed narrower/targeted cases.
**Called by:** none — run manually.

---

### test_block_gh_cli_local_path.py (83 LOC)

**Purpose:** 15-case smoke for `block_gh_cli_local_path.py` — blocked local-path arguments to
`gh-cli get_file_content`/`download_files` (incl. the `--dest` false-positive trap in both flag
positions), pass cases, untouched-command cases, and shell-strip-pass cases.
**Called by:** none — run manually.
**Writes:** `md/block_gh_cli_local_path_smoke_report.md`.

---

### test_block_rag_cli_index_isolated.py (146 LOC)

**Purpose:** 37-case smoke for `block_rag_cli_index_isolated.py` — blocked poll-then-index chain
shapes (noise before/after via `&&`/`;`, env-prefixed/multi-assignment-prefixed index, command/
process/arithmetic substitution smuggling, bare `&`) and allowed cases (bare index, cd-before-
index, quoted/heredoc-embedded index text, out-of-scope subcommands).
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_block_dangerous_kill.py (90 LOC)

**Purpose:** 18-case smoke for `block_dangerous_kill.py` — `pkill -f` patterns, pipe-kill chains,
heredoc/quote exemptions, allowlist cases.
**Called by:** none — run manually.

---

### test_block_git_destructive.py (107 LOC)

**Purpose:** 21-case smoke for `block_git_destructive.py` — force-push variants, `--amend`,
`--no-verify`, `--allow-empty`, `git config` writes (block), plain push/commit/config-read and a
force-push phrase inside a quoted message (allow), plus 2 FP-regression allow cases.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_block_manual_worker_cleanup.py (100 LOC)

**Purpose:** 21-case smoke for `block_manual_worker_cleanup.py` — blocked `tmux kill-session` on
a `worker-*` target (incl. flag-order and no-space-after-`-t` variants) and blocked
`git worktree remove` on `.claude/worktrees/`.
**Called by:** none — run manually.

---

### test_block_read_worktree.py (74 LOC)

**Purpose:** Smoke for `block_read_worktree.py` — foreign-worktree reads blocked, own-worktree
reads allowed.
**Called by:** none — run manually.

---

### test_log_janitor.py (75 LOC)

**Purpose:** 4-case smoke for `cleanup_old_jsonl` in `src/panes/log_janitor.py` — record older
than the retention window dropped, recent record kept, empty `ts` kept (fail-safe), naive-ts
without TZ kept (fail-safe on `TypeError`).
**Called by:** none — run manually.
**Calls out:** none — imports `log_janitor` directly via `sys.path.insert` on `src/panes/` to
avoid the `from src.` import restriction (not a `subprocess` call, unlike most of this suite).

---

### test_rewrite_background_sleep.py (184 LOC)

**Purpose:** 14-case smoke for `rewrite_background_sleep.py` — positive rewrites of `sleep N`/
chained-`sleep` shapes to the canonical `worker-cli wait` form, no-op cases for already-canonical
or foreground commands, and no-op cases from a `.claude/worktrees/`-shaped cwd (orchestrator-only
guard).
**Called by:** none — run manually.

---

### test_block_unauthorized_background.py (96 LOC)

**Purpose:** 14-case smoke for `block_unauthorized_background.py` — `sleep`/`worker-cli wait`
kept exempt from the foreground force, other backgrounded commands forced to foreground, one
already-foreground pass-through case.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_rewrite_chained_sleep.py (226 LOC)

**Purpose:** 8-case smoke for `rewrite_chained_sleep.py` — trivial-sync `cmd_before` (`echo`,
`true`) strips the sleep; load-bearing `cmd_before` (`kill`, `launchctl`), loop bodies, sleep-first
shapes, and the canonical timer form are no-ops.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_version_purge.sh (140 LOC)

**Purpose:** 8-assertion smoke for the version-aware dual-log purge
(`_janitor_version_purge_jsonl_logs` + `_compute_proxy_hash` in `src/claude_proxy_start.sh`),
run in a temp dir — version change purges stale logs, same version leaves them, fresh logs
survive a purge, absent marker triggers first-run cleanup.
**Called by:** none — run manually.
**Gotcha:** mirrors the production shell functions inline — keep in sync with
`src/claude_proxy_start.sh` when editing either.

---

### test_header_capture.py (179 LOC)

**Purpose:** 13-case smoke for the proxy header-capture logic in `src/proxy/addon.py` — beta-flag
extraction from the `anthropic-beta` header, and `_filter_response_headers()` exact-name/prefix
filtering with lowercase normalization.
**Reads:** minimal mock headers objects — no live mitmproxy process required.
**Called by:** none — run manually.
**Calls out:** none — imports `_filter_response_headers` directly from `src/proxy/addon.py` via
`sys.path.insert` on `src/`.

---

### test_bg_task_detection.py (145 LOC)

**Purpose:** 6-case smoke for `_has_active_bg` in `src/menubar/proc_cache.py` (open-file-handle
predicate) — 3 unit cases via a monkeypatched `_bg_task_open_paths` snapshot (match, no-match,
session-id prefix-collision boundary), 1 integration case (real subprocess holds a file open, a
real `lsof` scan detects it), 1 fail-open case (`lsof` raising leaves the prior snapshot in place),
1 TTL-gate case (`_PROC_REFRESH_INTERVAL` gates re-invoking `lsof`).
**Writes:** a scratch dir under the real `_TASKS_BASE`
(`/tmp/claude-<uid>/__test_bg_probe__/`) for the integration case only, cleaned up in a `finally`.
**Called by:** none — run manually.

---

### probe_bg_task_live.py (217 LOC)

**Purpose:** Live probe comparing the old 0-byte predicate against `_has_active_bg` (open-handle
predicate) against a real running background task, a synthetic writer loop, and a
no-background-task control session; benchmarks the batched `lsof` cache's per-tick cost.
`--snapshot` prints one JSON measurement and exits.
**Called by:** none — run manually; not CI-safe (depends on a live external task being supplied).
**Gotcha:** a Bash-tool-invoked check running INSIDE the same CC session it targets can itself
become a transient open `*.output` handle in that session's tasks dir — a long-lived
non-`--snapshot` run against its own session can hang indefinitely waiting for `new=False`, which
never arrives while it is itself the open handle. Drive repeated measurements via `--snapshot`
from an external shell loop instead of one long-lived Python loop; scope `lsof` to the specific
target file (`lsof <path>`), not the whole session directory, to avoid the self-entry.

---

### test_block_po_read.py (123 LOC)

**Purpose:** 19-case smoke for `block_po_read.py` — blocked readers (`head`/`tail`/`grep`/`cat`/
`sed`/`rg`, piped, and `split`/`dd` partitioning-escape) on a persisted-output `.txt` path under
`.claude/`, allowed cases (non-`.claude/` paths, non-`.txt` paths, writes, malformed stdin
fail-open), plus 3 real-file size-boundary cases (M2) proving the size gate against real bytes on
disk: a file at exactly the pinned ceiling still blocks, one byte over it passes, and `dd if=<path>`
against an over-ceiling file passes too (proving the `if=` token prefix is stripped before the file
is stat'ed, not left attached to a broken path). Pins its own literal `_PINNED_MAX_BYTES` copy of
the ceiling, independent of `block_po_read.py`'s own constant — see the Gotcha in
`src/hooks/DOCS.md`.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_block_cli_chained.py (188 LOC)

**Purpose:** 45-case smoke for `block_cli_chained.py` — the single hook covering all 3 chain-abuse
rule classes (pipe after a known-CLI segment, redirect on a protected subcommand, readback of a
redirected protected-subcommand's output) across all 8 known wrapper CLIs (`rag-cli`, `gh-cli`,
`worker-cli`, `websearch`, `duallog`, `linkedin-cli`, `penny-cli`, `reddit-cli`), 5 cases proving
the same rules apply when a wrapper's `cli.py` is invoked directly through its Python interpreter
path naming its project directory in the command, plus 3 cases for the same interpreter form
falling back to the payload's `cwd` when the command names no directory (2 measured real-transcript
bypasses BLOCK, one other project's own `cli.py` with an unrelated cwd stays PASS). Cases carrying a
4th tuple element pass that value as the payload's `cwd`.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### probe_replay_cli_chained.py (132 LOC)

**Purpose:** Feeds every historical `decision="block"` fire of the hooks `block_cli_chained.py`
replaced (`block_gh_cli_chained`, `block_rag_cli_chained`, `block_worker_cli_read_chained`,
`block_websearch_scrape_chained`, `block_duallog_chained`, `block_linkedin_cli_isolated`,
`block_penny_cli_chained`) from the main checkout's `hook_firing.jsonl` through the current
`block_cli_chained.py`, reporting still-blocks vs. now-passes per old hook.
**Reads:** `<main-repo-root>/src/logs/hook_firing.jsonl` (resolved by stripping this script's own
`.claude/worktrees/<name>` path suffix — works from any worktree).
**Writes:** `md/block_cli_chained_replay_report.md` (per-hook counts + full text of every
now-passing command, grouped by old hook).
**Called by:** none — run manually.

---

### test_block_rag_cli_document_repeat.py (193 LOC)

**Purpose:** 7-case smoke for `block_rag_cli_document_repeat.py` — a single `--document` call
passes, a 2nd call to the same collection+subcommand within the window blocks, collection-wide
calls always pass, per-session counters don't cross-contaminate, `delete --document` shares the
threshold with `index`, malformed stdin fails open. Each case uses a fresh
`MONITOR_CC_RAG_DOC_REPEAT_STATE` tempfile — no shared state across cases.
**Called by:** none — run manually; must be run from project root (HOOK path is relative).

---

### test_hook_setup_main_branch_gate.py (135 LOC)

**Purpose:** 10-case smoke for the two-condition install gate in `hook_setup.py`'s
`decide_entries()` — a hook script is installed only if it's both committed on `main` AND present
in the current working tree; either condition alone (or a query-unanswerable `None`) causes a
fail-safe skip. Uses stub `git_query_fn`/`tree_query_fn`, no real git or filesystem calls.
**Called by:** none — run manually.

---

### test_block_rag_corpus_read.py (152 LOC)

**Purpose:** smoke for `block_rag_corpus_read.py` — blocked raw-read commands (`cat`/`grep -r`/
`head`/`tail`/`sed`) over the rag-cli corpus document tree, allowed reads elsewhere.
**Called by:** none — run manually.

---

### test_block_rag_docs_layer.py (77 LOC)

**Purpose:** 11-case smoke for `block_rag_docs_layer.py` — `rag-cli search` against a `*-docs`
collection blocks without a `process-docs/%` filter (`--document` or `--exclude`), allows with it.
**Called by:** none — run manually.

---

### test_block_worker_kill_while_working.py (121 LOC)

**Purpose:** Smoke for `decide()` in `block_worker_kill_while_working.py`, using the real
`_strip_non_shell_active` and a stub `status_fn` — no real workers required, all status responses
injected via the stub.
**Called by:** none — run manually.
**Calls out:** none — imports `decide` directly from `src/hooks/block_worker_kill_while_working.py`
via `sys.path.insert`.

---

### test_block_worker_send_while_working.py (138 LOC)

**Purpose:** Smoke for `decide()` in `block_worker_send_while_working.py` via the same stub
pattern as `test_block_worker_kill_while_working.py`, plus one real `subprocess` invocation of the
hook entrypoint for the malformed-stdin fail-open case (`decide()` itself never touches stdin).
**Called by:** none — run manually.
**Calls out:** none — imports `decide` directly via `sys.path.insert`.

---

### test_fire_log.py (217 LOC)

**Purpose:** Regression for the shared hook fire-logging helper (`src/hooks/_fire_log.py`) —
verifies a block decision from `block_noop_edit.py` and a rewrite decision from
`rewrite_chained_sleep.py` each append the expected record to the fire log, an env-var override
of the log path is honored, and the tool-error writer path works.
**Called by:** none — run manually.

---

### test_block_non_canonical_edit.py (131 LOC)

**Purpose:** 18-case smoke for the retired `block_non_canonical_edit.py.disabled` — the
always-block shell-level forms (`sed -i`, `perl -pi`, `gawk -i inplace`), the always-block
python-body form (`open(..., 'r+')`), a truncating `cat >`/bare `tee` on an existing file, a
non-canonical python heredoc (wrong delimiter) on an existing file, the always-allow forms
(new-file creation, `>>`/`tee -a` appending, `python open() mode x`), the exact canonical
`'LINEEDIT'` form applied for real against a fixture file, an unresolvable path (`sys.argv`), the
two false-positive-avoidance cases found during the classification milestone's own calibration
(`sed -i` mentioned only as prose in a new-file heredoc, and only as a quoted search term), and
the shared malformed-stdin fail-open case. Its `HOOK` constant was updated to the `.disabled`
path on retirement so it keeps genuinely passing rather than silently testing nothing — see the
`test_block_chained_sleep.py` Gotcha below for what happens when that update is skipped. The
19th case from this hook's active period (a direct-import monkeypatch forcing `_decide` to raise)
was removed on retirement, not merely left broken: it required importing the module by name,
which a `.disabled` file cannot satisfy, and an uncaught `ModuleNotFoundError` would crash this
whole script rather than report a clean pass/fail count.
**Called by:** none — run manually.
**Calls out:** none — drives the hook via `subprocess` over stdin JSON, same shape as
`test_block_po_read.py`.

---

### verify_block_non_canonical_edit_corpus.py (64 LOC)

**Purpose:** Ran `block_non_canonical_edit.py`'s `_decide()` directly against every record in
`dev/cache/jsonl/bash_file_mods_*.jsonl` while the hook was live, measuring its real-world verdict
distribution before/during activation. The hook is now retired
(`block_non_canonical_edit.py.disabled`) and this script can no longer run as written: its
`from block_non_canonical_edit import _decide` needs a `.py`-suffixed, importable module name,
which the disabled file no longer has. Adapting the import (e.g. via
`importlib.util.spec_from_file_location`) was judged out of scope for the retirement — new loading
machinery the script never needed while the hook was live. Kept, not deleted, for its
already-committed findings and corpus-replay methodology (see
`md/block_non_canonical_edit_corpus_report.md` and `process-docs/tool_use_safety/`), not for
re-execution.
**Reads:** `dev/cache/jsonl/bash_file_mods_*.jsonl` (read-only, never written to).
**Writes:** nothing directly; delegates to `verify_block_non_canonical_edit_report.py`.
**Called by:** none — cannot currently run; see Purpose.
**Calls out:** `src.hooks.block_non_canonical_edit` (`_decide`) — target retired;
`verify_block_non_canonical_edit_report.py` (`_write_report`).

---

### verify_block_non_canonical_edit_report.py (87 LOC)

**Purpose:** Pure markdown rendering for the corpus-verification report — verdict counts, the
BLOCK/ERROR full lists, and the ALLOW spot-check (first 40) — from an already-evaluated
`results` list.
**Reads:** nothing — takes `results` as an argument.
**Writes:** `md/block_non_canonical_edit_corpus_report.md` — a historical snapshot from while the
hook was live, not regenerated (see `verify_block_non_canonical_edit_corpus.py`'s Purpose — the
caller can no longer run).
**Called by:** `verify_block_non_canonical_edit_corpus.py`.

---

## Gotchas

**`log_janitor`, `block_worker_kill_while_working`, and `block_worker_send_while_working`'s test
scripts import the hook/target module directly** (`sys.path.insert` + bare `import`), not via
`subprocess` — the pure-decision logic (`decide()`, `cleanup_old_jsonl()`) is unit-tested
in-process while every other script in this suite drives the hook as a subprocess over stdin JSON.

**Several HOOK paths inside these scripts are relative** (`src/hooks/<name>.py`) — those scripts
must be run from the project root or they silently fail to find the hook.

**`verify_block_non_canonical_edit_corpus.py`'s `cwd_guess` is a leading-`cd`-extraction heuristic
for offline testing only, not a real `cwd`.** The real hook receives `cwd` from Claude Code's own
stdin payload on every real invocation; the extracted corpus records carry no such field. A
command with no leading `cd` and a relative target path resolves against this worktree's own
`os.getcwd()` instead of the session's real working directory, which can silently misresolve a
target to a nonexistent path — confirmed concretely: `toolu_01DmbPtmA6jHZAL6LEXH2LLe`'s
`open(p).read()` / `open(p, "w")` read-modify-write of `dokumente/goethe/prozess/2026-09-14.md`
(no leading `cd`) reported ALLOW during verification because the relative path resolved into this
monitor-cc worktree rather than the real wise2627 project directory where the file genuinely
exists. Separately, on the BLOCK side: many `>`/`cat >` targets under `/tmp/` or inside a worker
worktree report BLOCK not because the original command was wrong but because either (a) that
exact command is what created the file, which is still sitting there from its real run, or (b) the
worker worktree it targeted has since been deleted post-merge, both confirmed against
`dev/hook_smoke/md/block_non_canonical_edit_corpus_report.md`'s BLOCK list by hand. None of this
is a defect in `block_non_canonical_edit.py` itself, retired since as
`block_non_canonical_edit.py.disabled` — see `process-docs/tool_use_safety/` for this hook's full
history.

**`test_block_chained_sleep.py` used to report PASS without ever executing its target — a real
defect, found while retiring `block_non_canonical_edit.py`, fixed in a follow-up milestone the
same day.** Its `HOOK` constant pointed at `src/hooks/block_chained_sleep.py`, the path from
before that hook was disabled; the file had not existed there since the rename to
`block_chained_sleep.py.disabled`. `subprocess.run(["python3", HOOK], ...)` against a nonexistent
path does not fail the way a broken hook invocation should — `python3` itself prints `can't open
file ... No such file or directory` and exits with status 2, and 2 is also this hook family's own
"block" exit code. The two codes collided by coincidence, not by any check this test performed.
The practical effect while broken: every case in `CASES` that expects BLOCK (`exit=2`) reported
OK, because `python3`'s own file-not-found exit code happened to equal 2 regardless of what the
(nonexistent) hook would have decided; every case that expects PASS (`exit=0`) reported FAIL,
because `python3`'s file-not-found exit code is never 0 — 5 of the 13 cases (`chained before
sleep`, `non-echo-done cont`, `real sleep after quoted`, `cmd-subst sleep`, `backtick sleep`)
spuriously OK, the other 8 spuriously FAIL. A test reporting PASS while never running its target
is worse than no test — it buys false confidence rather than none. **Fixed** by the same one-line
`HOOK`-path update `test_block_non_canonical_edit.py` got on its own retirement: pointed at
`block_chained_sleep.py.disabled` (`python3 <path>` runs a file regardless of extension), then run
for real. Result: 13/13 pass, unchanged from every case's original expectation — the retired
hook's own logic was never wrong, only this test's path was stale, so no case's expected exit code
needed to change and the hook itself was not touched.
```

## Salvage from dev/proxy/probe_bg_task_live.py

COMMENT L13:
```
# add src/ to path so menubar.proc_cache is importable without 'from src.' prefix
```

COMMENT L15:
```
# noqa: E402
```

COMMENT L18:
```
# synthetic session count to measure per-tick cost at scale
```

COMMENT L23:
```
# Print ONE measurement of a real task and exit — safe to call repeatedly from an external
```

COMMENT L24:
```
# shell until-loop (`until <check>; do sleep N; done`) when the target task lives in the SAME
```

COMMENT L25:
```
# CC session issuing the checks. See module docstring gotcha: never run this script itself as a
```

COMMENT L26:
```
# long-lived backgrounded/auto-backgrounded process against its own session.
```

COMMENT L36:
```
# Full workflow: poll a real task's output file, run a synthetic writer round-trip, bench
```

COMMENT L37:
```
# per-tick cost, write report. ONLY safe when the target session is NOT the session this script
```

COMMENT L38:
```
# itself runs in (e.g. driven from a separate terminal/process) — otherwise use snapshot_workflow
```

COMMENT L39:
```
# from an external polling loop instead (see module docstring gotcha).
```

COMMENT L50:
```
# Old predicate: any *.output file in tasks_dir is exactly 0 bytes
```

COMMENT L60:
```
# New predicate: force a fresh lsof scan (bypass TTL) then read the real _has_active_bg
```

COMMENT L67:
```
# Poll the real rag-cli index task's output file every poll_secs, up to max_polls or completion
```

COMMENT L82:
```
# One more sample after the file is non-empty, then keep polling until the handle closes
```

COMMENT L95:
```
# Control case: a session dir with no tasks/ activity at all -> both predicates must be False
```

COMMENT L104:
```
# Synthetic writer loop: real subprocess, real open fd, >0 bytes, still running -> new=True, old=False
```

COMMENT L115:
```
# matches the issue's synthetic-loop measurement point (>0 bytes, still running)
```

COMMENT L134:
```
# Measure per-tick cost: cache-hit tick (N sessions, no lsof call) vs cache-refresh tick (1 lsof call)
```

COMMENT L139:
```
# Refresh tick: force the TTL to expire, time the real lsof call
```

COMMENT L145:
```
# Cache-hit tick: TTL fresh, time N _has_active_bg lookups against the warm snapshot
```

COMMENT L159:
```
# Render the collected measurements as a markdown report under md/
```

## Salvage from dev/proxy/probe_replay_cli_chained.py

COMMENT L13:
```
# The seven hooks block_cli_chained.py replaces — every decision="block" fire of these,
```

COMMENT L14:
```
# from the MAIN checkout's log (not the worktree's — the worktree has no fire history of
```

COMMENT L15:
```
# its own), gets replayed through the new hook.
```

COMMENT L29:
```
# Replay every historical block fire of the 7 old hooks through the new block_cli_chained.py;
```

COMMENT L30:
```
# print per-hook blocks-kept/now-passing counts, write the passing commands to a report.
```

COMMENT L54:
```
# Resolve the MAIN checkout's hook_firing.jsonl — this worktree's own log has no fire
```

COMMENT L55:
```
# history; strip the `.claude/worktrees/<name>` suffix off this script's own path to
```

COMMENT L56:
```
# find the main repo root, mirroring worker-cli's resolve_project_path convention.
```

COMMENT L66:
```
# Read every decision="block" record whose hook is one of `old_hooks`; return list of
```

COMMENT L67:
```
# (hook_name, command) tuples in file order. Fails loudly (this is a probe, not a
```

COMMENT L68:
```
# fail-open hook) if the log is missing or malformed.
```

COMMENT L81:
```
# Feed one historical command through the new hook via a real subprocess call with a
```

COMMENT L82:
```
# real PreToolUse JSON payload; return its exit code (2 = still blocks, 0 = now passes).
```

COMMENT L92:
```
# Write the per-old-hook block/pass counts and the full text of every now-passing
```

COMMENT L93:
```
# command (for manual review — these are the previously-blocked-but-non-truncating
```

COMMENT L94:
```
# chains the milestone measured) to the markdown report.
```

## Salvage from dev/proxy/test_bg_task_detection.py

COMMENT L10:
```
# add src/ to path so menubar.proc_cache is importable without 'from src.' prefix
```

COMMENT L12:
```
# noqa: E402
```

COMMENT L19:
```
# Run all cases and print results; exit 1 if any fail
```

COMMENT L40:
```
# Unit: open path present under the exact tasks dir -> True
```

COMMENT L49:
```
# Unit: no open path for this session -> False
```

COMMENT L58:
```
# Unit: prefix-collision guard — 'sess1' must not match a path under 'sess12'
```

COMMENT L67:
```
# Integration: real subprocess holds a real file handle open under a scratch tasks dir;
```

COMMENT L68:
```
# real lsof scan (bypassing TTL) must detect it, then detect its absence after the writer exits.
```

COMMENT L75:
```
# own process group -> killpg reaches the loop's sleep children too
```

COMMENT L77:
```
# let the writer open its fd
```

COMMENT L78:
```
# force a fresh lsof scan, bypass TTL
```

COMMENT L81:
```
# kill bash + any orphaned sleep child holding the fd
```

COMMENT L95:
```
# Fail-open: lsof subprocess raising must not crash the refresh or the predicate
```

COMMENT L107:
```
# must not raise
```

COMMENT L114:
```
# TTL: second refresh call inside the window must not re-invoke lsof
```

COMMENT L128:
```
# well inside _PROC_REFRESH_INTERVAL
```

## Salvage from dev/proxy/test_block_broad_find.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L11:
```
# --- BLOCK: broad roots, no maxdepth, no head ---
```

COMMENT L29:
```
# --- PASS: head-bounded ---
```

COMMENT L37:
```
# --- PASS: -maxdepth present ---
```

COMMENT L43:
```
# --- PASS: non-broad roots ---
```

COMMENT L51:
```
# --- PASS: quoted/heredoc — no shell-active find ---
```

COMMENT L57:
```
# --- PASS: word-boundary — must not match substrings ---
```

COMMENT L84:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_broad_grep.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- true positives: must block ---
```

COMMENT L21:
```
# --- head-bounded exemption: must pass ---
```

COMMENT L32:
```
# --- existing exemptions: must pass ---
```

COMMENT L69:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_chained_sleep.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- canonical / allow cases ---
```

COMMENT L14:
```
# --- real block cases ---
```

COMMENT L18:
```
# --- heredoc body stripped (PASS) ---
```

COMMENT L21:
```
# --- quoted strings stripped (PASS) ---
```

COMMENT L25:
```
# --- command substitutions kept shell-active (BLOCK) ---
```

COMMENT L52:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_cli_chained.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L11:
```
# --- rule 1: pipe after a known-CLI segment (any of the 8 CLIs, any subcommand) ---
```

COMMENT L29:
```
# --- rule 2: redirect on a PROTECTED subcommand ---
```

COMMENT L61:
```
# --- rule 3: same-call readback of a CLI's own redirected file ---
```

COMMENT L73:
```
# --- interpreter-path bypass (2026-09-06): the wrapper name isn't the only way in;
```

COMMENT L74:
```
# `cd <project-dir> && ./venv/bin/python cli.py <sub>` never matched `_KNOWN_CLI_RE`
```

COMMENT L75:
```
# (which anchors on the WRAPPER name), so a protected subcommand escaped every rule
```

COMMENT L76:
```
# by taking this path — the real incident: a main agent ran the first case 3 times ---
```

COMMENT L98:
```
# --- allowed: chaining with ; or && is fine, for any CLI, with any other command ---
```

COMMENT L118:
```
# --- cwd-resolved interpreter form (measured bypass, 14/306 interpreter calls in real
```

COMMENT L119:
```
# transcripts carry no directory name while cwd IS a known CLI directory; 2 of those 14
```

COMMENT L120:
```
# were real bypasses of this hook's own rules) ---
```

COMMENT L166:
```
# Run hook with given command string wrapped in a valid PreToolUse payload; return exit code
```

COMMENT L177:
```
# Run hook with raw bytes on stdin (used for the malformed-payload fail-open case); return exit code
```

## Salvage from dev/proxy/test_block_dangerous_kill.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- true positives: must block ---
```

COMMENT L21:
```
# --- false positive fixes: must pass ---
```

COMMENT L30:
```
# --- safe patterns: must pass ---
```

COMMENT L43:
```
# --- allowlist: must pass ---
```

COMMENT L48:
```
# --- allowlist conservative: non-allowlisted still blocks ---
```

COMMENT L75:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_gh_cli_local_path.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- true positives: must block ---
```

COMMENT L21:
```
# --- allowed: must pass ---
```

COMMENT L30:
```
# --- other gh-cli commands and non-gh-cli commands: untouched ---
```

COMMENT L39:
```
# --- shell-strip: patterns inside quoted/heredoc regions must pass ---
```

COMMENT L68:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_git_destructive.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L11:
```
# --- FP regression: multi-line commands with git push + later [ -f ... ] must NOT block ---
```

COMMENT L17:
```
# --- BLOCK: genuine force-push variants ---
```

COMMENT L29:
```
# --- BLOCK: git commit --amend ---
```

COMMENT L35:
```
# --- BLOCK: --no-verify ---
```

COMMENT L41:
```
# --- BLOCK: --allow-empty ---
```

COMMENT L45:
```
# --- BLOCK: git config write variants ---
```

COMMENT L51:
```
# --- ALLOW: safe git ops ---
```

COMMENT L65:
```
# --- ALLOW: force-push phrase inside quoted commit message ---
```

COMMENT L92:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_manual_worker_cleanup.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- BLOCK: tmux kill-session on worker- target ---
```

COMMENT L19:
```
# --- BLOCK: git worktree remove on .claude/worktrees/ ---
```

COMMENT L28:
```
# --- ALLOW: recommended path ---
```

COMMENT L31:
```
# --- ALLOW: tmux non-worker sessions ---
```

COMMENT L38:
```
# --- ALLOW: git worktree non-.claude paths ---
```

COMMENT L45:
```
# --- ALLOW: git branch -D excluded ---
```

COMMENT L48:
```
# --- ALLOW: patterns in quoted strings (blanked by _strip_non_shell_active) ---
```

COMMENT L53:
```
# --- ALLOW: separator tightening (new cases) ---
```

COMMENT L58:
```
# --- ALLOW: shell comment residual (consistent with whole hook family) ---
```

COMMENT L85:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_non_canonical_edit.py

## Salvage from dev/proxy/test_block_po_read.py

COMMENT L32:
```
# (description, command, expected_exit_code)
```

COMMENT L33:
```
# --- true positives: must block ---
```

COMMENT L52:
```
# --- no-ops: must pass ---
```

COMMENT L65:
```
# --- real files, size boundary (M2: size-dependent block) ---
```

COMMENT L104:
```
# Run hook with given command string; return exit code
```

COMMENT L112:
```
# Run hook with raw stdin bytes; return exit code
```

## Salvage from dev/proxy/test_block_rag_cli_document_repeat.py

COMMENT L13:
```
# Run all rag-cli document-repeat tests; exit 1 if any fail
```

COMMENT L35:
```
# Run the hook via subprocess against a fresh state file; return exit code
```

COMMENT L52:
```
# A single --document call to a collection must pass — the genuine one-off case
```

COMMENT L72:
```
# A 2nd --document call to the SAME collection+subcommand within the window must block
```

COMMENT L100:
```
# Collection-wide calls (no --document) must always pass, any number of times,
```

COMMENT L101:
```
# and must never contribute to the repeat counter
```

COMMENT L121:
```
# A different session's --document calls must not count toward another session's counter
```

COMMENT L151:
```
# rag-cli delete --document is covered by the same threshold as index
```

COMMENT L176:
```
# Malformed stdin must fail open (exit 0), never block
```

## Salvage from dev/proxy/test_block_rag_cli_index_isolated.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- must block: the observed failure (tail + echo + cd + index in one call) ---
```

COMMENT L26:
```
# --- must block: HOLE 1 — env-var prefix must not defeat the anchor ---
```

COMMENT L33:
```
# --- must block: HOLE 2 — standalone assignment line does not exempt a tail before it ---
```

COMMENT L36:
```
# --- must block: HOLE 3 — command substitution smuggles a second command in via an
```

COMMENT L37:
```
#     assignment value / argument / redirect target (_shell_strip keeps these shell-active) ---
```

COMMENT L54:
```
# --- must block: bare & smuggles a second command regardless of surrounding whitespace ---
```

COMMENT L59:
```
# --- must allow: bare index ---
```

COMMENT L62:
```
# --- must allow: index with redirect (not a separator) ---
```

COMMENT L65:
```
# --- must allow: leading cd before index ---
```

COMMENT L68:
```
# --- must allow: leading cd before index with redirect ---
```

COMMENT L71:
```
# --- must allow: env-var prefix on the index call itself ---
```

COMMENT L74:
```
# --- must allow: the real HOLE 2 command — assignment line, cd, env-prefixed index,
```

COMMENT L75:
```
#     backslash line-continuation before the redirect ---
```

COMMENT L84:
```
# --- must allow: quoted metacharacters that are NOT command substitution ---
```

COMMENT L91:
```
# --- out of scope: rag-cli without index ---
```

COMMENT L98:
```
# --- no rag-cli at all ---
```

COMMENT L101:
```
# --- shell-strip: rag-cli index inside single-quoted string must be blanked ---
```

COMMENT L104:
```
# --- shell-strip: rag-cli index inside heredoc body must be blanked ---
```

COMMENT L131:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_rag_corpus_read.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- must block: raw-read commands over the corpus tree ---
```

COMMENT L36:
```
# --- glob dodge: renamed checkout/worktree still matches rag-* ---
```

COMMENT L41:
```
# --- must allow: mutations and file management stay sanctioned ---
```

COMMENT L50:
```
# --- must allow: no corpus path involved ---
```

COMMENT L55:
```
# --- must allow: the sanctioned forms themselves ---
```

COMMENT L60:
```
# --- false-positive avoidance ---
```

COMMENT L65:
```
# --- known text-only-matching limitation: a relative path with no rag-* prefix visible in
```

COMMENT L66:
```
# the command text is out of scope (same limitation the sibling rag-cli isolation hooks have —
```

COMMENT L67:
```
# none of them resolve paths against cwd) ---
```

COMMENT L109:
```
# The allowed-form wording the block message must carry — see task requirement: a rejection
```

COMMENT L110:
```
# that only forbids invites workarounds (process-docs/tool_use_safety/
```

COMMENT L111:
```
# 2026-08-28_rag_cli_path_indirection_bypass.md)
```

COMMENT L120:
```
# Run hook with given command string; return exit code
```

COMMENT L125:
```
# Run hook with given command string; return (exit_code, stderr_text)
```

COMMENT L133:
```
# Build the PreToolUse JSON payload for a Bash command
```

COMMENT L141:
```
# Run hook with raw bytes on stdin (used for the malformed-payload fail-open case); return exit code
```

## Salvage from dev/proxy/test_block_rag_docs_layer.py

COMMENT L9:
```
# (description, command, expected_exit_code)
```

COMMENT L10:
```
# --- must block: *-docs search with no layer filter ---
```

COMMENT L17:
```
# --- must allow: *-docs search with process-docs filter ---
```

COMMENT L26:
```
# --- must allow: non-docs collection unaffected ---
```

COMMENT L29:
```
# --- must allow: non search subcommand unaffected ---
```

COMMENT L32:
```
# --- must allow: no rag-cli at all ---
```

COMMENT L35:
```
# --- shell-strip: rag-cli inside single-quoted string must be blanked ---
```

COMMENT L62:
```
# Run hook with given command string; return exit code
```

## Salvage from dev/proxy/test_block_read_worktree.py

COMMENT L9:
```
# Derive the current worktree root (tests run from inside the hook-heredoc worktree)
```

COMMENT L11:
```
# e.g. /path/.../worktrees/hook-heredoc
```

COMMENT L14:
```
# (description, file_path, expected_exit_code)
```

COMMENT L15:
```
# --- foreign worktree reads → BLOCK ---
```

COMMENT L18:
```
# --- main-project path (no worktrees fragment) → PASS ---
```

COMMENT L21:
```
# --- own worktree read → PASS (only testable when running inside a worktree) ---
```

COMMENT L24:
```
# --- path without worktree fragment → PASS ---
```

COMMENT L26:
```
# --- empty / None field → PASS (fail-open) ---
```

COMMENT L37:
```
# missing file_path field — send payload without it
```

COMMENT L58:
```
# Run hook with given file_path string; return exit code
```

COMMENT L63:
```
# Run hook with raw JSON payload; return exit code
```

## Salvage from dev/proxy/test_block_unauthorized_background.py

COMMENT L8:
```
# (description, command, run_in_background, expected_rewritten_bg)
```

COMMENT L9:
```
# expected_rewritten_bg:
```

COMMENT L10:
```
#   None  = hook emits no output (pass-through, command stays background or already foreground)
```

COMMENT L11:
```
#   False = hook emits rewrite flipping run_in_background to false (foreground-forced)
```

COMMENT L13:
```
# --- ALLOW: sleep-only forms — must NOT be foreground-forced (order-independence vs rewrite hook) ---
```

COMMENT L21:
```
# --- ALLOW: worker-cli wait forms — canonical pull-based wake-up command ---
```

COMMENT L31:
```
# --- FORCE: former pipeline whitelists — no whitelist, must be foreground-forced ---
```

COMMENT L37:
```
# --- FORCE: genuine non-canonical background commands — must be foreground-forced ---
```

COMMENT L47:
```
# --- PASS: already foreground — hook is no-op ---
```

COMMENT L75:
```
# Run hook; return run_in_background value from rewrite output, or None if hook emits no output
```

## Salvage from dev/proxy/test_block_worker_kill_while_working.py

DOCSTRING L2-8:
```

Smoke test for block_worker_kill_while_working.py.
Uses real _strip_non_shell_active (called inside decide()) and a stub status_fn.
No real workers required — all status responses are injected via the stub.

Usage: python3 dev/hook_smoke/test_block_worker_kill_while_working.py

```

COMMENT L16:
```
# Stub builder: name_to_status maps name → return value.
```

COMMENT L17:
```
# Raises RuntimeError for the special sentinel name 'raises'.
```

COMMENT L27:
```
# (label, command, stub_map, expect_block)
```

## Salvage from dev/proxy/test_block_worker_send_while_working.py

DOCSTRING L2-10:
```

Smoke test for block_worker_send_while_working.py.
Uses real _strip_non_shell_active (called inside decide()) and a stub status_fn for the
pure-decision cases, plus one subprocess invocation of the real script for the malformed-stdin
fail-open case (decide() never touches stdin, so that path needs the actual entrypoint).
No real workers required — all status responses are injected via the stub.

Usage: python3 dev/hook_smoke/test_block_worker_send_while_working.py

```

COMMENT L22:
```
# Stub builder: name_to_status maps name → return value.
```

COMMENT L23:
```
# Raises RuntimeError for the special sentinel name 'raises'.
```

COMMENT L32:
```
# Worker statuses are exactly working / idle / dead — nothing else.
```

COMMENT L34:
```
# (label, command, stub_map, expect_block)
```

COMMENT L109:
```
# Malformed stdin fail-open — decide() never touches stdin, so this exercises the real entrypoint.
```

COMMENT L121:
```
# A working worker via the real entrypoint, stub-free but status_fn unreachable in this sandbox
```

COMMENT L122:
```
# (no real worker-cli / worker named 'foo') — must still exit 0, proving the fail-open path holds
```

COMMENT L123:
```
# when _live_worker_status cannot resolve a real status at all.
```

## Salvage from dev/proxy/test_fire_log.py

COMMENT L15:
```
# Run all fire-log tests; exit 1 if any fail
```

COMMENT L35:
```
# Run a hook via subprocess with a given log path env var; return (exit_code, log_line_or_None)
```

COMMENT L55:
```
# Block fire test: block_noop_edit with old_string == new_string → decision=block
```

COMMENT L96:
```
# Rewrite fire test: rewrite_chained_sleep with a trivial-predecessor sleep → decision=rewrite, both fields present
```

COMMENT L133:
```
# Env-var override test: log written to custom path, NOT to canonical path
```

COMMENT L140:
```
# Use custom path via env var; canonical path is a different temp path (should NOT be written)
```

COMMENT L169:
```
# Tool-error writer unit test: call append_tool_errors with a synthetic error dict, verify JSONL output
```

COMMENT L176:
```
# Import the writer from the src package
```

## Salvage from dev/proxy/test_header_capture.py

COMMENT L7:
```
# noqa: E402
```

COMMENT L11:
```
# Build a minimal mock of mitmproxy headers (case-insensitive dict-like via SimpleNamespace with items())
```

COMMENT L24:
```
# Build a minimal mock flow for beta-flags extraction (request side)
```

COMMENT L30:
```
# ── beta-flags extraction tests ──────────────────────────────────────────────
```

DOCSTRING L33:
```
Mirror the extraction logic in request() verbatim.
```

COMMENT L63:
```
# comma with no content between (malformed header edge case)
```

COMMENT L68:
```
# ── _filter_response_headers tests ───────────────────────────────────────────
```

COMMENT L117:
```
# mitmproxy may surface headers in original wire case
```

COMMENT L127:
```
# original mixed-case keys must NOT appear
```

COMMENT L150:
```
# ── runner ────────────────────────────────────────────────────────────────────
```

## Salvage from dev/proxy/test_hook_setup_main_branch_gate.py

DOCSTRING L2-9:
```

Smoke test for the two-condition install gate in hook_setup.py (decide_entries()).
A script installs only if BOTH: committed on 'main' (git_query_fn) AND present in the current
working tree at the path that will be registered (tree_query_fn). Uses stub query functions —
no real git calls, no real filesystem checks, no real settings.json writes.

Usage: python3 dev/hook_smoke/test_hook_setup_main_branch_gate.py

```

COMMENT L17:
```
# Stub builders: maps map script filename -> verdict. Missing key -> default (present), so cases
```

COMMENT L18:
```
# only need to name the interesting scripts.
```

COMMENT L31:
```
# (label, hook_scripts, git_verdict_map, tree_present_map, expect_installed, expect_skipped_scripts)
```

COMMENT L104:
```
# multi-matcher case: confirm all 3 matcher entries for 'multi.py' produced a skip reason each
```

COMMENT L118:
```
# reason text distinguishes the two conditions — a maintainer needs to know which one failed
```

## Salvage from dev/proxy/test_log_janitor.py

COMMENT L8:
```
# add src/panes/ to path so log_janitor is importable without 'from src.' prefix
```

COMMENT L10:
```
# noqa: E402
```

COMMENT L17:
```
# Case payloads — written as JSON lines, compared after cleanup
```

COMMENT L21:
```
# Naive ts: 9 days old but no timezone suffix → fromisoformat returns naive datetime →
```

COMMENT L22:
```
# comparison with UTC-aware cutoff raises TypeError → keep (fail-safe)
```

COMMENT L25:
```
# (description, input_lines, expected_kept_lines)
```

COMMENT L36:
```
# Run all cases and print results; exit 1 if any fail
```

COMMENT L58:
```
# Write input_lines to a temp file, run cleanup_old_jsonl, return (kept_lines, ok)
```

## Salvage from dev/proxy/test_rewrite_background_sleep.py

COMMENT L8:
```
# Absolute path — required so the subprocess's cwd (deliberately forced per-case below, incl. a
```

COMMENT L9:
```
# worktree-shaped cwd) never affects where the hook script itself is found.
```

COMMENT L13:
```
# (description, command, run_in_background, expected_rewrite_or_None, cwd_kind)
```

COMMENT L14:
```
# expected_rewrite_or_None: None = no rewrite expected (hook should emit nothing and exit 0)
```

COMMENT L15:
```
# cwd_kind: "orchestrator" = plain non-worktree cwd (no .claude/worktrees/ fragment anywhere in
```

COMMENT L16:
```
#           it — required so this suite's own on-disk worktree path can never leak in and mask
```

COMMENT L17:
```
#           a case, see _ORCHESTRATOR_CWD below); "worktree" = cwd inside a .claude/worktrees/
```

COMMENT L18:
```
#           path, proving the 2026-08 orchestrator-only guard actually fires.
```

COMMENT L20:
```
# --- positive (orchestrator cwd): any sleep-only background command → rewrite to worker-cli wait ---
```

COMMENT L63:
```
# --- negative A: foreground (run_in_background=false) → no rewrite ---
```

COMMENT L71:
```
# --- negative B: already the canonical worker-cli wait — no rewrite (not a sleep pattern) ---
```

COMMENT L86:
```
# --- negative C: non-canonical command (not sleep N && echo done form) → no rewrite ---
```

COMMENT L94:
```
# --- negative D: sleep but wrong chain target (not echo done) → no rewrite ---
```

COMMENT L102:
```
# --- negative E (2026-08 live incident fix): worktree cwd → NEVER rewrite, worker sleeps stay sleeps ---
```

COMMENT L129:
```
# Run all cases and print results; exit 1 if any fail
```

COMMENT L132:
```
# Plain tempdir — guaranteed no ".claude/worktrees/" fragment anywhere in the path.
```

COMMENT L160:
```
# Run hook with given command, run_in_background flag, and explicit cwd (never inherited — see
```

COMMENT L161:
```
# module docstring on why); return (exit_code, rewritten_command_or_None)
```

## Salvage from dev/proxy/test_rewrite_chained_sleep.py

COMMENT L8:
```
# (description, command, expected_rewrite_or_None)
```

COMMENT L9:
```
# None = no rewrite expected (hook should emit nothing and exit 0)
```

COMMENT L11:
```
# --- positive: trivial-sync echo before sleep → strip ---
```

COMMENT L27:
```
# --- negative: load-bearing cmd_before → no rewrite ---
```

COMMENT L38:
```
# --- negative: sleep inside loop body → no rewrite ---
```

COMMENT L44:
```
# --- negative: sleep-first (canonical or intent) → no rewrite ---
```

COMMENT L55:
```
# --- positive: new single-token _TRIVIAL entries ---
```

COMMENT L91:
```
# --- positive: new _TRIVIAL_PAIRS (git) ---
```

COMMENT L112:
```
# --- positive: new _TRIVIAL_PAIRS (rag-cli, worker-cli) ---
```

COMMENT L133:
```
# --- negative: critical no-strip — load-bearing git subcommands ---
```

COMMENT L144:
```
# --- negative: critical no-strip — load-bearing rag-cli/worker-cli subcommands ---
```

COMMENT L165:
```
# --- negative: critical no-strip — background & is not a chain op ---
```

COMMENT L171:
```
# --- negative: critical no-strip — git -C flag between cmd and subcommand ---
```

COMMENT L182:
```
# Run all cases and print results; exit 1 if any fail
```

COMMENT L207:
```
# Run hook with given command; return (exit_code, rewritten_command_or_None)
```

## Salvage from dev/proxy/verify_block_non_canonical_edit_corpus.py

## Salvage from dev/proxy/verify_block_non_canonical_edit_report.py

