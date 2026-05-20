
## Fixes Session 2 (2026-05-21)

### Crash — CFUNCTYPE-GC (H1)

Root cause: `register_cmd_arrow_right`/`left` used per-call CFUNCTYPEs returned as `(cb, hk_ref)`. In `_close_*_panel`, setting `app._hotkey_arr_*_cb = None` GC'd the CFUNCTYPE. `unregister_single_hotkey` only called `UnregisterEventHotKey` (removes the key-combo binding) — it did NOT remove the Carbon event handler installed via `InstallEventHandler` (whose `handler_ref` was a local variable, lost after `register_cmd_arrow_*` returned). Carbon still held the handler pointing to freed memory. Next hotkey event (any Cmd+key) called the dangling pointer → SIGABRT.

Fix: migrated Cmd+→/← to module-level persistent CFUNCTYPE pattern, identical to Cmd+1..9:
- `_ARROW_CALLBACKS = {}`, `_ARROW_HANDLER_CB = None`, `_ARROW_HANDLER_REF = None` at module scope
- `_ensure_arrow_handler()` installs ONE handler for both arrows, called once, never GC'd
- `register_cmd_arrow_right/left(cb)`: sets `_ARROW_CALLBACKS[id] = cb` + `RegisterEventHotKey` → returns `(None, hk_ref)` (None = module holds anchor)
- `unregister_cmd_arrow_right/left(hk_ref)`: clears callback from dict + `UnregisterEventHotKey`

Safety-net: `_deferred_switch_to_tracker`/`_deferred_switch_to_main` wrap NSBlockOperation lambdas with `try/except + stderr-print`. Any future Python exception in the deferred block logs instead of SIGABRT.

### Header Window Indicator (Problem 2)

Tracker top_bar changed from `_CursorlessLabel` (static "Bead Tracker") to `_CursorlessButton` (same style/size as main panel `toggle_btn`), wired to `toggleAutoJump:`.

Titles (both updated on every `toggleAutoJump_` call and on panel rebuild):
- Main panel: `[Sessions] · Beads     Auto-Jump: {state}`
- Tracker panel: `Sessions · [Beads]     Auto-Jump: {state}`

`_make_bead_nspanel` now returns `(panel, stack, toggle_btn)`. `app._tracker_toggle_btn` stored on `CCMenuBarApp`. Wired in `_tick` init block alongside `_toggle_btn`. `toggleAutoJump_` updates both buttons directly (not via `sender`).
