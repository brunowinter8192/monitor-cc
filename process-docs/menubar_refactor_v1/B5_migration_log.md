# B5 — Step 6/6: HotkeyController migration log

## What we did

git mv `src/menubar/hotkey.py` → `src/menubar/hotkey_controller.py`, added `HotkeyController(app)` class at the end of the module, and rewired all call sites in `app.py`.

**hotkey_controller.py changes:**
- Added `from .system import _focus_session` (needed by `reregister_digits`)
- Added `HotkeyController` class after all existing module-level functions (INFRASTRUCTURE/FUNCTIONS sections unchanged)
- Class owns 4 migrated attrs: `_hotkey_digits_cb`, `_hotkey_digits_refs`, `_hotkey_arr_right_ref`, `_hotkey_arr_left_ref`
- Methods: `reregister_digits(desktop_to_cwd)`, `register_arrow_right/left(callback)`, `unregister_arrow_right/left()`, `unregister_digits()`

**app.py changes:**
- Import: `from .hotkey import (register_cmd_l, …, register_cmd_k)` → `from .hotkey_controller import HotkeyController, register_cmd_l, register_cmd_k`
- `CCMenuBarApp.__init__`: removed `self._hotkey_digits_cb/refs`, `self._hotkey_arr_right/left_ref` inits; added `self.hotkey = HotkeyController(self)`
- Removed `_reregister_digit_hotkeys()` function (16 lines)
- 3 `_reregister_digit_hotkeys(app/self)` call sites → `app/self.hotkey.reregister_digits(app/self.panel._desktop_to_cwd)`
- 6 arrow register call sites (3 panels × open): `register_cmd_arrow_right/left(...)` + manual ref storage → `app.hotkey.register_arrow_right/left(...)`
- 6 arrow unregister call sites (3 panels × close): `unregister_cmd_arrow_right/left(ref); ref = None` → `app.hotkey.unregister_arrow_right/left()`
- 1 digit unregister block in `_close_main_panel` (4 lines) → `app.hotkey.unregister_digits()`

## What we found

**GC-pinning constraint confirmed:** `_hotkey_cb/_ref/_k_cb/_k_ref` (Cmd+L and Cmd+K CFUNCTYPE + hk_ref) remain on `app`. Moving them to HotkeyController would invalidate the C callback after GC → SIGSEGV. The 4 migrated digit/arrow attrs were safe to move because the CFUNCTYPE anchors for those are held at module scope (`_DIGIT_HANDLER_CB`, `_ARROW_HANDLER_CB`) — the per-registration refs (hk_refs) can live anywhere since they only need to outlive the registration, not the CFUNCTYPE.

**`panel._desktop_to_cwd` access:** `_reregister_digit_hotkeys` previously accessed `app.panel._desktop_to_cwd` directly inside the function. In `reregister_digits(desktop_to_cwd)` it becomes a parameter — call sites pass `app.panel._desktop_to_cwd` explicitly. Cleaner interface (no hidden dependency on `app.panel`).

**No circular import from `.system`:** `hotkey_controller.py` now imports `_focus_session` from `system.py`. `system.py` has no module-level import of `hotkey_controller.py` — no cycle.

**LOC:** hotkey_controller.py 320 LOC (+55 vs hotkey.py 265). app.py 495 LOC (−32 vs pre-step 527).

## dev/ scripts used

None — pure refactor, no probe needed.

## Decision / next

Step 6/6 complete. All 6 controllers extracted:
1. `SessionsController` (B1)
2. `BeadController` (B2)
3. `QueueController` (B3)
4. `PanelManager` (B4)
5. `FocusController` (B4b)
6. `HotkeyController` (B5, this step)

`app.py` is now 495 LOC (down from ~700+ at refactor start). The composition refactor declared in the Phase A architecture decision is fully implemented. Remaining LOC ceiling violation in `app.py` is deferred (residual glue code: `_PanelController`, lifecycle functions, blink/settings helpers — no further concern extraction warranted without overcoupling).
