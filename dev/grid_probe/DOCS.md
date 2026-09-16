# dev/grid_probe/

## Role
Standalone PyObjC probe verifying `NSGridView` column alignment and click routing before that
layout was used in a real pane. No `src/` import — a visual/interactive AppKit check, not a
regression guard. Touch only to re-verify a new `NSGridView` API surface before adopting it
elsewhere.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python3 dev/grid_probe/probe.py`
(interactive GUI script — opens a real floating panel, quit with Cmd-Q or close window).

## Flow
No data in — all layout values are module constants. Builds a floating `NSPanel` containing a
5-column `NSGridView`, prints the expected column x-positions to stdout, then blocks in the AppKit
event loop printing one line per cell click until the window is closed.

## Modules

### probe.py (191 LOC)

**Purpose:** Builds a 5-column, 3-row `NSGridView` in a floating `NSPanel` and routes cell clicks
to a handler that prints the clicked row's tag — a manual visual + click-routing check.
**Reads:** nothing external — all layout values are module constants.
**Writes:** stdout (startup report, column x-positions, click log lines); the floating panel itself.
**Called by:** none — run manually (`./venv/bin/python3 dev/grid_probe/probe.py`); quit with Cmd-Q.
**Calls out:** `objc`, `AppKit`, `Foundation` (PyObjC).

---

## State
No persistent state — `probe.py` holds its own column-width/panel-geometry constants at module
scope and its live click-count/tag state only inside the running `_ClickController` instance for
the duration of one interactive run; nothing is read from or written to disk.
