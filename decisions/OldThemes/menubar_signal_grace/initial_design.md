# Menubar Auto-Abort — Signal-Based Grace + Hook Cache Split

## Two Observed Bugs (2026-05-24)

### Bug 1 — worker-cli false-working

`worker-cli status <name>` reports `working` while the worker is actually idle (hook state shows `idle`, CC has fired `Stop`). Symptom seen during a session where the menubar correctly displayed idle and aborted the timer, but `worker-cli status` simultaneously returned `working`.

Source: `iterative-dev/src/spawn/tmux_spawn.sh:_worker_detect_status` uses tmux `window_activity` with a 10s threshold. The heuristic assumes that an idle CC pane produces no output. In practice CC writes UI elements (spinner frames, status footers, cursor refreshes) that bump `window_activity` even when CC is between turns. The 10s threshold catches some but not all of these — false-working is intermittent.

### Bug 2 — menubar abort fires after prompt-send

After `worker-cli send <name> <prompt>`, the menubar aborted the immediately-spawned Opus background sleep timer despite the worker being in the process of starting a new turn. The abort fired ~5s after the send, before CC's `UserPromptSubmit` hook update had propagated through the menubar cache.

Root cause: `Monitor_CC/src/menubar/proc_cache.py` uses ONE constant `_PROC_REFRESH_INTERVAL = 10s` for both the expensive `ps -A` cache AND the cheap `hooks.json` cache. The hook state read by `_read_hook_state` can be up to 10s stale while CC has already written the new state. The auto-abort debounce of 5s (`app.py:_auto_abort_check`) fires within that staleness window — by the time the cache refreshes, the timer is already dead.

## Divergence — Two Status Sources

Menubar uses `hooks.json` (CC events `UserPromptSubmit`/`Stop` write to it). worker-cli uses tmux `window_activity`. These measure different signals and inevitably diverge — they cannot be reconciled by tuning thresholds.

The CC hook events are the authoritative ground truth of when CC is processing vs idle. tmux activity is a heuristic that approximates this signal indirectly via screen output. Resolution: both must read `hooks.json` to agree.

## Design Alternatives Considered

### Option A — Generic time buffer (idle → working grace)

`status_for_session(sid)` returns `working` if `entry.status == "working"` OR if `entry.status == "idle" AND now - updated_ts < BUFFER`. Buffer e.g. 10s.

Pros: simple, fully decoupled from the trigger event.
Cons: delays the true-idle detection by the buffer width. With BUFFER=10s plus 5s abort debounce, abort fires ~15s after worker is really idle. Slow.

### Option B — Send-event as explicit signal

`worker-cli send` writes a per-worker timestamp to a shared signal file BEFORE delivering the tmux keys. Menubar reads the signal file and treats workers with recent signals as `working` for abort purposes, independent of hooks.json state. After the signal expires (~5s), normal hook-based decision takes over.

Pros: send-event is the actual orchestrator intent — using it as the signal is direct, not heuristic. Buffer can be small (5s) because the signal lifecycle is bound to the orchestrator action, not to CC's hook latency. True-idle detection stays fast (~5s after Stop hook + signal expiry).

Cons: requires a coordination file shared between iterative-dev (worker-cli) and Monitor_CC (menubar). Path lives in Monitor_CC's app-support directory.

### Decision

**Option B.** Send-event-as-signal aligns the mechanism with the orchestrator's intent. Smaller buffer (5s vs 10s) means faster auto-abort on true-idle while eliminating the false-abort class.

## Implementation Design

### Signal File

Path: `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/orchestrator_signals.json`

Format:
```json
{
  "worker-RAG-refactor-cli-server": 1779576800.123,
  "worker-Monitor_CC-foo": 1779570000.0
}
```

Key: tmux session name (`worker-<project>-<worker>`).
Value: unix timestamp of last send.

### worker-cli `worker_send`

In `iterative-dev/src/spawn/tmux_spawn.sh:worker_send`, BEFORE the `tmux send-keys`, write the signal entry for this worker's tmux session name. Use atomic-rename pattern (write to `.tmp`, then `mv`) to avoid partial JSON reads by menubar.

In `worker_kill`, remove the entry on cleanup.

Old entries are pruned periodically by the menubar reader (entries > 1h old dropped on each read).

### menubar `_auto_abort_check`

Read `orchestrator_signals.json` on entry. For each worker in the project's worker set, if `now - signal[tmux_session_name] < ORCHESTRATOR_SIGNAL_BUFFER_SECS` (5s), treat that worker as `working` for the `all_idle` check.

Workers without a signal entry or with a stale signal fall through to the normal hook-state evaluation.

### Hook cache split

Separate constant in `proc_cache.py`:
- `_PROC_REFRESH_INTERVAL = 10.0` — keeps `ps -A` rebuild rate
- `_HOOK_REFRESH_INTERVAL = 1.0` — hooks.json reads (cheap, must be < POLL_INTERVAL=1.5s for tick-freshness)

`_read_hook_state` uses `_HOOK_REFRESH_INTERVAL`. The 1s TTL preserves intra-tick consistency (multiple readers in the same tick get the same snapshot) AND ensures the next tick gets fresh data.

This split is architecturally separate from the signal mechanism — it would have been the correct design even without Bug 2. The signal mechanism removes the ABORT-race; the cache split removes the DISPLAY-staleness (worker-status indicator on menubar showing wrong state for up to 10s).

## Buffer Tuning

`ORCHESTRATOR_SIGNAL_BUFFER_SECS = 5.0` chosen against:

| Latency component | Typical | Worst-case |
|---|---|---|
| `worker-cli send` → tmux delivers keys | <50ms | <200ms |
| CC reads keys → fires `UserPromptSubmit` | <300ms | ~2s (high JSONL load) |
| Hook writer → hooks.json updated | <50ms | <100ms |
| Menubar cache refresh (after Bug 2 fix) | <1s | <1.5s |
| **Total send → working in menubar** | **<500ms** | **~4s** |

5s buffer covers the worst-case with a ~1s safety margin. Below 3s gets risky on first-prompt-after-quiet-period when CC needs to load context. Above 5s adds latency to auto-abort with no marginal safety benefit.

## Cross-Project Symmetry

Both repos move in lockstep:
- **Monitor_CC** branch `menubar-signal-grace` — hook cache split + signal reader + abort skip logic + DOCS.md update
- **iterative-dev** (Meta repo, `blank/` subdir) — `worker_send` writes signal, `worker_kill` cleans up

Plugin-publish required for iterative-dev (cache stays stale otherwise). See `~/.claude/shared-rules/global/tool-use.md` § Push (PLUGIN repo).

## Bug 1 — Deferred

Worker-cli false-working (tmux window_activity unreliable) is NOT fixed in this iteration. The clean fix is to have worker-cli read hooks.json directly — same source as menubar, divergence eliminated by design. That requires session_id discovery from worktree path in bash, more complex than the signal addition. Deferred as a separate bead.

For now, after Bug 2 fix lands, the menubar is the authoritative status display. When `worker-cli status` disagrees with menubar, **menubar is correct.**
