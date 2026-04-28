#!/usr/bin/env bash
# Trigger SIGUSR1 RAM dump on all running monitor_cc panes.
# PID files: /tmp/.monitor_cc_pid_<pane>  (written by register_ram_dump at loop entry)
# Dumps land in: dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_<pane>.txt

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DUMPS_DIR="$SCRIPT_DIR/dumps"
MARKER=$(mktemp)

mkdir -p "$DUMPS_DIR"

count=0
for pid_file in /tmp/.monitor_cc_pid_*; do
    [ -f "$pid_file" ] || continue
    pane_name="${pid_file#/tmp/.monitor_cc_pid_}"
    pid=$(cat "$pid_file" 2>/dev/null) || continue
    if kill -0 "$pid" 2>/dev/null; then
        kill -USR1 "$pid"
        echo "  → $pane_name (pid $pid)"
        count=$((count + 1))
    else
        echo "  ✗ $pane_name (pid $pid not running, skipping)"
    fi
done

if [ "$count" -eq 0 ]; then
    echo "No active pane PID files found in /tmp/.monitor_cc_pid_*"
    rm -f "$MARKER"
    exit 0
fi

echo ""
echo "Waiting 1s for handlers to complete..."
sleep 1

echo ""
echo "Recent dumps:"
find "$DUMPS_DIR" -name "*.txt" -newer "$MARKER" | sort | while IFS= read -r f; do
    echo "  $f"
done

rm -f "$MARKER"
echo ""
echo "$count dumps written, see $DUMPS_DIR"
