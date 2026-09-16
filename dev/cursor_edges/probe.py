#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import signal

from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

import cursor_edges_constants as cec
from cursor_edges_constants import EDGE, PANEL_HEIGHT, PANEL_WIDTH
from cursor_edges_logging import _dump_hierarchy, _install_global_mouse_monitor, _log
from cursor_edges_panel import _make_probe_panel

# ORCHESTRATOR

def main() -> None:
    args = _parse_args()

    cec._LEAF_RECTS_ENABLED = args.fix and args.leaf_rects
    cec._TRACKING_ENABLED   = args.tracking

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    signal.signal(signal.SIGINT, lambda *_: app.terminate_(None))

    panel = _make_probe_panel(fix=args.fix, no_resizable=args.no_resizable)

    _install_global_mouse_monitor()

    _log_startup_banner(args)
    _log_signal_guide()
    _log('')
    _log('View hierarchy at startup:')
    _dump_hierarchy(panel.contentView())
    _log('')
    _log('Hover slowly over each edge and each widget. Quit: Cmd-Q or Ctrl-C.')
    _log('=' * 60)

    panel.orderFront_(None)
    app.activateIgnoringOtherApps_(True)
    app.run()


# FUNCTIONS

def _parse_args():
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
    return parser.parse_args()


def _log_startup_banner(args) -> None:
    _log('=' * 60)
    _log('cursor-edges probe  (Monitor_CC/dev/cursor_edges/probe.py)')
    flags = []
    if args.fix:                flags.append('--fix')
    if cec._LEAF_RECTS_ENABLED: flags.append('--leaf-rects')
    if args.no_resizable:       flags.append('--no-resizable')
    if args.tracking:           flags.append('--tracking')
    if not flags:                flags.append('baseline')
    mode_tag = ' '.join(flags)

    if args.tracking and args.no_resizable:
        mode = (f'MODE: {mode_tag}  '
                f'(Iteration 8 — NSTrackingArea cursorUpdate + custom drag resize, no native resize mask)')
    elif args.tracking:
        mode = (f'MODE: {mode_tag}  '
                f'(Iteration 8 — NSTrackingArea cursorUpdate, native resize mask kept)')
    elif args.no_resizable:
        mode = f'MODE: {mode_tag}  (H7 — no-resizable test, WindowServer edge-claim hypothesis)'
    elif cec._LEAF_RECTS_ENABLED:
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


def _log_signal_guide() -> None:
    _log(f'Panel geometry: {PANEL_WIDTH}×{PANEL_HEIGHT}  EDGE={EDGE}')
    if cec._TRACKING_ENABLED:
        _log('Signals to watch (--tracking mode):')
        _log('  updateTrackingAreas — tracking area installed/refreshed on resize')
        _log('  mouseMoved_         — TrackingCV called; logs loc + edge detection')
        _log('  cursor PUSH/POP     — edge transition log (nil↔edge, edge_a→edge_b)')
        _log('  cursorUpdate_       — called by AppKit on cursor-update event; sets cursor')
        _log('  mouseDown_/Dragged_ — custom resize events (--no-resizable only)')
    else:
        if cec._LEAF_RECTS_ENABLED:
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


main()
