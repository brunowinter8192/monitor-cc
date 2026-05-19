#!/usr/bin/env python3
"""
dev/cursor_edges/probe.py — Foreground cursor-rect race diagnostic.

Mirrors production NSPanel layout exactly (same geometry, same z-order,
same view classes where possible). Logs ALL cursor-related AppKit signals
to stderr so we can determine which view wins the cursor-rect race per
hover position.

Run from project root:
    venv/bin/python3 dev/cursor_edges/probe.py
    venv/bin/python3 dev/cursor_edges/probe.py --fix
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects

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

Quit: Cmd-Q or close the window. Ctrl-C also works (SIGINT handler).

All output goes to stderr. Pipe to file to capture a session:
    venv/bin/python3 dev/cursor_edges/probe.py 2>probe_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix 2>probe_fix_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects 2>probe_leaf_$(date +%H%M%S).log
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
from Foundation import NSMakeRect, NSMakeSize

# Mirror production geometry constants exactly
PANEL_WIDTH  = 380
PANEL_HEIGHT = 460
_FOOTER_H    = 30
_TOP_BAR_H   = 21
_ROW_H       = 21
EDGE         = 8   # cursor-rect edge width in production

# NSTrackingArea option flags
_TA_OPTS = NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved | NSTrackingActiveAlways

# Set to True by argparse (--fix --leaf-rects) before panel construction.
# Each Logging subclass checks this flag in resetCursorRects to install
# leaf-level edge rects in addition to super's rects.
_LEAF_RECTS_ENABLED = False


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
    """Replace all tracking areas on `view` with a fresh full-bounds area."""
    for ta in list(view.trackingAreas()):
        view.removeTrackingArea_(ta)
    ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
        view.bounds(), _TA_OPTS, view, None)
    view.addTrackingArea_(ta)


# Logging subclass for the contentView (mirrors _PanelContentView)
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


def _make_probe_panel(fix: bool = False) -> NSPanel:
    """Build probe NSPanel that mirrors production _make_nspanel() geometry and z-order exactly."""
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(300, 300, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskResizable, 2, False)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setContentMinSize_(NSMakeSize(250, 120))
    panel.setTitle_('cursor-edges probe')
    panel.setAcceptsMouseMovedEvents_(True)

    # contentView — _LoggingContentView mirrors _PanelContentView
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
            _log('[--fix]  ✓ cursor-rect dispatch enabled — hover an edge to see cursorUpdate_')
        else:
            _log('[--fix]  ✗ still disabled — hypothesis refuted, look elsewhere')

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
    global _LEAF_RECTS_ENABLED

    parser = argparse.ArgumentParser(description='cursor-edges probe')
    parser.add_argument(
        '--fix', action='store_true',
        help='call panel.enableCursorRects() after setContentView_ to test NonactivatingPanel hypothesis')
    parser.add_argument(
        '--leaf-rects', action='store_true',
        help='(requires --fix) install resize cursor rects on leaf subviews at their panel-edge portions')
    args = parser.parse_args()

    # Leaf rects only make sense with cursor-rect dispatch enabled
    _LEAF_RECTS_ENABLED = args.fix and args.leaf_rects

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    signal.signal(signal.SIGINT, lambda *_: app.terminate_(None))

    panel = _make_probe_panel(fix=args.fix)

    _install_global_mouse_monitor()

    _log('=' * 60)
    _log('cursor-edges probe  (Monitor_CC/dev/cursor_edges/probe.py)')
    if _LEAF_RECTS_ENABLED:
        mode = 'MODE: --fix --leaf-rects (Iteration 6 — subview-coverage hypothesis)'
    elif args.fix:
        mode = 'MODE: --fix (enableCursorRects hypothesis)'
    else:
        mode = 'MODE: baseline (no fix)'
    _log(mode)
    _log('=' * 60)
    _log(f'Panel geometry: {PANEL_WIDTH}×{PANEL_HEIGHT}  EDGE={EDGE}')
    if _LEAF_RECTS_ENABLED:
        _log('Leaf-rects ENABLED — each subview installs edge rects in its resetCursorRects:')
        _log('  StackView   : LEFT + RIGHT (full local height)')
        _log('  FooterView  : LEFT + RIGHT (full local height) + BOTTOM (full width)')
        _log('  TopBarView  : LEFT + RIGHT (full local height, no top)')
        _log('  Button      : LEFT if frame.origin.x < EDGE (Auto-Jump, session rows)')
    _log('View hierarchy at startup:')
    _dump_hierarchy(panel.contentView())
    _log('')
    _log('Cursor rects installed by ContentView.resetCursorRects:')
    _log(f'  ↕  bottom y=0..{EDGE}                    → resizeUpDown')
    _log(f'  ↔  left   x=0..{EDGE}                    → resizeLeftRight')
    _log(f'  ↔  right  x={PANEL_WIDTH-EDGE}..{PANEL_WIDTH}               → resizeLeftRight')
    _log(f'  →  interior ({EDGE},{EDGE})..({PANEL_WIDTH-EDGE},{PANEL_HEIGHT}) → arrow')
    _log('')
    _log('Signals to watch:')
    _log('  resetCursorRects — which views install rects (fires on activate + resize)')
    _log('  cursorUpdate_    — which view WINS the cursor race (the one that fires last)')
    _log('  [leaf] lines     — leaf-rect installation log (--leaf-rects mode only)')
    _log('  mouseEntered_    — tracking area entry')
    _log('  mouseMoved_      — per-move (tracking area owner)')
    _log('  NSEventMonitor   — pre-dispatch raw event')
    _log('')
    if _LEAF_RECTS_ENABLED:
        _log('Iteration 6 hypothesis: subview coverage shadows ContentView edge rects.')
        _log('Leaf rects installed on covering views — expected: cursorUpdate_ fires on')
        _log('StackView / FooterView / TopBarView / Button at edge positions.')
        _log('If cursorUpdate_ still 0 → subview-coverage is NOT the blocker; next: sendEvent_ override.')
    elif args.fix:
        _log('Hypothesis: cursorUpdate_ will now fire on hover → confirms enableCursorRects was the missing call.')
        _log('If cursorUpdate_ STILL fires 0 times → look at window-level event routing next.')
    _log('Hover slowly over each edge and each widget. Quit: Cmd-Q or Ctrl-C.')
    _log('=' * 60)

    panel.orderFront_(None)
    app.activateIgnoringOtherApps_(True)
    app.run()


main()
