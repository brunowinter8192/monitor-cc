# tmux Keybindings + Parameter Display - FAILED FIX ATTEMPT

**Date:** 2025-11-26 23:06

## Problem
User requested 6 improvements: full-buffer search, 1-line scroll, tool-call navigation, mode indicator, fixed panes, full parameter display. These were feature requests, not bugs - wrong workflow was used (/debug instead of /feature).

## Attempted Fix

**workflow.py:149-157** - Added tmux keybindings:
- `q` to toggle copy-mode
- `s` for search
- `Enter` for next match
- `Option+m`/`Option+s` for pane copy
- Status bar with COPY/SCROLL indicator

**src/subagent_ui.py:188-199** - Changed `get_input_preview()`:
- From: Show only first/important parameter
- To: Show all parameters as `key=value, key2=value2`

## Why It Failed

**What we observed when tested:**
- Multiple new problems appeared (regression)

**Specific symptoms:**
- `q` key shows persistent status bar `[monitor_c0:[tmux]]*` instead of toggling copy-mode
- Subagent tool calls no longer display (only header "Active Subagents" visible, no tool calls)
- Status bar is persistent and shows wrong info

**Comparison to before:**
- Worse than before - subagents completely broken, q-key unusable

**Side effects:**
- Option+m / Option+s for pane copy DOES work correctly

**Our best hypothesis for why it failed:**

1. **q-binding conflict**: Binding `q` in root table interferes with normal operation. The status bar appearing suggests copy-mode IS being entered but display is wrong.

2. **Subagent breakage**: The `get_input_preview()` change in subagent_ui.py likely caused a downstream error. Need to check if tool_calls are being passed correctly or if the new formatting crashes silently.

**Confidence in this analysis:** 60% - Medium
The q-binding issue is clear. The subagent issue needs log inspection to confirm.

**What we're still uncertain about:**
- Whether subagent issue is in get_input_preview() or elsewhere
- Why status bar shows [tmux] instead of COPY/SCROLL
- Whether other tmux bindings are interfering

## Next Steps
1. Revert subagent_ui.py changes first - test if subagents work again
2. Fix q-binding by using different key or proper copy-mode toggle
3. Check src/logs/08_ui_rendering.log for subagent errors
4. Consider using Ctrl+B prefix for custom bindings instead of root table
