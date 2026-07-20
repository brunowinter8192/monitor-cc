
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

---

## Layout Fixes (2026-05-21)

Four UI fixes across bead_panel.py, panel.py, hotkey.py, app.py.

### D1 — Bead-Panel Left-Aligned Bead Rows

Root cause: `_make_bead_row` NSView containers had `heightAnchor` constraint but no `widthAnchor` constraint. NSStackView with `NSLayoutAttributeLeading` alignment resolves item widths from `intrinsicContentSize`. NSTextField (project header) has `intrinsicContentSize.width` = text width; NSView container has `{-1, -1}`. Under Auto Layout, NSStackView position each item type differently → inconsistent x-offsets for bead rows.

Fix:
- `container.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)` added to `_make_bead_row` and `_make_expand_view`
- `expand_btn` x-offset changed from `0` to `indent=16` (16pt visual indent under project header, signals "child" relationship)
- `btn_w` reduced by 16 to compensate
- `x_btn` x-position stays at `pw - _UNTRACK_W` (right container edge, unchanged)

### D2 — Bead-Panel Title Wrapping

Root cause: `_make_bead_row` used manual char-count truncation (`title[:max_ch - 1] + '…'`) with no AppKit text measurement. Container height was fixed to `_ROW_H - 1 = 20`.

Fix:
- New helper `_bead_row_height(row_text, btn_w) -> int`: measures wrapped height via `NSAttributedString.boundingRectWithSize_options_context_(NSMakeSize(btn_w, 10000), 1, None)` (option 1 = `NSStringDrawingUsesLineFragmentOrigin`). Returns `max(_ROW_H - 1, int(height) + 4)`.
- `_make_bead_row`: removed truncation, uses full title, enables `expand_btn.cell().setWraps_(True)` + `setLineBreakMode_(0)` (word-wrap). Container height set to `row_h = _bead_row_height(row_text, btn_w)`.
- `x_btn` y-position: `row_h - (_ROW_H - 1)` — top-aligned to stay level with bead ID line on wrapping rows.
- `_compute_bead_height`: replaces `h += _ROW_H` with `_bead_row_height(row_text, btn_w)` call, reconstructing `row_text` per bead (same format as `_make_bead_row`).

### D3 — Sessions-Panel Fixed-Width Columns

Root cause: `_rebuild_panel` and `_update_panel_inplace` used `name_width = max(len(s.name) for s in sessions)` — dynamic per-rebuild. All other columns floated with name column width, causing session rows to drift on rebuild when session set changed.

Fix: removed dynamic `name_width`. Added fixed column constants (Menlo 13pt ≈ 7.8pt/char):
- `_COL_SLOT_W = 4` chars ≈ 28pt — `[N] ` or `    ` (worker indent)
- `_COL_NAME_W = 23` chars ≈ 180pt — name, ljust + right-truncate
- `_COL_TIMER_W = 9` chars ≈ 70pt — `[B M:SS]` badge (max `[B 99:59]` = 9 chars), ljust-padded

Name column now starts at string position 6 for both main sessions (`[N] ● ` = 4+2) and workers (`      ` = 6 spaces). Status column at position 30. Timer column at 35. Column positions are immutable across rebuilds.

### D4 — Cmd+K Panel Background

New global hotkey Cmd+K (`kVK_ANSI_K = 0x28`, id `_CMD_K_ID = 2`) following identical pattern to Cmd+L (`register_cmd_l`). Always-active (registered once in `__init__`, never unregistered).

State: `app._panel_backgrounded: bool = False`.

Handler (`_background_panel`): dispatched via `NSOperationQueue.mainQueue().addOperationWithBlock_` (main-thread safety, same as Cmd+→/←). Logic: if backgrounded → `orderFrontRegardless()` + clear flag; elif panel open → `orderBack_(None)` + set flag; else no-op.

`togglePanel_` (`_PanelController`): if `_panel_backgrounded` → bring to front + clear flag + return early (Cmd+L / bar-click → foreground, not close). This handles the "Cmd+L on backgrounded panel brings it to front" edge case.

`_close_main_panel` + `_close_tracker_panel`: both reset `_panel_backgrounded = False`. Handles Cmd+→/← cycling: close resets backgrounded state before opening the other panel in foreground.

## UI Fixes Round 2 + Cmd+K Debug

### D1 — Bead Title Left-Alignment

Root cause: `_make_bead_row` set no `setAlignment_` on `expand_btn.cell()`. NSButtonCell centers text by default across the full cell width (`btn_w` ≈ 340pt) — text landed at roughly x=indent+btn_w/2 instead of flush at the indent offset.

Fix: `expand_btn.cell().setAlignment_(0)` (NSTextAlignmentLeft = 0) after the existing `setWraps_` + `setLineBreakMode_` calls. Works with `NSButtonTypeMomentaryPushIn` + `setBordered_(False)` without a cell-type change.

### D2 — Expand-Content Wrapping

Root cause: `_make_expand_view` used a fixed `row_h = _ROW_H - 1` per line without enabling wrapping → long lines got truncated. `_compute_bead_height` computed identically with a fixed `(_ROW_H - 1)` → the panel was too short for wrapped expand views.

Fix in `_make_expand_view`:
- `line_heights = [_bead_row_height(line or ' ', inner_w) for line in lines]` — per-line height via AppKit measurement (analogous to `_make_bead_row`)
- `total = sum(line_heights)`, frame and constraints set from that
- Per tf: `cell().setWraps_(True)` + `cell().setLineBreakMode_(0)` + `setUsesSingleLineMode_(False)` — same treatment as expand_btn in `_make_bead_row`
- y-accumulation: `y = total; y -= lh` before each tf instead of a fixed step

Fix in `_compute_bead_height`: `expand_inner_w = pw - 16` + `sum(_bead_row_height(...) for line in ...)` instead of `len(lines) * (_ROW_H - 1)`. Mirrors `_make_expand_view`'s geometry exactly.

### D3 — Cmd+K ID Collision

Root cause: `_CMD_K_ID = 2` collided with the Cmd+1 digit (digit IDs = `slot + 1`, slot 1 → ID 2). The digit handler (`_ensure_digit_handler`) is installed when the panel opens — Carbon calls it first. For a Cmd+K event (id=2): `slot = 2-1 = 1`, `_DIGIT_CALLBACKS.get(1)` finds the Cmd+1 callback (if ≥1 session is active) → runs it → `return 0` (consumed). The Cmd+K handler never sees the event.

ID allocation: L=1, digits=2-10 (`slot+1`), arrow-right=20, arrow-left=21. Free slot: 30.

Fix: `_CMD_K_ID = 30`. The only change is in `hotkey.py` — a constant, not the `RegisterEventHotKey` keycode. An import check confirmed no more collision.

Debug prints were not added — the ID collision was unambiguously identifiable via static code analysis (the slot mapping `hkid.id - 1` + a table of all registered hotkey IDs).

## Cmd+K orderBack + Sessions Alignment (Round 2 Follow-Up)

### Cmd+K — orderBack_ Ineffective on NSStatusWindowLevel

Debug prints confirmed: registration OK (hk_ref non-null), `kEventHotKeyPressed` fires (`hkid.id=30`), `_background_panel` gets called, state flips correctly (`_panel_backgrounded` True↔False). The only problem: `orderBack_(None)` on a panel with `setLevel_(NSStatusWindowLevel)` (level ≈ 25) is visually ineffective. `orderBack_` orders the window behind other windows AT THE SAME OR HIGHER level — no normal app window sits at level ≥ 25, so the panel stays visibly in front.

Fix: temporarily lower the level before `orderBack_`, restore it when foregrounding:
- Background: `panel.setLevel_(0)` (NSNormalWindowLevel) → `panel.orderBack_(None)`
- Foreground: `panel.setLevel_(25)` (NSStatusWindowLevel) → `panel.orderFrontRegardless()`

Applies symmetrically to both panels (`_panel` + `_tracker_panel`).

`NSStatusWindowLevel` is not imported as a constant in `app.py` — the integer `25` is used directly (matches the AppKit enum value).

### Bug 5 — Sessions Column Drift (● vs ASCII)

`●` (U+25CF, BLACK CIRCLE) renders in Menlo 13pt with a wider advance width than a monospace cell → columns after the bullet drift slightly depending on project context. Fix: `●` → `*` (ASCII 0x2A) in both format strings in `panel.py` (main-row `_rebuild_panel` + `_update_panel_inplace`). The worker prefix (`"      "` 6 spaces) unchanged. Both prefixes are now purely ASCII → exact Menlo alignment guaranteed.

## Cmd+L Double-Tap Reset (2026-05-21)

**Feature:** double-tapping Cmd+L (two presses < 300ms) resets the active panel to its default size (PANEL_WIDTH=380, PANEL_HEIGHT=460). A single Cmd+L stays a toggle.

**Implementation in `togglePanel_` (`app.py`):**
- State: `app._last_cmd_l_ts: float = 0.0` (init in `CCMenuBarApp.__init__`)
- Detection: `is_double_tap = (now - app._last_cmd_l_ts) < 0.3` at method entry
- Double-tap path: `_reset_panel_to_default(app)` + `app._last_cmd_l_ts = 0.0` (sentinel), then `return`
- Single-tap path: `app._last_cmd_l_ts = now`, then normal toggle behavior unchanged

**`_reset_panel_to_default(app)` (new function in `app.py`):**
1. `app._panel_width = PANEL_WIDTH`
2. `app._panel_min_height = PANEL_HEIGHT`
3. Tracker open → `_resize_tracker_panel(app, PANEL_HEIGHT)` (imported from `bead_panel.py`)
4. Main open → `_resize_panel(app, PANEL_HEIGHT)` (from `panel.py`)
5. No `_save_settings` — the default is a code constant, not a user setting

**Sentinel pattern:** after a reset, `_last_cmd_l_ts = 0.0` is set. `now - 0.0 = now ≈ 1.7e9` → far above 0.3 → the next Cmd+L is guaranteed not to be a double-tap (triple-press: open+reset+close).

**Backgrounded panel:** the first press restores it (`orderFrontRegardless`, sets `_last_cmd_l_ts = now`, return). The second press finds the panel open and not backgrounded → hits the normal double-tap branch.

**Edge case: nothing open + double-tap:** `_reset_panel_to_default` is not called (guarded by `if _tracker_open or _panel_open`), `_last_cmd_l_ts = 0.0`, return — no open, no resize.
