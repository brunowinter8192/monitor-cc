# Hook API Capabilities — 2026-05-22

## Context

Investigation of the official Anthropic CC hook API surface. Trigger: current 17 hooks all use the exit-code interface (0=allow, 2=block). The compliance + FP analysis sessions (May 20–22) identified `pre-rewritable` patterns (e.g. `git diff dev..HEAD` → needs `--`) and `not-statically-hookable` patterns (read-before-edit) where block-only is insufficient. Prompted a question: can hooks REWRITE inputs instead of just blocking?

Sources read: `plugins/plugin-dev/skills/hook-development/SKILL.md` and `plugins/plugin-dev/skills/hook-development/references/advanced.md` from the `anthropics/claude-code` repo.

---

## Finding 1 — `updatedInput`: hooks can rewrite tool inputs

PreToolUse hooks can return a JSON body that rewrites the tool input BEFORE execution:

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "git diff dev..HEAD --"
    }
  },
  "systemMessage": "Added -- separator to disambiguate branch name from path."
}
```

The `updatedInput` object is merged into `tool_input` — only keys present in `updatedInput` are overwritten, others pass through unchanged. This is the **auto-correction path**: detect a known-bad input pattern AND emit the corrected form, so execution proceeds with the fix applied silently.

**Current state:** all 17 hooks use exit-0 (allow) or exit-2 (block). NONE use `updatedInput`. This leaves `pre-rewritable` patterns (currently classified as unhooked) without tooling.

**Migration path:** rewrite hooks that currently exit-2 on fixable inputs to instead emit `updatedInput` + exit-0. The `git-ambiguous` pattern (`fatal: ambiguous argument 'dev'`) is the clearest candidate: detect `git (diff|log|show) [^-]*\bdev\b.*\.\.HEAD` without `--`, return `updatedInput: {command: <cmd> + " --"}`.

**Implementation note:** returning a JSON body requires the hook to print JSON to stdout (not stderr) and exit 0. The hook cannot both block (exit 2) AND rewrite — the two paths are mutually exclusive. Hooks that want "rewrite if fixable, block if not" must implement the rewrite path and only fall back to exit-2 for unfixable cases.

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

With `"ask"`, CC surfaces the `systemMessage` to the user and awaits explicit confirmation before proceeding. Not used in Monitor_CC by design — every confirmation flow becomes a workflow tax. Hard-allow refinements + updatedInput rewrites are preferred over `ask`.

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

| Capability | Status | Candidate use |
|---|---|---|
| `updatedInput` rewrite | Not used by any hook | `git-ambiguous` fix (add ` --`) |
| `permissionDecision: ask` | Not used — rejected by design | — (hard-allow refinements + updatedInput preferred) |
| Prompt-based hooks | Not used | `diag-chain-and` (Rule 11), `edit-string-not-found` |
| Watchdog message injection on worker-idle | Not implemented | Replace blind wake + Opus polling-discipline rule |

`updatedInput`, `ask`, and prompt-based hooks are part of the official CC hook API. Watchdog injection is a Monitor_CC-side change independent of the CC hook API. Decision on which hook-API capabilities to migrate to is deferred until `dev/hook_firing/` and `dev/tool_use_errors/` have produced empirical FP + coverage-gap data over a real window.
