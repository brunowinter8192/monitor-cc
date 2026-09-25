#!/bin/bash

# INFRASTRUCTURE
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_CC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MITMPROXY_CA="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
COMBINED_CA="$HOME/.mitmproxy/combined-ca.pem"
SYSTEM_CA="/opt/homebrew/etc/ca-certificates/cert.pem"
MODEL_SELECTION_FILE="${MODEL_SELECTION_FILE:-$HOME/.claude/shared-rules/model_selection.json}"
LOG_DIR="$MONITOR_CC_ROOT/src/logs"

source "$SCRIPT_DIR/proxy_start_janitor.sh"
source "$SCRIPT_DIR/proxy_start_markers.sh"

# ORCHESTRATOR
proxy_start_workflow() {
    _start_worker_janitor
    _start_monitor_janitor
    _parse_args "$@"
    _resolve_config_model
    _derive_session_ids
    _find_free_port
    _ensure_mitmproxy_ca
    _build_combined_ca
    _prepare_log_dir
    _write_project_marker
    _write_tmp_marker
    _set_live_paths
    _janitor_cleanup_live_copies
    _janitor_cleanup_jsonl_logs
    _copy_live_proxy
    _reset_active_plugins
    _start_proxy
    _start_heartbeat
    trap cleanup EXIT INT TERM
    _wait_for_proxy
    _verify_proxy_alive
    _announce_proxy
    _resolve_claude_bin
    _enter_project
    _launch_claude
}

# FUNCTIONS
_start_worker_janitor() {
    if command -v worker-cli &>/dev/null; then
        nohup worker-cli janitor >/dev/null 2>&1 &
        disown
    fi
}

_start_monitor_janitor() {
    ( cd "$MONITOR_CC_ROOT" && nohup python3 -m src.monitor_janitor >/dev/null 2>&1 & )
}

_parse_args() {
    PROJECT=""
    CLAUDE_ARGS=()
    HAS_EXPLICIT_MODEL=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project)
                PROJECT="$2"
                shift 2
                ;;
            --model)
                HAS_EXPLICIT_MODEL=1
                CLAUDE_ARGS+=("$1" "$2")
                shift 2
                ;;
            *)
                CLAUDE_ARGS+=("$1")
                shift
                ;;
        esac
    done
    PROJECT="${PROJECT:-$(pwd)}"
}

_resolve_config_model() {
    [ -z "$HAS_EXPLICIT_MODEL" ] || return 0
    [ -f "$MODEL_SELECTION_FILE" ] || return 0
    if ! command -v jq &>/dev/null; then
        echo "claude_proxy_start: jq not found, $MODEL_SELECTION_FILE ignored, no --model injected" >&2
        return 0
    fi
    if [ ! -r "$MODEL_SELECTION_FILE" ]; then
        echo "claude_proxy_start: $MODEL_SELECTION_FILE unreadable, no --model injected" >&2
        return 0
    fi
    if ! CONFIG_MODEL="$(jq -r '.main // empty' "$MODEL_SELECTION_FILE" 2>/dev/null)"; then
        echo "claude_proxy_start: $MODEL_SELECTION_FILE is not valid JSON, no --model injected" >&2
        return 0
    fi
    if [ -n "$CONFIG_MODEL" ]; then
        CLAUDE_ARGS+=("--model" "$CONFIG_MODEL")
    fi
}

_derive_session_ids() {
    local normalized_project project_basename
    normalized_project="$(python3 -c "import os, sys; print(os.path.normpath(os.path.expanduser(sys.argv[1])))" "$PROJECT")"
    SESSION_ID="$(echo -n "$normalized_project" | md5 | head -c 8)"
    PROXY_SESSION_UID="${SESSION_ID}_$$_$(date +%s)"
    project_basename="$(basename "$PROJECT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_' | sed 's/^_*//;s/_*$//')"
    LOG_ID="opus_${project_basename}_$(date +%s)"
    MARKER_FILE="$LOG_DIR/.proxy_session_$SESSION_ID"
    TMP_MARKER="/tmp/.monitor_cc_proxy_${SESSION_ID}"
}

_find_free_port() {
    PROXY_PORT=8080
    while lsof -iTCP:$PROXY_PORT -sTCP:LISTEN &>/dev/null 2>&1; do
        PROXY_PORT=$((PROXY_PORT + 1))
    done
}

_ensure_mitmproxy_ca() {
    if [ ! -f "$MITMPROXY_CA" ]; then
        echo "First run: generating mitmproxy CA certificate..."
        mitmdump -p $PROXY_PORT -q &
        TEMP_PID=$!
        sleep 2
        kill $TEMP_PID 2>/dev/null
        wait $TEMP_PID 2>/dev/null
        echo "CA cert generated at $MITMPROXY_CA"
        echo "NOTE: You may need to trust this cert in your system keychain for HTTPS to work."
    fi
}

_build_combined_ca() {
    if [ -f "$MITMPROXY_CA" ] && [ -f "$SYSTEM_CA" ]; then
        cat "$SYSTEM_CA" "$MITMPROXY_CA" > "$COMBINED_CA"
    fi
}

_prepare_log_dir() {
    mkdir -p "$LOG_DIR"
}

_set_live_paths() {
    LIVE_ADDON="$LOG_DIR/.proxy_addon_live_${PROXY_SESSION_UID}.py"
    LIVE_DIR="$LOG_DIR/.proxy_live_${PROXY_SESSION_UID}"
}

_copy_live_proxy() {
    "$SCRIPT_DIR/copy_proxy_live.sh" "$LIVE_ADDON" "$LIVE_DIR"
}

_reset_active_plugins() {
    mkdir -p "$PROJECT/.claude"
    echo '{"plugins": ["iterative-dev"]}' > "$PROJECT/.claude/active_plugins.json"
}

_start_proxy() {
    export MONITOR_CC_ROOT
    export PROXY_SESSION_ID="$SESSION_ID"
    export PROXY_LOG_ID="$LOG_ID"
    export PROXY_PROJECT_PATH="$PROJECT"
    mitmdump -p $PROXY_PORT -s "$LIVE_ADDON" --set flow_detail=0 -q 2>/dev/null &
    PROXY_PID=$!
}

_start_heartbeat() {
    _marker_heartbeat &
    HEARTBEAT_PID=$!
}

_wait_for_proxy() {
    sleep 1
}

_verify_proxy_alive() {
    if ! kill -0 $PROXY_PID 2>/dev/null; then
        echo "claude_proxy_start: mitmdump failed to start on port $PROXY_PORT, aborting" >&2
        exit 1
    fi
}

_announce_proxy() {
    echo "Proxy for $PROJECT on port $PROXY_PORT, log: api_requests_${LOG_ID}.jsonl"
}

_resolve_claude_bin() {
    CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude-280}"
    if [ ! -x "$CLAUDE_BIN" ]; then
        echo "ERROR: $CLAUDE_BIN not found or not executable" >&2
        exit 1
    fi
    echo "Using claude binary: $CLAUDE_BIN"
}

_enter_project() {
    cd "$PROJECT" || { echo "ERROR: cannot cd to $PROJECT" >&2; exit 1; }
}

_launch_claude() {
    HTTPS_PROXY="http://localhost:$PROXY_PORT" \
    NODE_EXTRA_CA_CERTS="$MITMPROXY_CA" \
    SSL_CERT_FILE="$COMBINED_CA" \
    REQUESTS_CA_BUNDLE="$COMBINED_CA" \
    "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
}

proxy_start_workflow "$@"
