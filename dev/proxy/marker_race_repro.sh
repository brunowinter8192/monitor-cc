#!/bin/bash
# dev/proxy/marker_race_repro.sh
# Deterministic repro probe for proxy marker lifecycle race conditions.
#
# _proxy_pid_is_live() is sourced from the real claude_proxy_start.sh (no logic duplication).
# _is_stale() in this probe mirrors the inline write-guard logic in the real script and calls
# _proxy_pid_is_live as its primary check — it is test harness, not duplicated production code.
#
# Scenarios:
#   S1: restart-within-60s      dead PID + fresh log  → must be stale   (pre-fix mtime-only: live = BUG)
#   S2: parallel session        alive clone + fresh    → must be live    (no clobber)
#   S2b: clone dies             same marker, dead PID  → now stale       (heartbeat reclaim trigger)
#   S3: crash / kill-9          dead PID + stale log   → must be stale
#   S4: PID-reuse (new)         alive unrelated PID    → must be stale   (pre-fix kill-0 only: live = BUG)
#   S5a: heartbeat, missing     marker absent          → reclaims
#   S5b: heartbeat, dead PID    dead PID in marker     → reclaims
#   S5c: heartbeat, live owner  alive clone in marker  → keeps (no clobber)
#
# Usage (from project root):
#   bash dev/proxy/marker_race_repro.sh
#
# Exit: 0 if all PASS, 1 if any FAIL.

PASS=0; FAIL=0

check() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        printf "PASS  %s\n" "$desc"
        PASS=$((PASS + 1))
    else
        printf "FAIL  %s\n      expected: '%s'  got: '%s'\n" "$desc" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

# ── Source _proxy_pid_is_live from the real script ─────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROXY_SCRIPT="$REPO_ROOT/src/claude_proxy_start.sh"
[ -f "$PROXY_SCRIPT" ] || { echo "ERROR: $PROXY_SCRIPT not found"; exit 1; }

# Extract the function block (awk range: header → closing brace at column 0)
eval "$(awk '/^_proxy_pid_is_live\(\)/,/^}/' "$PROXY_SCRIPT")"
type _proxy_pid_is_live > /dev/null 2>&1 \
    || { echo "ERROR: failed to load _proxy_pid_is_live from $PROXY_SCRIPT"; exit 1; }
echo "Loaded _proxy_pid_is_live from $(basename "$PROXY_SCRIPT")"

# ── Test environment ───────────────────────────────────────────────────────────────────────
TMP_ROOT="$(mktemp -d)"
CLEANUP_PIDS=()
trap 'kill "${CLEANUP_PIDS[@]}" 2>/dev/null; wait "${CLEANUP_PIDS[@]}" 2>/dev/null; rm -rf "$TMP_ROOT"' EXIT

LOG_DIR="$TMP_ROOT/logs"
mkdir -p "$LOG_DIR/dual_log"
MARKER="$TMP_ROOT/.proxy_session_test"

# Create a fake forwarded log with controllable mtime
_make_log() {
    local id="$1" age_s="${2:-0}"
    local f="$LOG_DIR/dual_log/api_requests_${id}_forwarded.jsonl"
    echo '{"type":"forwarded_delta"}' > "$f"
    if [ "$age_s" -gt 0 ]; then
        local ts
        ts=$(date -v -${age_s}S +%Y%m%d%H%M.%S 2>/dev/null \
             || date -d "${age_s} seconds ago" +%Y%m%d%H%M.%S 2>/dev/null)
        touch -t "$ts" "$f" 2>/dev/null || true
    fi
}

# Simulate write-guard staleness decision (mirrors inline guard in claude_proxy_start.sh).
# Calls _proxy_pid_is_live (sourced from real script) as primary check.
_is_stale() {
    local marker="$1"
    [ -f "$marker" ] || { echo stale; return; }
    local log_id pid
    log_id=$(sed -n '2p' "$marker" 2>/dev/null)
    pid=$(sed -n '3p' "$marker" 2>/dev/null)
    [ -n "$log_id" ] || { echo stale; return; }
    if [ -n "$pid" ]; then
        _proxy_pid_is_live "$pid" || { echo stale; return; }
        local log="$LOG_DIR/dual_log/api_requests_${log_id}_forwarded.jsonl"
        [ -f "$log" ] || { echo stale; return; }
        local mtime now
        mtime=$(stat -f %m "$log" 2>/dev/null || stat -c %Y "$log" 2>/dev/null)
        now=$(date +%s)
        [ -n "$mtime" ] && [ $((now - mtime)) -lt 60 ] && { echo live; return; }
        echo stale
    else
        # Old format: mtime-only fallback
        local log="$LOG_DIR/dual_log/api_requests_${log_id}_forwarded.jsonl"
        [ -f "$log" ] || { echo stale; return; }
        local mtime now
        mtime=$(stat -f %m "$log" 2>/dev/null || stat -c %Y "$log" 2>/dev/null)
        now=$(date +%s)
        [ -n "$mtime" ] && [ $((now - mtime)) -lt 60 ] && { echo live; return; }
        echo stale
    fi
}

# Simulate heartbeat reclaim decision (mirrors _marker_heartbeat body in claude_proxy_start.sh).
_heartbeat_check() {
    local marker="$1" our_pid="$2" our_port="$3" our_log_id="$4"
    local m_pid
    m_pid=$(sed -n '3p' "$marker" 2>/dev/null)
    if ! _proxy_pid_is_live "$m_pid"; then
        printf "%s\n%s\n%s\n" "$our_port" "$our_log_id" "$our_pid" > "$marker"
        echo reclaimed
    else
        echo kept
    fi
}

# Find a reliably dead PID (high range, validate)
_dead_pid() {
    local p
    for p in 99999 99998 99997 99996; do
        kill -0 "$p" 2>/dev/null || { echo "$p"; return; }
    done
    # Fallback: start and immediately reap a subprocess
    sleep 0 &
    local pid=$!
    wait $pid 2>/dev/null
    echo $pid
}
DEAD_PID=$(_dead_pid)

# ── S1: restart-within-60s ─────────────────────────────────────────────────────────────────
# Symptom scenario: old session dead, log fresh (within 60s). Pre-fix mtime-only guard
# returns "live" (bug). Fixed guard sees dead PID → stale → new session claims.
echo ""
echo "── S1: restart-within-60s (dead PID, fresh log) ──"
LOG_S1="opus_test_s1_$(date +%s)"; _make_log "$LOG_S1" 0
printf "8080\n%s\n%s\n" "$LOG_S1" "$DEAD_PID" > "$MARKER"

check "S1: dead PID + fresh log → stale (fixed)" stale "$(_is_stale "$MARKER")"

# Document the pre-fix bug: mtime-only check would have returned "live"
_mtime=$(stat -f %m "$LOG_DIR/dual_log/api_requests_${LOG_S1}_forwarded.jsonl" 2>/dev/null \
         || stat -c %Y "$LOG_DIR/dual_log/api_requests_${LOG_S1}_forwarded.jsonl" 2>/dev/null)
_age=$(( $(date +%s) - _mtime ))
[ "$_age" -lt 60 ] && echo "  [evidence] pre-fix mtime-only check: log age ${_age}s < 60s → would return 'live' (BUG)"

# ── S2: parallel session (alive clone, no clobber) ────────────────────────────────────────
# A second session starts while first is alive. Must defer (not clobber).
echo ""
echo "── S2: parallel session (alive claude_proxy_start.sh PID, fresh log) ──"
LOG_S2="opus_test_s2_$(date +%s)"; _make_log "$LOG_S2" 0

# Spawn process with argv[0]=claude_proxy_start.sh (exec -a sets argv[0] without launching the real script)
bash -c 'exec -a claude_proxy_start.sh sleep 30' &
CLONE_PID=$!; CLEANUP_PIDS+=($CLONE_PID)
sleep 0.2  # allow exec to complete

printf "8080\n%s\n%s\n" "$LOG_S2" "$CLONE_PID" > "$MARKER"
check "S2: alive clone + fresh log → live (no clobber)" live "$(_is_stale "$MARKER")"
check "S2: _proxy_pid_is_live(clone) = true" "0" "$(_proxy_pid_is_live "$CLONE_PID" && echo 0 || echo 1)"

# ── S2b: clone dies → heartbeat reclaim ───────────────────────────────────────────────────
kill $CLONE_PID 2>/dev/null; wait $CLONE_PID 2>/dev/null || true
# Remove from CLEANUP_PIDS (already dead) — bash arrays: rebuild without it
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$CLONE_PID}")
sleep 0.1

check "S2b: after clone dies, same marker → stale (heartbeat trigger)" stale "$(_is_stale "$MARKER")"

# ── S3: crash / kill-9 (no cleanup, stale log) ───────────────────────────────────────────
echo ""
echo "── S3: crash / kill-9 (dead PID, stale log >60s) ──"
LOG_S3="opus_test_s3_$(date +%s)"; _make_log "$LOG_S3" 120
printf "8080\n%s\n%s\n" "$LOG_S3" "$DEAD_PID" > "$MARKER"
check "S3: dead PID + stale log → stale" stale "$(_is_stale "$MARKER")"

# ── S4: PID-reuse by unrelated process (Opus amendment) ──────────────────────────────────
# The old kill-0-only guard has the same false-positive class as the retired port-reuse guard:
# an alive but unrelated process with a recycled PID passes kill-0 and causes permanent deferral.
# New identity check (ps args must contain claude_proxy_start.sh) correctly rejects it.
echo ""
echo "── S4: PID-reuse — alive unrelated process (not claude_proxy_start.sh) ──"
LOG_S4="opus_test_s4_$(date +%s)"; _make_log "$LOG_S4" 0

sleep 30 &
UNRELATED_PID=$!; CLEANUP_PIDS+=($UNRELATED_PID)
sleep 0.1

printf "8080\n%s\n%s\n" "$LOG_S4" "$UNRELATED_PID" > "$MARKER"

# Confirm the process IS alive (kill -0 would pass — that's the bug)
kill -0 "$UNRELATED_PID" 2>/dev/null && ALIVE=yes || ALIVE=no
check "S4 setup: unrelated process is alive (kill-0 passes)" yes "$ALIVE"
check "S4: _proxy_pid_is_live(unrelated) = false (identity mismatch)" "1" \
    "$(_proxy_pid_is_live "$UNRELATED_PID" && echo 0 || echo 1)"
check "S4: fixed guard — alive recycled PID + fresh log → stale" stale "$(_is_stale "$MARKER")"
echo "  [evidence] pre-fix kill-0-only guard: process alive, log fresh → would return 'live' (BUG)"

kill $UNRELATED_PID 2>/dev/null; wait $UNRELATED_PID 2>/dev/null || true
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$UNRELATED_PID}")

# ── S5: heartbeat reclaim logic ───────────────────────────────────────────────────────────
echo ""
echo "── S5: heartbeat reclaim (mirrors _marker_heartbeat body) ──"
LOG_S5="opus_test_s5"; OUR_PID="$$"; PORT_S5=18080

# S5a: marker missing → reclaim
rm -f "$MARKER"
check "S5a: missing marker → reclaimed" reclaimed "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"
reclaimed_pid=$(sed -n '3p' "$MARKER" 2>/dev/null)
check "S5a: reclaimed marker has our PID ($$)" "$OUR_PID" "$reclaimed_pid"

# S5b: marker has dead PID → reclaim
printf "8080\n%s\n%s\n" "$LOG_S5" "$DEAD_PID" > "$MARKER"
check "S5b: dead PID in marker → reclaimed" reclaimed "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"

# S5c: marker has alive clone → keep (don't clobber live primary)
bash -c 'exec -a claude_proxy_start.sh sleep 30' &
LIVE2_PID=$!; CLEANUP_PIDS+=($LIVE2_PID)
sleep 0.2
printf "8080\n%s\n%s\n" "$LOG_S5" "$LIVE2_PID" > "$MARKER"
check "S5c: alive primary in marker → kept (no clobber)" kept "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"
kill $LIVE2_PID 2>/dev/null; wait $LIVE2_PID 2>/dev/null || true
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$LIVE2_PID}")

# ── Summary ───────────────────────────────────────────────────────────────────────────────
echo ""
printf "Results: %d passed, %d failed\n" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
