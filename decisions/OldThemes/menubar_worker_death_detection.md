# Worker Death Detection — menubar false-working fix

## Problem

Workers whose Claude Code process dies (context-limit, crash, quota-out) remain shown as
"working" (star icon) in the menubar bead-tracker panel for up to 1 hour. Symptom: star
persists long after the worker's CC session is gone; only disappears when the 1h hook
freshness window expires.

## Root Cause

`discover.py:_process_project_dir` worker branch (pre-fix lines 138-142):

```python
hook_entry = hook_state.get(session_id)
if hook_entry is not None and (now - hook_entry.get('updated_ts', 0)) <= ALIVE_WINDOW_SECS:
    status = hook_entry['status']   # ← trusts stale 'working' hook unconditionally
else:
    status = 'idle'
```

Two conditions conspire:

1. **`ALIVE_WINDOW_SECS = 3600`** — hook entry is considered "fresh" for 1 hour. The
   `UserPromptSubmit` hook writes `status='working'` at turn-start. If CC crashes mid-turn,
   Stop hook never fires; the `updated_ts` is recent; the entry is treated as fresh.

2. **`_tmux_session_exists` returns True** — the alive-guard on line 132 passes because the
   tmux pane stays alive (zsh is the pane command, not claude; zsh doesn't exit when CC
   crashes). So the function doesn't return `None`; it reaches the status-determination block.

Result: hook says `'working'`, hook is "fresh", tmux pane exists → status = `'working'` for
up to 1h.

## Why pane_dead Is NOT the Right Signal

tmux's `pane_dead` flag would be True only when the pane's **primary process** exits. In
this setup the pane's primary process is `zsh` (the login shell), not `claude`. CC is a
child of zsh, not the pane process. When CC crashes, zsh continues running, pane_dead stays
False indefinitely. Polling `pane_dead` would never detect a CC crash in this setup.

## Fix

Added a crash-safety demote inside the `hook_fresh=True` branch (`discover.py` lines 138-147
post-fix):

```python
hook_entry = hook_state.get(session_id)
hook_fresh = (hook_entry is not None
              and (now - hook_entry.get('updated_ts', 0)) <= ALIVE_WINDOW_SECS)
if hook_fresh:
    status = hook_entry['status']
    # Crash-safety: 'working' hook + stale JSONL = CC crashed before Stop-hook fired.
    # Demote to 'idle' so the menubar doesn't show false-working for up to 1h.
    if status == 'working' and (now - mtime) > WORKING_THRESHOLD_SECS:
        status = 'idle'
else:
    status = 'idle'
```

**Why JSONL-mtime is the right signal:** CC writes JSONL continuously while processing a
turn. When CC crashes, writes stop immediately. `WORKING_THRESHOLD_SECS = 10` is already the
canonical semantic boundary between "CC is actively writing" and "CC went quiet" — used in
the main-session branch as: `'working' if (now - mtime) <= WORKING_THRESHOLD_SECS else 'idle'`.

**Pattern is the main-branch pattern inverted:**
- Main: `hook_fresh=False` → JSONL-mtime **lifts** idle → working (if recent)
- Worker: `hook_fresh=True, status='working'` → JSONL-mtime **demotes** working → idle (if stale)

Shared constant `WORKING_THRESHOLD_SECS=10` gives both branches consistent semantics.

**4-case truth table (post-fix):**

| hook_fresh | hook status | JSONL age | result |
|---|---|---|---|
| False | — | any | `'idle'` |
| True | `'idle'` | any | `'idle'` |
| True | `'working'` | ≤ 10s | `'working'` ✓ genuinely active |
| True | `'working'` | > 10s | `'idle'` ✓ crash-safety demote |

## Verification

Live test (user-executed — CC crash cannot be triggered in worktree):

1. Open menubar bead panel; observe a worker showing the star (working) icon.
2. Kill the worker's CC process: `worker-cli kill <name>` (or SIGKILL to the claude PID).
   Confirm: tmux pane stays alive (zsh prompt appears), `tmux list-sessions` still shows the
   session.
3. Wait `WORKING_THRESHOLD_SECS + 1 = 11s`.
4. Within the next `_tick` interval (≤ 1.5s): star disappears / status shows idle in the
   menubar panel. Before the fix, the star would persist for up to 1 hour.
