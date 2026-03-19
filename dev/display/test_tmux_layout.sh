#!/bin/bash
# test_tmux_layout.sh — Verify tmux 3-pane layout for Monitor_CC
#
# Creates a temporary tmux session with the target layout:
#   Left (50%)  |  Right-Top (25% of right) — rules pane
#               |  Right-Bottom (75% of right) — subagent pane
#
# Outputs: tmux list-panes showing pane indices, dimensions, positions.
# This tells us which pane index maps to which screen position,
# so tmux_launcher.py can target the correct panes with commands.
#
# Source: tmux man page (github.com/tmux/tmux tmux.1 L3591-3648)
#   - split-window -h: horizontal split, new pane to the right
#   - split-window -v -t X: vertical split of pane X, new pane below
#   - -b flag: place new pane above/left instead of below/right
#   - -l 25%: percentage of the TARGET pane's available space
#
# Usage: bash dev/display/test_tmux_layout.sh

SESSION="monitor_cc_layout_test"

# Cleanup any previous test session
tmux kill-session -t "$SESSION" 2>/dev/null

# Step 1: Create session with first pane (will be "main" — left side)
tmux new-session -d -s "$SESSION" -x 200 -y 50

# Step 2: Horizontal split — creates right pane (pane 1)
# -h = horizontal, -l 50% = right pane gets 50% of window width
tmux split-window -h -t "$SESSION:0.0" -l 50%

# Step 3: Vertical split of the RIGHT pane (pane 1) — creates rules pane
# -v = vertical split, -t pane 1, -b = new pane ABOVE (top-right)
# -l 25% = new pane gets 25% of pane 1's height
tmux split-window -v -t "$SESSION:0.1" -b -l 25%

# Output: show all pane info
echo "=== tmux 3-pane layout test ==="
echo ""
echo "Expected layout:"
echo "  Pane ? (left 50%)       | Pane ? (top-right 25%)"
echo "                          | Pane ? (bottom-right 75%)"
echo ""
echo "Actual pane info:"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: #{pane_width}x#{pane_height} at (#{pane_left},#{pane_top}) — active=#{pane_active}"
echo ""

# Also show which pane is where by position
echo "Position mapping:"
tmux list-panes -t "$SESSION" -F "  Pane #{pane_index}: left=#{pane_left} top=#{pane_top} width=#{pane_width} height=#{pane_height}"
echo ""

# Cleanup
tmux kill-session -t "$SESSION"
echo "Test session cleaned up."
