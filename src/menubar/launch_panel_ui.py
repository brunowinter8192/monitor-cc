# INFRASTRUCTURE
import os

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSView)
from Foundation import NSMakeRect

from .panel import _ROW_H, _MENLO, _CursorlessButton

_DESKTOP_BTN_W   = 40

# FUNCTIONS

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
    buttons = {}
    for i, desktop in enumerate(desktops):
        btn = _make_desktop_button(desktop, desktop in occupied, desktop == selected,
                                   i * _DESKTOP_BTN_W, target)
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
