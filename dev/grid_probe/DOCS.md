# dev/grid_probe/

## Role

Standalone PyObjC probe verifying `NSGridView` column alignment and click routing before that
layout approach was used in a real pane. No `src/` import — a visual/interactive check of AppKit
API behavior, not a regression guard. Touch this directory only if re-verifying a new PyObjC
`NSGridView` API surface before adopting it elsewhere; it is not wired to any production code path.

## Modules

### probe.py (231 LOC)

**Purpose:** Builds a 5-column, 3-row `NSGridView` (merged separator row, an all-orange "session"
row, a partially-empty "worker" row) inside a floating `NSPanel`, prints each column's expected
x-position, and routes any cell click to a `rowClicked_` handler that prints the clicked row's tag
— a manual visual + click-routing check of `NSGridView`/`NSGridCell`/`NSGridColumn` bindings and
`mergeCellsInHorizontalRange_verticalRange_`.
**Reads:** nothing external — all layout values are module constants.
**Writes:** stdout (startup report, column x-positions, click log lines); the floating panel itself.
**Called by:** none — run manually (`./venv/bin/python3 dev/grid_probe/probe.py`); quit with Cmd-Q.
**Calls out:** `objc`, `AppKit`, `Foundation` (PyObjC).

---

## Gotchas

**Column 2 is the only flexible column** — its width is computed as the remainder after the four
fixed columns (`_COL0_W`/`_COL1_W`/`_COL3_W`/`_COL4_W`) and their spacing, so column 3's (the dot
column) left edge lands at the same x in both the session and worker rows regardless of which cells
in columns 0/1/4 are empty. Changing any fixed column width without recomputing `_COL2_W`/`_COL3_X`
breaks that alignment guarantee silently.
