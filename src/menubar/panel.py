# INFRASTRUCTURE
from itertools import groupby

from AppKit import (NSAttributedString, NSBox, NSButton, NSColor, NSCursor, NSFont,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSLayoutAttributeLeading, NSPanel, NSStackView, NSTextField,
                    NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel,
                    NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

ICON_NORMAL          = '◉'
ICON_BLINK           = '●'
ICON_BASELINE_OFFSET = 1.0   # pts — vertical offset applied via NSBaselineOffsetAttributeName; adjust if icon drifts
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red
_NO_BG         = '   '   # 3-char spacer when no background task

PANEL_WIDTH      = 380   # pts
PANEL_HEIGHT     = 460   # pts — initial height; floor for first-run (no settings)
PANEL_MIN_WIDTH  = 250   # pts — minimum width enforced by setContentMinSize_
PANEL_MIN_HEIGHT = 120   # pts — minimum height enforced by setContentMinSize_
PANEL_GAP        = 4     # pts below the status bar button
_FOOTER_H        = 30    # pts — fixed footer height for Restart button
_TOP_BAR_H       = 21    # pts — fixed top-bar height for Auto-Jump button (analog to footer, at top edge)
_ROW_H           = 21    # pts — session NSButton row (20) + 1pt NSStackView spacing
_LABEL_H         = 19    # pts — header/separator NSTextField (18) + 1pt NSStackView spacing

# FUNCTIONS

# NSView subclass as panel contentView — defines cursor rects for resize edges via resetCursorRects
# Canonical macOS cursor-zone API: AppKit calls resetCursorRects on window activation and after resize,
# merges all views' rects in z-order. Child views (NSTextField, NSButton) install their own rects in
# their resetCursorRects and win over NSCursor.set() calls in mouseMoved_ — that is why the
# mouseMoved_/NSTrackingArea approach failed (I-Beam from NSTextField labels always overrode our set()).
# resetCursorRects on the contentView installs rects at the correct z-order level.
class _PanelContentView(NSView):
    def resetCursorRects(self):
        w    = self.bounds().size.width
        h    = self.bounds().size.height
        EDGE = 8
        self.addCursorRect_cursor_(NSMakeRect(0,        0,    w,            EDGE),      NSCursor.resizeUpDownCursor())
        self.addCursorRect_cursor_(NSMakeRect(0,        0,    EDGE,         h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(NSMakeRect(w - EDGE, 0,    EDGE,         h),         NSCursor.resizeLeftRightCursor())
        self.addCursorRect_cursor_(NSMakeRect(EDGE,     EDGE, w - 2 * EDGE, h - EDGE),  NSCursor.arrowCursor())

# NSTextField subclass that suppresses the default I-Beam cursor rect installation
# NSTextField.resetCursorRects installs I-Beam over its full frame; no-op override prevents
# child-view I-Beam from winning over the panel edge cursors defined in _PanelContentView
class _CursorlessLabel(NSTextField):
    def resetCursorRects(self): pass

# Badge for sessions with active background tasks: [B M:SS] if timer running, [B] otherwise
def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'

# Build NSPanel + fixed footer (Restart) + fixed top_bar (Auto-Jump) + NSStackView (sessions, middle)
# Returns (panel, stack_view, quit_btn, toggle_btn) — stored on app instance; ObjC objects reject Python attrs
# Layout (y=0 = bottom of contentView):
#   [0, 0,                       pw, _FOOTER_H]   footer   mask=2  — widthSizable, bottom-anchored at y=0
#   [0, _FOOTER_H,               pw, stack_h]     stack    mask=18 — width+height sizable, fills middle
#   [0, PANEL_HEIGHT-_TOP_BAR_H, pw, _TOP_BAR_H]  top_bar  mask=10 — widthSizable|minYMargin, top-anchored
def _make_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
        NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskResizable, 2, True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorIgnoresCycle)
    panel.setHasShadow_(True)
    panel.setOpaque_(False)
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    cv = _PanelContentView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)
    footer = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, _FOOTER_H))
    footer.setAutoresizingMask_(2)   # NSViewWidthSizable
    quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(PANEL_WIDTH - 86, 4, 78, 22))
    quit_btn.setAutoresizingMask_(1)   # NSViewMinXMargin — right-anchored
    quit_btn.setTitle_('Restart')
    quit_btn.setBezelStyle_(1)   # NSBezelStyleRounded
    footer.addSubview_(quit_btn)
    cv.addSubview_(footer)
    top_bar = NSView.alloc().initWithFrame_(NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, PANEL_WIDTH, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable(2) | NSViewMinYMargin(8) — bottom margin flexible → stays at top edge on resize
    toggle_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    toggle_btn.setAutoresizingMask_(2)   # NSViewWidthSizable — stretches with top_bar
    top_bar.addSubview_(toggle_btn)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _FOOTER_H - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(
        NSMakeRect(0, _FOOTER_H, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)   # NSViewWidthSizable|NSViewHeightSizable — auto-fills middle on resize
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)   # NSStackViewDistributionGravityAreas — required for addView_inGravity_ to work
    cv.addSubview_(stack)
    return panel, stack, quit_btn, toggle_btn

# Position panel flush below the NSStatusItem button; reads current panel dimensions (set by _resize_panel)
def _reposition_panel(panel, nsstatusitem) -> None:
    w  = panel.frame().size.width    # dynamic — updated by _resize_panel on each rebuild
    h  = panel.frame().size.height
    sr = nsstatusitem.button().window().frame()   # button window is already in screen coords
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

# Borderless Menlo-font NSButton row for session / toggle entries
def _make_row_button(text: str, panel_width: int, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, panel_width - 22, 20))
    btn.setBordered_(False)
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return btn

# Non-interactive Menlo-font NSTextField for plain text labels (e.g. "No active sessions")
def _make_header_label(text: str, panel_width: int) -> NSTextField:
    tf = _CursorlessLabel.labelWithString_('')
    tf.setFrame_(NSMakeRect(0, 0, panel_width - 22, 18))
    tf.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            text, {NSFontAttributeName: _MENLO()}))
    return tf

# NSBox (1pt horizontal rule) spanning content width; used as top-level separator between toggle and sessions
# panel_width - 22: 22pt total horizontal margin matches row-button and label frames (consistent inset across all stack items)
def _make_line_separator(panel_width: int) -> NSView:
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — NSView has no intrinsicContentSize; without this NSStackView collapses it to 0 under Auto Layout
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator — 1pt system-colored horizontal rule
    container.addSubview_(line)
    return container

# NSBox (1pt horizontal rule) with NSTextField label overlay — project name masks the line behind it
# label background = NSColor.windowBackgroundColor() to opaquely cover the NSBox behind the text
def _make_separator_view(project_name: str, panel_width: int) -> NSView:
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — same reason as _make_line_separator
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator
    container.addSubview_(line)
    label_w = min(len(project_name) * 8 + 6, w - 12)
    tf = _CursorlessLabel.labelWithString_(project_name)
    tf.setFrame_(NSMakeRect(12, 0, label_w, 18))
    tf.setFont_(_MENLO())
    tf.setDrawsBackground_(True)
    tf.setBackgroundColor_(NSColor.windowBackgroundColor())
    container.addSubview_(tf)
    return container

# Compute exact panel height needed to display all sessions; no truncation
def _compute_required_height(sorted_sessions, bg_result) -> int:
    h = _FOOTER_H + _TOP_BAR_H + _LABEL_H   # footer + top-bar (Auto-Jump) + separator-in-stack
    if bg_result is not None:
        h += _ROW_H                           # abort timer button
    if not sorted_sessions:
        return h + _LABEL_H                   # "No active sessions" label
    for _, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        group_list = list(group_iter)
        h += _LABEL_H + len(group_list) * _ROW_H
    return h

# Resize NSPanel frame to new_h; anchors TOP edge (not bottom-left origin) so panel stays flush below bar icon
# NSStackView auto-resizes via autoresizingMask=18 (NSViewWidthSizable|NSViewHeightSizable)
def _resize_panel(app, new_h: float) -> None:
    w         = app._panel_width
    frame     = app._panel.frame()
    top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
    app._panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Full panel rebuild; populates _displayed_items + _cwd_map + _abort_btn
# bg_result: BgSleepInfo from _scan_bg_sleep_timers(), or None — callers always provide explicitly
def _rebuild_panel(app, sessions, bg_result=None) -> None:
    for sv in list(app._panel_sv.arrangedSubviews()):
        app._panel_sv.removeView_(sv)
    app._displayed_items = {}
    app._cwd_map = {}
    app._abort_btn = None
    next_tag = [1]
    pw = app._panel_width
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
    min_remaining = bg_result.min_remaining if bg_result else None
    name_width = max((len(s.name) for s in sorted_sessions), default=_NAME_WIDTH)
    required_h = _compute_required_height(sorted_sessions, bg_result)
    _resize_panel(app, max(app._panel_min_height, required_h))
    state = 'ON' if app._auto_focus else 'OFF'
    app._toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'Auto-Jump: {state}', {NSFontAttributeName: _MENLO()}))
    app._panel_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if bg_result is not None:
        abort_btn = _make_row_button('  ⊗ abort timer', pw)
        abort_btn.setTarget_(app._panel_controller)
        abort_btn.setAction_(b'abortBgTimer:')
        app._panel_sv.addView_inGravity_(abort_btn, 1)
        app._abort_btn = abort_btn
    if not sorted_sessions:
        app._panel_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        return
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        app._panel_sv.addView_inGravity_(_make_separator_view(project_name, pw), 1)
        for s in group_iter:
            dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
            name_col = s.name.ljust(name_width)
            if not s.is_worker:
                line = f'● {name_col} {dot} {badge}'
                btn  = _make_row_button(line, pw, NSColor.systemOrangeColor())
                tag  = next_tag[0]; next_tag[0] += 1
                btn.setTag_(tag)
                btn.setTarget_(app._panel_controller)
                btn.setAction_(b'focusSession:')
                app._cwd_map[tag] = s.cwd or ''
            else:
                line = f'  {name_col} {dot} {badge}'
                btn  = _make_row_button(line, pw)
            app._panel_sv.addView_inGravity_(btn, 1)
            app._displayed_items[s.name] = btn

# In-place title update while NSPanel is open; preserves widget positions
def _update_panel_inplace(app, sessions, bg_result) -> None:
    min_remaining = bg_result.min_remaining if bg_result else None
    name_width = max((len(s.name) for s in sessions), default=_NAME_WIDTH)
    session_map = {s.name: s for s in sessions}
    for name, btn in app._displayed_items.items():
        s = session_map.get(name)
        if s is None:
            continue
        dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        badge    = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
        name_col = name.ljust(name_width)
        if not s.is_worker:
            line, color = f'● {name_col} {dot} {badge}', NSColor.systemOrangeColor()
        else:
            line, color = f'  {name_col} {dot} {badge}', None
        attrs = {NSFontAttributeName: _MENLO()}
        if color is not None:
            attrs[NSForegroundColorAttributeName] = color
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(line, attrs))
