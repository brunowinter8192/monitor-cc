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

### test_block_dangerous_kill.py (90 LOC)

**Purpose:** 18-case smoke for `block_dangerous_kill.py` — pkill -f patterns, pipe-kill chains, heredoc/quote exemptions, and allowlist cases.

**Usage:**
```bash
python3 dev/hook_smoke/test_block_dangerous_kill.py
```

---

### test_block_read_worktree.py

**Purpose:** Smoke test for `block_read_worktree.py` — foreign worktree reads blocked, own-worktree
reads allowed.

**Usage:**
```bash
python3 dev/hook_smoke/test_block_read_worktree.py
```

---

### test_block_polling_loop.py (140 LOC)

**Purpose:** 15-case stateful smoke for `block_polling_loop.py`. Uses a temp state file (env var `MONITOR_CC_POLLING_STATE`) to isolate test runs. Five test groups: frequency (ps-p and tail each reach block on 3rd call), different-target (new target passes after saturation), single-check (one-off always passes), no-target (tail -n long form, ps aux, git status, quoted patterns), session-isolation (session B saturation does not affect session A's count).

**Usage:**
```bash
python3 dev/hook_smoke/test_block_polling_loop.py
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

### test_rewrite_background_sleep.py (117 LOC)

**Purpose:** 8-case smoke for `rewrite_background_sleep.py`. Verifies 3 positive-rewrite cases
(`sleep 300`, `sleep 5`, `sleep 1200` with `run_in_background=true` → rewritten to
`sleep 600 && echo done`) and 5 negative no-op cases (foreground flag; already 600; non-canonical
command; wrong chain target; bare sleep without `&& echo done`).

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_rewrite_background_sleep.py
```

**Expected output:** `All 8 tests passed.` (exit 0). HOOK path is relative — must be run from project root.

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
