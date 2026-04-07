#!/bin/bash
# Start mitmproxy addon for Claude Code API interception
MONITOR_CC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MONITOR_CC_ROOT
mitmdump -p 8080 -s "$MONITOR_CC_ROOT/src/proxy_addon.py" --set flow_detail=0 -q
