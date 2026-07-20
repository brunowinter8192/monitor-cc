# Hook Friction Reduction — 2026-05-21

## Context

`analyze_blocks.py` (first run: 2026-05-20) showed 38 blocks in 7 days across 8 hook types. Three hooks accounted for 79% (30/38) of blocks, with friction clusters (same hook+branch, ≥3 in 30 min) indicating stuck workers:

| Hook | Total | Worker | Main | Friction Clusters |
|---|---|---|---|---|
| block_chained_sleep | 11 | 7 | 4 | 1 (tracker-fixes) |
| block_read_worktree | 10 | 10 | 0 | 2 (bead-tracker, panel-fixes2) |
| block_dangerous_kill | 9 | 5 | 4 | 1 (safety-hooks worker) |

All 10 `block_read_worktree` worker blocks were own-worktree reads (100% false positive rate).
Most `block_dangerous_kill` worker blocks in `safety-hooks` were heredoc false positives.
`block_chained_sleep` tracker-fixes blocks were heredoc false positives (pre-fix).

## What We Did

### block_read_worktree — Own-Worktree Allowance

**Problem:** Hook blocked `'.claude/worktrees/' in file_path` unconditionally. CC resolves relative Read paths to absolute before passing to hook, so `Read('src/foo.py')` from a worktree becomes `Read('/.../.claude/worktrees/<name>/src/foo.py')` → blocked.

**Fix:** `_is_own_worktree(file_path)` uses `os.getcwd()` to check if the caller is a worker reading its own files. Hook subprocesses inherit the CC session's CWD (empirically verified: subprocess `os.getcwd()` == parent process CWD). Workers reading files under their own worktree root → allowed. Main sessions and cross-worker reads remain blocked.

**Safety guarantee unchanged:** main→worktree reads (the original documented problem from workers-2.md) are still blocked. Worker→own is the new allowance.

**Commit:** `0bb3d28`

### block_dangerous_kill — Heredoc Stripping

**Problem:** `_strip_quoted` handled `'...'` and `"..."` but NOT heredoc bodies. Test scaffolding in Python heredocs (`python3 <<'PYEOF'\n...\npkill -f ...\nPYEOF`) triggered false blocks. Original rationale for the hook remains fully intact — `pkill -f "workflow.py --mode menubar"` was and remains correctly blocked (session_findings.md documents 3 worker deaths from this exact pattern; panel-* worker prompts reference the menubar launch string).

**Fix:** Replaced `_strip_quoted` with `_strip_non_shell_active` (same single-pass scanner introduced in `block_chained_sleep.py`). Handles heredoc bodies, single/double-quoted strings, ANSI-C quotes. Command substitutions kept shell-active.

Also added Monitor_CC-specific PID-file example to block message (concrete alternative to `pkill -f "workflow.py --mode menubar"`).

**Commit:** `9e2e945`

### block_chained_sleep — Heredoc Fix (previous session)

Already committed `439b79f` (previous session, Bead Monitor_CC-wozp): heredoc bodies and quoted strings are now stripped before `_SLEEP_TOKEN` matching. The tracker-fixes friction cluster (3 blocks in 5 min from heredoc-containing Bash commands) would no longer fire after this fix is merged.

### analyze_blocks — Friction Detection + Trigger Capture

Extended `dev/hook_analysis/analyze_blocks.py`:
- **parentUuid lookup**: finds the tool_use call that triggered each block; extracts `command`/`file_path`
- **Pattern clustering**: normalizes trigger commands → top-5 patterns per hook
- **Friction candidates**: (hook, project, branch) groups with ≥3 blocks in 30 min → "stuck worker" signal

Commits: `d930b8b` (initial), `1b42cbf` (extension)

## What We Found

1. **CWD inheritance confirmed**: hook subprocess `os.getcwd()` == session CWD. Enables reliable own-worktree detection without any additional payload fields.

2. **pkill -f "workflow.py --mode menubar" is NOT safe**: user intuition that this pattern "doesn't match workers" is incorrect. session_findings.md documents 3 worker deaths from this exact pattern (May 12). Block is correct. Document the PID-file alternative.

3. **Both `block_chained_sleep` and `block_dangerous_kill` have the same heredoc false-positive class**: the scanner (`_strip_non_shell_active`) is the shared fix. Consider extracting to a shared utility module if a third hook needs it.

4. **Friction candidates from new analyze_blocks**: the 4 friction clusters (≥3 blocks / 30 min) are all cases now fixed by the three refinements above.

## Open Questions

- Should `_strip_non_shell_active` be extracted to a shared module (e.g. `src/hooks/_shell_strip.py`)? Currently duplicated in `block_chained_sleep.py` and `block_dangerous_kill.py`. Duplication is acceptable for now (hooks are standalone scripts), but divergence risk grows if the scanner needs updating.
- `block_read_worktree`: does the own-worktree fix handle the case where a worker is spawned without a worktree (i.e., `--no-worktree` flag, CWD = main project)? In that case `_WORKTREE_FRAGMENT not in cwd` → `_is_own_worktree` returns False → block fires. Correct behavior (no-worktree worker should use Bash cat, not Read on arbitrary paths). No action needed.
- `worker-cli send "$(cat <<'EOF'\n... sleep N ...\nEOF)"` — nested heredoc inside `$()` is not stripped by the scanner (the `$()` content is kept active, and heredoc detection inside `$()` is not implemented). Rare edge case; acceptable until recurrence.
