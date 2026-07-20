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

- app.py (632 LOC) exceeds 400 LOC ceiling; split-refactor tracked separately

---

## Architecture Pivot — Standalone Queue Panel

### Problem

The inline queue UI added in the mlpb merge had two hard failures:

1. **NSTextField not clickable.** Sessions panel uses `NSWindowStyleMaskNonactivatingPanel`. The panel never becomes the key window, so NSTextField can never become first responder. `app._panel.makeFirstResponder_(tf)` (called at end of `_add_queue_block`) silently fails. User cannot click the + row to type.

2. **Layout mix.** Queue rows interspersed between session rows created a confusing compound panel. The inline layout also pushed `_compute_required_height` to track queue row counts per session, coupling session height to queue state.

### Decision

Migrate queue UI to a standalone 3rd NSPanel (`queue_panel.py`) analogous to `bead_panel.py`. Sessions panel reverts to pure session listing.

### Architecture

**New file: `src/menubar/queue_panel.py`** — `_make_queue_nspanel()` returns `(panel, stack, toggle_btn)` with no footer. `_rebuild_queue_panel(app, sessions)` builds per-main-session blocks: `project › session` header + N message rows + add-button or NSTextField. Functions `_make_queue_msg_row`, `_make_queue_add_btn`, `_make_queue_input_field` moved verbatim from `panel.py`.

**Input-fix:** `NSWindowStyleMaskNonactivatingPanel` prevents app activation but does NOT prevent the panel from becoming the key window. `makeKeyAndOrderFront_(None)` called programmatically (after + button click triggers rebuild with pending mode) gives the panel keyboard focus without activating the app. Ghostty stays frontmost app; only the queue panel's NSTextField receives keystrokes. `makeFirstResponder_(tf)` then routes input to the text field.

**panel.py revert:** removed `_make_queue_msg_row`, `_make_queue_add_btn`, `_make_queue_input_field`, `_add_queue_block`. `_compute_required_height` reverted — no `queue_data` parameter, no per-session queue row counting. Header updated: `[Sessions] · Beads` → `[Sessions] · Beads · Queue`.

**3-panel cycling (Cmd+→/←):** Sessions → Beads → Queue → Sessions (right); reverse (left). Each `_open_*_panel` registers BOTH arrow directions; each `_close_*_panel` unregisters both. Generic `_deferred_close_open(app, from, to)` replaces the two old deferred functions.

**Header indicators:** all 3 panels show `[Active] · Other · Other` pattern. Updated in each `_rebuild_*` function and in `toggleAutoJump_`.

**Cmd+K:** `_background_panel` extended with `elif app._queue_open:` branch (setLevel 0 + orderBack).

**State added:** `_queue_open`, `_queue_panel`, `_queue_sv`, `_queue_toggle_btn`, `_queue_displayed_names`, `_last_sessions` — all on `app`. Queue UI state (`_pending_queue_sessions`, `_queue_add_tags`, etc.) retained on app, now managed by `_rebuild_queue_panel` instead of `_rebuild_panel`.

### Files changed

| File | Change |
|---|---|
| `src/menubar/queue_panel.py` | NEW — 211 LOC |
| `src/menubar/panel.py` | Reverted queue UI; 531 → 431 LOC |
| `src/menubar/app.py` | New state + queue panel lifecycle + 3-panel cycling; 548 → 632 LOC |
| `src/menubar/bead_panel.py` | Header text updated to include Queue |
| `src/menubar/DOCS.md` | queue_panel.py entry added; panel.py + app.py entries updated |
