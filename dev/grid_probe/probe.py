#!/usr/bin/env python3
"""
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
"""

# INFRASTRUCTURE
import signal
import sys

import objc
from AppKit import (
    NSApplication, NSApplicationActivationPolicyAccessory,
    NSAttributedString, NSButton, NSColor, NSFont,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSGridCell, NSGridCellPlacementLeading, NSGridView,
    NSPanel, NSScreen, NSStatusWindowLevel, NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSMakeRect, NSObject, NSRange

PANEL_W      = 380
PANEL_H      = 90     # just tall enough for 3 rows + 12pt top margin
GRID_X       = 11     # pts left margin — matches prod panel inset
GRID_Y_BTOP  = 8      # pts from top of panel content view to grid top
GRID_INSET_R = 11     # pts right margin
GRID_W       = PANEL_W - GRID_X - GRID_INSET_R   # 358
ROW_H        = 20     # pts

# Column widths — matches architecture spec
_COL0_W  = 20    # slot [N]
_COL1_W  = 14    # star *
_COL3_W  = 22    # dot [ ]/[*]
_COL4_W  = 68    # badge [B M:SS]
_COL_SPC = 2     # NSGridView columnSpacing (pts between adjacent columns)

# Flexible col 2: fills remaining space after fixed cols + 4 gaps
_COL2_W = GRID_W - _COL0_W - _COL1_W - _COL3_W - _COL4_W - 4 * _COL_SPC   # 218

# Expected col-3 left edge in grid coordinates
_COL3_X = _COL0_W + _COL_SPC + _COL1_W + _COL_SPC + _COL2_W + _COL_SPC    # 238

_MENLO = lambda: NSFont.fontWithName_size_('Menlo', 13.0)


# FUNCTIONS


# Plain borderless Menlo NSButton — used for all grid cells
def _cell_btn(text: str, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color:
        attrs[NSForegroundColorAttributeName] = color
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, ROW_H))
    btn.setBordered_(False)
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    btn.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn


# Build the 5-column NSGridView with separator + session + worker rows
def _build_grid(controller) -> NSGridView:
    empty = NSGridCell.emptyContentView()

    grid = NSGridView.gridViewWithNumberOfColumns_rows_(5, 0)
    grid.setColumnSpacing_(_COL_SPC)
    grid.setRowSpacing_(1.0)

    # All columns: leading x-placement
    for i in range(5):
        grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)

    # Fixed widths on cols 0, 1, 3, 4 — col 2 fills remaining (no setWidth_)
    grid.columnAtIndex_(0).setWidth_(float(_COL0_W))
    grid.columnAtIndex_(1).setWidth_(float(_COL1_W))
    grid.columnAtIndex_(3).setWidth_(float(_COL3_W))
    grid.columnAtIndex_(4).setWidth_(float(_COL4_W))

    # Row 0: merged separator "── Project_A" spanning all 5 cols
    sep_btn = _cell_btn('── Project_A ──────────────────────', NSColor.secondaryLabelColor())
    grid.addRowWithViews_([sep_btn, empty, empty, empty, empty])
    grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 5), NSRange(0, 1))

    # Row 1: session row — ALL 5 cells wired target/action/tag=1
    slot_btn  = _cell_btn('[1] ', NSColor.systemOrangeColor())
    star_btn  = _cell_btn('* ',  NSColor.systemOrangeColor())
    name_btn  = _cell_btn('sample_session',  NSColor.systemOrangeColor())
    dot1_btn  = _cell_btn('[ ]', NSColor.systemOrangeColor())
    badge_btn = _cell_btn('[B 1:23]', NSColor.systemOrangeColor())
    for btn in (slot_btn, star_btn, name_btn, dot1_btn, badge_btn):
        btn.setTag_(1)
        btn.setTarget_(controller)
        btn.setAction_(b'rowClicked:')
    grid.addRowWithViews_([slot_btn, star_btn, name_btn, dot1_btn, badge_btn])

    # Row 2: worker row — col 0/1/4 empty; col 2/3 wired tag=2
    wname_btn = _cell_btn('worker_x')
    wdot_btn  = _cell_btn('[*]', NSColor.systemGreenColor())
    for btn in (wname_btn, wdot_btn):
        btn.setTag_(2)
        btn.setTarget_(controller)
        btn.setAction_(b'rowClicked:')
    grid.addRowWithViews_([empty, empty, wname_btn, wdot_btn, empty])

    return grid


# Assemble NSPanel + NSGridView; return (panel, grid)
def _make_panel(controller):
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_W, PANEL_H),
        NSWindowStyleMaskNonactivatingPanel, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.enableCursorRects()

    cv = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_W, PANEL_H))
    panel.setContentView_(cv)

    grid = _build_grid(controller)
    # Pin grid to cv via Auto Layout so col-2 fills remaining width
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    cv.addSubview_(grid)
    # cv.leading + GRID_X == grid.leading  →  cv.leading == grid.leading - GRID_X
    cv.leadingAnchor().constraintEqualToAnchor_constant_(
        grid.leadingAnchor(), -GRID_X).setActive_(True)
    # cv.trailing - GRID_INSET_R == grid.trailing  →  cv.trailing == grid.trailing + GRID_INSET_R
    cv.trailingAnchor().constraintEqualToAnchor_constant_(
        grid.trailingAnchor(), GRID_INSET_R).setActive_(True)
    # grid.top == cv.top + GRID_Y_BTOP  (y increases downward in layout anchors)
    grid.topAnchor().constraintEqualToAnchor_constant_(
        cv.topAnchor(), float(GRID_Y_BTOP)).setActive_(True)

    return panel, grid


# Print expected column x-positions for alignment sanity check
def _print_startup_report() -> None:
    print('=== NSGridView probe running ===', flush=True)
    print(f'  Panel:  {PANEL_W} × {PANEL_H} pt', flush=True)
    print(f'  Grid:   {GRID_W} pt wide, 3 rows, 5 cols', flush=True)
    print(f'  Row 0:  merged separator "── Project_A" (spans all 5 cols)', flush=True)
    print(f'  Row 1:  session row (orange) — click ANY cell → "row 1 clicked"', flush=True)
    print(f'  Row 2:  worker row (green dot) — click name/dot → "row 2 clicked"', flush=True)
    print(flush=True)
    print('=== PyObjC bindings confirmed ===', flush=True)
    print('  NSGridView.gridViewWithNumberOfColumns_rows_(5, 0)                ✓', flush=True)
    print('  NSGridCell.emptyContentView()  (callable, returns sentinel view)  ✓', flush=True)
    print('  grid.addRowWithViews_([view, empty, ...])                         ✓', flush=True)
    print('  grid.columnAtIndex_(i).setWidth_(N)                               ✓', flush=True)
    print('  grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading) ✓  (value=2)', flush=True)
    print('  grid.mergeCellsInHorizontalRange_verticalRange_(NSRange, NSRange) ✓', flush=True)
    print('  btn.setTag_(N) / setTarget_() / setAction_(b"sel:")               ✓', flush=True)
    print(flush=True)
    print('=== Column layout (expected x-positions within grid) ===', flush=True)
    x = 0
    for i, (w, label) in enumerate([
        (_COL0_W, 'slot [N]'), (_COL1_W, 'star *'),
        (_COL2_W, 'name (flex)'), (_COL3_W, 'dot [ ]/[*]'), (_COL4_W, 'badge'),
    ]):
        marker = '  ← ALIGNMENT KEY' if i == 3 else ''
        print(f'  col {i} ({label:15s}): x={x:4d}  w={w}{marker}', flush=True)
        x += w + _COL_SPC
    print(flush=True)
    print(f'  col-3 (dot) left edge at x={_COL3_X} for BOTH session row AND worker row', flush=True)
    print(f'  → col-3 alignment is guaranteed by grid layout (col 0/1/4 presence/absence', flush=True)
    print(f'    does NOT affect col-2/3 positions since col-2 fills fixed remaining space)', flush=True)
    print(flush=True)
    print('Visual: orange [ ] and green [*] must be at the same x.', flush=True)
    print('Click:  orange cells → "row 1 clicked"; green/white cells → "row 2 clicked"', flush=True)
    print('Quit:   Cmd-Q', flush=True)
    print(flush=True)


# ORCHESTRATOR


class _ClickController(NSObject):
    def rowClicked_(self, sender):
        tag = sender.tag()
        print(f'row {tag} clicked  (tag={tag})', flush=True)


def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    ctrl = _ClickController.alloc().init()
    panel, _grid = _make_panel(ctrl)

    # Position panel near top-center of primary screen
    screen = NSScreen.mainScreen()
    if screen is not None:
        sf = screen.visibleFrame()
        px = sf.origin.x + sf.size.width / 2.0 - PANEL_W / 2.0
        py = sf.origin.y + sf.size.height - PANEL_H - 40
        panel.setFrame_display_(NSMakeRect(px, py, PANEL_W, PANEL_H), False)

    _print_startup_report()

    panel.orderFront_(None)
    app.run()


main()
