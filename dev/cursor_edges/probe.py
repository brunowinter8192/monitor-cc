#!/usr/bin/env python3
"""
dev/cursor_edges/probe.py — Foreground cursor-rect race diagnostic + NSTrackingArea probe.

Mirrors production NSPanel layout exactly (same geometry, same z-order,
same view classes where possible). Logs ALL cursor-related AppKit signals
to stderr so we can determine which view wins the cursor-rect race per
hover position.

Run from project root:
    venv/bin/python3 dev/cursor_edges/probe.py
    venv/bin/python3 dev/cursor_edges/probe.py --fix
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects
    venv/bin/python3 dev/cursor_edges/probe.py --fix --tracking
    venv/bin/python3 dev/cursor_edges/probe.py --tracking --no-resizable

--fix: calls panel.enableCursorRects() immediately after setContentView_,
       then logs areCursorRectsEnabled() to confirm the call was accepted.
       Hypothesis: NonactivatingPanel skips the becomeKeyWindow path that
       normally triggers enableCursorRects → cursor rects sit installed but
       are never dispatched. Explicit call should re-enable dispatch.

--leaf-rects (requires --fix): installs resize cursor rects directly on each
       leaf subview (StackView, FooterView, TopBarView, and left-edge Buttons)
       at their portion of the panel edges, AFTER super.resetCursorRects.
       Tests Iteration 6 hypothesis: subview coverage shadows ContentView's
       edge rects — installing rects on the covering views themselves should
       win the dispatch race.

--no-resizable: creates the panel WITHOUT NSWindowStyleMaskResizable (only
       NSWindowStyleMaskNonactivatingPanel). Combinable with --fix/--leaf-rects.
       Tests H7: WindowServer reserves edge regions for native resize, which
       for NonactivatingPanel blocks our cursor rects without showing any
       resize cursor itself. Without the resizable mask WindowServer should
       not claim the edges and our rects may fire.
       Trade-off: no native drag-resize. That is the POINT of this test.

--tracking: replaces _LoggingContentView with _TrackingContentView — uses
       NSTrackingArea with .cursorUpdate option instead of addCursorRect_cursor_.
       cursorUpdate_ fires regardless of key-window status (activeAlways).
       Bypasses the cursor-rect dispatch path entirely.
       hitTest_ override claims L/R/bottom edge zones so child views don't win.
       NSCursor.push()/pop() maintains cursor against child views that reset it.
       Ref: sw33tLie/macshot RecordingHUDPanel.swift + lifedever/PasteMemo
            RelayFloatingWindowController.swift (same nonactivatingPanel setup).

--tracking --no-resizable: full PasteMemo pattern — tracking area cursor +
       custom mouseDown_/mouseDragged_ resize (drops native NSWindowStyleMaskResizable).
       This is the production-candidate combination.

Quit: Cmd-Q or close the window. Ctrl-C also works (SIGINT handler).

All output goes to stderr. Pipe to file to capture a session:
    venv/bin/python3 dev/cursor_edges/probe.py 2>probe_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix 2>probe_fix_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects 2>probe_leaf_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --no-resizable 2>probe_noresize_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --tracking 2>probe_tracking_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --tracking --no-resizable 2>probe_tracking_noresize_$(date +%H%M%S).log
"""

# INFRASTRUCTURE
import argparse
import signal
import sys
import time

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSButton,
    NSCursor,
    NSEvent,
    NSEventMaskMouseMoved,
    NSPanel,
    NSStackView,
    NSTrackingActiveAlways,
    NSTrackingArea,
    NSTrackingCursorUpdate,
    NSTrackingInVisibleRect,
    NSTrackingMouseEnteredAndExited,
    NSTrackingMouseMoved,
    NSUserInterfaceLayoutOrientationVertical,
    NSLayoutAttributeLeading,
    NSStatusWindowLevel,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowStyleMaskNonactivatingPanel,
    NSWindowStyleMaskResizable,
)
from Foundation import NSMakeRect, NSMakeSize, NSPoint

# Mirror production geometry constants exactly
PANEL_WIDTH  = 380
PANEL_HEIGHT = 460
_FOOTER_H    = 30
_TOP_BAR_H   = 21
_ROW_H       = 21
EDGE         = 8   # cursor-rect / edge-detection width in production
PANEL_MIN_WIDTH  = 250
PANEL_MIN_HEIGHT = 120
PANEL_MAX_DIM    = 900   # upper clamp for custom drag resize

# NSTrackingArea option flags for legacy (non-tracking) modes
_TA_OPTS = NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved | NSTrackingActiveAlways

# NSTrackingArea option flags for --tracking mode
# .cursorUpdate fires cursorUpdate_ regardless of key-window status (activeAlways guarantees this)
_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)

# Module-level flags set by argparse before panel construction.
_LEAF_RECTS_ENABLED = False
_TRACKING_ENABLED   = False


# FUNCTIONS

def _log(msg: str) -> None:
    t = time.strftime('%H:%M:%S')
    print(f'[{t}] {msg}', file=sys.stderr, flush=True)


def _dump_hierarchy(view, indent: int = 0) -> None:
    cls = type(view).__name__
    f   = view.frame()
    _log(
        f'{"  " * indent}{cls}  '
        f'frame=({f.origin.x:.0f},{f.origin.y:.0f} '
        f'{f.size.width:.0f}×{f.size.height:.0f})'
    )
    for sv in view.subviews():
        _dump_hierarchy(sv, indent + 1)


def _install_tracking_area(view) -> None:
    """Replace all tracking areas on `view` with a fresh full-bounds area (legacy modes)."""
    for ta in list(view.trackingAreas()):
        view.removeTrackingArea_(ta)
    ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
        view.bounds(), _TA_OPTS, view, None)
    view.addTrackingArea_(ta)


# Logging subclass for the contentView (mirrors _PanelContentView) — cursor-rect mode
# Installs identical 4-zone cursor rects and logs every AppKit cursor signal.
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


# NSTrackingArea + cursorUpdate content view — Iteration 8 pattern
# Replaces addCursorRect_cursor_ entirely. Uses .cursorUpdate option on the tracking area
# so cursorUpdate_ fires on mouse movement regardless of key-window status (.activeAlways).
# hitTest_ claims L/R/bottom edge zones so child views don't intercept events there.
# NSCursor.push()/pop() maintains cursor against child views that call super.cursorUpdate_.
# Custom mouseDown_/mouseDragged_ handles resize when --no-resizable drops native mechanism.
# Edges: left (x<EDGE), right (x>w-EDGE), bottom (y<EDGE) — mirrors production exactly.
class _TrackingContentView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(_TrackingContentView, self).initWithFrame_(frame)
        if self is None:
            return None
        # Edge tracking state
        self._hovered_edge = None     # None | 'left' | 'right' | 'bottom'
        self._tracking_area = None
        # Custom drag-resize state (active when --no-resizable)
        self._drag_edge = None        # None | 'left' | 'right' | 'bottom'
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
            self.bounds(), _TA_TRACKING_OPTS, self, None)
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
        """Push/pop cursor stack on edge transitions; call set() for immediate visual update."""
        old = self._hovered_edge
        if edge == old:
            return
        if edge is not None and old is None:
            # nil → edge: push new cursor onto stack
            self._cursor_for_edge(edge).push()
            _log(f'cursor PUSH  edge={edge}  cursor={self._cursor_for_edge(edge).image()}')
        elif edge is None and old is not None:
            # edge → nil: pop our cursor off the stack
            NSCursor.pop()
            _log(f'cursor POP  was={old}')
        else:
            # edge_a → edge_b (e.g. left→bottom): pop old, push new
            NSCursor.pop()
            self._cursor_for_edge(edge).push()
            _log(f'cursor POP+PUSH  {old}→{edge}')
        self._hovered_edge = edge
        # call set() for immediate visual feedback in addition to the stack change
        if edge is not None:
            self._cursor_for_edge(edge).set()
        else:
            NSCursor.arrowCursor().set()

    @objc.python_method
    def _edge_for_point(self, local):
        """Determine edge zone for a point in local (view) coordinates."""
        w = self.bounds().size.width
        if local.x < EDGE:
            return 'left'
        if local.x > w - EDGE:
            return 'right'
        if local.y < EDGE:
            return 'bottom'
        return None

    def cursorUpdate_(self, event):
        """Called by AppKit when tracking area cursor-update event fires."""
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
        """Claim L/R/bottom edge zones for self; interior falls through to child views."""
        local = self.convertPoint_fromView_(point, self.superview())
        w = self.bounds().size.width
        h = self.bounds().size.height
        # Only claim the point if it's inside our bounds at all
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
            delta   = sx - current.x   # positive → dragging left → panel grows
            new_w   = max(PANEL_MIN_WIDTH, min(sw + delta, PANEL_MAX_DIM))
            new_x   = ox + sw - new_w  # right edge stays fixed
            win.setFrame_display_(NSMakeRect(new_x, oy, new_w, sh), True)
        elif self._drag_edge == 'right':
            delta   = current.x - sx   # positive → dragging right → panel grows
            new_w   = max(PANEL_MIN_WIDTH, min(sw + delta, PANEL_MAX_DIM))
            win.setFrame_display_(NSMakeRect(ox, oy, new_w, sh), True)
        elif self._drag_edge == 'bottom':
            delta   = sy - current.y   # positive → dragging down → panel grows taller
            new_h   = max(PANEL_MIN_HEIGHT, min(sh + delta, PANEL_MAX_DIM))
            new_y   = oy + sh - new_h  # top edge stays fixed
            win.setFrame_display_(NSMakeRect(ox, new_y, sw, new_h), True)

    def mouseUp_(self, event):
        if self._drag_edge is not None:
            _log(f'mouseUp_  TrackingCV  drag_edge={self._drag_edge}  done')
            self._drag_edge = None


# Logging subclass for the middle NSStackView (session rows live here)
class _LoggingStackView(NSStackView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  StackView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingStackView, self).resetCursorRects()
        if _LEAF_RECTS_ENABLED:
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


# Logging subclass for all NSButton instances (Kill, Restart, Auto-Jump, session rows)
class _LoggingButton(NSButton):

    def resetCursorRects(self):
        t = self.title() or '?'
        b = self.bounds()
        h = b.size.height
        _log(f'resetCursorRects  Button("{t}")  bounds={b.size.width:.0f}×{h:.0f}')
        objc.super(_LoggingButton, self).resetCursorRects()
        if _LEAF_RECTS_ENABLED:
            # Install left-edge rect only when button frame starts at panel left edge
            # (frame.origin.x < EDGE in parent coords → local x=0 maps to panel x≈0).
            # Auto-Jump and session-row buttons start at x=0; Kill/Restart do not.
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


# Logging subclass for the footer NSView (bottom bar, parent of Kill+Restart)
class _LoggingFooterView(NSView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  FooterView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingFooterView, self).resetCursorRects()
        if _LEAF_RECTS_ENABLED:
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


# Logging subclass for the top-bar NSView (parent of Auto-Jump button)
class _LoggingTopBarView(NSView):

    def resetCursorRects(self):
        b = self.bounds()
        w = b.size.width
        h = b.size.height
        _log(f'resetCursorRects  TopBarView  bounds={w:.0f}×{h:.0f}')
        objc.super(_LoggingTopBarView, self).resetCursorRects()
        if _LEAF_RECTS_ENABLED:
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


def _make_probe_panel(fix: bool = False, no_resizable: bool = False) -> NSPanel:
    """Build probe NSPanel that mirrors production _make_nspanel() geometry and z-order exactly."""
    style_mask = NSWindowStyleMaskNonactivatingPanel
    if not no_resizable:
        style_mask |= NSWindowStyleMaskResizable
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(300, 300, PANEL_WIDTH, PANEL_HEIGHT),
        style_mask, 2, False)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    panel.setTitle_('cursor-edges probe')
    panel.setAcceptsMouseMovedEvents_(True)

    # contentView — _TrackingContentView (--tracking) or _LoggingContentView (legacy modes)
    if _TRACKING_ENABLED:
        cv = _TrackingContentView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    else:
        cv = _LoggingContentView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)

    if fix:
        # Hypothesis: NonactivatingPanel never calls becomeKeyWindow → enableCursorRects
        # never invoked internally → cursor rects installed but dispatch disabled.
        # Explicit call should re-enable dispatch without requiring key-window status.
        panel.enableCursorRects()
        enabled = panel.areCursorRectsEnabled()
        _log(f'[--fix]  enableCursorRects() called — areCursorRectsEnabled={enabled}')
        if enabled:
            _log('[--fix]  cursor-rect dispatch enabled')
        else:
            _log('[--fix]  still disabled — hypothesis refuted, look elsewhere')

    # footer — bottom bar with Kill + Restart (mirror production layout exactly)
    footer = _LoggingFooterView.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH, _FOOTER_H))
    footer.setAutoresizingMask_(2)   # NSViewWidthSizable

    restart_btn = _LoggingButton.alloc().initWithFrame_(
        NSMakeRect(PANEL_WIDTH - 86, 4, 78, 22))
    restart_btn.setAutoresizingMask_(1)   # NSViewMinXMargin — right-anchored
    restart_btn.setTitle_('Restart')
    restart_btn.setBezelStyle_(1)
    footer.addSubview_(restart_btn)

    kill_btn = _LoggingButton.alloc().initWithFrame_(
        NSMakeRect(PANEL_WIDTH - 86 - 78 - 8, 4, 78, 22))
    kill_btn.setAutoresizingMask_(1)   # NSViewMinXMargin
    kill_btn.setTitle_('Kill')
    kill_btn.setBezelStyle_(1)
    footer.addSubview_(kill_btn)

    cv.addSubview_(footer)

    # top_bar — top bar with Auto-Jump button (mirror production layout exactly)
    top_bar = _LoggingTopBarView.alloc().initWithFrame_(
        NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, PANEL_WIDTH, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable | NSViewMinYMargin

    toggle_btn = _LoggingButton.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    toggle_btn.setTitle_('Auto-Jump: ON')
    toggle_btn.setAutoresizingMask_(2)   # NSViewWidthSizable
    top_bar.addSubview_(toggle_btn)

    cv.addSubview_(top_bar)

    # stack — NSStackView filling the middle (mirror production layout exactly)
    stack_h = PANEL_HEIGHT - _FOOTER_H - _TOP_BAR_H
    stack = _LoggingStackView.alloc().initWithFrame_(
        NSMakeRect(0, _FOOTER_H, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)   # NSViewWidthSizable | NSViewHeightSizable
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)   # NSStackViewDistributionGravityAreas

    # Three fake session row buttons — representative of production stack content
    for label in [
        '● Monitor_CC        [*]   ',
        '  cursor-edges      [ ]   ',
        '  another-worker    [ ]   ',
    ]:
        btn = _LoggingButton.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH - 22, 20))
        btn.setBordered_(False)
        btn.setButtonType_(7)
        btn.setTitle_(label)
        stack.addView_inGravity_(btn, 1)

    cv.addSubview_(stack)

    return panel


def _install_global_mouse_monitor() -> None:
    """NSEvent local monitor — captures mouseMoved before any view-level dispatch."""
    def _handler(event):
        pt = event.locationInWindow()
        win = event.window()
        win_cls = type(win).__name__ if win else 'None'
        _log(
            f'NSEventMonitor  mouseMoved  loc=({pt.x:.1f},{pt.y:.1f})'
            f'  window={win_cls}'
        )
        return event
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        NSEventMaskMouseMoved, _handler)


# ORCHESTRATOR

def main() -> None:
    global _LEAF_RECTS_ENABLED, _TRACKING_ENABLED

    parser = argparse.ArgumentParser(description='cursor-edges probe')
    parser.add_argument(
        '--fix', action='store_true',
        help='call panel.enableCursorRects() after setContentView_ to test NonactivatingPanel hypothesis')
    parser.add_argument(
        '--leaf-rects', action='store_true',
        help='(requires --fix) install resize cursor rects on leaf subviews at their panel-edge portions')
    parser.add_argument(
        '--no-resizable', action='store_true',
        help='create panel WITHOUT NSWindowStyleMaskResizable; with --tracking enables custom drag resize')
    parser.add_argument(
        '--tracking', action='store_true',
        help='use NSTrackingArea + cursorUpdate pattern (Iteration 8) instead of cursor-rect dispatch')
    args = parser.parse_args()

    # Leaf rects only make sense with cursor-rect dispatch enabled
    _LEAF_RECTS_ENABLED = args.fix and args.leaf_rects
    _TRACKING_ENABLED   = args.tracking

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    signal.signal(signal.SIGINT, lambda *_: app.terminate_(None))

    panel = _make_probe_panel(fix=args.fix, no_resizable=args.no_resizable)

    _install_global_mouse_monitor()

    _log('=' * 60)
    _log('cursor-edges probe  (Monitor_CC/dev/cursor_edges/probe.py)')
    flags = []
    if args.fix:           flags.append('--fix')
    if _LEAF_RECTS_ENABLED: flags.append('--leaf-rects')
    if args.no_resizable:  flags.append('--no-resizable')
    if args.tracking:      flags.append('--tracking')
    if not flags:          flags.append('baseline')
    mode_tag = ' '.join(flags)

    if args.tracking and args.no_resizable:
        mode = (f'MODE: {mode_tag}  '
                f'(Iteration 8 — NSTrackingArea cursorUpdate + custom drag resize, no native resize mask)')
    elif args.tracking:
        mode = (f'MODE: {mode_tag}  '
                f'(Iteration 8 — NSTrackingArea cursorUpdate, native resize mask kept)')
    elif args.no_resizable:
        mode = f'MODE: {mode_tag}  (H7 — no-resizable test, WindowServer edge-claim hypothesis)'
    elif _LEAF_RECTS_ENABLED:
        mode = f'MODE: {mode_tag}  (Iteration 6 — subview-coverage hypothesis)'
    elif args.fix:
        mode = f'MODE: {mode_tag}  (enableCursorRects hypothesis)'
    else:
        mode = f'MODE: {mode_tag}  (no fix)'
    _log(mode)

    if args.tracking:
        _log('[--tracking]  _TrackingContentView active — cursor-rect dispatch BYPASSED')
        _log(f'[--tracking]  NSTrackingArea opts: CursorUpdate|MouseMoved|MouseEntered/Exited|ActiveAlways|InVisibleRect')
        _log(f'[--tracking]  hitTest_ claims L/R/bottom edge zones (x<{EDGE}, x>w-{EDGE}, y<{EDGE})')
        _log(f'[--tracking]  NSCursor.push()/pop() on edge transitions')
        if args.no_resizable:
            _log('[--tracking --no-resizable]  custom mouseDown_/mouseDragged_ handles drag resize')
        else:
            _log('[--tracking]  native NSWindowStyleMaskResizable kept — drag resize via OS')
    if args.no_resizable:
        _log('[--no-resizable]  NSWindowStyleMaskResizable REMOVED')
    if args.fix:
        _log(f'[--fix]  areCursorRectsEnabled logged at panel build time (see above)')

    _log('=' * 60)
    _log(f'Panel geometry: {PANEL_WIDTH}×{PANEL_HEIGHT}  EDGE={EDGE}')
    if _TRACKING_ENABLED:
        _log('Signals to watch (--tracking mode):')
        _log('  updateTrackingAreas — tracking area installed/refreshed on resize')
        _log('  mouseMoved_         — TrackingCV called; logs loc + edge detection')
        _log('  cursor PUSH/POP     — edge transition log (nil↔edge, edge_a→edge_b)')
        _log('  cursorUpdate_       — called by AppKit on cursor-update event; sets cursor')
        _log('  mouseDown_/Dragged_ — custom resize events (--no-resizable only)')
    else:
        if _LEAF_RECTS_ENABLED:
            _log('Leaf-rects ENABLED — each subview installs edge rects in its resetCursorRects:')
            _log('  StackView   : LEFT + RIGHT (full local height)')
            _log('  FooterView  : LEFT + RIGHT (full local height) + BOTTOM (full width)')
            _log('  TopBarView  : LEFT + RIGHT (full local height, no top)')
            _log('  Button      : LEFT if frame.origin.x < EDGE (Auto-Jump, session rows)')
        _log('Signals to watch (cursor-rect mode):')
        _log('  resetCursorRects — which views install rects (fires on activate + resize)')
        _log('  cursorUpdate_    — which view WINS the cursor race (fires last)')
        _log('  mouseEntered_    — tracking area entry')
        _log('  mouseMoved_      — per-move (tracking area owner)')
        _log('  NSEventMonitor   — pre-dispatch raw event')
    _log('')
    _log('View hierarchy at startup:')
    _dump_hierarchy(panel.contentView())
    _log('')
    _log('Hover slowly over each edge and each widget. Quit: Cmd-Q or Ctrl-C.')
    _log('=' * 60)

    panel.orderFront_(None)
    app.activateIgnoringOtherApps_(True)
    app.run()


main()
