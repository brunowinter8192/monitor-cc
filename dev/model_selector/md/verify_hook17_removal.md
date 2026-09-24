# Hook 17 (block_worker_spawn_opus.py) removal verification

1. File deleted: True (/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/mcfix-tests3/src/hooks/block_worker_spawn_opus.py)
2. No longer in hook_setup.py's _HOOK_SCRIPTS: True (36 scripts total)

3. _sweep_stale_hooks() — the real pure function that heals settings.json —
   exercised on a synthetic in-memory dict (never the real ~/.claude/settings.json):
   swept_count=1 (expected 1 — the dead path)
   remaining_commands=['python3 /Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/mcfix-tests3/src/hooks/hook_setup.py'] (expected only the alive path)

4. Registration mechanism (read, not invoked — hook_setup.py refuses to run from a
   worktree via _guard_not_worktree()): .githooks/post-merge greps
   `git diff --name-only ORIG_HEAD HEAD` for `^src/hooks/` and re-runs hook_setup.py
   if matched. `git config core.hooksPath` = `.githooks` confirmed active on this
   machine (checked both at the worktree and main-repo level). Once this change
   reaches a real merge, that post-merge hook fires hook_setup.py automatically —
   no manual step, no hand-edit of the real settings.json needed.

RESULT: PASS — file gone, registration entry gone, sweep mechanism verified correct on a synthetic dict, real regeneration mechanism traced and confirmed active.
