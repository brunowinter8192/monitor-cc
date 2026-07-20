# kill-guard live failure — CC hook execution env has a stripped PATH

**Date:** 2026-06-20 · **Hook:** `block_worker_kill_while_working` (pipe07 Hook 20)

## Context

The kill-while-working guard blocks `worker-cli kill <name>` when the worker is `working`. Decision logic (double-gate): regex-capture the kill name, then run `worker-cli status <name>` as a subprocess; block iff the status output's first token is exactly `working`. Smoke (13 cases) and standalone tests (piping crafted JSON payloads to the script) all passed. But LIVE — running `worker-cli kill <working-worker>` through CC's hook system — it did NOT block; the kill went through.

## The wrong turn — "reload" hypothesis (stated as proof, then refuted)

First conclusion, wrongly presented as "eindeutig bewiesen": *CC loads hooks at session start; the kill-guard was added to `settings.json` mid-session by the post-merge installer, so it isn't active in the running session.* This was inferred only from "an EXISTING hook (`block_dangerous_kill`) fires, the new one doesn't" — a hypothesis dressed as a conclusion.

**Refuted** by building `block_manual_worker_cleanup` (also added mid-session) and testing it immediately → it FIRED on the very next command. CC loads new hooks immediately; mid-session additions are active with no restart. (`src/hooks/DOCS.md` Gotchas already stated this: "Hooks are active immediately after settings.json is written; no CC restart needed.") Therefore the kill-guard WAS loaded for the failed kills → it had a real bug, not a reload problem.

## Hypotheses tested worker-free and refuted

| Hypothesis | Test | Result |
|---|---|---|
| PATH (from Bash tool) | `echo $PATH` has plugin bin; `subprocess.run(['worker-cli',...])` from the Bash tool | worked → **wrongly dismissed PATH** (tested the Bash-tool env, NOT the hook env) |
| cwd-dependence | `worker-cli status` from `/tmp`, `$HOME`, `/usr` | identical (`idle …`) → not cwd |
| subprocess vs direct | both from the Bash tool | identical → no subprocess artifact |

## Root cause — found by instrumentation

Temporarily instrumented `_live_worker_status` to append `(PATH, cwd, shutil.which('worker-cli'), subprocess result/exception)` to `/tmp/killguard_debug.log` on every call, then triggered a live kill of a definitely-working throwaway worker. The trace:

```
which_worker_cli: null
exception:        FileNotFoundError  ('worker-cli')
PATH:             /usr/.../homebrew/bin:/usr/bin:/bin:.local/bin:...  — NO plugin-cache bin
returned:         ""  → allow
```

**CC's hook execution environment provides a PATH that does NOT include the plugin-cache `bin/` dirs** (where `worker-cli` lives). The Bash tool's env DOES (shell-sourced `~/.zshrc`). So the hook's `subprocess.run(['worker-cli', ...])` → `FileNotFoundError` → `''` → fail-open → never blocks. Every standalone test masked this because they ran with the Bash-tool PATH.

## Fix

`_resolve_worker_cli()`: `shutil.which('worker-cli')` first, fallback glob `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/*/bin/worker-cli` (newest), `None` if unresolvable. `_live_worker_status` calls worker-cli by the resolved **absolute path**. `tmux`/`jq` (worker-cli's own deps) are on the hook PATH via homebrew, so resolving worker-cli alone is sufficient.

## Live verification (this session)

Fixed → working worker (kt3) → `worker-cli kill kt3` **BLOCKED**; idle worker (hook-docs) → kill **allowed**. Full integrated chain with the worker-cli status demote: working→blocked, ESC force-stop→status shows idle (demote), idle→kill allowed.

## Lessons

1. **Hook env ≠ Bash-tool env.** CC hook subprocesses get a stripped PATH (no `~/.local/bin`, no plugin-cache bins). Any subprocess-hook invoking a plugin CLI MUST resolve it by absolute path (`shutil.which` + plugin-cache glob), never by bare name — else `FileNotFoundError` → fail-open → the hook silently never fires. Captured as a `src/hooks/DOCS.md` Gotcha + a Hook 20 note in `pipe07_safety_hooks.md`.
2. **Instrument the actual execution context.** The PATH hypothesis was raised early, dismissed on Bash-tool evidence, and only in-hook instrumentation proved it. Don't assume the Bash tool's environment equals the hook's.
3. **Hypothesis ≠ Conclusion.** The "reload" claim was asserted as proof; a pure-regex differential hook (`block_manual_worker_cleanup`) refuted it in one test.

## Cross-references

- `decisions/pipe07_safety_hooks.md` — Hook 20 (Hook-env PATH gotcha), Hook 31 (`block_manual_worker_cleanup`, the differential probe)
- `src/hooks/DOCS.md` — Gotchas: subprocess hooks resolve plugin CLIs by absolute path
