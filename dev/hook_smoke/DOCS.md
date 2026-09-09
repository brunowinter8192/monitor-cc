# dev/hook_smoke/

## Role

Smoke-test suite for `src/hooks/` — one test script per hook, verifying positive (blocks/rewrites)
and negative (pass-through) cases via subprocess. Each script invokes the hook with a JSON payload
on stdin and checks exit code + stdout/stderr.

Touch this suite when: adding a new hook (add matching test script); changing hook logic (extend
or fix existing test script); verifying after merges that no hook regressed.

## Modules

### test_block_chained_sleep.py (67 LOC)

**Purpose:** 13-case smoke for the now-disabled `block_chained_sleep.py`. Preserved for regression
reference — the file still exists as `block_chained_sleep.py.disabled`.

**Usage:**
```bash
# From project root — references src/hooks/block_chained_sleep.py (disabled, skip if not restored)
python3 dev/hook_smoke/test_block_chained_sleep.py
```

---

### test_block_broad_grep.py (84 LOC)

**Purpose:** 16-case smoke for `block_broad_grep.py`. Verifies 5 blocked cases (broad recursive, piped to non-head), 5 head-bounded exemptions (piped to `head`/`head -N`, with redirect before head, further pipe after head), and 6 existing-exemption passes (--include, file-targeted, non-recursive, git grep, quoted, heredoc).

**Usage:**
```bash
python3 dev/hook_smoke/test_block_broad_grep.py
```

---

### test_block_gh_cli_local_path.py (83 LOC)

**Purpose:** 15-case smoke for `block_gh_cli_local_path.py` (2026-08-07). Verifies 5 blocked cases
(`get_file_content` with `/Users/...` or `~/...` path, `download_files` with an absolute
positional or a `~/...` path among several, local path preceded by a `--limit` flag), 4 pass cases
(repo-relative path, **the `--dest` false-positive trap in both flag positions** — before and
after the repo-path positionals, `--metadata-only` flag present), 4 untouched-command cases
(`get_repo_tree`/`index_issues`/`repo_freshness`/non-gh-cli), and 2 shell-strip passes (pattern
inside single-quotes, pattern inside heredoc body).

**Usage:**
```bash
python3 dev/hook_smoke/test_block_gh_cli_local_path.py
```

**Report:** `md/block_gh_cli_local_path_smoke_report.md`.

---

### test_block_rag_cli_index_isolated.py (146 LOC)

**Purpose:** 37-case smoke for `block_rag_cli_index_isolated.py`. Verifies 20 blocked cases (the observed poll-then-index incident: `tail` + `echo` + `cd` + index across newlines; noise before/after index via `&&`/`;`; a second `rag-cli delete` command alongside index; index piped to `tee`; the 2026-08-01 holes — env-prefixed index preceded by `tail`, env-prefixed index followed by `echo`, multi-assignment-prefixed index piped to `tee`, standalone assignment line + `tail` + `cd` + env-prefixed index; the 2026-08-02 holes — command/backtick substitution in an assignment value, substitution in the `--collection` argument, process substitution on a redirect target and as input, arithmetic expansion in an assignment, substitution nested inside a double-quoted `cd` target, backtick in a redirect filename, bare `&` smuggling with and without surrounding whitespace) and 17 allow cases (bare index, index with redirect, cd-before-index with/without redirect, env-prefixed bare index, the real HOLE-2 command verbatim — assignment line + cd + env-prefixed index + backslash line-continuation before the redirect, assignment line + cd + bare index + redirect, bare index with a backslash-continued redirect, quoted semicolon in an assignment value, plain `$VAR` expansion in a `cd` target, `&>` redirect not mistaken for the bare-`&` separator, three out-of-scope rag-cli subcommands (`search_hybrid`/`list_documents`/`delete`), no rag-cli at all, index inside single-quotes, index inside heredoc body).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_block_rag_cli_index_isolated.py
```

**Expected output:** `All 37 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_block_dangerous_kill.py (90 LOC)

**Purpose:** 18-case smoke for `block_dangerous_kill.py` — pkill -f patterns, pipe-kill chains, heredoc/quote exemptions, and allowlist cases.

**Usage:**
```bash
python3 dev/hook_smoke/test_block_dangerous_kill.py
```

---

### test_block_git_destructive.py (107 LOC)

**Purpose:** 21-case smoke for `block_git_destructive.py`. Verifies 2 FP-regression ALLOW cases (minimal: `git push -u origin main\n[ -f .env ]`; actual recap command with push + echo + `[ -f .rag-docs.json ]` across lines), 13 BLOCK cases (force-push `--force`/`--force-with-lease`/`-f`, push with `-C` flag, `--amend`/`--amend --no-edit`, `--no-verify` on commit and push, `--allow-empty`, `git config` write and write-with-`-C`), and 6 ALLOW cases (plain push, `push -u`, normal commit, `config --list`/`--get`/`--show-origin`, force-push phrase inside quoted message).

**Usage (from project root):**
```bash
./venv/bin/python dev/hook_smoke/test_block_git_destructive.py
```

**Expected output:** `All 21 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_block_read_worktree.py (74 LOC)

**Purpose:** Smoke test for `block_read_worktree.py` — foreign worktree reads blocked, own-worktree
reads allowed.

**Usage:**
```bash
python3 dev/hook_smoke/test_block_read_worktree.py
```

---

### test_log_janitor.py (75 LOC)

**Purpose:** 4-case smoke for `src/panes/log_janitor.cleanup_old_jsonl`. Verifies: old record >7 days dropped,
recent record <7 days kept, empty `ts` kept (fail-safe), naive-ts without TZ kept (TypeError on
aware/naive comparison → fail-safe keep).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_log_janitor.py
```

**Expected output:** `All 4 tests passed.` (exit 0). Uses `sys.path.insert` on `src/panes/` + `from log_janitor import` to avoid the `from src.` import restriction.

---

### test_rewrite_background_sleep.py (184 LOC, Milestone 2 rewrite target change 2026-08; orchestrator-only guard cases 2026-08 Milestone 3b)

**Purpose:** 14-case smoke for `rewrite_background_sleep.py`. Verifies 6 positive-rewrite cases
(`sleep 300`, `sleep 5`, `sleep 1200`, the OLD canonical `sleep 3300 && echo done` (now also a stale
habit), bare `sleep 300` alone, `sleep 45 && echo "bg-ack-probe done"` custom echo — all rewritten to
the new canonical `worker-cli wait`), 5 negative no-op cases (foreground flag; `worker-cli wait`
bare already canonical; `worker-cli wait /path --timeout 600` already canonical; non-canonical
non-sleep command; wrong chain target `&& rag-cli`), and 3 negative worktree-cwd cases (bare
`sleep 300`, old-canonical `sleep 3300 && echo done`, foreground sleep — all still no-op from a
`.claude/worktrees/`-shaped cwd, proving the 2026-08 orchestrator-only guard fires). Every case's
subprocess `cwd` is set EXPLICITLY (`subprocess.run(..., cwd=...)`) — a plain `tempfile.
TemporaryDirectory()` for the 11 non-worktree cases, a `.../.claude/worktrees/fake-worker` path for
the 3 worktree cases — never inherited: this suite's own on-disk path already contains the
`.claude/worktrees/` fragment, so an inherited cwd would silently flip every non-worktree case to
the wrong expectation when the suite is run from inside a worktree (as it normally is, in dev).

**Usage (from project root, or any cwd — HOOK is resolved via an absolute path):**
```bash
python3 dev/hook_smoke/test_rewrite_background_sleep.py
```

**Expected output:** `All 14 tests passed.` (exit 0).

---

### test_block_unauthorized_background.py (96 LOC, Milestone 2 worker-cli wait exemption 2026-08)

**Purpose:** 14-case smoke for `block_unauthorized_background.py`. Verifies 3 sleep-only ALLOW cases (no foreground-force): `sleep N && echo done`, bare `sleep N`, custom echo `sleep 45 && echo "bg-ack-probe done"` (fire-log actual) — kept exempt for order-independence vs `rewrite_background_sleep.py`. Verifies 4 `worker-cli wait` ALLOW cases: bare, with `project_path`, with `--timeout`, with both. Verifies 6 FORCE cases (foreground-forced): `reddit-cli index_subreddits`, `workflow.py index-dir` (former whitelisted, now forced), `./venv/bin/python script.py`, `rag-cli update_docs .` (original triggering incident), `worker-cli wait && rag-cli index docs` (chained — tail-guard rejects it), `worker-cli waitfoo` (word-boundary rejects a non-`wait` token). Verifies 1 PASS case (already foreground → no output): `./venv/bin/python script.py` with `run_in_background=false`.

**Usage (from project root):**
```bash
./venv/bin/python dev/hook_smoke/test_block_unauthorized_background.py
```

**Expected output:** `All 14 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_chained_sleep.py (226 LOC)

**Purpose:** 8-case smoke for `rewrite_chained_sleep.py`. Verifies 3 positive-strip cases (`echo`
and `true` cmd_before → sleep stripped) and 5 negative no-op cases (load-bearing: `kill`, `launchctl`;
loop body; sleep-first; canonical timer).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_chained_sleep.py
```

**Expected output:** `All 8 tests passed.` (exit 0). HOOK path in the script is relative
(`src/hooks/rewrite_chained_sleep.py`) — must be run from project root.

---

### test_version_purge.sh (140 LOC)

**Purpose:** 8-assertion smoke for the version-aware dual-log purge (`_janitor_version_purge_jsonl_logs` + `_compute_proxy_hash` in `src/claude_proxy_start.sh`). Runs in a temp dir; never touches real `src/logs/`. Four cases: (a) version change purges stale (>60min) logs; (b) same version leaves stale files untouched; (c) fresh (<60min) logs survive a version-change purge; (d) absent marker triggers first-run cleanup and creates the marker. Mirrors the production functions inline — keep in sync with `src/claude_proxy_start.sh` when editing either.

**Usage (from project root):**
```bash
bash dev/hook_smoke/test_version_purge.sh
```

**Expected output:** `All 8 assertions passed.` (exit 0).

---

### test_header_capture.py (179 LOC)

**Purpose:** 13-case smoke for the proxy header-capture additions in `src/proxy/addon.py`. Tests two
independent surfaces: (1) beta-flags extraction logic (split/strip/drop-empty on `anthropic-beta`
header value); (2) `_filter_response_headers()` — exact-name and prefix-based filter with lowercase
normalization. Does NOT require a live mitmproxy process — uses minimal mock headers objects.

**Usage (from project root):**
```bash
./venv/bin/python dev/hook_smoke/test_header_capture.py
```

**Expected output:** `13/13 passed` (exit 0). Imports `_filter_response_headers` directly from
`src/proxy/addon` via `sys.path.insert` on `src/`.

---

### test_bg_task_detection.py (145 LOC)

**Purpose:** 6-case smoke for `src/menubar/proc_cache.py::_has_active_bg` (open-file-handle predicate, replacing the old 0-byte-file check). 3 unit cases via a monkeypatched `_bg_task_open_paths` snapshot (match, no-match, session-id prefix-collision boundary), 1 integration case (real subprocess holds a real file open under a scratch tasks dir, real `lsof` scan detects it while open and its absence after the writer is killed), 1 fail-open case (`lsof` raising leaves the prior snapshot in place, does not crash), 1 TTL-gate case (second refresh call inside `_PROC_REFRESH_INTERVAL` does not re-invoke `lsof`).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_bg_task_detection.py
```

**Expected output:** `All 6 tests passed.` (exit 0). Creates/removes a scratch dir under the real `_TASKS_BASE` (`/tmp/claude-<uid>/__test_bg_probe__/`) for the integration case only; cleaned up in a `finally` block.

---

### probe_bg_task_live.py (n/a — live measurement tool, not a smoke test)

**Purpose:** Live probe comparing the old 0-byte predicate against the new handle-based predicate against a REAL running background task (e.g. a `rag-cli index` run), a synthetic writer loop, and a no-background-task control session; also benchmarks the per-tick cost of the batched `lsof` cache (refresh-tick cost vs. N-session cache-hit-tick cost). `--snapshot` mode prints one JSON measurement and exits. `probe_bg_task_detection_workflow` (no `--snapshot`) runs the full poll-loop + synthetic-writer + cost-bench + report-write in one process. Not CI-safe (depends on a live external task being supplied) — kept for future re-verification if the predicate regresses. **Gotcha:** any Bash-tool-invoked check running INSIDE the same CC session it targets can itself become a transient open `*.output` handle in that session's tasks dir for the duration of the check (CC's own tracked-wrapper mechanism, not specific to this script) — a long-lived process built this way (the original `probe_bg_task_detection_workflow` loop, run via `run_in_background=true` against its own session) got stuck for 14 minutes waiting for `new=False`, which could never arrive while it was itself the open handle. Mitigations used: (1) drive repeated measurements via `--snapshot` from an external shell `until`-loop (each invocation is independent and short) rather than one long-lived Python loop; (2) for a "handle is now closed" claim, scope `lsof` to the SPECIFIC target file (`lsof <path>`), not the whole session directory, to avoid the self-entry noise entirely.

**Usage (from project root):**
```bash
# repeated snapshots, driven by an external loop (safe even when target == own session)
until [ -s <tasks_dir>/<task_id>.output ]; do sleep 5; done
python3 dev/hook_smoke/probe_bg_task_live.py --encoded-dir=<encoded_dir> --session-id=<session_id> --task-id=<task_id> --snapshot

# full workflow — only when the target session is NOT the one this script runs in
python3 dev/hook_smoke/probe_bg_task_live.py --encoded-dir=<encoded_dir> --session-id=<session_id> --task-id=<task_id> --poll-secs 4 --max-polls 100
```

---




### test_block_po_read.py (94 LOC)

**Purpose:** 16-case smoke for `block_po_read.py`. Verifies 9 blocked cases (`head`/`tail`/`grep`/`cat`/`sed`/`rg` each on a `~/.claude/.../tool-results/<id>.txt` persisted-output path, the piped `cat <path> | head -20` case, and the `split -l 400 <path> /tmp/x` / `dd if=<path> of=/tmp/x` partitioning-escape cases) and 7 no-op cases (reader on a normal file, reader on a `.log` file, reader on `/tmp/foo.txt` not under `.claude/`, reader on a `.claude/` path not ending `.txt`, redirect-write to a PO path, PO path only inside a quoted string, malformed-JSON stdin fail-open).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_block_po_read.py
```

**Expected output:** `All 14 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_block_cli_chained.py (168 LOC, new 2026-09 chain-hook unification; interpreter-path-bypass + stale-subcommand-name cases added 2026-09-06)

**Purpose:** 42-case smoke for `block_cli_chained.py` — the single hook that replaced `block_gh_cli_chained.py`/`block_rag_cli_chained.py`/`block_worker_cli_read_chained.py`/`block_websearch_scrape_chained.py`/`block_duallog_chained.py`/`block_linkedin_cli_isolated.py`/`block_penny_cli_chained.py`. Verifies all 3 rule classes across all 8 CLIs: rule 1 (pipe after any known-CLI segment, both a protected subcommand like `rag-cli search` and an unprotected one like `gh-cli get_file_content`/`worker-cli kill`, plus a for-loop with one piped iteration); rule 2 (redirect on a protected subcommand, one case per CLI incl. `duallog`/`linkedin`/`penny-cli`'s every-subcommand-protected shape, plus the bare-`2>`-does-not-count PASS and the unprotected-subcommand-redirect-stays-allowed PASS for `rag-cli index`/`worker-cli status`/`reddit-cli index_subreddits`); rule 3 (the milestone's canonical `rag-cli update_docs . > file; tail file` incident, readback via `head`/`cat`, a different-file PASS, a no-readback-at-all PASS). Also verifies the "no allowlist of chain segments" thesis directly: `mkdir -p x && rag-cli index`, `ls; gh-cli get_issue`, `echo test && penny-cli` (isolation retired), a `cd` guard, a cross-CLI chain with neither pipe nor redirect, a for-loop with no pipe/redirect, and the `duallog`/`worker-cli` path-substring false-positive cases all PASS — plus 1 malformed-stdin fail-open case.

**2026-09-06 additions (6 cases, two independent holes against `websearch`):** the `websearch` redirect-BLOCK case was corrected from the stale, non-existent subcommand name `scrape_url` to the real one, `scrape_url_chromium` (hole 1 — the table named a subcommand `cli.py` had already renamed away from), plus a `search_web` redirect PASS confirming the real unprotected subcommand still passes. Five interpreter-path-bypass cases (hole 2 — `_KNOWN_CLI_RE` matches only the 8 WRAPPER names, but 5 of those wrappers just `exec <dir>/venv/bin/python <dir>/cli.py "$@"`, so invoking that same `cli.py` through the interpreter directly matched nothing): the verbatim real incident (`cd <websearch-dir> && ./venv/bin/python cli.py scrape_url_chromium <url> > out 2>&1`, BLOCK), the same piped instead of redirected (BLOCK, proving rule 1 applies to the interpreter form too), a different tool via the interpreter form (`gh-cli`, `.venv` not `venv`, absolute paths, no `cd` at all) redirected (BLOCK, proving the mechanism generalizes), an unprotected subcommand (`search_web`) via the interpreter form redirected (PASS), and an unrelated project's own `cli.py` with none of the 5 known project-directory markers present (PASS, no false positive).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_block_cli_chained.py
```

**Expected output:** `All 42 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### probe_replay_cli_chained.py (n/a — replay probe, not a smoke test)

**Purpose:** Feeds every historical `decision="block"` fire of the 7 replaced hooks (`block_gh_cli_chained`, `block_rag_cli_chained`, `block_worker_cli_read_chained`, `block_websearch_scrape_chained`, `block_duallog_chained`, `block_linkedin_cli_isolated`, `block_penny_cli_chained`) from the MAIN checkout's `src/logs/hook_firing.jsonl` (never the worktree's own — a worktree has no fire history of its own) through the real `block_cli_chained.py` via subprocess, and reports per-old-hook counts of still-blocks vs now-passes. As of the 2026-09 rewrite: 115 historical block fires total, 49 still block, 66 now pass — every now-passing command's full text is written to the report for manual review (the milestone's own pre-implementation estimate was "about 83/32"; the measured split is more permissive than that estimate, traced case-by-case to the literal 3-rule text rather than a design gap — see the report).
**Reads:** `<main-repo-root>/src/logs/hook_firing.jsonl` (main checkout, resolved by stripping this script's own `.claude/worktrees/<name>` path suffix).
**Writes:** `md/block_cli_chained_replay_report.md` (per-hook counts table + full text of every now-passing command, grouped by old hook).

**Usage (from project root, in ANY worktree — the main-checkout log path is resolved automatically):**
```bash
python3 dev/hook_smoke/probe_replay_cli_chained.py
```

**Expected output:** per-hook block/pass counts to stdout, `~83/~32` order of magnitude per the milestone's estimate (measured 2026-09: 49/66 — see Purpose).

---

### test_block_rag_cli_document_repeat.py (193 LOC)

**Purpose:** 7-case smoke for `block_rag_cli_document_repeat.py`. Verifies: a single `--document` call passes (exit 0); a 2nd `--document` call to the same collection+subcommand within the window blocks (exit 0 then exit 2); collection-wide calls (no `--document`) always pass, 3x in a row; a different session's `--document` call does not count toward another session's counter (session A #1 = 0, session B #1 = 0, session A #2 = 2); `rag-cli delete --document` is covered by the same threshold as `index`; malformed stdin fails open (exit 0). Each case uses `MONITOR_CC_RAG_DOC_REPEAT_STATE` set to a fresh `tempfile` per case — no shared/leftover state across cases.

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_block_rag_cli_document_repeat.py
```

**Expected output:** `All rag-cli document-repeat tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_hook_setup_main_branch_gate.py (135 LOC)

**Purpose:** 10-case smoke for the two-condition install gate in `hook_setup.py` (`decide_entries()`). Stub `git_query_fn` (script → `True`/`False`/`None`, on-`main` presence) and stub `tree_query_fn` (script → bool, working-tree presence), both defaulting to present so cases only name the interesting scripts — no real git or filesystem calls. Verifies: all-present → all installed; one absent from `main` → skipped, rest installed; `git_query_fn` returns `None` (query unanswerable) → fail-safe skip; mixed present/absent/query-error set resolved independently; a multi-matcher script (e.g. `block_path_typo.py`-shaped) absent from `main` has EVERY entry skipped; **on `main` but missing from the working tree → skipped** (the mirror-image condition — a script can be genuinely committed on `main` yet absent from the CURRENT tree if a branch deleted/renamed it while its `_HOOK_SCRIPTS` entry stayed); on `main` AND in the tree → installed (mirror-image positive); missing from BOTH → skipped, reporting the main-branch reason (checked first); skip-reason text distinguishes "not committed on main" from "missing from the current working tree" so a maintainer knows which condition failed.

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_hook_setup_main_branch_gate.py
```

**Expected output:** `10/10 passed` (exit 0).
