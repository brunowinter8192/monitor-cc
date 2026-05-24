# Menubar Session Status Detection

## Status Quo (IST)

Session status detection in `src/menubar/` uses separate logic for Workers vs Mains.

**Workers** (tmux sessions, `discover.py` + `proc_cache.py`):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prevents prefix false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Alive fallback (cwd unreadable from JSONL): `ALIVE_WINDOW_SECS=3600s` JSONL age guard.
- **Status — Hook-based with stale-demote** (`APP_SUPPORT/hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. No entry or stale → `idle`. If `status == working` AND `(now - jsonl_mtime) > WORKING_THRESHOLD_SECS (10s)` → demote to `idle` (covers context-limit-hit workers and crashed workers where Stop-hook never fired). `UserPromptSubmit` sets working from T=0; `Stop`/`StopFailure` set idle immediately.
- **Auto-abort** (`app.py:_auto_abort_check`): every tick, if ALL workers of a project are idle (post-demote AND signal-grace not active) AND that project has an active bg sleep timer → 5s debounce (`_all_workers_idle_since_ts[project_name]`) → `_abort_bg_sleep_timers`. A worker is treated as working (blocking the all_idle check) when either (a) hook status is working post-demote OR (b) iterative-dev wrote an orchestrator-signal for its `tmux_session_name` within `ORCHESTRATOR_SIGNAL_BUFFER_SECS` (60s). Signal-grace covers send-event AND spawn-event (Fix A). Any worker returning to working resets the debounce. `'unknown'`-attributed timers excluded. Projects with no workers excluded (`bool([])` guard). All abort decisions logged to `/tmp/menubar-abort.log` (always-on, no env-var gate).
- worker-cli status detection (`iterative-dev/src/spawn/tmux_spawn.sh:_worker_detect_status`) reads the same hooks.json with the same demote rule — single source of truth for worker status across menubar and CLI.

**Mains** (Ghostty terminals, `discover.py` + `proc_cache.py`):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600s`.
- **Priority 1 — Hook state** (`APP_SUPPORT/hooks.json`): `session_id` == JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. `UserPromptSubmit` sets working from T=0 (captures thinking phase); `Stop`/`StopFailure` set idle immediately. No heuristic lag.
- **Priority 2 — JSONL mtime** (fallback when hooks absent/stale): `(now - jsonl_mtime) ≤ WORKING_THRESHOLD_SECS=10s` = working. TTY mtime removed (cursor blinks caused stuck-at-working).
- **Priority 3 — Proxy override** (fallback): `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → working. Proxy writes at the START of the reasoning phase, staying ahead for the full thinking duration. After response completion the proxy latency entry lands ~0.1s before CC writes JSONL, so `proxy_mtime` drops just below `jsonl_mtime` — no false positive.
- TTY used only for click-to-focus UUID lookup via `_cc_proc_cache`; not used for working detection.
- **Auto-focus**: on `working → idle` transition with `has_bg=False`, `_focus_session(cwd)` fires after a 3s debounce (`_idle_since_ts` dict).

**Key thresholds** (all in `proc_cache.py` / `discover.py`):

| Constant | Value | Purpose |
|---|---|---|
| `ALIVE_WINDOW_SECS` | 3600s | JSONL age guard for alive check; hook stale guard |
| `WORKING_THRESHOLD_SECS` | 10s | Priority-2 JSONL-mtime window |
| `THINKING_OVERRIDE_MAX_SECS` | 300s | Priority-3 proxy-mtime max lag |
| auto-abort debounce | 5s | `_all_workers_idle_since_ts` → `_abort_bg_sleep_timers` |
| `ORCHESTRATOR_SIGNAL_BUFFER_SECS` | 60s | signal-grace window — workers with recent worker-cli send/spawn signal treated as working for auto-abort |
| auto-focus debounce | 3s | `_idle_since_ts` → `_focus_session` |

## Evidenz

No measurement eval. IST is the production behavioral specification derived from code inspection.

## Recommendation (SOLL)

Pending — no eval of detection accuracy vs alternative threshold values.

## Offene Fragen

- WORKING_THRESHOLD_SECS=10s: is this too short for heavy disk I/O sessions where JSONL write lags?
- THINKING_OVERRIDE_MAX_SECS=300s: any sessions where thinking >300s causes premature idle display?

## Quellen

None.
