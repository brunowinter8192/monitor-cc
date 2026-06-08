# Hook Taxonomy — Tool-Hooks vs Activity-Hooks

## Why this exists

Recurring terminology collision: "hooks" in this repo refers to TWO unrelated
systems that both ride CC's hook mechanism. The state file the worker-status
machinery reads is literally named `hooks.json`, which sounds like it belongs to
the `src/hooks/` safety system — it does not. This file fixes the vocabulary so
future discussion names the right system.

## Definition

A **hook** is an event-based mechanism: when event E fires, CC runs handler H
(`python3 <script>`, registered in `~/.claude/settings.json`). Two orthogonal
axes describe any hook in this repo:

1. **Event class** — WHAT fires the hook:
   - **Tool events** (`PreToolUse` / `PostToolUse`) — fire around every tool call.
   - **Session-lifecycle events** (`UserPromptSubmit` / `Stop` / `StopFailure`) — fire around conversation turns.
   Both event classes are **CC-standard** — they always exist. You opt in by
   registering a handler. Registering a handler for `UserPromptSubmit` does not
   make the event custom; the EVENT is standard, only the HANDLER is ours.

2. **Handler purpose** — WHAT the script does:
   - **Safety / control** — block (exit 2) or rewrite (exit 0 + `updatedInput`) tool inputs.
   - **Activity tracking** — record session working/idle state.

"Custom" always refers to the HANDLER (our script), never the EVENT.

## The two systems

| | Tool-Hooks (Safety) | Activity-Hooks |
|---|---|---|
| Events | `PreToolUse`, `PostToolUse` | `UserPromptSubmit`, `Stop`, `StopFailure` |
| Handler | `src/hooks/*.py` (22 PreToolUse + 1 PostToolUse; 28 total registrations across Bash/Edit/Read matchers) | `src/menubar/hook_writer.py` (one script, all three events) |
| Does what | Intercept Bash/Edit/Read → block destructive patterns / rewrite broken inputs | Track turn boundaries → write current session status |
| Output | `src/logs/hook_firing.jsonl` — append-forever fire LOG | app-support `hooks.json` — live STATE file (overwritten, not appended) |
| Installer | `src/hooks/hook_setup.py` | `src/menubar/hook_setup.py` |
| Consumers | FP-analysis / audit (`jq` over the jsonl) | menubar `proc_cache.py` (reads every 1s, status display + auto-abort); iterative-dev `worker-cli status` |

## The activity `hooks.json` state file

NOT a log. A ~1KB live state map, one entry per CC session:

```json
"af20354b-...": { "status": "idle", "cwd": ".../cost-sweep", "updated_ts": 1780874843 }
```

- `UserPromptSubmit` fires at turn-start → `hook_writer.py` sets `status: working`.
- `Stop` / `StopFailure` fires at turn-end → sets `status: idle`.
- Overwritten each turn; only the latest state survives.
- `hook_writer.py` also delivers queued menubar messages from `msg_queue.json` on Stop (separate feature, same handler).

This file is the single authoritative "is session X working or idle" source. The
menubar reads it; `worker-cli status` reads the same file. When the project says
"worker-cli orients on the menubar," it means THIS file — not the safety-hook
fire log.

## Naming collision (the trap)

`hooks.json` (activity state) ⟂ `src/hooks/` (safety scripts) ⟂ `hook_firing.jsonl`
(safety fire log). Three "hook" names, two unrelated systems. The activity state
file predates the `src/hooks/` safety suite's naming and was never renamed.

## Convention going forward

- **"Tool-Hooks"** = `PreToolUse`/`PostToolUse` safety scripts in `src/hooks/` → `hook_firing.jsonl`.
- **"Activity-Hooks"** = `UserPromptSubmit`/`Stop`/`StopFailure` handler `src/menubar/hook_writer.py` → state file `hooks.json`.
- **"hooks.json"** unqualified = the activity state file. The safety fire log is always called by its full name `hook_firing.jsonl`.

## Surfaced in

Session investigating `worker-cli status` returning `unknown`: worker-cli reads
the activity `hooks.json` for status, broke when the menubar's app-support dir was
renamed (`com.brunowinter.monitor_cc_menubar` → `monitor-cc-menubar`) and worker-cli
kept the old underscore path. Root cause is path divergence in the activity-hook
system, entirely unrelated to the `src/hooks/` safety system.
