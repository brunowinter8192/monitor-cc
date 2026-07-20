# Menubar Session Status Detection

## Status Quo (IST)

Session status detection in `src/menubar/` uses separate logic for Workers vs Mains.

**Workers** (tmux sessions, `discover.py` + `proc_cache.py`):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prevents prefix false positives.
- Session name reconstructed from worker JSONL cwd: partition on `/.claude/worktrees/` → `project_path` (left) and `worktree_rest` (right). **Worker name** = `worktree_rest.split('/')[0]` — the first path component after the marker. This is stable even when the worker `cd`s into subdirectories of its worktree (JSONL `cwd` drifts, but the first component is always the worktree leaf). `os.path.basename(cwd)` was previously used but is WRONG for drifted cwds: yields the innermost subdir name instead of the worktree name → wrong tmux session → worker dropped. `SessionInfo.name` (display) uses the same first-component value. NOT from the `~/.claude/projects/` encoded-dir name: `encode_project_path` replaces `_` with `-` (lossy); encoded-dir-derived names corrupt underscores → tmux name mismatch.
- **`project_name` (group-header)** (`discover.py:_process_project_dir`): `project_name = os.path.basename(project_path) or project_name` — `project_path` is the left side of the `/.claude/worktrees/` partition, computed once and reused. Set inside the `if cwd and '/.claude/worktrees/' in cwd:` block. Overrides the `_decode_dir_name` value from `_classify_encoded_dir`. Ensures the header matches the live project dir name.
- Alive fallback (cwd unreadable from JSONL): `ALIVE_WINDOW_SECS=3600s` JSONL age guard; display name and `project_name` fall back to lossy encoded-dir decode (no tmux check in this branch, so mismatch is moot).
- **Status — Hook-based with window_activity stale-demote** (`APP_SUPPORT/hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. No entry or stale → `idle`. If `status == working` AND `tmux_session` is non-empty: query `tmux display-message -t {session}:^ -p '#{window_activity}'` → `wa_age = now - window_activity`. If `wa == 0` or `wa_age > WORKING_THRESHOLD_SECS (10s)` → demote to `idle`. Rationale: CC writes JSONL only on assistant-message completion; long thinking phases (Caramelizing/Concocting) keep JSONL mtime stale for minutes. `window_activity` is bumped by every pane byte-write (spinner ticks ~1/sec, streaming chunks) → stays fresh through thinking phases. Empirically: 98.3% detection on working sessions, 0% false positives on idle (see Evidenz). If `tmux_session` is empty (cwd-unavailable fallback), demote is skipped. `UserPromptSubmit` sets working from T=0; `Stop`/`StopFailure` set idle immediately.
- **Auto-abort** (`app.py:_auto_abort_check`): every tick, if ALL workers of a project are idle (post-demote AND signal-grace not active) AND that project has an active bg sleep timer → 5s debounce (`_all_workers_idle_since_ts[project_name]`) → `_abort_bg_sleep_timers`. A worker is treated as working (blocking the all_idle check) when either (a) hook status is working post-demote OR (b) iterative-dev wrote an orchestrator-signal for its `tmux_session_name` within `ORCHESTRATOR_SIGNAL_BUFFER_SECS` (60s). Signal-grace covers send-event AND spawn-event (Fix A). Any worker returning to working resets the debounce. `'unknown'`-attributed timers excluded. Projects with no workers excluded (`bool([])` guard). All abort decisions logged to `src/logs/menubar.log` ([abort] category, always-on, no env-var gate).
- worker-cli status detection (`iterative-dev/src/spawn/tmux_spawn.sh:_worker_detect_status`) uses the identical sensor and threshold — single source of truth for worker status across menubar and CLI.

**Mains** (Ghostty terminals, `discover.py` + `proc_cache.py`):
- Alive iff a live `claude` process exists for the session (`_proc_cwd_for_encoded_dir` returns non-None). JSONL age is NOT used for aliveness — a pre-proc-check holdover (`ALIVE_WINDOW_SECS=3600s` drop) was removed because it incorrectly dropped idle-but-alive mains with JSONL older than 1h. `ALIVE_WINDOW_SECS` is retained for hook staleness checks and the worker cwd-unavailable fallback.
- **Case-insensitive encoded-dir matching** (`_proc_cwd_for_encoded_dir` in `discover.py`): comparison uses `.lower()` on both sides — `encode_project_path(proc_cwd).lower() == encoded_dir.lower()`. Required because `~/.claude/projects/` dir names retain the case at creation time (e.g. `-Users-...-Monitor-CC`), while `encode_project_path` on the live process cwd reflects the current filesystem name (`monitor-cc` → `-Users-...-monitor-cc`). macOS FS is case-insensitive so the dir was never physically renamed; the old case persists. Same pattern used in `matches_project_filter()` (`src/session_finder.py`).
- **`project_name` (group-header) from live cwd basename** (`discover.py:_process_project_dir`): `project_name = os.path.basename(proc_cwd.rstrip('/'))` — set immediately after `proc_cwd` confirmed non-None. Overrides the `_decode_dir_name` value from `_classify_encoded_dir`. Proxy key derived as `project_name.lower().replace('-','_')` → `monitor_cc` unchanged (`.lower()` already neutralised the case difference pre-fix).
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

Worker stale-demote sensor selection — three-option probe (`window_activity` vs JSONL mtime vs TTY mtime):
- Script: `dev/worker_status_probes/` suite
- Report: `dev/worker_status_probes/01_reports/comparison_20260524_183937.md`
- Dataset: ccwrap-phase1 worker session (idle) + status-probe worker session (idle); manually-observed working phases

| Sensor | Working detection | False-positive rate (idle) | Notes |
|---|---|---|---|
| `window_activity` | 98.3% | 0% (300+ idle-session-secs) | Spinner ticks keep it fresh during thinking phases |
| JSONL mtime | ~60% | 0% | Stale during long thinking (CC writes JSONL only on message completion) |
| TTY mtime | 100% | ~30% | Cursor blinks bump TTY mtime → stuck-at-working on idle sessions |

Decision: `window_activity` wins on both axes. Empirically refuted the prior "cursor blinks bump window_activity" concern — cursor blinks do NOT touch window_activity. `window_activity` is updated only on actual pane output (byte writes to the PTY), not on cursor rendering.

## Recommendation (SOLL)

Pending — no eval of detection accuracy vs alternative threshold values.

## Offene Fragen

- WORKING_THRESHOLD_SECS=10s: is this too short for heavy disk I/O sessions where JSONL write lags?
- THINKING_OVERRIDE_MAX_SECS=300s: any sessions where thinking >300s causes premature idle display?

## Quellen

None.
