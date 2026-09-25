# INFRASTRUCTURE
from collections import Counter
from datetime import datetime
from itertools import groupby

from AppKit import (NSAttributedString, NSBox, NSButton, NSColor, NSFont,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSGridCell, NSGridCellPlacementLeading, NSGridView,
                    NSLayoutAttributeLeading, NSStackView, NSTextField,
                    NSTrackingActiveAlways, NSTrackingArea, NSTrackingCursorUpdate,
                    NSTrackingInVisibleRect,
                    NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel,
                    NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize, NSRange

from src.menubar.panel_dims import PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT, PANEL_GAP
from src.menubar.panel_tabs import TAB_SEPARATOR, header_pieces
from src.menubar.panel_views import _CursorlessButton, _CursorlessLabel, _KeyablePanel, _PanelContentView

_NAME_WIDTH    = 22
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'
_BADGE_IDLE    = '[ ]'

_FOOTER_H        = 30
_TOP_BAR_H       = 21
_ROW_H           = 21
_LABEL_H         = 19
_TA_CURSOR_OPTS   = NSTrackingCursorUpdate | NSTrackingActiveAlways | NSTrackingInVisibleRect

# FUNCTIONS

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

def _text_width(text: str) -> float:
    return NSAttributedString.alloc().initWithString_attributes_(
        text, {NSFontAttributeName: _MENLO()}).size().width

def _make_tab_button(piece: str, tag: int, x: float, width: float, height: float):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(x, 0, width, height))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(piece, {NSFontAttributeName: _MENLO()}))
    btn.setTag_(tag)
    return btn

def _make_tab_separator(x: float, width: float, height: float):
    label = _CursorlessLabel.labelWithString_('')
    label.setFrame_(NSMakeRect(x, 0, width, height))
    label.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            TAB_SEPARATOR, {NSFontAttributeName: _MENLO()}))
    return label

def _make_tab_header(active: str, pw: int):
    height = _TOP_BAR_H - 1
    pieces = header_pieces(active)
    widths = [_text_width(p) for p in pieces]
    sep_w = _text_width(TAB_SEPARATOR)
    total = sum(widths) + sep_w * (len(pieces) - 1)
    strip = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw - 22, height))
    strip.setAutoresizingMask_(2)
    header = NSView.alloc().initWithFrame_(NSMakeRect((pw - 22 - total) / 2.0, 0, total, height))
    header.setAutoresizingMask_(5)
    x = 0.0
    for index, (piece, width) in enumerate(zip(pieces, widths)):
        header.addSubview_(_make_tab_button(piece, index, x, width, height))
        x += width
        if index < len(pieces) - 1:
            header.addSubview_(_make_tab_separator(x, sep_w, height))
            x += sep_w
    strip.addSubview_(header)
    return strip

def _header_buttons(strip) -> list:
    return [v for v in strip.subviews()[0].subviews() if isinstance(v, NSButton)]

def _wire_header_buttons(strip, target) -> None:
    for btn in _header_buttons(strip):
        btn.setTarget_(target)
        btn.setAction_(b'selectTab:')

def _make_panel_top_bar(active: str, pw: int):
    top_bar = NSView.alloc().initWithFrame_(NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, pw, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)
    header = _make_tab_header(active, pw)
    top_bar.addSubview_(header)
    return top_bar, header

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
    top_bar, header_view = _make_panel_top_bar('Sessions', PANEL_WIDTH)
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
    return panel, stack, quit_btn, header_view, kill_btn

def _reposition_panel(panel, nsstatusitem) -> None:
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = nsstatusitem.button().window().frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

def _make_tab_nspanel(active: str):
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
    header = _make_tab_header(active, PANEL_WIDTH)
    top_bar.addSubview_(header)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)
    cv.addSubview_(stack)
    return panel, stack, header

def _reposition_tab_panel(panel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = btn_win.frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

def _resize_panel_keep_top(panel, width, new_h: float) -> None:
    frame = panel.frame()
    top_y = frame.origin.y + frame.size.height
    panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, width, new_h), False)

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
