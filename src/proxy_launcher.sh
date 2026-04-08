#!/bin/bash
# Start mitmproxy addon for Claude Code API interception
# NOTE: For normal use, prefer claude_proxy_start.sh — it starts both the proxy and Claude Code together.
MONITOR_CC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MONITOR_CC_ROOT

# Parse optional --project argument for readable log filenames
PROJECT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            PROJECT="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Generate per-start log id: sanitized project basename + timestamp, or just timestamp in standalone mode
if [ -n "$PROJECT" ]; then
    PROJECT_BASENAME="$(basename "$PROJECT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_' | sed 's/^_*//;s/_*$//')"
    export PROXY_LOG_ID="${PROJECT_BASENAME}_$(date +%s)"
else
    export PROXY_LOG_ID="$(date +%s)"
fi

# Copy addon to isolated live copy — prevents git merge hot-reload
LIVE_ADDON="/tmp/.proxy_addon_live.py"
cp "$MONITOR_CC_ROOT/src/proxy_addon.py" "$LIVE_ADDON"

mitmdump -p 8080 -s "$LIVE_ADDON" --set flow_detail=0 -q
