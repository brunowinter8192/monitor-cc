# rewrite_gh_cli_read_noise Hook Added, 2026-07-21

## Motivation

`gh-cli get_issue ...` / `gh-cli list_issues ...` piped through `| tail` / `| head` / `| grep` silently truncates the output. For an issue read this is fatal — missing sources, missing context, decisions made on a partial view with no signal that anything was cut. Nothing previously prevented this: `block_gh_cli_chained.py` explicitly EXEMPTS `get_issue`/`list_issues` from its chain-block (those two are legitimately pipeable for other reasons in that hook's model), so a truncating pipe on them passed straight through.

## Design — silent rewrite, not a block

Same principle as the existing `rewrite_worker_cli_capture_noise.py` / `rewrite_worker_cli_response_noise.py` hooks: strip the pipe silently rather than blocking the command outright, since the fix (drop the truncating pipe, return full output) is unambiguous and unique — a block would just force the agent to retype the same command without the pipe.

Built as a direct structural clone of `rewrite_worker_cli_capture_noise.py`: anchor swapped to `\bgh-cli\s+(?:get_issue|list_issues)\b`; `_SEGMENT_END_RE`, `_NOISE_RE` (pipe-only, excludes `||`), `_parse_command`, `_apply_ranges`, `_emit_rewrite` byte-identical to the template — those are generic shell-segment mechanics, not worker-cli-specific. Only the anchor regex, the workflow function name, and the fire-log name changed. Deliberately excludes `create_issue`/`update_issue` — those are writes with a one-line confirmation, no truncation risk, out of scope.

Redirects (`>`, `>>`, `2>&1`, `&>`) preserved — same rationale as capture: they save the FULL output somewhere, they don't truncate it, so they're not noise.

## Hook ordering note

Registered in `_HOOK_SCRIPTS` (`hook_setup.py`) right after `block_gh_cli_chained.py`. Both hooks can independently observe the same `gh-cli get_issue ... | tail` command: `block_gh_cli_chained.py` explicitly allows it through (its exemption for issue-read commands), and `rewrite_gh_cli_read_noise.py` then strips the pipe. No conflict — the block hook's exemption and the rewrite hook's scope are the same two commands by design, and PreToolUse hooks execute independently per the CC hook model; the rewrite firing after the block hook's allow is the intended sequence, not a race.

## Verification — this session

`py_compile` clean on the new hook and `hook_setup.py`. Smoke test (`dev/hook_smoke/test_rewrite_gh_cli_read_noise.py`, 12 cases, all real subprocess invocations of the hook with real stdin JSON): 12/12 PASS — 5 positive strips, 2 redirect-preserved no-ops, 2 out-of-scope-command no-ops (create_issue/update_issue), 2 bare no-ops, 1 quoted-string no-op. Static import of `hook_setup._HOOK_SCRIPTS` confirmed the new entry present, list length 37→38. Live fire against a real running CC session / deployment onto the actual `~/.claude/settings.json` was not attempted from this worktree — `hook_setup.py`'s own `_guard_not_worktree()` refuses execution from a worktree path (by design, prevents dead-path registration and avoids mutating the real settings file out-of-band); that live-fire verify is deferred to the orchestrator after merge onto the main repo.
