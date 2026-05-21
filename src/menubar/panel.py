# INFRASTRUCTURE
import objc
import os
from datetime import datetime
from itertools import groupby

from AppKit import (NSAttributedString, NSBox, NSButton, NSColor, NSCursor, NSFont,
                    NSFontAttributeName, NSForegroundColorAttributeName,
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
from Foundation import NSMakeRect, NSMakeSize

ICON_NORMAL          = '◉'
ICON_BLINK           = '●'
ICON_BASELINE_OFFSET = 1.0   # pts — vertical offset applied via NSBaselineOffsetAttributeName; adjust if icon drifts
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red
_NO_BG         = '   '   # 3-char spacer when no background task

_COL_SLOT_W  = 4    # chars — "[N] " slot or "    " worker indent (≈28pt Menlo 13pt)
_COL_NAME_W  = 23   # chars — name column, ljust + truncate at end   (≈180pt Menlo 13pt)
_COL_TIMER_W = 9    # chars — "[B M:SS]" badge max = "[B 99:59]"=9ch (≈70pt Menlo 13pt)

PANEL_WIDTH      = 380   # pts
PANEL_HEIGHT     = 460   # pts — initial height; floor for first-run (no settings)
PANEL_MIN_WIDTH  = 250   # pts — minimum width enforced by setContentMinSize_
PANEL_MIN_HEIGHT = 120   # pts — minimum height enforced by setContentMinSize_
PANEL_GAP        = 4     # pts below the status bar button
_FOOTER_H        = 30    # pts — fixed footer height for Restart button
_TOP_BAR_H       = 21    # pts — fixed top-bar height for Auto-Jump button (analog to footer, at top edge)
_ROW_H           = 21    # pts — session NSButton row (20) + 1pt NSStackView spacing
_LABEL_H         = 19    # pts — header/separator NSTextField (18) + 1pt NSStackView spacing
EDGE             = 8     # pts — cursor-zone width at L/R/bottom edges
_TA_TRACKING_OPTS = (NSTrackingCursorUpdate | NSTrackingMouseMoved |
                     NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways |
                     NSTrackingInVisibleRect)
_TA_CURSOR_OPTS   = NSTrackingCursorUpdate | NSTrackingActiveAlways | NSTrackingInVisibleRect

# FUNCTIONS

def _cursor_log(msg: str) -> None:
    if not os.environ.get('MENUBAR_CURSOR_DEBUG'):
        return
    with open('/tmp/menubar-cursor.log', 'a') as f:
        f.write(f'{datetime.now().strftime("%H:%M:%S.%f")[:-3]} {msg}\n')

# NSView contentView — tracking-area event detection + state-driven cursor rects (winit pattern)
# mouseMoved_ (via NSTrackingArea) detects edge and calls _set_hovered_edge, which calls
# invalidateCursorRectsForView_ on the window. AppKit then calls resetCursorRects which
# installs a single full-bounds rect with the cursor for the current edge state.
# _CursorlessButton/Label suppress child-view resetCursorRects so they cannot override ours.
# areCursorRectsEnabled override keeps cursor-rect dispatch active for non-key windows.
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

    # Claim L/R/bottom edge zones for self; interior falls through to child views
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

# NSTextField subclass that suppresses the default I-Beam cursor rect installation
# NSTextField.resetCursorRects installs I-Beam over its full frame; no-op override prevents
# child-view I-Beam from winning over the panel edge cursors defined in _PanelContentView
class _CursorlessLabel(NSTextField):
    def resetCursorRects(self): pass

# NSButton subclass that suppresses default cursor rect installation
# NSButton.resetCursorRects would install rects that override ContentView edge cursors at edges
class _CursorlessButton(NSButton):
    def resetCursorRects(self): pass

# Badge for sessions with active background tasks: [B M:SS] if timer running, [B] otherwise
def _format_bg_badge(remaining) -> str:
    if remaining is None:
        return '[B]'
    mins, secs = divmod(remaining, 60)
    return f'[B {mins}:{secs:02d}]'

# Build NSPanel + fixed footer (Kill + Restart) + fixed top_bar (Auto-Jump) + NSStackView (sessions, middle)
# Returns (panel, stack_view, quit_btn, toggle_btn, kill_btn) — stored on app instance; ObjC objects reject Python attrs
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
    panel.setAcceptsMouseMovedEvents_(True)   # required — without this NSWindow suppresses mouseMoved dispatch → _hovered_edge never updates → no resize cursors
    panel.setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))
    cv = _PanelContentView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    panel.setContentView_(cv)
    # NonactivatingPanel never calls becomeKeyWindow → enableCursorRects() is never invoked
    # automatically → cursor-rect dispatch is silently disabled (no cursor changes anywhere).
    # Explicit call here restores dispatch; confirmed via dev/cursor_edges/probe.py --fix.
    panel.enableCursorRects()
    footer = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, _FOOTER_H))
    footer.setAutoresizingMask_(2)   # NSViewWidthSizable
    quit_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(PANEL_WIDTH - 86, 4, 78, 22))
    quit_btn.setAutoresizingMask_(1)   # NSViewMinXMargin — right-anchored
    quit_btn.setTitle_('Restart')
    quit_btn.setBezelStyle_(1)   # NSBezelStyleRounded
    footer.addSubview_(quit_btn)
    kill_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(PANEL_WIDTH - 86 - 78 - 8, 4, 78, 22))
    kill_btn.setAutoresizingMask_(1)   # NSViewMinXMargin — right-anchored, 8pt gap left of Restart
    kill_btn.setTitle_('Kill')
    kill_btn.setBezelStyle_(1)   # NSBezelStyleRounded
    footer.addSubview_(kill_btn)
    cv.addSubview_(footer)
    top_bar = NSView.alloc().initWithFrame_(NSMakeRect(0, PANEL_HEIGHT - _TOP_BAR_H, PANEL_WIDTH, _TOP_BAR_H))
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable(2) | NSViewMinYMargin(8) — bottom margin flexible → stays at top edge on resize
    toggle_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
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
    # Child views (NSView/NSStackView) have no cursorUpdate_ handler — AppKit dispatches
    # cursorUpdate_ only to the topmost view with a handler, skipping our ContentView.
    # Fix: install a tracking area on each child with owner=cv so AppKit fires cursorUpdate_
    # on cv regardless of which child the cursor is over.
    for child in (footer, top_bar, stack):
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            child.bounds(), _TA_CURSOR_OPTS, cv, None)
        child.addTrackingArea_(ta)
    return panel, stack, quit_btn, toggle_btn, kill_btn

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
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, panel_width - 22, 20))
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
# If proj_min_remaining is not None, adds an inline abort button at the right end (Option B).
# Returns (container_view, abort_NSButton_or_None); caller sets target/action on the button.
def _make_separator_view(project_name: str, panel_width: int, proj_min_remaining=None):
    w = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 18))
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — same reason as _make_line_separator
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator
    container.addSubview_(line)
    abort_btn = None
    if proj_min_remaining is not None:
        mins, secs = divmod(proj_min_remaining, 60)
        btn_text = f'⊗ {mins}:{secs:02d}'
        btn_w = len(btn_text) * 8 + 8   # approx Menlo char width; right-anchored
        abort_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(w - btn_w, 0, btn_w, 18))
        abort_btn.setBordered_(False)
        abort_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
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

# NSView container: "  [N] <msg>  −" for one queued message
# Returns (container, minus_btn); caller wires minus_btn tag/target/action
def _make_queue_msg_row(msg: str, idx: int, panel_width: int):
    pw    = panel_width - 22
    row_h = _ROW_H - 1
    minus_w = 18
    text_w  = pw - minus_w - 2
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, row_h))
    container.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
    container.heightAnchor().constraintEqualToConstant_(float(row_h)).setActive_(True)
    prefix = f'  [{idx}] '
    label  = _CursorlessLabel.labelWithString_('')
    label.setFrame_(NSMakeRect(0, 0, text_w, row_h))
    label.cell().setLineBreakMode_(4)   # NSLineBreakByTruncatingTail
    label.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            prefix + msg, {NSFontAttributeName: _MENLO()}))
    container.addSubview_(label)
    minus_btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(pw - minus_w, 0, minus_w, row_h))
    minus_btn.setBordered_(False)
    minus_btn.setButtonType_(7)
    minus_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '−', {NSFontAttributeName: _MENLO(),
                  NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    container.addSubview_(minus_btn)
    return container, minus_btn

# Plain NSButton "  +" row for adding a new queue message; caller wires tag/target/action
def _make_queue_add_btn(panel_width: int) -> 'NSButton':
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, panel_width - 22, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '  +', {NSFontAttributeName: _MENLO(),
                    NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    return btn

# NSView container holding an editable NSTextField for inline queue message input
# Returns (container, NSTextField); caller wires tf tag/target/action/delegate
def _make_queue_input_field(panel_width: int, tag: int):
    pw    = panel_width - 22
    row_h = _ROW_H - 1
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, row_h))
    container.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
    container.heightAnchor().constraintEqualToConstant_(float(row_h)).setActive_(True)
    tf = NSTextField.alloc().initWithFrame_(NSMakeRect(2, 2, pw - 4, row_h - 4))
    tf.setFont_(_MENLO())
    tf.setEditable_(True)
    tf.setSelectable_(True)
    tf.setBezeled_(True)
    tf.setDrawsBackground_(True)
    tf.setTag_(tag)
    tf.setPlaceholderString_('message…')
    container.addSubview_(tf)
    return container, tf

# Add queue block rows to panel_sv for one main session (messages + add-btn or input field)
# Modifies app._queue_add_tags, app._queue_remove_tags, app._pending_queue_tags in place
def _add_queue_block(app, s, pw: int, q_add_tag: list, q_rmv_tag: list, q_tf_tag: list) -> None:
    msgs       = app._queue_data.get(s.session_id, [])
    is_pending = s.session_id in app._pending_queue_sessions
    for i, msg in enumerate(msgs):
        row, minus_btn = _make_queue_msg_row(msg, i + 1, pw)
        rmv_tag = q_rmv_tag[0]; q_rmv_tag[0] += 1
        minus_btn.setTag_(rmv_tag)
        minus_btn.setTarget_(app._panel_controller)
        minus_btn.setAction_(b'removeQueueMsg:')
        app._queue_remove_tags[rmv_tag] = (s.session_id, i)
        app._panel_sv.addView_inGravity_(row, 1)
    if is_pending:
        tf_tag = q_tf_tag[0]; q_tf_tag[0] += 1
        cont, tf = _make_queue_input_field(pw, tf_tag)
        tf.setTarget_(app._panel_controller)
        tf.setAction_(b'commitQueueField:')
        tf.setDelegate_(app._panel_controller)
        app._pending_queue_tags[tf_tag] = s.session_id
        app._panel_sv.addView_inGravity_(cont, 1)
        app._panel.makeFirstResponder_(tf)
    else:
        add_tag = q_add_tag[0]; q_add_tag[0] += 1
        add_btn = _make_queue_add_btn(pw)
        add_btn.setTag_(add_tag)
        add_btn.setTarget_(app._panel_controller)
        add_btn.setAction_(b'addQueueRow:')
        app._queue_add_tags[add_tag] = s.session_id
        app._panel_sv.addView_inGravity_(add_btn, 1)

# Compute exact panel height needed to display all sessions; no truncation.
# queue_data: {session_id: [msgs]} for computing queue block heights per main session.
# Abort buttons (Option B) are embedded in separator views — zero height cost.
def _compute_required_height(sorted_sessions, queue_data=None) -> int:
    h = _FOOTER_H + _TOP_BAR_H + _LABEL_H   # footer + top-bar (Auto-Jump) + separator-in-stack
    if not sorted_sessions:
        return h + _LABEL_H                   # "No active sessions" label
    for _, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        group_list = list(group_iter)
        h += _LABEL_H
        for s in group_list:
            h += _ROW_H   # session row
            if not s.is_worker:
                msgs_count = len((queue_data or {}).get(s.session_id, []))
                h += (msgs_count + 1) * _ROW_H   # N message rows + 1 add/input row
    return h

# Resize NSPanel frame to new_h; anchors TOP edge (not bottom-left origin) so panel stays flush below bar icon
# NSStackView auto-resizes via autoresizingMask=18 (NSViewWidthSizable|NSViewHeightSizable)
def _resize_panel(app, new_h: float) -> None:
    w         = app._panel_width
    frame     = app._panel.frame()
    top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
    app._panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Full panel rebuild; populates _displayed_items + _cwd_map + _abort_btns_by_project + _abort_project_for_tag
# bg_by_project: Dict[project_name, BgSleepInfo] from _scan_bg_sleep_timers(); None = no timers.
# Abort buttons (Option B) are embedded inline in per-project separator rows — zero height delta.
def _rebuild_panel(app, sessions, bg_by_project=None) -> None:
    for sv in list(app._panel_sv.arrangedSubviews()):
        app._panel_sv.removeView_(sv)
    app._displayed_items = {}
    app._cwd_map = {}
    app._abort_btns_by_project = {}
    app._abort_project_for_tag = {}
    app._queue_add_tags = {}
    app._queue_remove_tags = {}
    app._pending_queue_tags = {}
    next_tag  = [1]
    abort_tag = 1000   # abort button tags start above session row tags (1..N)
    q_add_tag = [2000]
    q_rmv_tag = [3000]
    q_tf_tag  = [4000]
    pw = app._panel_width
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
    required_h = _compute_required_height(sorted_sessions, app._queue_data)
    _resize_panel(app, max(app._panel_min_height, required_h))
    state = 'ON' if app._auto_focus else 'OFF'
    app._toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'[Sessions] · Beads     Auto-Jump: {state}', {NSFontAttributeName: _MENLO()}))
    app._panel_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if not sorted_sessions:
        app._panel_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        return
    main_slot = 0
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        proj_bg = (bg_by_project or {}).get(project_name)
        sep_view, abort_btn = _make_separator_view(
            project_name, pw,
            proj_bg.min_remaining if proj_bg else None)
        app._panel_sv.addView_inGravity_(sep_view, 1)
        if abort_btn is not None:
            abort_btn.setTag_(abort_tag)
            abort_btn.setTarget_(app._panel_controller)
            abort_btn.setAction_(b'abortBgTimer:')
            app._abort_btns_by_project[project_name] = abort_btn
            app._abort_project_for_tag[abort_tag] = project_name
            abort_tag += 1
        for s in group_iter:
            dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            badge    = _format_bg_badge(proj_bg.min_remaining) if proj_bg else _NO_BG
            name_col = s.name[:_COL_NAME_W].ljust(_COL_NAME_W)
            if not s.is_worker:
                main_slot += 1
                slot_str = f'[{main_slot}] ' if main_slot <= 9 else '    '
                line = f'{slot_str}* {name_col} {dot} {badge.ljust(_COL_TIMER_W)}'
                btn  = _make_row_button(line, pw, NSColor.systemOrangeColor())
                tag  = next_tag[0]; next_tag[0] += 1
                btn.setTag_(tag)
                btn.setTarget_(app._panel_controller)
                btn.setAction_(b'focusSession:')
                app._cwd_map[tag] = s.cwd or ''
                app._panel_sv.addView_inGravity_(btn, 1)
                app._displayed_items[s.name] = btn
                _add_queue_block(app, s, pw, q_add_tag, q_rmv_tag, q_tf_tag)
            else:
                line = f'      {name_col} {dot} {badge.ljust(_COL_TIMER_W)}'
                btn  = _make_row_button(line, pw)
                app._panel_sv.addView_inGravity_(btn, 1)
                app._displayed_items[s.name] = btn

# In-place title update while NSPanel is open; preserves widget positions.
# Updates session row titles AND per-project abort button countdowns.
def _update_panel_inplace(app, sessions, bg_by_project) -> None:
    session_map = {s.name: s for s in sessions}
    main_slot = 0
    for name, btn in app._displayed_items.items():
        s = session_map.get(name)
        if s is None:
            continue
        proj_bg  = (bg_by_project or {}).get(s.project_name)
        dot      = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        badge    = _format_bg_badge(proj_bg.min_remaining) if proj_bg else _NO_BG
        name_col = name[:_COL_NAME_W].ljust(_COL_NAME_W)
        if not s.is_worker:
            main_slot += 1
            slot_str = f'[{main_slot}] ' if main_slot <= 9 else '    '
            line, color = f'{slot_str}* {name_col} {dot} {badge.ljust(_COL_TIMER_W)}', NSColor.systemOrangeColor()
        else:
            line, color = f'      {name_col} {dot} {badge.ljust(_COL_TIMER_W)}', None
        attrs = {NSFontAttributeName: _MENLO()}
        if color is not None:
            attrs[NSForegroundColorAttributeName] = color
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(line, attrs))
    # Update per-project abort button countdowns inline (no layout change needed)
    if bg_by_project:
        for proj_name, abort_btn in app._abort_btns_by_project.items():
            proj_bg = bg_by_project.get(proj_name)
            if proj_bg is None:
                continue
            mins, secs = divmod(proj_bg.min_remaining, 60)
            abort_btn.setAttributedTitle_(
                NSAttributedString.alloc().initWithString_attributes_(
                    f'⊗ {mins}:{secs:02d}',
                    {NSFontAttributeName: _MENLO(),
                     NSForegroundColorAttributeName: NSColor.systemRedColor()}))
