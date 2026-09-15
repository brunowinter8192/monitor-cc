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

**Purpose:** 13-case smoke for the disabled `block_chained_sleep.py` (`.disabled` on disk),
preserved for regression reference.
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

### verify_block_non_canonical_edit_corpus.py (115 LOC)

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
**Writes:** `md/block_non_canonical_edit_corpus_report.md` — a historical snapshot from while the
hook was live, not regenerated.
**Called by:** none — cannot currently run; see Purpose.
**Calls out:** `src.hooks.block_non_canonical_edit` (`_decide`) — target retired.

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
is a defect in `block_non_canonical_edit.py` itself — see its own Gotcha in `src/hooks/DOCS.md`.

**`test_block_chained_sleep.py` reports PASS without ever executing its target — a real defect,
found while retiring `block_non_canonical_edit.py` and left as-is here since fixing it is separate
work.** Its `HOOK` constant still points at `src/hooks/block_chained_sleep.py`, the path from
before that hook was disabled; the file has not existed there since the rename to
`block_chained_sleep.py.disabled`. `subprocess.run(["python3", HOOK], ...)` against a nonexistent
path does not fail the way a broken hook invocation should — `python3` itself prints `can't open
file ... No such file or directory` and exits with status 2, and 2 is also this hook family's own
"block" exit code. The two codes collide by coincidence, not by any check this test performs. The
practical effect: every case in `CASES` that expects BLOCK (`exit=2`) reports OK, because
`python3`'s own file-not-found exit code happens to equal 2 regardless of what the (nonexistent)
hook would have decided; every case that expects PASS (`exit=0`) reports FAIL, because
`python3`'s file-not-found exit code is never 0. Running it now: 5 of the 13 cases are BLOCK-
expecting and show as spuriously OK (`chained before sleep`, `non-echo-done cont`, `real sleep
after quoted`, `cmd-subst sleep`, `backtick sleep`); the other 8 are PASS-expecting and show as
FAIL (`canonical pass`, `canonical float pass`, `no sleep pass`, `heredoc quoted body PASS`,
`heredoc unquoted body PASS`, `single-quoted sleep PASS`, `double-quoted sleep PASS`, `ANSI-C
quote sleep PASS`) — meaning the script's own summary line reads "FAILED: 8 case(s)", which is
itself somewhat self-revealing, but a prior pass at the actual per-case output before reading past
the summary would report "OK" on 5 cases that never touched real hook logic at all. A test
reporting PASS while never running its target is worse than no test — it buys false confidence
rather than none. Not fixed here
because retiring a *different* hook is not licence to fix an unrelated, pre-existing one; if this
is ever revived, the fix is the same one-line `HOOK` path update `test_block_non_canonical_edit.py`
got on its own retirement, documented above.
