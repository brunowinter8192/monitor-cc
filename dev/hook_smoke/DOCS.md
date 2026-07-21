# dev/hook_smoke/

## Role

Smoke-test suite for `src/hooks/` — one test script per hook, verifying positive (blocks/rewrites)
and negative (pass-through) cases via subprocess. Each script invokes the hook with a JSON payload
on stdin and checks exit code + stdout/stderr.

Touch this suite when: adding a new hook (add matching test script); changing hook logic (extend
or fix existing test script); verifying after merges that no hook regressed.

## Modules

### test_block_chained_sleep.py

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

### test_block_gh_cli_chained.py (89 LOC)

**Purpose:** 18-case smoke for `block_gh_cli_chained.py`. Verifies 9 blocked cases (each of the 7 search/research tools piped/chained with a non-search command), 6 pass cases (two search tools chained together, standalone with tool-native args, redirect to file), 2 exempt issue-command passes (`list_issues` / `get_issue` piped to grep/head), and 2 shell-strip passes (pattern inside single-quotes, pattern inside heredoc body).

**Usage:**
```bash
python3 dev/hook_smoke/test_block_gh_cli_chained.py
```

---

### test_block_rag_cli_chained.py (79 LOC)

**Purpose:** 11-case smoke for `block_rag_cli_chained.py`. Verifies 4 blocked cases (rag-cli followed via `;`, `&&`, `|` by tail/echo/grep/head), and 7 allow cases (redirect to file, file-guard before rag-cli, cd before rag-cli, two rag-cli calls chained, no rag-cli at all, rag-cli inside single-quotes, rag-cli inside heredoc body).

**Usage:**
```bash
python3 dev/hook_smoke/test_block_rag_cli_chained.py
```

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

### test_block_read_worktree.py

**Purpose:** Smoke test for `block_read_worktree.py` — foreign worktree reads blocked, own-worktree
reads allowed.

**Usage:**
```bash
python3 dev/hook_smoke/test_block_read_worktree.py
```

---

### test_log_janitor.py (75 LOC)

**Purpose:** 4-case smoke for `src/log_janitor.cleanup_old_jsonl`. Verifies: old record >7 days dropped,
recent record <7 days kept, empty `ts` kept (fail-safe), naive-ts without TZ kept (TypeError on
aware/naive comparison → fail-safe keep).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_log_janitor.py
```

**Expected output:** `All 4 tests passed.` (exit 0). Uses `sys.path.insert` on `src/` + `from log_janitor import` to avoid the `from src.` import restriction.

---

### test_rewrite_rag_cli_search_noise.py (140 LOC)

**Purpose:** 15-case smoke for `rewrite_rag_cli_search_noise.py`. Verifies 9 positive-strip cases (`| head`, `| tail`, `| grep`, `> redirect`, `2>&1`, `2>&1 | head`, `cd &&` chain, trailing `; bd list` chain, `|| echo fail` chain) and 6 negative no-op cases (bare search_hybrid, cd chain no noise, trailing chain no pipe, `list_collections | head` out of scope, `read_document | head` out of scope, search_hybrid inside quoted echo).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_rag_cli_search_noise.py
```

**Expected output:** `All 15 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_worker_cli_capture_noise.py (152 LOC)

**Purpose:** 17-case smoke for `rewrite_worker_cli_capture_noise.py`. Verifies 5 positive-strip cases (`| tail -40`, `| grep bar`, `| head -20 | sed`, `cd && ... | tail ; echo done` chain, `| wc -l`), 1 `--raw`-survives case (`--raw | tail -40` → `--raw` preserved), 3 redirect-preserved no-op cases (`> /tmp/x.txt`, `>> /tmp/x.txt`, `2>&1` all UNCHANGED), and 8 negative no-op cases (bare capture, `--raw` no-pipe, `response | tail` out-of-scope, wrong subcommands, chains without noise, quoted capture inside send-message).

**Critical assertions:** `> /tmp/x.txt` UNCHANGED (redirect preserved), `--raw | tail -40` → `--raw` (flag survives), `worker-cli send w "... capture foo | tail"` UNCHANGED (shell-strip blanks quoted region).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_worker_cli_capture_noise.py
```

**Expected output:** `All 17 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_gh_cli_read_noise.py (127 LOC)

**Purpose:** 12-case smoke for `rewrite_gh_cli_read_noise.py`. Verifies 5 positive-strip cases (`get_issue | tail -40`, `2>&1 | tail -40` with `2>&1` preserved, `list_issues | head`, `| tail ; echo done` chain, `cd && get_issue | tail` chain prefix), 2 redirect-preserved no-op cases (`> /tmp/x`, `>> /tmp/x` both UNCHANGED), 2 out-of-scope-command no-op cases (`create_issue | tail`, `update_issue | tail` — writes, not covered), 2 bare no-op cases (`get_issue`/`list_issues` with no pipe), and 1 quoted-string no-op case (`worker-cli send w "... gh-cli get_issue x | tail"` UNCHANGED).

**Critical assertions:** `> /tmp/x` UNCHANGED (redirect preserved), `create_issue`/`update_issue` UNCHANGED (anchor excludes writes), quoted send-message UNCHANGED (shell-strip blanks quoted region).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_gh_cli_read_noise.py
```

**Expected output:** `All 12 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_worker_cli_response_noise.py (144 LOC)

**Purpose:** 16-case smoke for `rewrite_worker_cli_response_noise.py`. Verifies 9 positive-strip cases (`| head`, `| tail`, `| grep`, `> redirect`, `2>&1`, `2>&1 | head`, `cd &&` chain, trailing `; bd list` chain, `|| echo fail` chain) and 7 negative no-op cases (bare response, **`worker-cli capture X | tail -40` critical pass-through**, `worker-cli status`, `worker-cli list`, cd chain no noise, trailing chain no pipe, response inside quoted echo).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_worker_cli_response_noise.py
```

**Expected output:** `All 16 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_background_sleep.py (117 LOC)

**Purpose:** 11-case smoke for `rewrite_background_sleep.py`. Verifies 5 positive-rewrite cases
(`sleep 300`, `sleep 5`, `sleep 1200` with `run_in_background=true`; bare `sleep 300` alone;
`sleep 45 && echo "bg-ack-probe done"` custom echo; `sleep 600 && echo "custom text"` N=600 non-canonical
→ all rewritten to `sleep 600 && echo done`) and 6 negative no-op cases (foreground flag; exact target
`sleep 600 && echo done`; non-canonical non-sleep command; wrong chain target `&& rag-cli`).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_background_sleep.py
```

**Expected output:** `All 8 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_block_unauthorized_background.py (84 LOC)

**Purpose:** 9-case smoke for `block_unauthorized_background.py`. Verifies 4 ALLOW cases (no foreground-force): original `sleep N && echo done`, bare `sleep N`, custom echo `sleep 45 && echo "bg-ack-probe done"` (fire-log actual), normalized `sleep 600 && echo done`. Verifies 4 FORCE cases (foreground-forced): `reddit-cli index_subreddits`, `workflow.py index-dir` (former whitelisted, now forced), `./venv/bin/python script.py`, `rag-cli update_docs .` (original triggering incident). Verifies 1 PASS case (already foreground → no output): `./venv/bin/python script.py` with `run_in_background=false`.

**Usage (from project root):**
```bash
./venv/bin/python dev/hook_smoke/test_block_unauthorized_background.py
```

**Expected output:** `All 9 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

---

### test_rewrite_chained_sleep.py (104 LOC)

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
