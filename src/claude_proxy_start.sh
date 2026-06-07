#!/bin/bash
# Start Claude Code with API request logging via mitmproxy
# Usage: ./src/claude_proxy_start.sh [--project <path>] [claude args...]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_CC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MITMPROXY_CA="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"

# Parse --project argument; remaining args passed to claude
PROJECT=""
CLAUDE_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            PROJECT="$2"
            shift 2
            ;;
        *)
            CLAUDE_ARGS+=("$1")
            shift
            ;;
    esac
done
PROJECT="${PROJECT:-$(pwd)}"

# Generate session_id from project path: first 8 chars of md5 (matches monitor.py hash logic)
if command -v md5 &>/dev/null; then
    SESSION_ID="$(echo -n "$PROJECT" | md5 | head -c 8)"
else
    SESSION_ID="$(echo -n "$PROJECT" | md5sum | head -c 8)"
fi
# Per-start unique id: project hash + pid + epoch — prevents live-copy collision when two
# sessions run in the same project simultaneously (SESSION_ID stays per-project for worker discovery)
PROXY_SESSION_UID="${SESSION_ID}_$$_$(date +%s)"

# Generate per-start log id: opus_ prefix + sanitized project basename + unix timestamp
PROJECT_BASENAME="$(basename "$PROJECT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_' | sed 's/^_*//;s/_*$//')"
LOG_ID="opus_${PROJECT_BASENAME}_$(date +%s)"

# Find a free port starting at 8080
PROXY_PORT=8080
while lsof -iTCP:$PROXY_PORT -sTCP:LISTEN &>/dev/null 2>&1; do
    PROXY_PORT=$((PROXY_PORT + 1))
done

# Generate CA cert if first run
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

# Build combined CA bundle (system CAs + mitmproxy CA) for Python MCP servers
COMBINED_CA="$HOME/.mitmproxy/combined-ca.pem"
SYSTEM_CA="/opt/homebrew/etc/ca-certificates/cert.pem"
if [ -f "$MITMPROXY_CA" ] && [ -f "$SYSTEM_CA" ]; then
    cat "$SYSTEM_CA" "$MITMPROXY_CA" > "$COMBINED_CA"
fi

# Write marker file so monitor can discover port and log_id for this session
LOG_DIR="$MONITOR_CC_ROOT/src/logs"
mkdir -p "$LOG_DIR"
MARKER_FILE="$LOG_DIR/.proxy_session_$SESSION_ID"
# Only overwrite marker if its referenced log_id is no longer being actively written.
# Parallel sessions (e.g. hi-test) for the same project must NOT clobber the live marker.
# Check via log file mtime, not the listed port — port can be reused by an unrelated mitmdump
# of another project, which led to false-positive "fresh" reads of marker pointing to a stale log_id.
MARKER_IS_STALE=true
if [ -f "$MARKER_FILE" ]; then
    existing_log_id=$(sed -n '2p' "$MARKER_FILE" 2>/dev/null)
    if [ -n "$existing_log_id" ]; then
        existing_log="$LOG_DIR/dual_log/api_requests_${existing_log_id}_forwarded.jsonl"
        if [ -f "$existing_log" ]; then
            log_mtime=$(stat -f %m "$existing_log" 2>/dev/null || stat -c %Y "$existing_log" 2>/dev/null)
            now=$(date +%s)
            if [ -n "$log_mtime" ] && [ $((now - log_mtime)) -lt 60 ]; then
                MARKER_IS_STALE=false
            fi
        fi
    fi
fi
if [ "$MARKER_IS_STALE" = true ]; then
    printf "%s\n%s\n" "$PROXY_PORT" "$LOG_ID" > "$MARKER_FILE"
fi
# Also write to /tmp for cross-repo discovery (workers find proxy via this)
# Format: line 1 = port, line 2 = log_id, line 3 = MONITOR_CC_ROOT
# Same guard: only overwrite if existing marker's port is not listening
TMP_MARKER="/tmp/.monitor_cc_proxy_${SESSION_ID}"
TMP_IS_STALE=true
if [ -f "$TMP_MARKER" ]; then
    existing_tmp_log_id=$(sed -n '2p' "$TMP_MARKER" 2>/dev/null)
    if [ -n "$existing_tmp_log_id" ]; then
        existing_tmp_log="$LOG_DIR/dual_log/api_requests_${existing_tmp_log_id}_forwarded.jsonl"
        if [ -f "$existing_tmp_log" ]; then
            tmp_log_mtime=$(stat -f %m "$existing_tmp_log" 2>/dev/null || stat -c %Y "$existing_tmp_log" 2>/dev/null)
            tmp_now=$(date +%s)
            if [ -n "$tmp_log_mtime" ] && [ $((tmp_now - tmp_log_mtime)) -lt 60 ]; then
                TMP_IS_STALE=false
            fi
        fi
    fi
fi
if [ "$TMP_IS_STALE" = true ]; then
    printf "%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$MONITOR_CC_ROOT" > "$TMP_MARKER"
fi

# Copy addon and entire proxy/ package to isolated live copies — prevents git merge hot-reload
# Use PROXY_SESSION_UID (not SESSION_ID) so parallel sessions in the same project don't overwrite each other
LIVE_ADDON="$LOG_DIR/.proxy_addon_live_${PROXY_SESSION_UID}.py"
LIVE_DIR="$LOG_DIR/.proxy_live_${PROXY_SESSION_UID}"

# Janitor: remove orphan live-copies left by sessions that exited without cleanup.
# Runs before this session's own live-copies are created so they cannot be self-evicted.
_janitor_cleanup_live_copies() {
    local orphan_count=0 id shim dir_path

    # Pass 1: iterate shim files — each shim is the authoritative reference for its pair
    for shim in "$LOG_DIR"/.proxy_addon_live_*.py; do
        [ -f "$shim" ] || continue
        id="${shim##*/.proxy_addon_live_}"
        id="${id%.py}"
        dir_path="$LOG_DIR/.proxy_live_${id}"
        # Skip if any mitmdump process is running with this shim's full path
        pgrep -f "$shim" >/dev/null 2>&1 && continue
        rm -f "$shim"
        [ -d "$dir_path" ] && rm -rf "$dir_path"
        orphan_count=$((orphan_count + 1))
    done

    # Pass 2: remove live dirs whose shim was already removed (or never created)
    for dir_path in "$LOG_DIR"/.proxy_live_*/; do
        [ -d "$dir_path" ] || continue
        id="${dir_path##*/.proxy_live_}"
        id="${id%/}"
        [ -f "$LOG_DIR/.proxy_addon_live_${id}.py" ] && continue
        rm -rf "$dir_path"
        orphan_count=$((orphan_count + 1))
    done

    echo "Janitor: cleaned $orphan_count orphan live-copies"
}
_janitor_cleanup_live_copies

# Janitor: rotate dual-log files (keep 30 opus + 30 worker by _original count) + legacy cleanup.
_janitor_cleanup_jsonl_logs() {
    local keep=30
    local rotated_dual=0 f
    local DUAL_LOG_DIR="$LOG_DIR/dual_log"

    if [ -d "$DUAL_LOG_DIR" ]; then
        local surviving_ids stem log_id sfx

        # Phase 1a: rotate opus _original files — keep 30 newest, delete older
        while IFS= read -r f; do
            [ -f "$f" ] || continue
            rm -f "$f"
            rotated_dual=$((rotated_dual + 1))
        done < <(ls -t "$DUAL_LOG_DIR"/api_requests_opus_*_original.jsonl 2>/dev/null | tail -n +$((keep + 1)))

        # Phase 1b: rotate worker _original files — keep 30 newest, delete older
        while IFS= read -r f; do
            [ -f "$f" ] || continue
            rm -f "$f"
            rotated_dual=$((rotated_dual + 1))
        done < <(ls -t "$DUAL_LOG_DIR"/api_requests_worker_*_original.jsonl 2>/dev/null | tail -n +$((keep + 1)))

        # Phase 2: union surviving log_ids from remaining _original files after rotation
        surviving_ids="$(
            for f in "$DUAL_LOG_DIR"/api_requests_opus_*_original.jsonl \
                     "$DUAL_LOG_DIR"/api_requests_worker_*_original.jsonl; do
                [ -f "$f" ] || continue
                stem="$(basename "$f" .jsonl)"
                stem="${stem#api_requests_}"
                echo "${stem%_original}"
            done
        )"

        # Phase 3: delete other dual-log files not in surviving set
        # suffix list includes 'errors' (pre-existing bug: was missing, causing _errors to always be deleted)
        for f in "$DUAL_LOG_DIR"/api_requests_*.jsonl; do
            [ -f "$f" ] || continue
            stem="$(basename "$f" .jsonl)"
            stem="${stem#api_requests_}"
            for sfx in original forwarded stripped injected errors response; do stem="${stem%_$sfx}"; done
            log_id="$stem"
            if ! echo "$surviving_ids" | grep -qxF "$log_id"; then
                rm -f "$f"
                rotated_dual=$((rotated_dual + 1))
            fi
        done
    fi

    # Remove legacy api_error_payload_*.json files (writer switched to api_errors.jsonl)
    find "$LOG_DIR" -maxdepth 1 -type f -name 'api_error_payload_*.json' -delete 2>/dev/null

    # Remove legacy proxy_errors_*.log files (mitmdump uses 2>/dev/null since 2026-05-28)
    find "$LOG_DIR" -maxdepth 1 -type f -name 'proxy_errors_*.log' -delete 2>/dev/null

    # Remove legacy tool_use_errors.jsonl (no writer; superseded by _errors dual-log)
    rm -f "$LOG_DIR/tool_use_errors.jsonl"

    echo "Janitor: rotated $rotated_dual dual-log files"
}
_janitor_cleanup_jsonl_logs

cp "$SCRIPT_DIR/proxy_addon.py" "$LIVE_ADDON"
mkdir -p "$LIVE_DIR"
cp -r "$SCRIPT_DIR/proxy" "$LIVE_DIR/"

# Reset active_plugins.json to default — only iterative-dev injected at session start
mkdir -p "$PROJECT/.claude"
echo '{"plugins": ["iterative-dev"]}' > "$PROJECT/.claude/active_plugins.json"

# Start proxy in background
export MONITOR_CC_ROOT
export PROXY_SESSION_ID="$SESSION_ID"
export PROXY_LOG_ID="$LOG_ID"
export PROXY_PROJECT_PATH="$PROJECT"
mitmdump -p $PROXY_PORT -s "$LIVE_ADDON" --set flow_detail=0 -q 2>/dev/null &
PROXY_PID=$!

# Cleanup on exit: kill proxy, remove per-session live-copies, and conditionally the per-project marker
cleanup() {
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
    # Only remove the per-project marker if it still contains OUR log_id — a parallel session
    # in the same project may have overwritten it with its own log_id.
    if [ -f "$MARKER_FILE" ]; then
        local marker_log_id
        marker_log_id=$(sed -n '2p' "$MARKER_FILE" 2>/dev/null)
        if [ "$marker_log_id" = "$LOG_ID" ]; then
            rm -f "$MARKER_FILE"
        fi
    fi
    # Only remove the /tmp per-project marker if it still contains OUR port — another session
    # that started later may have already overwritten it with its own port, so don't clobber it.
    local tmp_marker="/tmp/.monitor_cc_proxy_${SESSION_ID}"
    if [ -f "$tmp_marker" ]; then
        local marker_port
        marker_port=$(sed -n '1p' "$tmp_marker" 2>/dev/null)
        if [ "$marker_port" = "$PROXY_PORT" ]; then
            rm -f "$tmp_marker"
        fi
    fi
    rm -f "$LIVE_ADDON"
    rm -rf "$LIVE_DIR"
}
trap cleanup EXIT INT TERM

sleep 1
echo "Proxy for $PROJECT on port $PROXY_PORT, log: api_requests_${LOG_ID}.jsonl"

# Pinned to v2.1.149 via ~/.local/bin/claude-149 wrapper. Override with CLAUDE_BIN env var if needed.
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude-149}"
if [ ! -x "$CLAUDE_BIN" ]; then
    echo "ERROR: $CLAUDE_BIN not found or not executable" >&2
    exit 1
fi
echo "Using claude binary: $CLAUDE_BIN"

# Claude Code uses cwd as working directory — switch to target project
cd "$PROJECT" || { echo "ERROR: cannot cd to $PROJECT" >&2; exit 1; }

# Start Claude Code with proxy settings
HTTPS_PROXY="http://localhost:$PROXY_PORT" \
NODE_EXTRA_CA_CERTS="$MITMPROXY_CA" \
SSL_CERT_FILE="$COMBINED_CA" \
REQUESTS_CA_BUNDLE="$COMBINED_CA" \
"$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
