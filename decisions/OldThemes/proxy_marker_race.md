# Proxy Marker Race — Investigation & Fix

## Symptom

After a proxy restart while a previous session's log mtime is < 60s, the monitor's proxy pane
permanently shows "No API requests logged yet". Observed live 2026-06-10 ~00:54.

Read side: `parse_proxy_log_forwarded()` (`src/proxy_display/forwarded_parser.py`) resolves
`log_id` from marker line 2. Missing marker → falls back to `log_id = session_id` →
nonexistent file → graceful empty return → pane blind forever.

## Race Timeline (verified in `src/claude_proxy_start.sh` pre-fix)

**Session IDs:** old = `opus_monitor_cc_1781033215`, new = `opus_monitor_cc_1781045499`

1. 00:50 — Session A writes last log entry. Marker on disk: `port_A / log_id_A`.
2. 00:51 — Session B starts. Write-guard (lines ~73-86): `existing_log` mtime < 60s →
   `MARKER_IS_STALE=false` → B does NOT write its own log_id. Marker still points to A.
3. 00:54 — Session A exits. Cleanup (lines ~262-268): `marker_log_id == LOG_ID` (A's) → `rm -f`
   MARKER_FILE. Cleanup (lines ~274-278): `marker_port == PROXY_PORT` (A's port still in TMP_MARKER
   because B never claimed it) → `rm -f` TMP_MARKER.
4. Result: both markers deleted. Session B running, no marker. Pane blind forever.

**Root cause:** the write-once-at-start design + mtime-only staleness check cannot distinguish
"parallel session is alive" from "session is dying but its log is still fresh". The guard needs a
direct liveness signal, not a proxy (mtime).

## Alternatives Considered

### Alt 1: log mtime guard with longer window (e.g. 300s)
Rejected: doesn't fix the race, only widens it. A restart after 5 minutes would still corrupt the
marker. The problem is structural, not a threshold tuning issue.

### Alt 2: port-listening check (the original pre-mtime design)
Retired for documented reason (comment lines 71-72 in pre-fix script): port reuse by an unrelated
mitmdump of another project produced false-positive "fresh" reads. Cannot re-introduce.

### Alt 3: PID liveness via kill -0 only (initial plan, rejected by Opus review)
`kill -0 $PID` checks process existence but not identity. A recycled PID from an unrelated process
(e.g. a new `sleep`, new bash shell) passes kill-0 and would keep the guard in "not stale" state
permanently — the same class of false-positive as the retired port-reuse guard.

### Alt 4 (chosen): PID + process-identity + heartbeat reclaim
See "Chosen Mechanism" below.

## Chosen Mechanism

**Three components, all in `src/claude_proxy_start.sh`:**

### 1. `_proxy_pid_is_live()` function

```bash
_proxy_pid_is_live() {
    kill -0 "$pid" 2>/dev/null || return 1
    cmd=$(ps -p "$pid" -o args= 2>/dev/null)
    case "$cmd" in
        *claude_proxy_start.sh*) return 0 ;;
        *) return 1 ;;
    esac
}
```

Primary gate: `kill -0` (quick). Secondary gate: `ps -o args=` identity check. An unrelated process
with a recycled PID fails the identity check → correctly treated as stale.

### 2. Marker format extended with owner PID

| File | Pre-fix | Post-fix |
|---|---|---|
| `src/logs/.proxy_session_<sid>` | port / log_id | port / log_id / **pid** |
| `/tmp/.monitor_cc_proxy_<sid>` | port / log_id / root | port / log_id / root / **pid** |

Read side (`forwarded_parser.py`) reads `lines[1]` for log_id — unchanged. Backward-compatible.
Old markers (no PID line): write guard falls back to mtime-only for safe rollout.

### 3. Write guard: PID+identity primary, mtime secondary

```
if PID present in marker:
    if _proxy_pid_is_live(PID):
        if log_mtime < 60s: MARKER_IS_STALE=false  # belt-and-suspenders
    else: stale (PID dead or unrelated)
else (old format): mtime-only fallback
```

### 4. Background heartbeat (every 10s)

After `mitmdump &`, spawns `_marker_heartbeat &`. Loop: check proxy alive (plain kill-0 on OWN
process — no reuse risk), then read marker PID, call `_proxy_pid_is_live`. If dead/unrelated/missing
→ write own port+log_id+`$$` to marker. `$$` in background bash subshell = parent shell's PID
(bash spec: `$$` in subshell = invoking PID — consistent with cleanup's `$$` comparison).

Max blindness after primary exits: 10s (one heartbeat interval).

### 5. Cleanup guard: PID ownership

Old: `rm if marker_log_id == LOG_ID` (MARKER_FILE) and `rm if marker_port == PROXY_PORT` (TMP).
New: `rm if marker_pid (line 3 / line 4) == $$`.

A parallel session that reclaimed the marker via heartbeat will have its own PID on line 3/4 →
exiting session's cleanup skips the rm → reclaiming session's marker is preserved. ✓

## Robustness Table

| Scenario | Pre-fix | Post-fix |
|---|---|---|
| Restart within 60s | Blind forever | ≤10s blind (heartbeat reclaims) |
| Restart after crash (kill-9) | Blind forever | 0s blind (dead PID → immediate claim at startup) |
| Parallel sessions — no clobber | Correct (mtime guard) | Correct (PID alive + identity) |
| Port reuse by unrelated mitmdump | Fixed before this work | N/A (guard is PID-based) |
| PID reuse by unrelated process | BUG (kill-0 alone) | Fixed (identity check) |
| Old marker format (no PID) | Current behavior | Mtime-only fallback (safe rollout) |

## Probe Results

`dev/proxy/marker_race_repro.sh` — all 12 scenarios pass:

```
PASS  S1: dead PID + fresh log → stale (fixed)
  [evidence] pre-fix mtime-only check: log age 0s < 60s → would return 'live' (BUG)
PASS  S2: alive clone + fresh log → live (no clobber)
PASS  S2: _proxy_pid_is_live(clone) = true
PASS  S2b: after clone dies, same marker → stale (heartbeat trigger)
PASS  S3: dead PID + stale log → stale
PASS  S4 setup: unrelated process is alive (kill-0 passes)
PASS  S4: _proxy_pid_is_live(unrelated) = false (identity mismatch)
PASS  S4: fixed guard — alive recycled PID + fresh log → stale
  [evidence] pre-fix kill-0-only guard: process alive, log fresh → would return 'live' (BUG)
PASS  S5a: missing marker → reclaimed
PASS  S5a: reclaimed marker has our PID
PASS  S5b: dead PID in marker → reclaimed
PASS  S5c: alive primary in marker → kept (no clobber)
Results: 12 passed, 0 failed
```

## Files Changed

- `src/claude_proxy_start.sh` — `_proxy_pid_is_live()`, write guards, heartbeat, cleanup
- `dev/proxy/marker_race_repro.sh` — repro probe (NEW)
- `decisions/OldThemes/proxy_marker_race.md` — this file (NEW)
- `decisions/pipe05_proxy_cache.md` — Marker Lifecycle IST section added
