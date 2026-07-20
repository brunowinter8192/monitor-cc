# Timer-Guard Redesign — "only one timer at a time" (2026-07-20)

Redesign of the PreToolUse Bash hook that guards background sleep-timers, replacing a worker-cli-adjacency proxy with a direct one-timer-at-a-time check.

## Prior design (as of before 2026-07-20)
`src/hooks/block_background_sleep_nonworker.py` allowed a background sleep-timer (`run_in_background=true` + `_SLEEP_ONLY_BG` match) ONLY if the immediately preceding non-timer Bash command in the session was a `worker-cli` call. It tracked one last-command per session in `src/logs/last_cmd_state.jsonl` and blocked otherwise, on the rationale that the only legitimate timer is the worker-wait poll loop where each timer directly follows `worker-cli spawn/status/send`.

## Problem observed (2026-07-20)
The adjacency check false-positive-blocked the canonical poll loop. Repro during a live orchestration session: after `worker-cli status <name>`, the orchestrator reviewed the working worker's already-committed areas with read-only `git log` / `git diff` commands (early cross-model review), then set the 10-min poll timer. By then the recorded "last command" was `git diff`, not `worker-cli`, so the legitimate timer was blocked with "Go idle immediately …". Interleaving any read-only orchestration command between the worker-cli call and the timer triggered the block.

Root cause: the hook proxied "is this timer legitimate?" through worker-cli adjacency, but the actual intent was narrower — prevent a SECOND timer while one is already running (runaway/duplicate timers). Adjacency was the wrong signal; interleaved review is normal orchestration.

## Redesign
Renamed `block_background_sleep_nonworker.py` → `src/hooks/block_concurrent_timer.py`. New logic:
- On a canonical-timer request, compute `expiry = now + 600s`. The 600s is hardcoded, not parsed from the command: `src/hooks/rewrite_background_sleep.py` silently normalizes every background sleep-timer to exactly `sleep 600 && echo done`, so every timer is 600s.
- Track per-session timer expiry in `src/logs/timer_state.jsonl` (one entry per session, 24h prune by write-ts). If a stored expiry exists AND `now < stored_expiry` → BLOCK (a timer is still running). Else → record the new expiry and ALLOW.
- Non-timer commands are ignored entirely (no state write). Fail-open (exit 0) on any state-file IO/parse error.

The whole worker-cli / last-command / `_shell_strip` machinery was dropped. State file + env var renamed `last_cmd_state.jsonl`/`MONITOR_CC_LAST_CMD_STATE` → `timer_state.jsonl`/`MONITOR_CC_TIMER_STATE`.

Why this fixes it: the check no longer cares what commands ran between the poll and the timer — only whether a timer is currently live. The canonical loop (status → timer(600) → wake at +600 → status → timer(600)) always passes because each new timer is set only after the previous expired. Only a genuine second timer set while the first still counts down is blocked. Sibling guards `block_busywait_loop.py` (while/until sleep-loops) and `block_unauthorized_background.py` (non-canonical background) remain and still cover real abuse.

## Accepted edge case
An interrupted timer (turn aborted before the background sleep completes) leaves a stale future expiry with no live sleep process → the next timer for that session is wrongly blocked until the recorded expiry passes (≤ 10 min). Accepted as rare and low-impact; the alternative (pgrep-verify a live sleep process) was rejected to keep the hook self-contained and off the process table.

## Verification (2026-07-20)
- Live, post-merge: `~/.claude/settings.json` synced by the post-merge `hook_setup.py` run — old hook name 0 occurrences, new hook 1. Live stdin test: first timer for a session → exit 0; second concurrent timer same session → exit 2 with "A background timer is already running … expires <ts> …".
- Regression test `dev/hook_smoke/test_block_concurrent_timer.py`: 7/7 cases (first-allow, second-same-session-block, different-session-independent, non-timer no-op + no state write, expired-timer allow, IO-error fail-open).
- `hook_setup._sweep_stale_hooks` removes the stale old-name settings entry automatically on the next installer run (path no longer exists after the rename).
