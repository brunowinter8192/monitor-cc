# block_concurrent_timer Hook Removed, 2026-07-21

## Decision

Removed `block_concurrent_timer.py` entirely (hook script, `hook_setup.py` wiring, `dev/hook_smoke/test_block_concurrent_timer.py` smoke test, `src/hooks/DOCS.md` module doc). `rewrite_background_sleep.py` (600s sleep normalization) and `src/logs/timer_state.jsonl` (leftover state data) were explicitly out of scope and left untouched.

## Rationale

The hook enforced a single-timer-per-session guard: a new background sleep-timer request was blocked while a prior 600s window for the same session had not yet expired ("A background timer is already running…"). Failure mode: when a worker goes idle BEFORE the 600s elapses, the orchestrator is already woken by the worker-idle signal and legitimately wants to arm a fresh timer — the hook then false-blocked it. A rare stray second timer running concurrently is harmless (no resource contention, no incorrect behavior downstream); the single-timer invariant was not worth the false-block cost on the idle-before-timeout path. Superseded prior design documented as of 2026-07-20 (concurrent-redesign attempt) — that entry stands as a historical record of the guard's last shape before full removal, not touched by this change.

## Scope confirmed by repo-wide grep

`grep -rn 'block_concurrent_timer|concurrent_timer'` across the repo (excluding `__pycache__`) found exactly 5 hits pre-removal: the hook file, its smoke test, the `hook_setup.py` wiring tuple, the `src/hooks/DOCS.md` module section, and the pre-existing process-docs snapshot (left as-is per write-once rule). No other live code or config referenced it — no orchestrator script, no rule file, no menubar/proxy code depended on `timer_state.jsonl`'s concurrent-guard semantics beyond the hook itself.

## Verification

`hook_setup.py`'s own `_guard_not_worktree()` refuses execution from a `.claude/worktrees/` path (by design — prevents dead-path registration into the live `~/.claude/settings.json`), so the removal could not be live-verified against real settings from this worktree; running it would also mutate the real settings.json out-of-band, undesirable for a worktree task. Verified instead: (1) `py_compile` clean on `hook_setup.py`; (2) static import of `hook_setup._HOOK_SCRIPTS` confirms `block_concurrent_timer.py` absent and the list length dropped from 38 to 37 entries; (3) repo grep post-removal returns zero live references (`src/`, `dev/`, `.py`/`.md`) outside the untouched process-docs snapshot. The repo's own `.githooks/post-commit` fired `hook_setup.py` automatically on the commit and hit the same worktree guard, exiting 2 as expected — confirms the guard is exercised correctly by real git tooling, not just by manual invocation. Deployment onto the live `~/.claude/settings.json` (removal of the stale hook entry from the actual file) happens on the next `hook_setup.py` run from the main repo root, out of scope for this worktree session.

Total hook count (`block_*.py` + `rewrite_*.py` under `src/hooks/`) dropped from 33 to 32 as a direct result.
