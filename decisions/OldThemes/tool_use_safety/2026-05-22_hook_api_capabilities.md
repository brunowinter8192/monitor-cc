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

With `"ask"`, CC surfaces the `systemMessage` to the user and awaits explicit confirmation before proceeding. Useful for patterns that are dangerous BUT sometimes intentional — the current exit-2 blocks unconditionally and forces the user to retype.

**Candidate patterns for "ask" instead of block:**
- `block_dangerous_kill`: `pkill -f` targeting the menubar process is sometimes intentional (after confirming PID). Currently always blocks.
- `block_chained_sleep` with N ≤ 5 settling-time: identified as FP class in this session. Current hook blocks unconditionally; "ask" would surface the rule and let the user confirm.

**Note:** "ask" adds user friction. Only worth it for patterns where (a) blocking is too strict, and (b) the user has enough context to make the right call in 2 seconds.

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

## Finding 4 — Worker idle wake-up via Stop hook (candidate pattern)

**Context:** Workers signal completion by going idle (pane stops outputting). Opus currently polls via `worker-cli response <name>` after a `sleep N && echo done` timer. This is reactive polling — Opus wakes after N seconds regardless of whether the worker finished in 10s or 5 minutes.

**Candidate mechanism (CC Stop hook → tmux send-keys → Opus auto-receives prompt):**

CC fires a `Stop` hook when a session is about to produce a final response and go idle. A worker-side Stop hook could:
1. Detect the session is idle (hook fires when worker's own response cycle ends)
2. Run `tmux send-keys -t worker-Monitor_CC-<opus_session> "" Enter` to inject an empty prompt into the Opus pane
3. Opus receives the injected prompt, wakes, and polls the now-idle worker

This eliminates the timer entirely: worker signals done → Opus wakes immediately.

**What we know:** Stop hook fires at session response completion. The hook has access to CWD, which contains the worker name (via `.claude/worktrees/<name>`). The Opus session name is `worker-Monitor_CC-opus` or similar (discoverable via `tmux list-sessions`).

**What we don't know:** Whether `tmux send-keys` from inside a hook subprocess reliably lands in the Opus pane across session boundaries. Whether the Stop hook fires when the worker is blocked (tool call pending) vs only on clean idle. Whether Opus's session name is stable enough to target.

**Status:** candidate only. No implementation. Next step: build a dev/ probe in a worker session that fires a Stop hook and verifies the Opus pane receives the keys.

---

## Summary

| Capability | Status | Candidate use |
|---|---|---|
| `updatedInput` rewrite | Not used by any hook | `git-ambiguous` fix (add ` --`) |
| `permissionDecision: ask` | Not used | `block_chained_sleep` settling-FP; `block_dangerous_kill` |
| Prompt-based hooks | Not used | `diag-chain-and` (Rule 11), `edit-string-not-found` |
| Stop hook → worker wake-up | Candidate (unverified) | Replace sleep-based polling |

All four capabilities are part of the official CC hook API. None are implemented in Monitor_CC yet. Decision on which to migrate to is deferred until `dev/hook_firing/` and `dev/tool_use_errors/` have produced empirical FP + coverage-gap data over a real window.
