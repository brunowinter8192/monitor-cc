# Message Queue — Implementation Narrative

## What we did

Built a turn-end message queue for CC main sessions in the menubar app. User fills a per-session queue via inline NSTextField panel UI; on each Stop/StopFailure hook, the head message is delivered to the Ghostty terminal via AppleScript keystroke.

## Key design decision: IPC via ghostty_cwd_uuid.json

**Problem:** hook_writer.py is a standalone subprocess (run by CC as `async: true` hook). It cannot access the menubar app's module-level caches (`_ghostty_tty_to_id`, `_cc_proc_cache`). Ghostty's AppleScript sdef exposes NO `write text` / `type` command on terminals — `perform action "write_to_pty:..."` returns `false` (not implemented).

**Confirmed AppleScript delivery path:**
```applescript
tell application "Ghostty"
  focus terminal id "<UUID>"
end tell
delay 0.1
tell application "System Events"
  keystroke "<message>"
  key code 36
end tell
```

Focus + System Events keystroke is the ONLY way to inject text into a Ghostty terminal programmatically.

**IPC bridge:** menubar app writes `APP_SUPPORT/ghostty_cwd_uuid.json = {cwd: uuid}` on every tick (change-detected in `_write_cwd_uuid_map`, defined in `ghostty.py`, called from `discover.py:list_alive_sessions`). hook_writer.py reads this file at delivery time to get the UUID. Falls back to cwd-based focus (`focus (first terminal whose working directory is "...")`) when UUID not found — limited to PTY initial cwd, acceptable fallback.

## Storage schema

`APP_SUPPORT/msg_queue.json = {session_id: [msg1, msg2, ...]}` — key = JSONL stem (CC session_id), value = ordered list. Session_id added to `SessionInfo` NamedTuple in discover.py for panel→queue association.

## Queue file locking

hook_writer.py uses exclusive flock on `queue.lock` for pop + save. Menubar app (app.py, queue.py) uses non-locked writes for UI operations (add/remove) — acceptable since UI writes happen on main thread and concurrent delivery pops are rare (at most one per turn-end event). Race window is narrow: UI save → hook_writer read between save and replace. Atomic `os.replace` on APFS means reads see either old or new file atomically. No partial-read corruption possible.

## End-to-end smoke result

Tested 2026-05-21:
1. Wrote `{session_id: ["echo first_message_delivered", "echo second_message_stays"]}` to `msg_queue.json`
2. Triggered Stop hook via stdin: `_queue_pop_head` → msg popped → `_deliver_message` → osascript `focus terminal id + keystroke + Return` → AppleScript landed in Ghostty terminal (user confirmed)
3. Queue after: `{session_id: ["echo second_message_stays"]}` ✅
4. Second Stop trigger → second message delivered → queue empty `{}` ✅
5. Re-enqueuement on failure: `_queue_push_head` path tested by breaking UUID lookup (verified head restored)

## ghostty_cwd_uuid.json observed output

```json
{"/Users/brunowinter2000/Documents/ai/Monitor_CC": "77C9C194-65BB-40B7-899C-4200A968B6DA"}
```

Written correctly on first tick. Change-detection (`_ghostty_cwd_uuid_last`) prevents redundant writes.

## Pending

- Panel UI visual verification (queue rows under session rows, + button, inline NSTextField editing) — to be verified by user post-merge
- panel.py (531 LOC) and app.py (548 LOC) both exceed 400 LOC ceiling; split-refactor tracked separately
