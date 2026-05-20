
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

## Layout-Fixes (2026-05-21)

Four UI fixes across bead_panel.py, panel.py, hotkey.py, app.py.

### D1 — Bead-Panel Linksbündige Bead-Zeilen

Root cause: `_make_bead_row` NSView containers had `heightAnchor` constraint but no `widthAnchor` constraint. NSStackView with `NSLayoutAttributeLeading` alignment resolves item widths from `intrinsicContentSize`. NSTextField (project header) has `intrinsicContentSize.width` = text width; NSView container has `{-1, -1}`. Under Auto Layout, NSStackView position each item type differently → inconsistent x-offsets for bead rows.

Fix:
- `container.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)` added to `_make_bead_row` and `_make_expand_view`
- `expand_btn` x-offset changed from `0` to `indent=16` (16pt visual indent under project header, signals "child" relationship)
- `btn_w` reduced by 16 to compensate
- `x_btn` x-position stays at `pw - _UNTRACK_W` (right container edge, unchanged)

### D2 — Bead-Panel Titel Wrapping

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

## UI-Fixes Runde 2 + Cmd+K Debug

### D1 — Bead-Titel linksbündig

Root cause: `_make_bead_row` setzte kein `setAlignment_` auf `expand_btn.cell()`. NSButtonCell zentriert Text defaultmäßig in der vollen Cell-Breite (`btn_w` ≈ 340pt) — Text landete bei ca. x=indent+btn_w/2 statt bündig am indent-Offset.

Fix: `expand_btn.cell().setAlignment_(0)` (NSTextAlignmentLeft = 0) nach den bestehenden `setWraps_` + `setLineBreakMode_` Aufrufen. Funktioniert mit `NSButtonTypeMomentaryPushIn` + `setBordered_(False)` ohne Cell-Type-Wechsel.

### D2 — Expand-Inhalt gewrappt

Root cause: `_make_expand_view` verwendete fixed `row_h = _ROW_H - 1` pro Zeile ohne Wrapping-Aktivierung → lange Zeilen abgeschnitten. `_compute_bead_height` rechnete identisch mit fixed `(_ROW_H - 1)` → Panel zu niedrig für gewrappte Expand-Views.

Fix in `_make_expand_view`:
- `line_heights = [_bead_row_height(line or ' ', inner_w) for line in lines]` — per-Zeile Höhe via AppKit-Messung (analog `_make_bead_row`)
- `total = sum(line_heights)`, Frame und Constraints damit gesetzt
- Pro tf: `cell().setWraps_(True)` + `cell().setLineBreakMode_(0)` + `setUsesSingleLineMode_(False)` — gleiche Behandlung wie expand_btn in `_make_bead_row`
- y-Akkumulation: `y = total; y -= lh` vor jedem tf statt fixed step

Fix in `_compute_bead_height`: `expand_inner_w = pw - 16` + `sum(_bead_row_height(...) for line in ...)` statt `len(lines) * (_ROW_H - 1)`. Spiegelt `_make_expand_view`-Geometrie exakt wider.

### D3 — Cmd+K ID-Kollision

Root cause: `_CMD_K_ID = 2` kollidierte mit Cmd+1-Digit (Digit-IDs = `slot + 1`, Slot 1 → ID 2). Digit-Handler (`_ensure_digit_handler`) wird beim Panel-Öffnen installiert — Carbon ruft ihn zuerst auf. Für Cmd+K-Event (id=2): `slot = 2-1 = 1`, `_DIGIT_CALLBACKS.get(1)` findet Cmd+1-Callback (falls ≥1 Session aktiv) → führt ihn aus → `return 0` (consumed). Cmd+K-Handler bekommt das Event nie zu sehen.

ID-Belegung: L=1, Digits=2-10 (`slot+1`), Arrow-Right=20, Arrow-Left=21. Freier Slot: 30.

Fix: `_CMD_K_ID = 30`. Einzige Änderung in `hotkey.py` — Konstante, nicht `RegisterEventHotKey`-Keycode. Import-Check bestätigt keine Kollision mehr.

Debug-Prints wurden nicht eingebaut — ID-Kollision war durch statische Code-Analyse eindeutig identifizierbar (slot-Mapping `hkid.id - 1` + ID-Tabelle aller registrierten Hotkeys).
