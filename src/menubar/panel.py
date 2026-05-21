# INFRASTRUCTURE
import objc
import os
from datetime import datetime
from itertools import groupby

from AppKit import (NSAttributedString, NSBox, NSButton, NSColor, NSCursor, NSFont,
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

ICON_NORMAL          = '◉'
ICON_BLINK           = '●'
ICON_BASELINE_OFFSET = 1.0   # pts — vertical offset applied via NSBaselineOffsetAttributeName; adjust if icon drifts
_NAME_WIDTH    = 22     # chars for left-justified name column
_MENLO         = lambda: NSFont.fontWithName_size_('Menlo', 13.0)

_BADGE_WORKING = '[*]'   # green — ASCII fixed-width, no emoji drift
_BADGE_IDLE    = '[ ]'   # red

# Grid column widths (pts) — 5-column main-panel layout, measured from Menlo 13pt char widths
_GRID_COL0_W  = 33   # slot "[N]" (3 chars × 7.8pt + buffer)
_GRID_COL1_W  = 17   # star "* " (2 chars × 7.8pt + buffer)
_GRID_COL3_W  = 25   # dot "[ ]"/"[*]" (3 chars × 7.8pt + buffer)
_GRID_COL4_W  = 72   # badge "[B M:SS]" max 9 chars × 7.8pt + buffer
_GRID_COL_SPC = 2    # column spacing (pts between adjacent columns)

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
_rebuild_panel_in_progress = False   # re-entry guard: defensive mirror of queue_panel guard

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

# NSPanel subclass that allows the panel to become key window while keeping NSWindowStyleMaskNonactivatingPanel.
# The mask prevents the APPLICATION from activating (Ghostty stays foreground); canBecomeKeyWindow is a separate
# gate that controls whether the PANEL can receive keyboard events. Without this override the default ObjC
# implementation returns False for NonactivatingPanel masks, silently making makeFirstResponder_ a no-op.
class _KeyablePanel(NSPanel):
    def canBecomeKeyWindow(self):
        return True

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
    panel = _KeyablePanel.alloc().initWithContentRect_styleMask_backing_defer_(
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

# Borderless Menlo-font NSButton for a single NSGridView cell
def _make_grid_cell_btn(text: str, color=None) -> NSButton:
    attrs = {NSFontAttributeName: _MENLO()}
    if color is not None:
        attrs[NSForegroundColorAttributeName] = color
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, _ROW_H - 1))
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
    container.heightAnchor().constraintEqualToConstant_(18.0).setActive_(True)   # explicit height — NSGridView turns off TAMIC on content views; without this height=0 → subviews bleed into row above
    line = NSBox.alloc().initWithFrame_(NSMakeRect(0, 9, w, 1))
    line.setBoxType_(2)   # NSBoxSeparator
    container.addSubview_(line)
    abort_btn = None
    if proj_min_remaining is not None:
        btn_text = 'abort'
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

# Compute exact panel height needed to display all sessions; no truncation.
# Abort buttons (Option B) are embedded in separator views — zero height cost.
def _compute_required_height(sorted_sessions) -> int:
    h = _FOOTER_H + _TOP_BAR_H + _LABEL_H   # footer + top-bar (Auto-Jump) + separator-in-stack
    if not sorted_sessions:
        return h + _LABEL_H                   # "No active sessions" label
    for _, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        h += _LABEL_H
        for s in group_iter:
            h += _ROW_H   # session row
    return h

# Resize NSPanel frame to new_h; anchors TOP edge (not bottom-left origin) so panel stays flush below bar icon
# NSStackView auto-resizes via autoresizingMask=18 (NSViewWidthSizable|NSViewHeightSizable)
def _resize_panel(app, new_h: float) -> None:
    w         = app._panel_width
    frame     = app._panel.frame()
    top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
    app._panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Full panel rebuild; populates _displayed_items + _cwd_map + _abort_btns_by_project + _abort_project_for_tag.
# _displayed_items[name] = (dot_btn, badge_btn_or_None) — only the two cells that change per-tick.
# bg_by_project: Dict[project_name, BgSleepInfo] from _scan_bg_sleep_timers(); None = no timers.
# ONE NSGridView holds all project-separator + session/worker rows; added to _panel_sv after the
# line separator. Separator rows are merged across all 5 columns; worker rows leave cols 0/1/4 empty.
def _rebuild_panel(app, sessions, bg_by_project=None) -> None:
    global _rebuild_panel_in_progress
    if _rebuild_panel_in_progress:
        return
    _rebuild_panel_in_progress = True
    try:
        _rebuild_panel_inner(app, sessions, bg_by_project)
    finally:
        _rebuild_panel_in_progress = False

def _rebuild_panel_inner(app, sessions, bg_by_project=None) -> None:
    for sv in list(app._panel_sv.arrangedSubviews()):
        app._panel_sv.removeView_(sv)
        sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists as regular subview without this
    app._displayed_items = {}
    app._cwd_map = {}
    app._abort_btns_by_project = {}
    app._abort_project_for_tag = {}
    next_tag  = [1]
    abort_tag = 1000   # abort button tags start above session row tags (1..N)
    pw = app._panel_width
    sorted_sessions = sorted(sessions, key=lambda s: (s.project_name, s.is_worker, s.name))
    required_h = _compute_required_height(sorted_sessions)
    _resize_panel(app, max(app._panel_min_height, required_h))
    state = 'ON' if app._auto_focus else 'OFF'
    app._toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'[Sessions] \u00b7 Beads \u00b7 Queue     Auto-Jump: {state}',
            {NSFontAttributeName: _MENLO()}))
    app._panel_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if not sorted_sessions:
        app._panel_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        return
    empty = NSGridCell.emptyContentView()
    grid  = NSGridView.gridViewWithNumberOfColumns_rows_(5, 0)
    grid.setColumnSpacing_(float(_GRID_COL_SPC))
    grid.setRowSpacing_(1.0)
    for i in range(5):
        grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)
    grid.columnAtIndex_(0).setWidth_(float(_GRID_COL0_W))
    grid.columnAtIndex_(1).setWidth_(float(_GRID_COL1_W))
    grid.columnAtIndex_(3).setWidth_(float(_GRID_COL3_W))
    grid.columnAtIndex_(4).setWidth_(float(_GRID_COL4_W))
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    row_idx   = 0
    main_slot = 0
    for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
        proj_bg = (bg_by_project or {}).get(project_name)
        sep_view, abort_btn = _make_separator_view(
            project_name, pw, proj_bg.min_remaining if proj_bg else None)
        grid.addRowWithViews_([sep_view, empty, empty, empty, empty])
        grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
        grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 5), NSRange(row_idx, 1))
        row_idx += 1
        if abort_btn is not None:
            abort_btn.setTag_(abort_tag)
            abort_btn.setTarget_(app._panel_controller)
            abort_btn.setAction_(b'abortBgTimer:')
            app._abort_btns_by_project[project_name] = abort_btn
            app._abort_project_for_tag[abort_tag] = project_name
            abort_tag += 1
        for s in group_iter:
            dot   = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            color = NSColor.systemOrangeColor()
            if not s.is_worker:
                main_slot += 1
                slot_str = f'[{main_slot}]' if main_slot <= 9 else ''
                tag      = next_tag[0]; next_tag[0] += 1
                slot_btn = _make_grid_cell_btn(slot_str, color)
                star_btn = _make_grid_cell_btn('*', color)
                name_btn = _make_grid_cell_btn(s.name, color)
                dot_btn  = _make_grid_cell_btn(dot, color)
                for btn in (slot_btn, star_btn, name_btn, dot_btn):
                    btn.setTag_(tag)
                    btn.setTarget_(app._panel_controller)
                    btn.setAction_(b'focusSession:')
                app._cwd_map[tag] = s.cwd or ''
                if proj_bg is not None:
                    badge_btn = _make_grid_cell_btn(
                        _format_bg_badge(proj_bg.min_remaining), color)
                    badge_btn.setTag_(tag)
                    badge_btn.setTarget_(app._panel_controller)
                    badge_btn.setAction_(b'focusSession:')
                    views = [slot_btn, star_btn, name_btn, dot_btn, badge_btn]
                else:
                    badge_btn = None
                    views     = [slot_btn, star_btn, name_btn, dot_btn, empty]
                grid.addRowWithViews_(views)
                grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
                row_idx += 1
                app._displayed_items[s.name] = (dot_btn, badge_btn)
            else:
                name_btn = _make_grid_cell_btn(s.name)
                dot_btn  = _make_grid_cell_btn(dot)
                grid.addRowWithViews_([empty, empty, name_btn, dot_btn, empty])
                grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
                row_idx += 1
                app._displayed_items[s.name] = (dot_btn, None)
    app._panel_sv.addView_inGravity_(grid, 1)
    grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)

# In-place dot + badge update while NSPanel is open; preserves grid layout.
# Only dot (col 3) and badge (col 4, sessions with active bg timer) change per-tick.
# Slot (col 0), star (col 1), name (col 2) are static between rebuilds.
def _update_panel_inplace(app, sessions, bg_by_project) -> None:
    session_map = {s.name: s for s in sessions}
    for name, (dot_btn, badge_btn) in app._displayed_items.items():
        s = session_map.get(name)
        if s is None:
            continue
        proj_bg = (bg_by_project or {}).get(s.project_name)
        dot     = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        attrs   = {NSFontAttributeName: _MENLO()}
        if not s.is_worker:
            attrs[NSForegroundColorAttributeName] = NSColor.systemOrangeColor()
        dot_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(dot, attrs))
        if badge_btn is not None and proj_bg is not None:
            badge_btn.setAttributedTitle_(
                NSAttributedString.alloc().initWithString_attributes_(
                    _format_bg_badge(proj_bg.min_remaining),
                    {NSFontAttributeName: _MENLO(),
                     NSForegroundColorAttributeName: NSColor.systemOrangeColor()}))
