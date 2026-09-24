#!/bin/bash

SESSION="monitor_cc_layout_test"

tmux kill-session -t "$SESSION" 2>/dev/null

tmux new-session -d -s "$SESSION" -x 200 -y 50

tmux split-window -h -t "$SESSION:0.0" -l 50%

tmux split-window -v -t "$SESSION:0.1" -b -l 25%

echo "=== tmux 3-pane layout test ==="
echo ""
echo "Expected layout:"
echo "  Pane ? (left 50%)       | Pane ? (top-right 25%)"
echo "                          | Pane ? (bottom-right 75%)"
echo ""
echo "Actual pane info:"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: #{pane_width}x#{pane_height} at (#{pane_left},#{pane_top}) — active=#{pane_active}"
echo ""

echo "Position mapping:"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: left=#{pane_left} top=#{pane_top} width=#{pane_width} height=#{pane_height}"
echo ""

tmux kill-session -t "$SESSION"
echo "Test session cleaned up."
