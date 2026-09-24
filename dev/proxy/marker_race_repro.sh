#!/bin/bash

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

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROXY_SCRIPT="$REPO_ROOT/src/proxy_start_markers.sh"
[ -f "$PROXY_SCRIPT" ] || { echo "ERROR: $PROXY_SCRIPT not found"; exit 1; }

eval "$(awk '/^_proxy_pid_is_live\(\)/,/^}/' "$PROXY_SCRIPT")"
type _proxy_pid_is_live > /dev/null 2>&1 \
    || { echo "ERROR: failed to load _proxy_pid_is_live from $PROXY_SCRIPT"; exit 1; }
echo "Loaded _proxy_pid_is_live from $(basename "$PROXY_SCRIPT")"

TMP_ROOT="$(mktemp -d)"
CLEANUP_PIDS=()
trap 'kill "${CLEANUP_PIDS[@]}" 2>/dev/null; wait "${CLEANUP_PIDS[@]}" 2>/dev/null; rm -rf "$TMP_ROOT"' EXIT

LOG_DIR="$TMP_ROOT/logs"
mkdir -p "$LOG_DIR/dual_log"
MARKER="$TMP_ROOT/.proxy_session_test"

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
        local log="$LOG_DIR/dual_log/api_requests_${log_id}_forwarded.jsonl"
        [ -f "$log" ] || { echo stale; return; }
        local mtime now
        mtime=$(stat -f %m "$log" 2>/dev/null || stat -c %Y "$log" 2>/dev/null)
        now=$(date +%s)
        [ -n "$mtime" ] && [ $((now - mtime)) -lt 60 ] && { echo live; return; }
        echo stale
    fi
}

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

_dead_pid() {
    local p
    for p in 99999 99998 99997 99996; do
        kill -0 "$p" 2>/dev/null || { echo "$p"; return; }
    done
    sleep 0 &
    local pid=$!
    wait $pid 2>/dev/null
    echo $pid
}
DEAD_PID=$(_dead_pid)

echo ""
echo "── S1: restart-within-60s (dead PID, fresh log) ──"
LOG_S1="opus_test_s1_$(date +%s)"; _make_log "$LOG_S1" 0
printf "8080\n%s\n%s\n" "$LOG_S1" "$DEAD_PID" > "$MARKER"

check "S1: dead PID + fresh log → stale (fixed)" stale "$(_is_stale "$MARKER")"

_mtime=$(stat -f %m "$LOG_DIR/dual_log/api_requests_${LOG_S1}_forwarded.jsonl" 2>/dev/null \
         || stat -c %Y "$LOG_DIR/dual_log/api_requests_${LOG_S1}_forwarded.jsonl" 2>/dev/null)
_age=$(( $(date +%s) - _mtime ))
[ "$_age" -lt 60 ] && echo "  [evidence] pre-fix mtime-only check: log age ${_age}s < 60s → would return 'live' (BUG)"

echo ""
echo "── S2: parallel session (alive claude_proxy_start.sh PID, fresh log) ──"
LOG_S2="opus_test_s2_$(date +%s)"; _make_log "$LOG_S2" 0

bash -c 'exec -a claude_proxy_start.sh sleep 30' &
CLONE_PID=$!; CLEANUP_PIDS+=($CLONE_PID)
sleep 0.2

printf "8080\n%s\n%s\n" "$LOG_S2" "$CLONE_PID" > "$MARKER"
check "S2: alive clone + fresh log → live (no clobber)" live "$(_is_stale "$MARKER")"
check "S2: _proxy_pid_is_live(clone) = true" "0" "$(_proxy_pid_is_live "$CLONE_PID" && echo 0 || echo 1)"

kill $CLONE_PID 2>/dev/null; wait $CLONE_PID 2>/dev/null || true
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$CLONE_PID}")
sleep 0.1

check "S2b: after clone dies, same marker → stale (heartbeat trigger)" stale "$(_is_stale "$MARKER")"

echo ""
echo "── S3: crash / kill-9 (dead PID, stale log >60s) ──"
LOG_S3="opus_test_s3_$(date +%s)"; _make_log "$LOG_S3" 120
printf "8080\n%s\n%s\n" "$LOG_S3" "$DEAD_PID" > "$MARKER"
check "S3: dead PID + stale log → stale" stale "$(_is_stale "$MARKER")"

echo ""
echo "── S4: PID-reuse — alive unrelated process (not claude_proxy_start.sh) ──"
LOG_S4="opus_test_s4_$(date +%s)"; _make_log "$LOG_S4" 0

sleep 30 &
UNRELATED_PID=$!; CLEANUP_PIDS+=($UNRELATED_PID)
sleep 0.1

printf "8080\n%s\n%s\n" "$LOG_S4" "$UNRELATED_PID" > "$MARKER"

kill -0 "$UNRELATED_PID" 2>/dev/null && ALIVE=yes || ALIVE=no
check "S4 setup: unrelated process is alive (kill-0 passes)" yes "$ALIVE"
check "S4: _proxy_pid_is_live(unrelated) = false (identity mismatch)" "1" \
    "$(_proxy_pid_is_live "$UNRELATED_PID" && echo 0 || echo 1)"
check "S4: fixed guard — alive recycled PID + fresh log → stale" stale "$(_is_stale "$MARKER")"
echo "  [evidence] pre-fix kill-0-only guard: process alive, log fresh → would return 'live' (BUG)"

kill $UNRELATED_PID 2>/dev/null; wait $UNRELATED_PID 2>/dev/null || true
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$UNRELATED_PID}")

echo ""
echo "── S5: heartbeat reclaim (mirrors _marker_heartbeat body) ──"
LOG_S5="opus_test_s5"; OUR_PID="$$"; PORT_S5=18080

rm -f "$MARKER"
check "S5a: missing marker → reclaimed" reclaimed "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"
reclaimed_pid=$(sed -n '3p' "$MARKER" 2>/dev/null)
check "S5a: reclaimed marker has our PID ($$)" "$OUR_PID" "$reclaimed_pid"

printf "8080\n%s\n%s\n" "$LOG_S5" "$DEAD_PID" > "$MARKER"
check "S5b: dead PID in marker → reclaimed" reclaimed "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"

bash -c 'exec -a claude_proxy_start.sh sleep 30' &
LIVE2_PID=$!; CLEANUP_PIDS+=($LIVE2_PID)
sleep 0.2
printf "8080\n%s\n%s\n" "$LOG_S5" "$LIVE2_PID" > "$MARKER"
check "S5c: alive primary in marker → kept (no clobber)" kept "$(_heartbeat_check "$MARKER" "$OUR_PID" "$PORT_S5" "$LOG_S5")"
kill $LIVE2_PID 2>/dev/null; wait $LIVE2_PID 2>/dev/null || true
CLEANUP_PIDS=("${CLEANUP_PIDS[@]/$LIVE2_PID}")

echo ""
printf "Results: %d passed, %d failed\n" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
