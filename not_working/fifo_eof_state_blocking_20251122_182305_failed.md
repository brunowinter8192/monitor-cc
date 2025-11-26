# Subagent Click Expansion - FAILED FIX ATTEMPT

**Date:** 2025-11-22 18:23

## Problem
Mouse clicks on subagent tabs in right pane (UI mode) produced yellow "clicked" tmux status message but did NOT expand agents. Zero FIFO_READ events logged despite clicks writing to FIFO.

## Attempted Fix
Changed FIFO opening from non-blocking to blocking-then-non-blocking approach to prevent macOS EOF-state race condition.

**Based on:** Agent 2's analysis (Option B)

**Changes made:**
- src/monitor.py:2 - Added `import fcntl`
- src/monitor.py:439-440 - Changed FIFO open logic:
  - From: `os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)`
  - To: `os.open(fifo_path, os.O_RDONLY)` then `fcntl.fcntl(fifo_fd, fcntl.F_SETFL, os.O_NONBLOCK)`

**Theory:** Opening FIFO with O_NONBLOCK before any writer connects on macOS creates persistent EOF-state. Blocking open forces wait for first writer, avoiding EOF-state.

## Why It Failed
Monitor startup now shows **NO subagents at all** in right pane (worse than original problem).

**Observed behavior:**
- Monitor starts successfully
- Tmux split-screen appears
- Left pane shows main tool calls normally
- **Right pane is empty** (should show 6 collapsed subagent tabs)
- No subagents render, not even collapsed state

**Root cause of failure:**
Blocking FIFO open blocks Python monitor process startup, preventing subagent UI rendering. The monitor waits indefinitely for first FIFO writer (mouse click), but UI never renders so user can't click. **Deadlock scenario.**

## Next Steps
Revert this fix and try alternative approaches:
1. **Agent 1 & 3's approach:** Session-scoped tmux binding (workflow.py:226 add `-t session_name`)
2. **Agent 2's Option A:** Reorder startup sequence - configure mouse binding BEFORE opening FIFO, prime FIFO with dummy write
3. Investigate why original multiple-session hypothesis was incorrect - may reveal actual root cause
