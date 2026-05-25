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

### test_block_dangerous_kill.py

**Purpose:** Smoke test for `block_dangerous_kill.py` — pkill -f patterns and pipe-kill chains.

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

### test_block_parallel_bash_timer.py (118 LOC)

**Purpose:** 11-case smoke for `block_parallel_bash_timer.py`. Verifies 5 true-positive blocks
(strict canonical timer + foreground Bash; loose `echo "<quoted>"` timer + foreground;
three Bashes one is timer; thinking + tool_use mix with timer; float-second timer) and 6
false-positive passes (single Bash no timer; single Bash IS timer no partner; two non-timer Bashes;
quoted timer-text inside other command; chained sleep in larger command; missing transcript_path
fail-open).

Each case writes a temporary JSONL transcript with a fingierter assistant-message content array,
invokes the hook with `transcript_path` pointing at the temp file, compares exit code. Test isolation
via `MONITOR_CC_HOOK_FIRING_LOG=/tmp/test_block_parallel_bash_timer_fire.jsonl` env var — avoids
polluting the production `src/logs/hook_firing.jsonl`.

**Usage (from project root):**
```bash
python3 dev/hook_smoke/test_block_parallel_bash_timer.py
```

**Expected output:** `All 11 tests passed.` (exit 0). HOOK path is relative
(`src/hooks/block_parallel_bash_timer.py`) — must be run from project root.
