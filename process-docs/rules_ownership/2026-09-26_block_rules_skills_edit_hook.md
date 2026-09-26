# 2026-09-26 — Hook blocking agent edits of rules and skills

## Decision

Rules and skills are owned by the user. A global PreToolUse hook, `src/hooks/block_rules_skills_edit.py`, blocks `Edit` and `Write` from every agent (orchestrator and workers) on:

- any path starting with `<home>/.claude/shared-rules/` (home via `os.path.expanduser("~")`)
- any path with a directory component named exactly `skills`, at any depth (the file name itself is excluded)

Existing and new files are both blocked. The agent writes the proposed change into its process-docs and the user applies it.

Block message (stderr and fire log, exit 2):
`BLOCKED: rules and skills are user-owned — put the proposed change in your process-docs; the user applies it.`

## Scope choices stated by the user

- A `skills` component at any depth is blocked, not only at a repo root.
- A worktree copy of a skills directory is blocked too; editing a skill in a worktree and merging would otherwise bypass the user.
- Bash-based writes are out of scope; never observed as a bypass.
- No path normalization beyond `expanduser`: Claude Code passes absolute paths for Edit and Write. No `realpath` (filesystem dependence, no observed symlink bypass), no `..` collapsing (never observed).
- Fail-open on unparseable stdin, a missing `file_path` or another tool; a parse error writes a `trace` fire-log line.

## Why the hook fires at all

Observed 2026-09-26 in the orchestrator session under `defaultMode: acceptEdits`: an `Edit` on `/tmp/edit_probe/dev/probe.py` adding `from src.probe import y` was blocked by `block_dev_imports_src.py` (exit 2, stderr shown to the model, file unchanged, fire-log line written). PreToolUse hooks on Edit therefore fire in this environment. The 2026-05-22 "Edit hook no-fire" entry in the tool_use_safety area was not reproduced.

## Pitfall for the next agent

The shared test helper `exit_code_runners` calls `run_hook_fn(case[1], *case[3:])` and compares against `case[2]`. Cases must be ordered `(desc, first_arg, expected_exit, *extra_args)`. A first draft with `(desc, tool, path, expected)` failed with `exit=0 (expected <path>)`. Here the case is `(desc, file_path, expected, tool_name)`.

Example, observed: `("Write into iterative-dev skills directory BLOCK", f"{HOME}/Documents/ai/Meta/iterative-dev/skills/new-skill/SKILL.md", 2, "Write")`.

## Test

`dev/hook_smoke/test_block_rules_skills_edit.py`, 7 strands, all pass on 2026-09-26: Edit and Write under shared-rules blocked, Edit under `~/.claude/skills` blocked, Write into the iterative-dev skills directory blocked, ordinary-path Edit passes, Read of a skills path passes, malformed JSON fails open. Paths are literals built from `expanduser("~")`; nothing touches disk. Deliberately omitted (never observed): traversal, lookalike names such as `myskills/`, nested skills, `shared-rules-backup`, fire-log assertion. Registered in `run_all.py`; `run_all.py` as a whole was not run.

## Activation

`hook_setup.py` has two new entries (Write, Edit) but was not run in the worktree; it aborts outside the main repo root (the post-commit git hook attempted it and printed that error). Activation and live verification (Write a new file into a skills directory and into shared-rules, both must be blocked) happen on main after merge.

## Hypothesis, not observed

A symlink pointing into shared-rules or a skills directory would bypass the string-based check.
