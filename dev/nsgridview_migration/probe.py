#!/usr/bin/env python3
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
PANEL_H      = 90
GRID_X       = 11
GRID_Y_BTOP  = 8
GRID_INSET_R = 11
GRID_W       = PANEL_W - GRID_X - GRID_INSET_R
ROW_H        = 20

_COL0_W  = 20
_COL1_W  = 14
_COL3_W  = 22
_COL4_W  = 68
_COL_SPC = 2

_COL2_W = GRID_W - _COL0_W - _COL1_W - _COL3_W - _COL4_W - 4 * _COL_SPC

_COL3_X = _COL0_W + _COL_SPC + _COL1_W + _COL_SPC + _COL2_W + _COL_SPC

_MENLO = lambda: NSFont.fontWithName_size_('Menlo', 13.0)


# ORCHESTRATOR

def main():
    install_sigint_exit_handler()

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    ctrl = _ClickController.alloc().init()
    panel, _grid = _make_panel(ctrl)

    screen = NSScreen.mainScreen()
    if screen is not None:
        sf = screen.visibleFrame()
        px = compute_px(sf)
        py = compute_py(sf)
        panel.setFrame_display_(NSMakeRect(px, py, PANEL_W, PANEL_H), False)

    _print_startup_report()

    panel.orderFront_(None)
    app.run()


# FUNCTIONS

def install_sigint_exit_handler():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))


class _ClickController(NSObject):
    def rowClicked_(self, sender):
        tag = sender.tag()
        print(f'row {tag} clicked  (tag={tag})', flush=True)


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
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    cv.addSubview_(grid)
    cv.leadingAnchor().constraintEqualToAnchor_constant_(
        grid.leadingAnchor(), -GRID_X).setActive_(True)
    cv.trailingAnchor().constraintEqualToAnchor_constant_(
        grid.trailingAnchor(), GRID_INSET_R).setActive_(True)
    grid.topAnchor().constraintEqualToAnchor_constant_(
        cv.topAnchor(), float(GRID_Y_BTOP)).setActive_(True)

    return panel, grid


def _build_grid(controller) -> NSGridView:
    empty = NSGridCell.emptyContentView()

    grid = NSGridView.gridViewWithNumberOfColumns_rows_(5, 0)
    grid.setColumnSpacing_(_COL_SPC)
    grid.setRowSpacing_(1.0)

    for i in range(5):
        grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)

    grid.columnAtIndex_(0).setWidth_(float(_COL0_W))
    grid.columnAtIndex_(1).setWidth_(float(_COL1_W))
    grid.columnAtIndex_(3).setWidth_(float(_COL3_W))
    grid.columnAtIndex_(4).setWidth_(float(_COL4_W))

    sep_btn = _cell_btn('── Project_A ──────────────────────', NSColor.secondaryLabelColor())
    grid.addRowWithViews_([sep_btn, empty, empty, empty, empty])
    grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 5), NSRange(0, 1))

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

    wname_btn = _cell_btn('worker_x')
    wdot_btn  = _cell_btn('[*]', NSColor.systemGreenColor())
    for btn in (wname_btn, wdot_btn):
        btn.setTag_(2)
        btn.setTarget_(controller)
        btn.setAction_(b'rowClicked:')
    grid.addRowWithViews_([empty, empty, wname_btn, wdot_btn, empty])

    return grid


def _cell_btn(text: str, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color:
        attrs[NSForegroundColorAttributeName] = color
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, ROW_H))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn


def compute_px(sf):
    return sf.origin.x + sf.size.width / 2.0 - PANEL_W / 2.0


def compute_py(sf):
    return sf.origin.y + sf.size.height - PANEL_H - 40


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


if __name__ == '__main__':
    main()
