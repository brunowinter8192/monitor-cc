# INFRASTRUCTURE
import objc
from AppKit import (
    NSButton,
    NSCursor,
    NSEvent,
    NSStackView,
    NSTrackingArea,
    NSView,
)
from Foundation import NSMakeRect

import cursor_edges_constants as cec
from cursor_edges_constants import EDGE, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT, PANEL_MAX_DIM
from cursor_edges_logging import _log, _install_tracking_area

# FUNCTIONS

class _LoggingContentView(NSView):

    def resetCursorRects(self):
        w = self.bounds().size.width
        h = self.bounds().size.height
        _log(f'resetCursorRects  ContentView  bounds={w:.0f}×{h:.0f}')
        self.addCursorRect_cursor_(
            NSMakeRect(0,        0,    w,             EDGE),      NSCursor.resizeUpDownCursor())
        self.addCursorRect_cursor_(
            NSMakeRect(0,        0,    EDGE,          h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(
            NSMakeRect(w - EDGE, 0,    EDGE,          h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(
            NSMakeRect(EDGE,     EDGE, w - 2 * EDGE,  h - EDGE),  NSCursor.arrowCursor())
        _log(f'  ↕  bottom-edge  rect=(0,0 {w:.0f}×{EDGE})')
        _log(f'  ↔  left-edge   rect=(0,0 {EDGE}×{h:.0f})')
        _log(f'  ↔  right-edge  rect=({w-EDGE:.0f},0 {EDGE}×{h:.0f})')
        _log(f'  →  interior    rect=({EDGE},{EDGE} {w-2*EDGE:.0f}×{h-EDGE:.0f})')

    def cursorUpdate_(self, event):
        pt = event.locationInWindow() if event else None
        xy = f'({pt.x:.1f},{pt.y:.1f})' if pt else '?'
        _log(f'cursorUpdate_  ContentView  loc={xy}')
        objc.super(_LoggingContentView, self).cursorUpdate_(event)

    def mouseMoved_(self, event):
        pt  = event.locationInWindow()
        hit = self.hitTest_(pt)
        cls = type(hit).__name__ if hit else 'None'
        _log(f'mouseMoved_  ContentView  loc=({pt.x:.1f},{pt.y:.1f})  hitTest→{cls}')

    def mouseEntered_(self, event):
        _log('mouseEntered_  ContentView')

    def mouseExited_(self, event):
        _log('mouseExited_  ContentView')

    def updateTrackingAreas(self):
        objc.super(_LoggingContentView, self).updateTrackingAreas()
        _install_tracking_area(self)


class _TrackingContentView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(_TrackingContentView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._hovered_edge = None
        self._tracking_area = None
        self._drag_edge = None
        self._drag_start_width  = 0.0
        self._drag_start_height = 0.0
        self._drag_start_screen_x = 0.0
        self._drag_start_screen_y = 0.0
        self._drag_start_origin_x = 0.0
        self._drag_start_origin_y = 0.0
        return self

    def updateTrackingAreas(self):
        objc.super(_TrackingContentView, self).updateTrackingAreas()
        if self._tracking_area is not None:
            self.removeTrackingArea_(self._tracking_area)
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), cec._TA_TRACKING_OPTS, self, None)
        self.addTrackingArea_(ta)
        self._tracking_area = ta
        _log(f'updateTrackingAreas  TrackingCV  bounds={self.bounds().size.width:.0f}×{self.bounds().size.height:.0f}')

    @objc.python_method
    def _cursor_for_edge(self, edge):
        if edge == 'bottom':
            return NSCursor.resizeUpDownCursor()
        return NSCursor.resizeLeftRightCursor()

    @objc.python_method
    def _set_hovered_edge(self, edge):
        old = self._hovered_edge
        if edge == old:
            return
        if edge is not None and old is None:
            self._cursor_for_edge(edge).push()
            _log(f'cursor PUSH  edge={edge}  cursor={self._cursor_for_edge(edge).image()}')
        elif edge is None and old is not None:
            NSCursor.pop()
            _log(f'cursor POP  was={old}')
        else:
            NSCursor.pop()
            self._cursor_for_edge(edge).push()
            _log(f'cursor POP+PUSH  {old}→{edge}')
        self._hovered_edge = edge
        if edge is not None:
            self._cursor_for_edge(edge).set()
        else:
            NSCursor.arrowCursor().set()

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
            self._cursor_for_edge(self._hovered_edge).set()
            _log(f'cursorUpdate_  TrackingCV  edge={self._hovered_edge}  → set cursor')
        else:
            objc.super(_TrackingContentView, self).cursorUpdate_(event)
            _log('cursorUpdate_  TrackingCV  edge=None  → super')

    def mouseMoved_(self, event):
        local = self.convertPoint_fromView_(event.locationInWindow(), None)
        edge  = self._edge_for_point(local)
        _log(f'mouseMoved_  TrackingCV  loc=({local.x:.1f},{local.y:.1f})  edge={edge}')
        self._set_hovered_edge(edge)

    def mouseEntered_(self, event):
        local = self.convertPoint_fromView_(event.locationInWindow(), None)
        _log(f'mouseEntered_  TrackingCV  loc=({local.x:.1f},{local.y:.1f})')

    def mouseExited_(self, event):
        _log('mouseExited_  TrackingCV  → clear edge')
        self._set_hovered_edge(None)

    def hitTest_(self, point):
        local = self.convertPoint_fromView_(point, self.superview())
        w = self.bounds().size.width
        h = self.bounds().size.height
        if local.x < 0 or local.y < 0 or local.x > w or local.y > h:
            return objc.super(_TrackingContentView, self).hitTest_(point)
        if local.x < EDGE or local.x > w - EDGE or local.y < EDGE:
            return self
        return objc.super(_TrackingContentView, self).hitTest_(point)

    def mouseDown_(self, event):
        local = self.convertPoint_fromView_(event.locationInWindow(), None)
        edge  = self._edge_for_point(local)
        if edge is None:
            self._drag_edge = None
            return
        win = self.window()
        if win is None:
            return
        frame = win.frame()
        self._drag_edge          = edge
        self._drag_start_width   = frame.size.width
        self._drag_start_height  = frame.size.height
        self._drag_start_origin_x = frame.origin.x
        self._drag_start_origin_y = frame.origin.y
        screen = NSEvent.mouseLocation()
        self._drag_start_screen_x = screen.x
        self._drag_start_screen_y = screen.y
        _log(f'mouseDown_  TrackingCV  edge={edge}  '
             f'start_w={self._drag_start_width:.0f}  start_h={self._drag_start_height:.0f}')

    def mouseDragged_(self, event):
        if self._drag_edge is None:
            return
        win = self.window()
        if win is None:
            return
        current = NSEvent.mouseLocation()
        ox = self._drag_start_origin_x
        oy = self._drag_start_origin_y
        sw = self._drag_start_width
        sh = self._drag_start_height
        sx = self._drag_start_screen_x
        sy = self._drag_start_screen_y
        if self._drag_edge == 'left':
            delta   = sx - current.x
            new_w   = max(PANEL_MIN_WIDTH, min(sw + delta, PANEL_MAX_DIM))
            new_x   = ox + sw - new_w
            win.setFrame_display_(NSMakeRect(new_x, oy, new_w, sh), True)
        elif self._drag_edge == 'right':
            delta   = current.x - sx
            new_w   = max(PANEL_MIN_WIDTH, min(sw + delta, PANEL_MAX_DIM))
            win.setFrame_display_(NSMakeRect(ox, oy, new_w, sh), True)
        elif self._drag_edge == 'bottom':
            delta   = sy - current.y
            new_h   = max(PANEL_MIN_HEIGHT, min(sh + delta, PANEL_MAX_DIM))
            new_y   = oy + sh - new_h
            win.setFrame_display_(NSMakeRect(ox, new_y, sw, new_h), True)

    def mouseUp_(self, event):
        if self._drag_edge is not None:
            _log(f'mouseUp_  TrackingCV  drag_edge={self._drag_edge}  done')
            self._drag_edge = None


class _LoggingStackView(NSStackView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  StackView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingStackView, self).resetCursorRects()
        if cec._LEAF_RECTS_ENABLED:
            self.addCursorRect_cursor_(
                NSMakeRect(0, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            self.addCursorRect_cursor_(
                NSMakeRect(w - EDGE, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            _log(f'  [leaf] ↔ left  StackView  (0,0 {EDGE}×{h:.0f})')
            _log(f'  [leaf] ↔ right StackView  ({w-EDGE:.0f},0 {EDGE}×{h:.0f})')

    def cursorUpdate_(self, event):
        pt = event.locationInWindow() if event else None
        xy = f'({pt.x:.1f},{pt.y:.1f})' if pt else '?'
        _log(f'cursorUpdate_  StackView  loc={xy}')
        objc.super(_LoggingStackView, self).cursorUpdate_(event)

    def mouseEntered_(self, event):
        _log('mouseEntered_  StackView')

    def mouseExited_(self, event):
        _log('mouseExited_  StackView')

    def updateTrackingAreas(self):
        objc.super(_LoggingStackView, self).updateTrackingAreas()
        _install_tracking_area(self)


class _LoggingButton(NSButton):

    def resetCursorRects(self):
        t = self.title() or '?'
        b = self.bounds()
        h = b.size.height
        _log(f'resetCursorRects  Button("{t}")  bounds={b.size.width:.0f}×{h:.0f}')
        objc.super(_LoggingButton, self).resetCursorRects()
        if cec._LEAF_RECTS_ENABLED:
            if self.frame().origin.x < EDGE:
                self.addCursorRect_cursor_(
                    NSMakeRect(0, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
                _log(f'  [leaf] ↔ left  Button("{t}")  (0,0 {EDGE}×{h:.0f})')

    def cursorUpdate_(self, event):
        t  = self.title() or '?'
        pt = event.locationInWindow() if event else None
        xy = f'({pt.x:.1f},{pt.y:.1f})' if pt else '?'
        _log(f'cursorUpdate_  Button("{t}")  loc={xy}  ← WINNER')
        objc.super(_LoggingButton, self).cursorUpdate_(event)

    def mouseEntered_(self, event):
        _log(f'mouseEntered_  Button("{self.title() or "?"}")')

    def mouseExited_(self, event):
        _log(f'mouseExited_   Button("{self.title() or "?"}")')

    def updateTrackingAreas(self):
        objc.super(_LoggingButton, self).updateTrackingAreas()
        _install_tracking_area(self)


class _LoggingFooterView(NSView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  FooterView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingFooterView, self).resetCursorRects()
        if cec._LEAF_RECTS_ENABLED:
            self.addCursorRect_cursor_(
                NSMakeRect(0, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            self.addCursorRect_cursor_(
                NSMakeRect(w - EDGE, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            self.addCursorRect_cursor_(
                NSMakeRect(0, 0, w, EDGE), NSCursor.resizeUpDownCursor())
            _log(f'  [leaf] ↔ left   FooterView  (0,0 {EDGE}×{h:.0f})')
            _log(f'  [leaf] ↔ right  FooterView  ({w-EDGE:.0f},0 {EDGE}×{h:.0f})')
            _log(f'  [leaf] ↕ bottom FooterView  (0,0 {w:.0f}×{EDGE})')

    def cursorUpdate_(self, event):
        pt = event.locationInWindow() if event else None
        xy = f'({pt.x:.1f},{pt.y:.1f})' if pt else '?'
        _log(f'cursorUpdate_  FooterView  loc={xy}')
        objc.super(_LoggingFooterView, self).cursorUpdate_(event)

    def mouseEntered_(self, event):
        _log('mouseEntered_  FooterView')

    def mouseExited_(self, event):
        _log('mouseExited_  FooterView')

    def updateTrackingAreas(self):
        objc.super(_LoggingFooterView, self).updateTrackingAreas()
        _install_tracking_area(self)


class _LoggingTopBarView(NSView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  TopBarView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingTopBarView, self).resetCursorRects()
        if cec._LEAF_RECTS_ENABLED:
            self.addCursorRect_cursor_(
                NSMakeRect(0, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            self.addCursorRect_cursor_(
                NSMakeRect(w - EDGE, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
            _log(f'  [leaf] ↔ left  TopBarView  (0,0 {EDGE}×{h:.0f})')
            _log(f'  [leaf] ↔ right TopBarView  ({w-EDGE:.0f},0 {EDGE}×{h:.0f})')

    def cursorUpdate_(self, event):
        pt = event.locationInWindow() if event else None
        xy = f'({pt.x:.1f},{pt.y:.1f})' if pt else '?'
        _log(f'cursorUpdate_  TopBarView  loc={xy}')
        objc.super(_LoggingTopBarView, self).cursorUpdate_(event)

    def mouseEntered_(self, event):
        _log('mouseEntered_  TopBarView')

    def mouseExited_(self, event):
        _log('mouseExited_  TopBarView')

    def updateTrackingAreas(self):
        objc.super(_LoggingTopBarView, self).updateTrackingAreas()
        _install_tracking_area(self)
