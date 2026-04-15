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
printf "%s\n%s\n" "$PROXY_PORT" "$LOG_ID" > "$MARKER_FILE"
# Also write to /tmp for cross-repo discovery (workers find proxy via this)
# Format: line 1 = port, line 2 = log_id, line 3 = MONITOR_CC_ROOT
printf "%s\n%s\n%s\n" "$PROXY_PORT" "$LOG_ID" "$MONITOR_CC_ROOT" > "/tmp/.monitor_cc_proxy_${SESSION_ID}"

# Copy addon and entire proxy/ package to isolated live copies — prevents git merge hot-reload
LIVE_ADDON="$LOG_DIR/.proxy_addon_live_${SESSION_ID}.py"
LIVE_DIR="$LOG_DIR/.proxy_live_${SESSION_ID}"
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
mitmdump -p $PROXY_PORT -s "$LIVE_ADDON" --set flow_detail=0 -q 2>"$LOG_DIR/proxy_errors_$LOG_ID.log" &
PROXY_PID=$!

# Log rotation: keep max 30 log files total (jsonl + error logs), delete oldest by mtime
(cd "$LOG_DIR" && ls -t api_requests_*.jsonl proxy_errors_*.log 2>/dev/null | tail -n +31 | while IFS= read -r f; do rm -f "$f"; done)

# Cleanup on exit: kill proxy and remove marker file
cleanup() {
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
    rm -f "$MARKER_FILE"
    rm -f "/tmp/.monitor_cc_proxy_${SESSION_ID}"
    rm -f "$LIVE_ADDON"
    rm -rf "$LIVE_DIR"
}
trap cleanup EXIT INT TERM

sleep 1
echo "Proxy for $PROJECT on port $PROXY_PORT, log: api_requests_${LOG_ID}.jsonl"

# Pinned to v2.1.109 via ~/.local/bin/claude-109 wrapper. Override with CLAUDE_BIN env var if needed.
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude-109}"
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
