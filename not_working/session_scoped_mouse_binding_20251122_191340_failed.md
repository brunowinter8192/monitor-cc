# Session-Scoped Mouse Binding for Click-Expansion - FAILED FIX ATTEMPT

**Date:** 2025-11-22 19:13

## Problem
Mouse clicks on subagent tabs in right pane (UI mode) produce yellow tmux status message but do NOT expand agents. FIFO writes from mouse binding never reach Python process (zero FIFO_READ events in logs).

## Attempted Fix
Changed mouse binding from global to session-scoped to prevent interference with tmux text selection and ensure FIFO writes route correctly.

**Based on:** Agent 3's analysis

**Changes made:**
- workflow.py:227 - Added `-t session_name` to bind-key command:
  - From: `tmux bind-key -T root MouseDown1Pane ...`
  - To: `tmux bind-key -t session_name -T root MouseDown1Pane ...`

**Theory:** Global binding (`-T root` without `-t`) might route FIFO writes to wrong session or interfere with tmux's native mouse handling. Session-scoped binding should ensure click events write to correct FIFO for this specific session.

## Why It Failed
Click on [+] still produces ZERO expansion effect.

**Observed behavior:**
- Click triggers yellow tmux status bar (proves binding fires)
- [+] remains [+] (no toggle to [-])
- No tool calls appear below agent entry
- Exactly same symptoms as before fix

**Root cause of failure:**
Session-scoped binding did NOT solve the FIFO communication issue. The `-t session_name` flag with `-T root` may be unsupported by tmux, or the root cause is elsewhere:

1. **Possible syntax incompatibility:** tmux may not support `-t` (session target) combined with `-T root` (key table). Binding might have failed silently.

2. **FIFO write succeeds but read fails:** Yellow status bar proves shell command executes (`echo toggle:... > FIFO`), but Python process may not be reading from FIFO in polling loop.

3. **Line mapping broken:** FIFO read might succeed but `get_agent_id_at_line()` returns None, causing silent failure in `process_fifo_command()`.

## Next Steps
Debug actual root cause with diagnostics:

1. **Verify binding was set:** `tmux list-keys -t session_name | grep MouseDown1Pane`
   - If empty: Session-scoped syntax not supported, revert to global

2. **Test FIFO read manually:** `echo "toggle:5:0" > /tmp/monitor_cc_control_*.fifo`
   - If works: Binding is the problem
   - If fails: FIFO read loop or line mapping is the problem

3. **Check logs for FIFO_READ:** `grep FIFO_READ src/logs/09_click_handling.log`
   - If zero: Python not reading from FIFO (handle_fifo_commands not called or FD None)
   - If present: Line mapping logic is broken

4. **Alternative approaches:**
   - Revert to global binding (remove `-t session_name`)
   - Use window-scoped binding instead: `-t session_name:window_index`
   - Debug handle_fifo_commands() polling frequency
   - Add debug logging to process_fifo_command() to see if it's called
