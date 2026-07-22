# block_read_oversize Hook Disabled, 2026-07-22

## Motivation

`block_read_oversize.py` pre-empted CC's own >256KB Read rejection with its own block message. Three problems converged:

1. **Redundant** — CC enforces its 256KB Read limit itself regardless of this hook; the hook only duplicated a rejection CC already produces natively.
2. **Stale-prone** — the 256KB figure is a CC-internal constant hardcoded into the hook; it silently drifts out of sync whenever CC changes its own limit, with no signal that it has.
3. **Actively contradictory** — its block message told the agent to "grep the file first, then Read with offset/limit". `block_po_read.py` (added same day) forbids exactly that for persisted-output exports (`.../tool-results/<id>.txt` under `.claude/`) — grepping instead of a full Read risks acting on a partial view. The two hooks disagreed on the correct escape for an oversize file whenever that file happened to be a persisted-output export.

## Resolution — disable, no replacement

Renamed `block_read_oversize.py` → `block_read_oversize.py.disabled` via `git mv` (kept in repo for history, matching the existing `block_chained_sleep.py.disabled` convention) and removed its `("block_read_oversize.py", "Read")` entry from `_HOOK_SCRIPTS` in `hook_setup.py` (39 → 38 entries). No replacement hook — CC's native >256KB rejection is left to fire on its own; there is no need to re-implement it locally now that the "grep first" advice is retired.

## Verification — this session

`py_compile` clean on `hook_setup.py`. `_HOOK_SCRIPTS` entry count confirmed 39 → 38 via direct regex parse of the source (not `git log`). `git status` confirmed the rename as a 100% match (no content change to the disabled file itself). `grep -rn "block_read_oversize" src/hooks/ --include='*.py' --include='*.disabled'` confirmed zero references outside the disabled file's own internals (its function name, `log_fire` tag, `__main__` call) — no other active hook or `hook_setup.py` code path names it anymore. No smoke test existed for this hook (`dev/hook_smoke/test_block_read_oversize.py` was never created), so nothing to move there. Live deploy onto the real `~/.claude/settings.json` not attempted — `hook_setup.py`'s worktree guard refuses execution from this worktree by design; deferred to the orchestrator after merge.
