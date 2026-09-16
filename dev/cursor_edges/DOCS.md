# dev/cursor_edges/

## Role
Standalone NSPanel cursor-rect investigation probe mirroring production panel layout exactly, to
isolate which view wins the cursor-rect dispatch race — never touches `src/`. Touch when
re-investigating NSPanel edge-hover cursor behavior. Never import or execute `probe.py`; it calls
`main()` unguarded and opens a real window.

## Public Interface
No `__init__.py` in this directory. `probe.py` is the entry point, run directly (never imported —
see Role); the other 4 modules are its support files, imported by `probe.py` only.

## Flow
CLI flags (`--fix`/`--leaf-rects`/`--no-resizable`/`--tracking`) go in. `probe.py` builds a real
`NSApplication` + `NSPanel` mirroring production geometry, installs cursor-rect/tracking-area
logging on every view, and runs the foreground event loop. Output is stderr log lines only,
captured via `2>file.log`.

## Modules

### probe.py (130 LOC)

**Purpose:** Entry script — parses CLI flags, builds the app and panel, logs the startup banner,
runs the foreground event loop.
**Reads:** nothing — standalone GUI window, no file/log input.
**Writes:** nothing — stderr log lines only, via the imported `_log`.
**Called by:** none — run manually, foreground only (`Cmd-Q`/`Ctrl-C` to quit). Never import this
module; `main()` runs unguarded at module scope.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_panel.py`;
`AppKit` (pyobjc bridge).

---

### cursor_edges_constants.py (27 LOC)

**Purpose:** Geometry constants mirroring production exactly, `NSTrackingArea` option-flag
combinations, and the two mutable flags `probe.py` sets from CLI args.
**Reads:** nothing.
**Writes:** nothing — its two flags are mutated in place by `probe.py`, module-qualified.
**Called by:** `probe.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`,
`cursor_edges_panel.py`.
**Calls out:** `AppKit` (pyobjc bridge).

---

### cursor_edges_logging.py (47 LOC)

**Purpose:** stderr logging helpers (`_log`, `_dump_hierarchy`) and the two tracking helpers
(`_install_tracking_area`, `_install_global_mouse_monitor`).
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `probe.py`, `cursor_edges_views.py`.
**Calls out:** `cursor_edges_constants.py`; `AppKit` (pyobjc bridge).

---

### cursor_edges_views.py (344 LOC)

**Purpose:** The 6 logging/tracking NSView-family subclasses that mirror production views, each
printing to stderr on every cursor/tracking AppKit callback.
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `cursor_edges_panel.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`; `objc`, `AppKit`,
`Foundation` (pyobjc bridge).

---

### cursor_edges_panel.py (140 LOC)

**Purpose:** Builds the probe `NSPanel` that mirrors production panel geometry and z-order
exactly (window, content view, footer, top bar, session-row stack).
**Reads:** nothing.
**Writes:** nothing — constructs but never shows the panel; `probe.py`'s `main()` orders it front.
**Called by:** `probe.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`;
`AppKit`, `Foundation` (pyobjc bridge).

---

## State
No persistent state lives in this directory. `cursor_edges_constants.py` owns the two mutable
flags (`_LEAF_RECTS_ENABLED`, `_TRACKING_ENABLED`), written once by `probe.py` from CLI args and
read by every other module for the lifetime of one foreground run; nothing survives past process
exit.
