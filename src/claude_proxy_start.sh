#!/bin/bash
# Start Claude Code with API request logging via mitmproxy
# Usage: ./src/claude_proxy_start.sh [claude args...]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_CC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROXY_PORT=8080
MITMPROXY_CA="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"

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

# Start proxy in background
export MONITOR_CC_ROOT
mitmdump -p $PROXY_PORT -s "$SCRIPT_DIR/proxy_addon.py" --set flow_detail=0 -q &
PROXY_PID=$!

# Cleanup on exit
cleanup() {
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
}
trap cleanup EXIT INT TERM

sleep 1
echo "Proxy running on port $PROXY_PORT (PID: $PROXY_PID)"

# Start Claude Code with proxy
HTTPS_PROXY="http://localhost:$PROXY_PORT" \
NODE_EXTRA_CA_CERTS="$MITMPROXY_CA" \
claude "$@"
