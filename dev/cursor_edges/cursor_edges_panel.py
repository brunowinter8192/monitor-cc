# INFRASTRUCTURE
from AppKit import (
    NSLayoutAttributeLeading,
    NSPanel,
    NSStatusWindowLevel,
    NSUserInterfaceLayoutOrientationVertical,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowStyleMaskNonactivatingPanel,
    NSWindowStyleMaskResizable,
)
from Foundation import NSMakeRect, NSMakeSize

import cursor_edges_constants as cec
from cursor_edges_constants import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT, _FOOTER_H, _TOP_BAR_H
from cursor_edges_logging import _log
from cursor_edges_views import (
    _LoggingButton,
    _LoggingContentView,
    _LoggingFooterView,
    _LoggingStackView,
    _LoggingTopBarView,
    _TrackingContentView,
)

# FUNCTIONS

def _build_panel_window(no_resizable):
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
    return panel


def _build_content_view():
    if cec._TRACKING_ENABLED:
        return _TrackingContentView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    return _LoggingContentView.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))


def _apply_fix_flag(panel):
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


def _add_footer(cv):
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


def _add_top_bar(cv):
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


def _add_session_stack(cv):
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


def _make_probe_panel(fix: bool = False, no_resizable: bool = False) -> NSPanel:
    """Build probe NSPanel that mirrors production _make_nspanel() geometry and z-order exactly."""
    panel = _build_panel_window(no_resizable)
    cv = _build_content_view()
    panel.setContentView_(cv)

    if fix:
        _apply_fix_flag(panel)

    _add_footer(cv)
    _add_top_bar(cv)
    _add_session_stack(cv)

    return panel
