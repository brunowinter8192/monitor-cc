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

### probe.py (728 LOC)

**Purpose:** Launches a foreground NSPanel with 5 logging view subclasses
(`_LoggingContentView`, `_LoggingStackView`, `_LoggingButton`, `_LoggingFooterView`,
`_LoggingTopBarView`, each mirroring one production view) that print to stderr on
`resetCursorRects`, `cursorUpdate_`, `mouseEntered_`/`mouseExited_`, `mouseMoved_`+hitTest, and a
global `NSEventMaskMouseMoved` monitor — surfaces which view's cursor rect (or tracking area)
actually wins at each screen position.
**Reads:** nothing — standalone GUI window, no file/log input.
**Writes:** nothing — stderr log lines only (capture with `2>file.log`).
**Called by:** none — run manually, foreground only (`Cmd-Q`/`Ctrl-C` to quit).
**Calls out:** `objc`, `AppKit`, `Foundation` (pyobjc bridge).

**CLI flags:** `--fix` (calls `enableCursorRects()` after `setContentView_`), `--leaf-rects`
(installs resize rects on covering leaf subviews too, requires `--fix`), `--no-resizable`
(constructs the panel without `NSWindowStyleMaskResizable`) — combinable.

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
