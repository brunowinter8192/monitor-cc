# 2026-09-16 — Comment/docstring salvage for dev/grid_probe/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/grid_probe/` (1 `.py` file, 231 LOC) into conformance with the project's
three-marker comment standard. Every comment and the one docstring below were relocated here
verbatim before deletion from the code. Zero `__doc__`/`argparse` hits, so the docstring was not
load-bearing and deleted outright.

**Area-name mismatch, flagged per Main's instruction:** this milestone's process-docs path is
`process-docs/nsgridview_migration/`, but the directory being cleaned is `dev/grid_probe/` — the
two names don't match, unlike every other area processed in this comment-salvage cycle (where
`dev/<x>/` paired with `process-docs/<x>/`). Main confirmed this mismatch is real and pre-existing,
not something to fix here — renaming either directory is out of scope for this milestone. Filed
here for whoever eventually reconciles `dev/` and `process-docs/` naming across the project.

**`probe.py` is a real desktop-driving GUI script — NEVER run or imported for this milestone.**
`main()` executes unconditionally at module scope (no `if __name__ == '__main__':` guard), so even
a plain `import probe` would trigger it. `main()` builds a real `NSApplication`, positions a real
`NSPanel` at the top-center of the primary screen, calls `panel.orderFront_(None)` (which shows
the window), and then blocks in `app.run()`'s AppKit event loop until Cmd-Q or the window is
closed. Behavior-unchanged proof for this file used a **token-skeleton diff** instead of execution:
tokenized the file before and after editing, dropped every `COMMENT` token and the module
docstring's `STRING` token (identified by AST position) plus whitespace-only tokens (`NL`,
`NEWLINE`, `INDENT`, `DEDENT`, `ENCODING`), and diffed the remaining token stream — 1246 tokens
before, byte-identical after (see completion checklist in the task response for the exact command
and result). This proves zero code tokens were added, removed, or reordered; only comments and the
docstring were touched.

---

## Salvage from dev/grid_probe/probe.py

Shebang (line 1, stays — not a comment per the standard):
```
#!/usr/bin/env python3
```

Module docstring (was lines 2-23, immediately after the shebang):
```
dev/grid_probe/probe.py — NSGridView column-alignment + click-routing verification.

Builds a 5-column NSGridView with 3 hardcoded rows:
  Row 0: merged-cell project separator spanning all 5 columns
  Row 1: session row — [1] * sample_session   [ ]  [B 1:23]  (all cells NSButton, tag=1)
  Row 2: worker row  —       worker_x         [*]            (col 0/1/4 empty, tag=2)

Confirms:
  - PyObjC bindings for NSGridView, NSGridCell, NSGridColumn
  - Column alignment: dot col-3 must align across row 1 and row 2
  - Click routing: any cell in row 1 → "row 1 clicked"; row 2 cells → "row 2 clicked"
  - mergeCellsInHorizontalRange_verticalRange_ for separator row
  - NSGridCell.emptyContentView() for absent cells

Prints column x-positions to stdout for alignment verification without visual inspection.

Run from project root:
    ./venv/bin/python3 dev/grid_probe/probe.py

Quit: Cmd-Q or close window.
```

Was line 43, trailing on the `PANEL_H` assignment:
```
PANEL_H      = 90     # just tall enough for 3 rows + 12pt top margin
```
(the comment token itself is `# just tall enough for 3 rows + 12pt top margin`)

Was line 44, trailing on the `GRID_X` assignment:
```
GRID_X       = 11     # pts left margin — matches prod panel inset
```
(the comment token itself is `# pts left margin — matches prod panel inset`)

Was line 45, trailing on the `GRID_Y_BTOP` assignment:
```
GRID_Y_BTOP  = 8      # pts from top of panel content view to grid top
```
(the comment token itself is `# pts from top of panel content view to grid top`)

Was line 46, trailing on the `GRID_INSET_R` assignment:
```
GRID_INSET_R = 11     # pts right margin
```
(the comment token itself is `# pts right margin`)

Was line 47, trailing on the `GRID_W` assignment:
```
GRID_W       = PANEL_W - GRID_X - GRID_INSET_R   # 358
```
(the comment token itself is `# 358`)

Was line 48, trailing on the `ROW_H` assignment:
```
ROW_H        = 20     # pts
```
(the comment token itself is `# pts`)

Was line 50 (above the column-width constants block):
```
# Column widths — matches architecture spec
```

Was line 51, trailing on the `_COL0_W` assignment:
```
_COL0_W  = 20    # slot [N]
```
(the comment token itself is `# slot [N]`)

Was line 52, trailing on the `_COL1_W` assignment:
```
_COL1_W  = 14    # star *
```
(the comment token itself is `# star *`)

Was line 53, trailing on the `_COL3_W` assignment:
```
_COL3_W  = 22    # dot [ ]/[*]
```
(the comment token itself is `# dot [ ]/[*]`)

Was line 54, trailing on the `_COL4_W` assignment:
```
_COL4_W  = 68    # badge [B M:SS]
```
(the comment token itself is `# badge [B M:SS]`)

Was line 55, trailing on the `_COL_SPC` assignment:
```
_COL_SPC = 2     # NSGridView columnSpacing (pts between adjacent columns)
```
(the comment token itself is `# NSGridView columnSpacing (pts between adjacent columns)`)

Was line 57 (above the `_COL2_W` assignment):
```
# Flexible col 2: fills remaining space after fixed cols + 4 gaps
```

Was line 58, trailing on the `_COL2_W` assignment:
```
_COL2_W = GRID_W - _COL0_W - _COL1_W - _COL3_W - _COL4_W - 4 * _COL_SPC   # 218
```
(the comment token itself is `# 218`)

Was line 60 (above the `_COL3_X` assignment):
```
# Expected col-3 left edge in grid coordinates
```

Was line 61, trailing on the `_COL3_X` assignment:
```
_COL3_X = _COL0_W + _COL_SPC + _COL1_W + _COL_SPC + _COL2_W + _COL_SPC    # 238
```
(the comment token itself is `# 238`)

Was line 69 (above `_cell_btn`):
```
# Plain borderless Menlo NSButton — used for all grid cells
```

Was line 76, trailing on a statement (inside `_cell_btn`):
```
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
```
(the comment token itself is `# NSButtonTypeMomentaryPushIn`)

Was line 81 (above `_build_grid`):
```
# Build the 5-column NSGridView with separator + session + worker rows
```

Was line 89 (inside `_build_grid`, above the column-placement loop):
```
    # All columns: leading x-placement
```

Was line 93 (inside `_build_grid`, above the fixed-width-setting block):
```
    # Fixed widths on cols 0, 1, 3, 4 — col 2 fills remaining (no setWidth_)
```

Was line 99 (inside `_build_grid`, above the Row 0 block):
```
    # Row 0: merged separator "── Project_A" spanning all 5 cols
```

Was line 104 (inside `_build_grid`, above the Row 1 block):
```
    # Row 1: session row — ALL 5 cells wired target/action/tag=1
```

Was line 116 (inside `_build_grid`, above the Row 2 block):
```
    # Row 2: worker row — col 0/1/4 empty; col 2/3 wired tag=2
```

Was line 128 (above `_make_panel`):
```
# Assemble NSPanel + NSGridView; return (panel, grid)
```

Was line 145 (inside `_make_panel`, above the Auto Layout pin block):
```
    # Pin grid to cv via Auto Layout so col-2 fills remaining width
```

Was line 148 (inside `_make_panel`, above the leading-anchor constraint):
```
    # cv.leading + GRID_X == grid.leading  →  cv.leading == grid.leading - GRID_X
```

Was line 151 (inside `_make_panel`, above the trailing-anchor constraint):
```
    # cv.trailing - GRID_INSET_R == grid.trailing  →  cv.trailing == grid.trailing + GRID_INSET_R
```

Was line 154 (inside `_make_panel`, above the top-anchor constraint):
```
    # grid.top == cv.top + GRID_Y_BTOP  (y increases downward in layout anchors)
```

Was line 161 (above `_print_startup_report`):
```
# Print expected column x-positions for alignment sanity check
```

Was line 217 (inside `main`, above the screen-positioning block):
```
    # Position panel near top-center of primary screen
```

## Salvage from dev/grid_probe/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas

**Column 2 is the only flexible column** — its width is computed as the remainder after the four
fixed columns (`_COL0_W`/`_COL1_W`/`_COL3_W`/`_COL4_W`) and their spacing, so column 3's (the dot
column) left edge lands at the same x in both the session and worker rows regardless of which cells
in columns 0/1/4 are empty. Changing any fixed column width without recomputing `_COL2_W`/`_COL3_X`
breaks that alignment guarantee silently.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
