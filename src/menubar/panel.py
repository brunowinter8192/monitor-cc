# INFRASTRUCTURE
import objc
import os
from collections import Counter
from datetime import datetime
from itertools import groupby

from AppKit import (NSAttributedString, NSBox, NSButton, NSColor, NSCursor, NSFont,
                    NSEventModifierFlagCommand, NSEventModifierFlagDeviceIndependentFlagsMask,
                    NSEventModifierFlagShift,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSGridCell, NSGridCellPlacementLeading, NSGridView,
                    NSLayoutAttributeLeading, NSPanel, NSStackView, NSTextField,
                    NSTrackingActiveAlways, NSTrackingArea, NSTrackingCursorUpdate,
                    NSTrackingInVisibleRect, NSTrackingMouseEnteredAndExited,
                    NSTrackingMouseMoved,
                    NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel,
                    NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize, NSRange

from .menubar_log import log_menubar
from .panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT, PANEL_GAP

_NAME_WIDTH    = 22
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'
_BADGE_IDLE    = '[ ]'

_FOOTER_H        = 30
_TOP_BAR_H       = 21
_ROW_H           = 21
_LABEL_H         = 19
EDGE             = 8
_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)
_TA_CURSOR_OPTS   = NSTrackingCursorUpdate | NSTrackingActiveAlways | NSTrackingInVisibleRect

# FUNCTIONS

def _cursor_log(msg: str) -> None:
    if not os.environ.get('MENUBAR_CURSOR_DEBUG'):
        return
    log_menubar('cursor', msg)

class _PanelContentView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(_PanelContentView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._hovered_edge  = None
        self._tracking_area = None
        _cursor_log(f'initWithFrame_  bounds={frame.size.width:.0f}x{frame.size.height:.0f}')
        return self

    def updateTrackingAreas(self):
        objc.super(_PanelContentView, self).updateTrackingAreas()
        had_area = self._tracking_area is not None
        if had_area:
            self.removeTrackingArea_(self._tracking_area)
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), _TA_TRACKING_OPTS, self, None)
        self.addTrackingArea_(ta)
        self._tracking_area = ta
        _cursor_log(f'updateTrackingAreas  bounds={self.bounds().size.width:.0f}x{self.bounds().size.height:.0f}  had_area={had_area}')

    def areCursorRectsEnabled(self):
        return True

    def resetCursorRects(self):
        cursor = self._cursor_for_edge(self._hovered_edge) if self._hovered_edge else NSCursor.arrowCursor()
        self.addCursorRect_cursor_(self.bounds(), cursor)
        _cursor_log(f'resetCursorRects  edge={self._hovered_edge}  → installed {cursor}')

    @objc.python_method
    def _cursor_for_edge(self, edge):
        if edge == 'bottom':
            return NSCursor.resizeUpDownCursor()
        return NSCursor.resizeLeftRightCursor()

    @objc.python_method
    def _set_hovered_edge(self, edge):
        if edge == self._hovered_edge:
            return
        _cursor_log(f'_set_hovered_edge  {self._hovered_edge}→{edge}  invalidate')
        self._hovered_edge = edge
        win = self.window()
        if win is not None:
            win.invalidateCursorRectsForView_(self)

    @objc.python_method
    def _edge_for_point(self, local):
        w = self.bounds().size.width
        if local.x < EDGE:
            return 'left'
        if local.x > w - EDGE:
            return 'right'
        if local.y < EDGE:
            return 'bottom'
        return None

    def cursorUpdate_(self, event):
        if self._hovered_edge is not None:
            _cursor_log(f'cursorUpdate_  edge={self._hovered_edge}  → set()')
            self._cursor_for_edge(self._hovered_edge).set()
        else:
            _cursor_log('cursorUpdate_  edge=None  → super')
            objc.super(_PanelContentView, self).cursorUpdate_(event)

    def mouseEntered_(self, event):
        loc = event.locationInWindow()
        _cursor_log(f'mouseEntered_  loc=({loc.x:.1f},{loc.y:.1f})')

    def mouseMoved_(self, event):
        local = self.convertPoint_fromView_(event.locationInWindow(), None)
        edge  = self._edge_for_point(local)
        _cursor_log(f'mouseMoved_  loc=({local.x:.1f},{local.y:.1f})  edge={edge}')
        self._set_hovered_edge(edge)

    def mouseExited_(self, event):
        _cursor_log('mouseExited_  → clear edge')
        self._set_hovered_edge(None)

    def hitTest_(self, point):
        local = self.convertPoint_fromView_(point, self.superview())
        w = self.bounds().size.width
        h = self.bounds().size.height
        if local.x < 0 or local.y < 0 or local.x > w or local.y > h:
            return objc.super(_PanelContentView, self).hitTest_(point)
        if local.x < EDGE or local.x > w - EDGE or local.y < EDGE:
            _cursor_log(f'hitTest_  loc=({local.x:.1f},{local.y:.1f})  → self (edge zone)')
            return self
        _cursor_log(f'hitTest_  loc=({local.x:.1f},{local.y:.1f})  → super (interior)')
        return objc.super(_PanelContentView, self).hitTest_(point)

class _CursorlessLabel(NSTextField):
    def resetCursorRects(self): pass

class _CursorlessButton(NSButton):
    def resetCursorRects(self): pass

class _KeyablePanel(NSPanel):
    def canBecomeKeyWindow(self):
        return True

    def performKeyEquivalent_(self, event):
        flags = event.modifierFlags() & NSEventModifierFlagDeviceIndependentFlagsMask
        if flags == NSEventModifierFlagCommand:
            ch = (event.charactersIgnoringModifiers() or "").lower()
            responder = self.firstResponder()
            if responder is not None:
                sel_map = {"v": "paste:", "c": "copy:", "x": "cut:",
                           "a": "selectAll:", "z": "undo:"}
                sel = sel_map.get(ch)
                if sel and responder.respondsToSelector_(sel):
                    responder.performSelector_withObject_(sel, None)
                    return True
        if flags == (NSEventModifierFlagCommand | NSEventModifierFlagShift):
            ch = (event.charactersIgnoringModifiers() or "").lower()
            if ch == "z":
                responder = self.firstResponder()
                if responder is not None and responder.respondsToSelector_("redo:"):
                    responder.performSelector_withObject_("redo:", None)
                    return True
        return objc.super(_KeyablePanel, self).performKeyEquivalent_(event)

def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'

def _make_panel_footer(pw: int):
    footer = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, _FOOTER_H))
    footer.setAutoresizingMask_(2)
    quit_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(pw - 86, 4, 78, 22))
    quit_btn.setAutoresizingMask_(1)
    quit_btn.setTitle_('Restart')
    quit_btn.setBezelStyle_(1)
    footer.addSubview_(quit_btn)
    kill_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(pw - 86 - 78 - 8, 4, 78, 22))
    kill_btn.setAutoresizingMask_(1)
    kill_btn.setTitle_('Kill')
    kill_btn.setBezelStyle_(1)
    footer.addSubview_(kill_btn)
    return footer, quit_btn, kill_btn

def _make_panel_top_bar(pw: int):
    top_bar = NSView.alloc().initWithFrame_(NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, pw, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)
    toggle_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, pw - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)
    toggle_btn.setAutoresizingMask_(2)
    top_bar.addSubview_(toggle_btn)
    return top_bar, toggle_btn

def _make_nspanel():
    panel = _KeyablePanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskResizable, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setAcceptsMouseMovedEvents_(True)
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    cv = _PanelContentView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)
    panel.enableCursorRects()
    footer, quit_btn, kill_btn = _make_panel_footer(PANEL_WIDTH)
    cv.addSubview_(footer)
    top_bar, toggle_btn = _make_panel_top_bar(PANEL_WIDTH)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _FOOTER_H - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(
        NSMakeRect(0, _FOOTER_H, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)
    cv.addSubview_(stack)
    for child in (footer, top_bar, stack):
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            child.bounds(), _TA_CURSOR_OPTS, cv, None)
        child.addTrackingArea_(ta)
    return panel, stack, quit_btn, toggle_btn, kill_btn

def _reposition_panel(panel, nsstatusitem) -> None:
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = nsstatusitem.button().window().frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

def _make_grid_cell_btn(text: str, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn

def _make_header_label(text: str, panel_width: int) -> NSTextField:
    tf = _CursorlessLabel.labelWithString_('')
    tf.setFrame_(NSMakeRect(0, 0, panel_width - 22, 18))
    tf.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            text, {NSFontAttributeName: _MENLO()}))
    return tf

def _make_line_separator(panel_width: int) -> NSView:
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)
    container.addSubview_(line)
    return container

def _make_separator_view(project_name: str, panel_width: int, proj_min_remaining=None):
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)
    container.addSubview_(line)
    abort_btn = None
    if proj_min_remaining is not None:
        btn_text = 'abort'
        btn_w = len(btn_text) * 8 + 8
        abort_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(w - btn_w, 0, btn_w, 18))
        abort_btn.setBordered_(False)
        abort_btn.setButtonType_(7)
        abort_btn.setWantsLayer_(True)
        abort_btn.setBackgroundColor_(NSColor.windowBackgroundColor())
        abort_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                btn_text, {NSFontAttributeName: _MENLO(),
                           NSForegroundColorAttributeName: NSColor.systemRedColor()}))
        container.addSubview_(abort_btn)
    label_w = min(len(project_name) * 8 + 6, w - 12)
    tf = _CursorlessLabel.labelWithString_(project_name)
    tf.setFrame_(NSMakeRect(12, 0, label_w, 18))
    tf.setFont_(_MENLO())
    tf.setDrawsBackground_(True)
    tf.setBackgroundColor_(NSColor.windowBackgroundColor())
    container.addSubview_(tf)
    return container, abort_btn

def _project_desktop_no(sessions, project_name: str):
    vals = [s.desktop_no for s in sessions
            if not s.is_worker and s.project_name == project_name
            and s.desktop_no is not None]
    return min(vals) if vals else None

def _compute_required_height(sorted_sessions) -> int:
    h = _FOOTER_H + _TOP_BAR_H + _LABEL_H
    if not sorted_sessions:
        return h + _LABEL_H
    for _, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        h += _LABEL_H
        for s in group_iter:
            h += _ROW_H
    return h
