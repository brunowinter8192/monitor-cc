# INFRASTRUCTURE
import os

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSLayoutAttributeLeading,
                    NSStatusWindowLevel, NSStackView, NSView,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

from .panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT, PANEL_GAP
from .panel import _TOP_BAR_H, _ROW_H, _MENLO, _CursorlessButton, _CursorlessLabel, _KeyablePanel

_DESKTOP_LABEL_W = 170
_DESKTOP_BTN_W   = 40
_DESKTOP_LABEL   = 'Desktop (* = main session)'

# FUNCTIONS

def _make_launch_nspanel():
    panel = _KeyablePanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskResizable, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setAcceptsMouseMovedEvents_(True)
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    cv = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)
    panel.enableCursorRects()
    top_bar = NSView.alloc().initWithFrame_(
        NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, PANEL_WIDTH, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)
    header_btn = _CursorlessButton.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    header_btn.setBordered_(False)
    header_btn.setButtonType_(7)
    header_btn.setAutoresizingMask_(2)
    top_bar.addSubview_(header_btn)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)
    cv.addSubview_(stack)
    return panel, stack, header_btn

def _reposition_launch_panel(panel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    if btn_win is None:
        return
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = btn_win.frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

def _styled_title(text: str, color=None):
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    return NSAttributedString.alloc().initWithString_attributes_(text, attrs)

def _desktop_title(desktop: int, occupied: bool, selected: bool) -> str:
    mark = '*' if occupied else ''
    if selected:
        return f'[{desktop}{mark}]'
    return f' {desktop}{mark}'.ljust(3 + len(mark))

def _make_desktop_button(desktop: int, occupied: bool, selected: bool, x: float, target):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(x, 0, _DESKTOP_BTN_W, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    color = NSColor.systemOrangeColor() if selected else None
    btn.setAttributedTitle_(_styled_title(_desktop_title(desktop, occupied, selected), color))
    btn.setTag_(desktop)
    btn.setTarget_(target)
    btn.setAction_(b'selectDesktop:')
    return btn

def _make_desktop_row(pw: int, desktops, occupied, selected, target):
    row = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw - 22, _ROW_H))
    row.heightAnchor().constraintEqualToConstant_(float(_ROW_H)).setActive_(True)
    label = _CursorlessLabel.labelWithString_('')
    label.setFrame_(NSMakeRect(0, 0, _DESKTOP_LABEL_W, _ROW_H - 3))
    label.setAttributedStringValue_(_styled_title(_DESKTOP_LABEL))
    row.addSubview_(label)
    buttons = {}
    for i, desktop in enumerate(desktops):
        btn = _make_desktop_button(desktop, desktop in occupied, desktop == selected,
                                   _DESKTOP_LABEL_W + i * _DESKTOP_BTN_W, target)
        row.addSubview_(btn)
        buttons[desktop] = btn
    return row, buttons

def _project_label(project: str) -> str:
    return os.path.basename(project.rstrip('/'))

def _make_project_button(pw: int, project: str, index: int, target):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, pw - 22, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(_styled_title(_project_label(project)))
    btn.setTag_(index)
    btn.setTarget_(target)
    btn.setAction_(b'launchProject:')
    return btn
