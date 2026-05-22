# Hook API Capabilities — 2026-05-22

## Context

Investigation of the official Anthropic CC hook API surface. Trigger: current 17 hooks all use the exit-code interface (0=allow, 2=block). The compliance + FP analysis sessions (May 20–22) identified `pre-rewritable` patterns (e.g. `git diff dev..HEAD` → needs `--`) and `not-statically-hookable` patterns (read-before-edit) where block-only is insufficient. Prompted a question: can hooks REWRITE inputs instead of just blocking?

Sources read: `plugins/plugin-dev/skills/hook-development/SKILL.md` and `plugins/plugin-dev/skills/hook-development/references/advanced.md` from the `anthropics/claude-code` repo.

---

## Finding 1 — `updatedInput`: hypothesis REFUTED for general PreToolUse Bash

**Original hypothesis (from anthropics SKILL.md):** PreToolUse hooks can return a JSON body that silently rewrites the tool input BEFORE execution, using `hookSpecificOutput.updatedInput` with `permissionDecision: "allow"`. Shape:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {"command": "git diff dev --"}
  },
  "systemMessage": "..."
}
```

**Empirical refutation (2026-05-22):** built `src/hooks/rewrite_git_ambiguous.py` following the SKILL.md format (with the `hookEventName` field that mpsuesser/effect-claudecode TS schema clarified — SKILL.md omits it). Live-tested: hook fires correctly, emits valid JSON to stdout, exits 0. CC executes the ORIGINAL command anyway. No rewrite applied.

**Root cause (from anthropics/claude-code CHANGELOG):**
- Line 1324 (in the release that added `updatedInput` to PreToolUse): "PreToolUse hooks can now satisfy `AskUserQuestion` by returning `updatedInput` alongside `permissionDecision: 'allow'`, enabling headless integrations that collect answers via their own UI." → the `allow + updatedInput` path is **scoped to the `AskUserQuestion` tool**, not to general PreToolUse on Bash/Edit/Write/etc.
- Line 2629 (later release): "Fixed PreToolUse hooks to allow `updatedInput` when returning `ask` permission decision, enabling hooks to act as middleware while still requesting user consent." → general PreToolUse rewrite requires `permissionDecision: "ask"`, which surfaces a confirmation prompt — rejected by design (see Finding 2).
- Line 891: `PermissionRequest` is a separate event class with its own `updatedInput` semantics, not PreToolUse.

**Verdict:** the auto-correction path described in SKILL.md does not exist for Bash in CC v2.1.114 (and likely no current version). The SKILL.md is either incomplete or describes a roadmap state.

**What this means in practice:**
- Hooks can ONLY block (exit 2) or allow (exit 0) for general PreToolUse on Bash. No silent rewrite.
- For pre-rewritable patterns (like git-ambiguous), the best we can do is block-with-hint: exit 2 with a one-line stderr that tells the model how to fix the input. The model retries with the fix applied — one extra tool call per occurrence, no user confirmation.
- `src/hooks/rewrite_git_ambiguous.py` was converted to this block-with-hint form 2026-05-22. The `updatedInput` JSON shape is preserved as a comment in the script for the future if the API expands.

**Current state:** all 18 hooks use exit-0 (allow) or exit-2 (block). NONE use `updatedInput`. This is structurally final until Anthropic extends the API.

**Implementation note for future updates:** if `allow + updatedInput` ever gains general PreToolUse Bash support, the `_emit_block_hint` function in `rewrite_git_ambiguous.py` can be swapped to `_emit_rewrite` (the documented JSON dict at the bottom of the function). Test with a fresh CC version when CHANGELOG indicates the extension.

---

## Finding 2 — `permissionDecision: "ask"`: third option besides allow/deny

Beyond `"allow"` (exit 0 equivalent) and `"deny"` (exit 2 equivalent), the JSON output schema supports `"ask"`:

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "ask"
  },
  "systemMessage": "This command matches pkill -f — confirm PID-file alternative first."
}
```

With `"ask"`, CC surfaces the `systemMessage` to the user and awaits explicit confirmation before proceeding. Not used in Monitor_CC by design — every confirmation flow becomes a workflow tax. Per Finding 1's empirical refutation, `ask + updatedInput` is the ONLY supported rewrite path for general PreToolUse Bash. Since `ask` is rejected, the practical fallback for `pre-rewritable` patterns is block-with-hint (exit 2 + stderr) — the model retries with the fix applied.

---

## Finding 3 — Prompt-based hooks

An alternative hook type where the hook definition is a SHORT PROMPT rather than a shell command. CC evaluates the tool call by running the prompt as a mini LLM request (default timeout: 30s).

```json
{
  "type": "prompt",
  "prompt": "Does this Bash command use && to chain diagnostic commands that may exit non-zero (grep, ls, find, test -f) before other commands? If yes, respond DENY with a short explanation. If no, respond ALLOW.",
  "timeout": 30
}
```

**Use case:** Rule 11 violations (`diag-chain-and`) — the regex in `rule_compliance.py` has confirmed false-positive risk on legitimate prereq chains (mkdir && build). A prompt hook could decide with much lower FP rate by understanding the INTENT of each segment.

**Current state:** not used. All 17 hooks are `type: command` (python3 script invocation).

**Tradeoff:** 30s timeout adds latency on every matching tool call. Practical only for high-value decisions where regex is unreliable AND the pattern is rare enough that the latency doesn't block flow. `edit-string-not-found` prevention is another candidate: "Does old_string plausibly appear in this file?" — but the file content isn't in the hook payload, making this harder.

---

## Finding 4 — Watchdog message injection on worker-idle (Monitor_CC enhancement)

**Context:** When a worker goes idle, Monitor_CC's menubar/watchdog component already detects the transition and SIGTERMs Opus's background `sleep N && echo done` process. This causes Opus's background job to "complete" early (exit code 0). But the wake-up is blind — Opus receives only a generic "Background command completed (exit code 0)" notification with no information about which worker went idle. Opus must then run `worker-cli list` from scratch to determine what happened.

**Mechanism:** The SIGTERM is already issued at the correct code site in the watchdog. The enhancement is to add a `tmux send-keys` call at that SAME site — immediately after the SIGTERM — to inject a message into Opus's tmux pane:

```
tmux send-keys -t <opus-session> "worker <name> idle" Enter
```

Opus then wakes WITH context: it knows which worker finished and can proceed directly to `worker-cli response <name>` without a `list` round-trip.

**Status:** Monitor_CC-side change, not a CC hook API capability per se. Included here because it addresses the same problem class — reducing Opus's reactive polling discipline by making the signal self-describing. Implementation deferred; no code change in this session.

**Migration path:** once injection is live and verified over a real window, delete the "Timer wakes → `worker-cli status <name>`" discipline line from `~/.claude/shared-rules/opus/workers-2.md § Timer & Polling Flow`. The injected message replaces the rule: structural signal eliminates the need for self-discipline. Same pattern as the `pkill -f` → `block_dangerous_kill.py` migration.

---

## Summary

| Capability | Status | Note |
|---|---|---|
| `updatedInput` rewrite (allow + JSON) | NOT supported for general PreToolUse Bash | Scoped to `AskUserQuestion` tool only (CHANGELOG line 1324). SKILL.md is misleading on this. |
| `updatedInput` rewrite (ask + JSON) | Supported but rejected by design | Requires user confirmation each call — workflow tax. |
| `permissionDecision: ask` | Not used — rejected by design | Same workflow-tax reason. |
| Block-with-hint (exit 2 + stderr) | Used for `rewrite_git_ambiguous` (Hook 18) | Fallback when rewrite path is unavailable. Model retries with fix. |
| Prompt-based hooks | Not used | `diag-chain-and` (Rule 11), `edit-string-not-found` candidates. 30s LLM latency tradeoff per matching call. |
| Watchdog message injection on worker-idle | Implemented 2026-05-22 in `src/menubar/bg_timer.py` | Replaces blind wake + Opus polling-discipline rule. Requires menubar restart to activate. |

**Bottom line:** auto-correction without user friction is NOT achievable via the current CC hook API on Bash. The structural prevention pattern (Hooks > Rules > Discipline) maxes out at block-with-hint for fixable patterns and full block for unfixable ones. Watchdog message injection is the only mechanism in this session that genuinely eliminates a discipline rule (the wake-up rule from `workers-2.md`).
