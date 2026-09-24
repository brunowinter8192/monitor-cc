#!/bin/bash

# FUNCTIONS
_write_project_marker() {
    if _marker_is_stale "$MARKER_FILE" 3; then
        printf "%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$$" > "$MARKER_FILE"
    fi
}

_write_tmp_marker() {
    if _marker_is_stale "$TMP_MARKER" 4; then
        printf "%s\n%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$MONITOR_CC_ROOT" "$$" > "$TMP_MARKER"
    fi
}

_marker_is_stale() {
    local marker="$1" pid_line="$2" log_id pid log log_mtime
    [ -f "$marker" ] || return 0
    log_id=$(sed -n '2p' "$marker" 2>/dev/null)
    pid=$(sed -n "${pid_line}p" "$marker" 2>/dev/null)
    [ -n "$log_id" ] && [ -n "$pid" ] || return 0
    _proxy_pid_is_live "$pid" || return 0
    log="$LOG_DIR/dual_log/api_requests_${log_id}_forwarded.jsonl"
    [ -f "$log" ] || return 0
    log_mtime=$(stat -f %m "$log" 2>/dev/null || stat -c %Y "$log" 2>/dev/null)
    if [ -n "$log_mtime" ] && [ $(($(date +%s) - log_mtime)) -lt 60 ]; then
        return 1
    fi
    return 0
}

_proxy_pid_is_live() {
    local pid="$1"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    local cmd
    cmd=$(ps -p "$pid" -o args= 2>/dev/null)
    case "$cmd" in
        *claude_proxy_start.sh*) return 0 ;;
        *) return 1 ;;
    esac
}

_marker_heartbeat() {
    while sleep 10; do
        kill -0 $PROXY_PID 2>/dev/null || break
        local m_pid
        m_pid=$(sed -n '3p' "$MARKER_FILE" 2>/dev/null)
        if ! _proxy_pid_is_live "$m_pid"; then
            printf "%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$$" > "$MARKER_FILE"
        fi
        local t_pid
        t_pid=$(sed -n '4p' "$TMP_MARKER" 2>/dev/null)
        if ! _proxy_pid_is_live "$t_pid"; then
            printf "%s\n%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$MONITOR_CC_ROOT" "$$" > "$TMP_MARKER"
        fi
    done
}

_remove_marker_if_owned() {
    local marker="$1" pid_line="$2" marker_pid
    if [ -f "$marker" ]; then
        marker_pid=$(sed -n "${pid_line}p" "$marker" 2>/dev/null)
        if [ "$marker_pid" = "$$" ]; then
            rm -f "$marker"
        fi
    fi
}

cleanup() {
    kill $HEARTBEAT_PID 2>/dev/null
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
    _remove_marker_if_owned "$MARKER_FILE" 3
    _remove_marker_if_owned "$TMP_MARKER" 4
    rm -f "$LIVE_ADDON"
    rm -rf "$LIVE_DIR"
}
