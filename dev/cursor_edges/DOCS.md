# dev/cursor_edges/

## Role
Standalone NSPanel cursor-rect investigation probe mirroring production panel layout, to isolate which view wins the cursor-rect dispatch race. Never touches `src/`. Touch when re-investigating edge-hover cursor behavior. Never import or execute `probe.py` casually; it opens a real window.

## Public Interface
No `__init__.py`. `probe.py` is the entry point, run directly and never imported; the other four modules are its support files.

## Flow
CLI flags go in. `probe.py` builds a real NSApplication and NSPanel mirroring production geometry, installs cursor-rect and tracking-area logging on every view, and runs the foreground event loop. Output is stderr log lines only.

## Modules

### probe.py (143 LOC)

**Purpose:** Entry script: parses CLI flags, builds the app and panel, logs the startup banner, runs the foreground event loop.
**Reads:** nothing; standalone GUI window.
**Writes:** stderr log lines only.
**Called by:** none; run manually, foreground only. Runs unguarded at module scope, so never import it.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_panel.py`; `AppKit`.

---

### cursor_edges_constants.py (27 LOC)

**Purpose:** Geometry values mirroring production, tracking-area option combinations and the two mutable mode flags set from CLI args.
**Reads:** nothing.
**Writes:** nothing; its flags are mutated in place by `probe.py`.
**Called by:** `probe.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`, `cursor_edges_panel.py`.
**Calls out:** `AppKit`.

---

### cursor_edges_logging.py (47 LOC)

**Purpose:** stderr logging helpers plus the tracking-area and global-mouse-monitor installers.
**Reads:** nothing.
**Writes:** stderr.
**Called by:** `probe.py`, `cursor_edges_views.py`.
**Calls out:** `cursor_edges_constants.py`; `AppKit`.

---

### cursor_edges_views.py (344 LOC)

**Purpose:** Six logging NSView-family subclasses mirroring production views, each printing to stderr on every cursor or tracking callback.
**Reads:** nothing.
**Writes:** stderr.
**Called by:** `cursor_edges_panel.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`; `objc`, `AppKit`, `Foundation`.

---

### cursor_edges_panel.py (140 LOC)

**Purpose:** Builds the probe NSPanel mirroring production panel geometry and z-order; constructs but never shows it.
**Reads:** nothing.
**Writes:** nothing; the entry script orders the panel front.
**Called by:** `probe.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`; `AppKit`, `Foundation`.

---

## State
No persistent state. The constants module owns two mutable mode flags, written once by the entry script and read by the other modules for one foreground run.
