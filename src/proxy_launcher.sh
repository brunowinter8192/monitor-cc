#!/bin/bash
# Start mitmproxy addon for Claude Code API interception
# NOTE: For normal use, prefer claude_proxy_start.sh — it starts both the proxy and Claude Code together.
MONITOR_CC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MONITOR_CC_ROOT
mitmdump -p 8080 -s "$MONITOR_CC_ROOT/src/proxy_addon.py" --set flow_detail=0 -q
