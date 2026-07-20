# block_path_typo Hook — Edit-Matcher No-Fire (2026-05-22)

## Context

`block_path_typo.py` is registered in `~/.claude/settings.json` for Bash, Read, Write, Edit. The hook matches `.claire/` and `..letter` typos in `tool_input.command` (Bash) or `tool_input.file_path` (Read/Write/Edit). On a worker Edit with a `.claire/` path, **the hook did NOT fire** — CC's own filesystem check later rejected the edit with `tool_use_error>File does not exist`. On the same hook setup, the hook fired correctly for Bash and Read in the same worker.

## Evidence

Three live observations 2026-05-22, workers on `acceptEdits` permission mode (`defaultMode` in `~/.claude/settings.json`):

| Timestamp | Worker | Tool | Path/Command | Hook Outcome |
|---|---|---|---|---|
| 23:40:07 | search-bar-fix | **Edit** | `file_path: /Users/.../.claire/worktrees/search-bar-fix/src/core/monitor_display.py` | **Did NOT fire** — CC's filesystem check rejected with `tool_use_error>File does not exist` |
| 00:02:08 | search-bar-fix | **Bash** | `sed -n '72,100p' /Users/.../.claire/worktrees/.../utils.py 2>/dev/null` | **Fired correctly** — exit 2 + BLOCKED stderr |
| 23:43:18 | wakeup-dedup | **Read** | `file_path: /Users/.../.claire/worktrees/wakeup-dedup/src/proxy/payload_helpers.py` | **Fired correctly** — exit 2 + BLOCKED stderr |

Setup identical at all three timestamps:
- `~/.claude/settings.json` contained `block_path_typo.py` registered for all 4 matchers (Bash, Read, Write, Edit) — verified via `python3 -c "import json; d=json.load(open(...)); ..."` showing 24 PreToolUse hooks with `block_path_typo.py` present for each matcher.
- The worktree's `.claude/settings.local.json` contained only `permissions.allow` rules — no hooks override.
- `block_path_typo.py`'s source matches the `.claire/` literal via `re.compile(r'\.claire/')` — no regex bug that would skip the path.

## Hypothesis

The CC permission pipeline handles Edit-tool requests differently from Bash and Read. The `acceptEdits` mode auto-grants permission for Edit/Write tool calls; this may short-circuit the PreToolUse hook chain for Edit specifically. Read and Write are documented as part of `acceptEdits` scope too — but only Edit shows the no-fire behavior in this evidence sample. Possible explanations:

1. **Edit-specific bypass under `acceptEdits`** — Edit's permission flow may skip PreToolUse hooks when `acceptEdits` is the active mode (Read/Write may follow a different code path that still invokes hooks).
2. **Worker-session settings staleness for Edit matchers only** — unlikely because Bash/Read in the same worker session fired hooks correctly; a pure Edit-matcher race is implausible.
3. **CC bug / undocumented behavior** — the Edit + `acceptEdits` + PreToolUse-hook combination is in a regression class that hasn't surfaced because PreToolUse-on-Edit is uncommon.

Hypothesis 1 is the leading candidate. An earlier upstream issue (anthropics/claude-code #47853) documented exactly this Edit-specific pipeline anomaly: `updatedInput` for Edit is silently ignored even when the hook fires, while Read and Bash apply it correctly. The same Edit-specific divergence may extend to the firing path itself.

## Reproducer Plan (Deferred)

1. Spawn a fresh worker (clean tmux + worktree).
2. From the worker, attempt three tool calls in sequence on a `.claire/`-typo path:
   - Read with `file_path: .../.claire/...`
   - Edit with `file_path: .../.claire/...` + old_string/new_string supplied
   - Bash with `sed -n '1p' .../.claire/...`
3. Expected (correct behavior): all three blocked by `block_path_typo`.
4. Actual evidence-based prediction: Bash + Read blocked, Edit not blocked → confirms the Edit-specific bypass.
5. If reproduced: file an issue at anthropics/claude-code referencing #47853 as a related Edit-pipeline anomaly.

## Mitigation in Production Code

2026-05-22, same session: `block_path_typo.py` upgraded from block-and-hint to auto-rewrite via `hookSpecificOutput.permissionDecision: "allow"` + `updatedInput`. Commit `ce8d220`. New behavior:

- When the hook DOES fire (Bash/Read confirmed): the path typo is silently rewritten to the correct form; the tool call proceeds with the corrected input.
- When the hook does NOT fire (the Edit case under investigation): no rewrite happens, the original `.claire/` path passes to Edit, CC's filesystem check rejects with `tool_use_error>File does not exist`. Net effect: Edit still fails (same as the 23:40:07 incident), but without a block-stderr message. The investigation gap remains but is now lower priority because the failure mode is self-evident to the model from the file-does-not-exist error.

## Sources

- Issue #47853 (anthropics/claude-code, open 2026-04-14) — `updatedInput` ignored for Edit while working for Bash/Read. Comment #1 (2026-05-14) notes `bypassPermissions` drops `updatedInput` for Bash. Comment #2 (2026-05-17) notes stale-detection on Edit runs upstream of PreToolUse hooks.
- `~/.claude/shared-rules/global/tool-use.md` Rule 13 (`.claire/` typo class).
- `src/hooks/block_path_typo.py` (rewrite-form post `ce8d220`).
- `src/hooks/hook_setup.py` (registration entries lines 21-25 for the four matchers).
