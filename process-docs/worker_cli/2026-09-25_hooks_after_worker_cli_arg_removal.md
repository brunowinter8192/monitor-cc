# Hooks after worker-cli lost project_path and the model argument

2026-09-25, monitor-cc. Area worker_cli. The CLI side (iterative-dev) is documented in the worker_cli area of that repo.

## Why

`worker-cli` no longer takes a project path: `wait` uses the cwd project, `spawn` uses the current project (or the proxy project), every other command finds the worker in the registry. A path after `wait` or a third positional after `spawn` now aborts in the CLI with exit 2 and the correct form. Two hooks still produced or expected the old forms.

## rewrite_worker_wait.py

Before: `cd X && worker-cli wait [args]` was rewritten to `worker-cli wait X [args]` (the path replaced the cd); the block message recommended `worker-cli wait /path/to/project`. Both would now hit the CLI's wait tripwire.

Owner decision (Option 1): any `cd ... ; worker-cli wait` is blocked, the block message says wait takes no path and uses the current project, so it must run from the project directory as its own Bash call. `_CD_WAIT_RE` and `_collapse_cd` are deleted; a cd-prefixed wait falls through to the existing block because the canonical regex only matches a bare `worker-cli wait [...]`. Canonical calls are still forced to `run_in_background=true`. The hook does not reject `worker-cli wait /path` itself: it stays a flag normaliser, the CLI owns the rejection (observed case shapes in `dev/hook_smoke/test_rewrite_worker_wait.py`: five cd shapes now BLOCK, exit 2).

Not changed: `block_unauthorized_background.py` `_WAIT_FORM` still allows any argument after `wait`; the hook only decides whether a background call is authorised, the CLI rejects the argument.

## block_worker_spawn_placement.py

Before: `_SPAWN_RE` needed three positionals and compared the third (project path) with the cwd git root, blocking spawns into a foreign project. The path argument does not exist any more, so that check could not fire and its messages quoted the old forms (`... <prompt_file> c`, `... <project_path>`).

Now: only the `--no-worktree` block is left, regex `worker-cli spawn <name> <prompt_file>`, message `Use: worker-cli spawn <name> <prompt_file> (always spawns into a worktree of the current project).` The worktree-cwd early exit stays. The old forms `spawn n p c` and `spawn n p /other` pass the hook and are rejected by the CLI.

## Tests

- `dev/hook_smoke/test_rewrite_worker_wait.py` adapted (21 strands pass).
- `dev/hook_smoke/test_block_worker_spawn_placement.py` is new (10 strands pass) and registered in `run_all.py`. There was no test for this hook before. Lesson: the smoke runner's default cwd is the repo root; inside a `.claude/worktrees/` checkout that cwd trips the hooks' worktree early exit, so BLOCK cases must pass an explicit cwd outside a worktree (a temporary directory), as the new test does.

## docs-drift-check on the monitor-cc worktree, 2026-09-25

The stricter checker from iterative-dev integration reports findings unrelated to this change (module headings elsewhere, `dev/refactoring/DOCS.md` word limits, `Called by` naming files that do not exist, a directory without its own DOCS.md). Only the `run_all.py` LOC heading in `dev/hook_smoke/DOCS.md` was in scope and is fixed; the rest is left as is.
