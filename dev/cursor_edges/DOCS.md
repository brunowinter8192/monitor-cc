# dev/cursor_edges/

## Role

Standalone NSPanel cursor-rect investigation probe. `_PanelContentView.resetCursorRects` installs
4 cursor zones on the production NSPanel (bottom `↕`, left `↔`, right `↔`, interior `→`) — this
probe mirrors the production panel layout exactly (same geometry, z-order, autoresizing masks) in
a standalone foreground window to isolate which view wins the cursor-rect dispatch race, without
touching `src/`. Touch this directory when re-investigating NSPanel edge-hover cursor behavior;
the full iteration/hypothesis trail lives in `process-docs/menubar_build/` (see that area for
history — this probe's own current shape is documented below).

## Modules

### probe.py (189 LOC)

**Purpose:** Entry script — parses CLI flags, builds the app + panel, logs the startup banner,
runs the foreground event loop. Carries the full module docstring (flag semantics, hypotheses,
usage).
**Reads:** nothing — standalone GUI window, no file/log input.
**Writes:** nothing — stderr log lines only (capture with `2>file.log`), via the imported `_log`.
**Called by:** none — run manually, foreground only (`Cmd-Q`/`Ctrl-C` to quit).
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_panel.py`;
`AppKit` (pyobjc bridge).

**CLI flags:** `--fix` (calls `enableCursorRects()` after `setContentView_`), `--leaf-rects`
(installs resize rects on covering leaf subviews too, requires `--fix`), `--no-resizable`
(constructs the panel without `NSWindowStyleMaskResizable`) — combinable.

---

### cursor_edges_constants.py (32 LOC)

**Purpose:** Geometry constants mirroring production exactly, `NSTrackingArea` option flag
combinations, and the two mutable flags (`_LEAF_RECTS_ENABLED`, `_TRACKING_ENABLED`) `probe.py`
sets from CLI args and every other module in this directory reads.
**Reads:** nothing.
**Writes:** nothing (its two flags are mutated in place by `probe.py`, module-qualified —
`import cursor_edges_constants as cec; cec._LEAF_RECTS_ENABLED = ...` — never `from ... import`,
which would decouple the reader's copy from later writes).
**Called by:** `probe.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`,
`cursor_edges_panel.py`.
**Calls out:** `AppKit` (pyobjc bridge).

---

### cursor_edges_logging.py (49 LOC)

**Purpose:** stderr logging helpers (`_log`, `_dump_hierarchy`) and the two non-view-class
tracking helpers (`_install_tracking_area`, `_install_global_mouse_monitor`).
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `probe.py`, `cursor_edges_views.py`.
**Calls out:** `cursor_edges_constants.py`; `AppKit` (pyobjc bridge).

---

### cursor_edges_views.py (371 LOC)

**Purpose:** The 6 logging/tracking NSView-family subclasses that mirror production views
(`_LoggingContentView`, `_TrackingContentView`, `_LoggingStackView`, `_LoggingButton`,
`_LoggingFooterView`, `_LoggingTopBarView`) — each prints to stderr on `resetCursorRects`,
`cursorUpdate_`, `mouseEntered_`/`mouseExited_`, `mouseMoved_`+hitTest.
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `cursor_edges_panel.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`; `objc`, `AppKit`,
`Foundation` (pyobjc bridge).

---

### cursor_edges_panel.py (145 LOC)

**Purpose:** Builds the probe NSPanel that mirrors production `_make_nspanel()` geometry and
z-order exactly (window, content view, footer, top bar, session-row stack).
**Reads:** nothing.
**Writes:** nothing — constructs but never shows the panel (`probe.py`'s `main()` calls
`orderFront_`).
**Called by:** `probe.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`;
`AppKit`, `Foundation` (pyobjc bridge).

---

## Gotchas

**`cursorUpdate_` is not a reliable signal for cursor-rect dispatch.** It's the
`NSTrackingArea` callback mechanism; `addCursorRect_cursor_` dispatches directly at the AppKit
window level without firing `cursorUpdate_`. A zero `cursorUpdate_` count is consistent with
cursor-rect dispatch working normally. The correct signal is whether the visible cursor SHAPE
changes at the edge, not whether `cursorUpdate_` fired.

**`NSWindowStyleMaskNonactivatingPanel` blocks `enableCursorRects()` by default** — without an
explicit `enableCursorRects()` call after `setContentView_`, no cursor-rect dispatch happens on
a nonactivating panel at all (`--fix` tests this).
