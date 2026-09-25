# dev/nsgridview_migration/

## Role
Standalone PyObjC probe verifying NSGridView column alignment and click routing before that layout was used in a real pane. No `src/` import; a visual, interactive AppKit check, not a regression guard. Touch only to re-verify a new NSGridView API surface.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python3 dev/nsgridview_migration/probe.py` (interactive GUI; opens a real floating panel, quit with Cmd-Q).

## Flow
No data in; layout values are module constants. The probe builds a floating panel with a five-column grid, prints the expected column positions, then blocks in the AppKit event loop printing one line per cell click until closed.

## Modules

### probe.py (190 LOC)

**Purpose:** Builds a five-column, three-row grid in a floating panel and routes cell clicks to a handler printing the clicked row; a manual visual check.
**Reads:** nothing external.
**Writes:** stdout (startup report, column positions, click log); the floating panel.
**Called by:** none; run manually.
**Calls out:** `objc`, `AppKit`, `Foundation` (PyObjC).

---

## State
No persistent state. Geometry constants live at module scope; click state lives only in the running controller instance for one interactive run.
