# Hook API Auto-Rewrite Works for Bash — Correction (2026-05-22, later)

## Context

The hook-API-capabilities entry in this area, Finding 1, concluded `updatedInput` + `permissionDecision: "allow"` was **REFUTED for general PreToolUse Bash** — based on a single live test of `rewrite_git_ambiguous.py` that appeared not to apply the rewrite. That conclusion was wrong and led to three months of block-and-hint workarounds across hooks.

Today's session (same date) revisited the question via GitHub research and live re-verification. The earlier refutation is invalid; auto-rewrite DOES work for Bash in `acceptEdits` mode, and three hooks were converted accordingly.

## Evidence

### External (GitHub research)

**Issue [anthropics/claude-code#47853](https://github.com/anthropics/claude-code/issues/47853)** (open, 2026-04-14) — OP `i-dedova` reports:

> `updatedInput` works correctly for:
> - **Read** — `updatedInput` with modified `offset`/`limit` is applied (confirmed in existing setup)
> - **Bash** — `updatedInput` with modified `command` is applied (confirmed in existing setup)

The OP scope is an Edit-specific bug (`updatedInput` ignored for Edit). Bash + Read confirmed working as a baseline assumption of the bug report.

**Comment #1 by `User0394934`** (2026-05-14) reports a Bash counter-example BUT under `bypassPermissions` mode:

> Possible variable: bypassPermissions mode. This installation runs `"defaultMode": "bypassPermissions"` because the workflow is unattended/autonomous. The hypothesis: bypass mode fast-paths the command through ("permission already granted") and drops the updatedInput side of the hook output along with the now-moot permission decision.

So the refutation regime is narrower than thought: `updatedInput` works for Bash under `acceptEdits` (our mode) and breaks under `bypassPermissions`.

**CHANGELOG context** (anthropics/claude-code/CHANGELOG.md):
- Line 2662 (oldest, v before 2.0): "Fixed PreToolUse hooks to allow `updatedInput` when returning `ask` permission decision."
- Line 1357 (v2.1.85): "PreToolUse hooks can now satisfy `AskUserQuestion` by returning `updatedInput` alongside `permissionDecision: 'allow'`."
- Latest version current: 2.1.149.

The v2.1.85 line is specifically about `AskUserQuestion` tool. It does NOT say "for AskUserQuestion only" — it says "now satisfy AskUserQuestion" as the most recently added capability. The Issue #47853 OP report from v2.1.143 confirms `allow + updatedInput` works for Bash + Read in normal mode.

### Internal (this session, live verification)

Three hooks converted from block-and-hint (exit 2 + stderr) to auto-rewrite (exit 0 + `hookSpecificOutput.updatedInput`):

| Hook | Before | After | Verification |
|---|---|---|---|
| `src/hooks/rewrite_bd_invalid_repo.py` (NEW) | n/a | rewrites `bd --repo <invalid>` by stripping the invalid `--repo` token | Live test 2026-05-22: `bd --repo /Users/brunowinter2000/Wrong/Path create ...` produced bead `Monitor_CC-ggh6` (correct project prefix, cwd-default), `/Users/brunowinter2000/Wrong/` not auto-initialized. Hook stripped the bad flag before bd ran. |
| `src/hooks/rewrite_git_ambiguous.py` (UPGRADED) | exit 2 + stderr block hint, model retries with `--` appended | inserts `--` before first chain operator OR appends at end via `hookSpecificOutput.updatedInput.command` | Live test: `git -C ... log dev --oneline \| head -5` previously BLOCKED; now silently rewrites to `git -C ... log dev --oneline -- \| head -5`, output produced normally. Smoke 9/9 PASS. |
| `src/hooks/block_path_typo.py` (UPGRADED) | exit 2 + stderr block hint on `.claire/` or `..letter` patterns | rewrites `.claire/` → `.claude/`, `..letter` → `../letter` via `hookSpecificOutput.updatedInput.command` (Bash) or `.file_path` (Read/Write/Edit). Edit carries all 4 fields per Issue #47853 OP. | Smoke 7/7 PASS including Edit with all 4 fields preserved in `updatedInput`. |

The CC permission mode at all three live tests: `defaultMode: "acceptEdits"` (verified in `~/.claude/settings.json`).

`systemMessage` field is part of the JSON output of all three hooks — it surfaces in Opus's tool-call context after the rewrite. The model sees both the executed (rewritten) command and an explanation of what was changed.

## Hook output JSON shape (canonical)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {"command": "<rewritten>"}
  },
  "systemMessage": "Hook rewrote ..."
}
```

For Edit specifically (per Issue #47853 OP working repro), `updatedInput` must contain ALL Edit fields, not just the changed `file_path`:

```json
"updatedInput": {
  "file_path": "<rewritten>",
  "old_string": "<original>",
  "new_string": "<original>",
  "replace_all": false
}
```

Read and Write: only `file_path` (or other tool-specific field) required.

## Edit-Matcher Anomaly (deferred investigation)

`block_path_typo.py` after conversion exhibits Edit-specific no-fire behavior — see the block-path-typo-edit-no-fire entry in this area. Bash and Read matchers fire correctly under the same setup; Edit doesn't fire AT ALL (not "fires but updatedInput dropped" like Issue #47853). The two phenomena may share a root cause in the CC Edit-pipeline.

## Implication for future hooks

Pattern is now: any PreToolUse hook that wants to silently correct a recognizable-broken input should use the rewrite form (exit 0 + `hookSpecificOutput.updatedInput`) instead of the block-and-hint form (exit 2 + stderr). The block form is for damage-prevention only (per the hook-principle-block-vs-allow entry in this area).

Remaining block-form hooks that COULD be candidates for conversion (require analysis of whether the broken pattern has a unique correct fix that the hook can compute):
- `block_broad_grep.py` — could auto-inject `--include='*.py'`? Risky: language extension is content-dependent. Keep as block.
- `block_chained_sleep.py` — no obvious rewrite. Keep as block.
- `block_dangerous_kill.py` — fundamentally blocking damage. Keep as block.
- Others — mostly damage-prevention class.

The conversion candidates are the **structural-typo class**: patterns where the corrected form is computable from the broken form. `.claire/`→`.claude/`, `--repo <bad>`→strip, `git diff <ref>`→add `--`. Beyond these three, no more obvious candidates in the current hook set.

## Sources

- Issue [#47853](https://github.com/anthropics/claude-code/issues/47853) (anthropics/claude-code) — OP `i-dedova` 2026-04-14, comment `User0394934` 2026-05-14, comment `ymonster` 2026-05-17.
- anthropics/claude-code/CHANGELOG.md lines 2662 (`ask` decision), 1357 (`AskUserQuestion` allow+updatedInput), 924 (`PermissionRequest` updatedInput).
- anthropics/claude-code/plugins/plugin-dev/skills/hook-development/SKILL.md (`updatedInput` documented as part of PreToolUse `hookSpecificOutput`).
- `src/hooks/rewrite_bd_invalid_repo.py`, `src/hooks/rewrite_git_ambiguous.py`, `src/hooks/block_path_typo.py` (current rewrite-form sources).
- The hook-API-capabilities entry in this area (predecessor entry with the now-corrected Finding 1).
- The block-path-typo-edit-no-fire entry in this area (Edit-matcher anomaly).
- The hook-principle-block-vs-allow entry in this area (when to block vs rewrite).
