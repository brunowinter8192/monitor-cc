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

# Write marker file so monitor can discover port for this session
LOG_DIR="$MONITOR_CC_ROOT/src/logs"
mkdir -p "$LOG_DIR"
MARKER_FILE="$LOG_DIR/.proxy_session_$SESSION_ID"
echo "$PROXY_PORT" > "$MARKER_FILE"

# Start proxy in background
export MONITOR_CC_ROOT
export PROXY_SESSION_ID="$SESSION_ID"
mitmdump -p $PROXY_PORT -s "$SCRIPT_DIR/proxy_addon.py" --set flow_detail=0 -q 2>"$LOG_DIR/proxy_errors_$SESSION_ID.log" &
PROXY_PID=$!

# Cleanup on exit: kill proxy and remove marker file
cleanup() {
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
    rm -f "$MARKER_FILE"
}
trap cleanup EXIT INT TERM

sleep 1
echo "Proxy for $PROJECT on port $PROXY_PORT, log: api_requests_$SESSION_ID.jsonl"

# Start Claude Code with proxy settings
HTTPS_PROXY="http://localhost:$PROXY_PORT" \
NODE_EXTRA_CA_CERTS="$MITMPROXY_CA" \
SSL_CERT_FILE="$COMBINED_CA" \
REQUESTS_CA_BUNDLE="$COMBINED_CA" \
claude "${CLAUDE_ARGS[@]}"
