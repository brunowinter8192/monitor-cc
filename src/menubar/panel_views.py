# INFRASTRUCTURE
import objc
import os

from AppKit import (NSButton, NSCursor,
                    NSEventModifierFlagCommand, NSEventModifierFlagDeviceIndependentFlagsMask,
                    NSEventModifierFlagShift,
                    NSPanel, NSTextField,
                    NSTrackingActiveAlways, NSTrackingArea, NSTrackingCursorUpdate,
                    NSTrackingInVisibleRect, NSTrackingMouseEnteredAndExited,
                    NSTrackingMouseMoved,
                    NSView)

from src.menubar.menubar_log import log_menubar

EDGE             = 8
_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)

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
