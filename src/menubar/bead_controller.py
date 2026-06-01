# INFRASTRUCTURE
from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCell, NSGridCellPlacementLeading,
                    NSGridView, NSLayoutAttributeLeading,
                    NSPanel, NSScrollView, NSStackView, NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize, NSRange

# From bead_data.py: bd subprocess wrappers + session-db discovery
from .bead_data import bd_show_text, bd_label_remove, project_db_map, load_tracked_beads
# From panel.py: UI constants, factories, helpers shared across panels
from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _CursorlessLabel, _KeyablePanel,
                    _make_line_separator, _make_header_label,
                    _GRID_COL_SPC)

_STATUS_W              = 22   # pts — col 1 width: ? status-query button
_UNTRACK_W             = 22   # pts — col 2 width: × untrack button
_BEAD_EXPAND_MAX_LINES = 20   # max visible lines in expand view; content beyond scrolls

# FUNCTIONS

# Build NSPanel for bead tracker; returns (panel, stack, toggle_btn)
# toggle_btn: top-bar button wired to toggleAutoJump: — same style as main panel's toggle_btn
def _make_bead_nspanel():
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
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable | NSViewMinYMargin — stays at top edge
    toggle_btn = _CursorlessButton.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    toggle_btn.setAutoresizingMask_(2)   # NSViewWidthSizable
    top_bar.addSubview_(toggle_btn)
    cv.addSubview_(top_bar)
    stack_h = PANEL_HEIGHT - _TOP_BAR_H
    stack = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, PANEL_WIDTH, stack_h))
    stack.setAutoresizingMask_(18)   # NSViewWidthSizable | NSViewHeightSizable
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setAlignment_(NSLayoutAttributeLeading)
    stack.setSpacing_(1.0)
    stack.setDistribution_(-1)   # NSStackViewDistributionGravityAreas
    cv.addSubview_(stack)
    return panel, stack, toggle_btn

# Position bead tracker panel flush below the NSStatusItem button (same logic as main panel)
def _reposition_bead_panel(panel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    if btn_win is None:
        return
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = btn_win.frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

# Compute wrapped pixel height for a bead row expand button in Menlo 13pt at btn_w pixels wide.
# Uses NSAttributedString.boundingRectWithSize_options_context_ (option 1 =
# NSStringDrawingUsesLineFragmentOrigin) for accurate multi-line measurement.
def _bead_row_height(row_text: str, btn_w: int) -> int:
    astr = NSAttributedString.alloc().initWithString_attributes_(
        row_text, {NSFontAttributeName: _MENLO()})
    bounds = astr.boundingRectWithSize_options_context_(
        NSMakeSize(float(btn_w), 10000.0), 1, None)
    return max(_ROW_H - 1, int(bounds.size.height) + 4)

# Wrapping expand NSButton for col 0 of the bead grid row.
# Text prefix "  " (2 spaces ≈ 16pt) provides visual indent under project header.
# Returns (btn, row_h) — caller sets tag/target/action; row_h used for NSGridRow.setHeight_.
def _make_bead_expand_btn(bead: dict, panel_width: int, is_expanded: bool):
    pw       = panel_width - 22
    btn_w    = pw - _STATUS_W - _UNTRACK_W - 2 * _GRID_COL_SPC
    bead_id  = bead.get('id', '')
    title    = bead.get('title', '')
    indicator = '▾' if is_expanded else '▸'
    row_text  = f'  {indicator} {bead_id}  {title}'   # 2 leading spaces ≈ 16pt indent
    row_h     = _bead_row_height(row_text, btn_w)
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, btn_w, row_h))
    btn.setBordered_(False)
    btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    btn.cell().setWraps_(True)
    btn.cell().setLineBreakMode_(0)   # NSLineBreakByWordWrapping
    btn.cell().setAlignment_(0)       # NSTextAlignmentLeft — prevent default centering
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            row_text, {NSFontAttributeName: _MENLO(),
                       NSForegroundColorAttributeName: NSColor.systemBlueColor()}))
    return btn, row_h

# ? status-query button for col 1 of the bead grid row; caller sets tag/target/action
def _make_bead_status_btn():
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, _STATUS_W, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '?', {NSFontAttributeName: _MENLO(),
                  NSForegroundColorAttributeName: NSColor.systemBlueColor()}))
    return btn

# × untrack button for col 2 of the bead grid row; caller sets tag/target/action
def _make_bead_x_btn() -> NSView:
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, _UNTRACK_W, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '×', {NSFontAttributeName: _MENLO(),
                  NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    return btn

# NSView container with per-line NSTextFields for a bead expand block (col 0, merged with col 1).
# heightAnchor + widthAnchor required — NSGridView disables TAMIC on content views; without
# explicit constraints height=0 → bleed, and width=0 → container doesn't fill merged cell.
# w = panel_width (full merged-cell width); inner_w = w - 16 (16pt left indent).
# When total > _BEAD_EXPAND_MAX_LINES * _ROW_H, returns NSScrollView wrapper at fixed max_h;
# container.widthAnchor is anchored to scrollView.contentView so text wraps to sv width.
def _make_expand_view(text: str, panel_width: int):
    w       = panel_width         # merged cell spans full grid width
    inner_x = 16                  # inset to visually nest under bead row
    inner_w = w - inner_x
    lines        = text.split('\n')
    line_heights = [_bead_row_height(line or ' ', inner_w) for line in lines]
    total        = sum(line_heights)
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, total))
    container.heightAnchor().constraintEqualToConstant_(float(total)).setActive_(True)   # explicit height — NSGridView disables TAMIC on content views; without this height=0 → subviews bleed into row above
    y = total   # NSView y=0 is bottom; subtract each lh before placing
    for line, lh in zip(lines, line_heights):
        y -= lh
        tf = _CursorlessLabel.labelWithString_('')
        tf.setFrame_(NSMakeRect(inner_x, y, inner_w, lh))
        tf.cell().setWraps_(True)
        tf.cell().setLineBreakMode_(0)   # NSLineBreakByWordWrapping
        tf.setUsesSingleLineMode_(False)
        tf.setAttributedStringValue_(
            NSAttributedString.alloc().initWithString_attributes_(
                line or ' ', {NSFontAttributeName: _MENLO(),
                              NSForegroundColorAttributeName: NSColor.secondaryLabelColor()}))
        container.addSubview_(tf)
    max_h = float(_BEAD_EXPAND_MAX_LINES * _ROW_H)
    if total > max_h:
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, w, max_h))
        sv.setHasVerticalScroller_(True)
        sv.setHasHorizontalScroller_(False)
        sv.setAutohidesScrollers_(False)
        sv.setDocumentView_(container)
        # anchor container width to sv contentView so text wraps at sv interior width
        container.widthAnchor().constraintEqualToAnchor_(sv.contentView().widthAnchor()).setActive_(True)
        sv.heightAnchor().constraintEqualToConstant_(max_h).setActive_(True)
        sv.widthAnchor().constraintEqualToConstant_(float(w)).setActive_(True)
        return sv, int(max_h)
    container.widthAnchor().constraintEqualToConstant_(float(w)).setActive_(True)
    return container, total

# Resize tracker NSPanel anchored at top edge; accesses app._panel_width + app._tracker_panel (both stay on app)
def _resize_tracker_panel(app, new_h: float) -> None:
    w     = app._panel_width
    frame = app._tracker_panel.frame()
    top_y = frame.origin.y + frame.size.height
    app._tracker_panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Per-concern controller for bead tracker: state ownership, tick refresh, panel render, action dispatch
class BeadController:
    def __init__(self, app) -> None:
        self.app = app
        self._bead_data: dict         = {}
        self._bead_db_paths: dict     = {}
        self._bead_expanded: dict     = {}
        self._bead_displayed: dict    = {}
        self._bead_expand_tags: dict  = {}
        self._bead_untrack_tags: dict = {}
        self._bead_query_tags: dict   = {}
        self._bead_tick_counter: int  = 4   # starts at 4 → first tick fires refresh
        self._rebuild_in_progress: bool = False

    # Called from CCMenuBarApp._tick; owns counter + condition + refresh
    def tick(self, sessions) -> None:
        self._bead_tick_counter += 1
        if self._bead_tick_counter % 5 == 0 or self.app._tracker_open:
            self._do_refresh(sessions)

    # Fetch fresh bead data from sessions; rebuild tracker panel on change if open
    def _do_refresh(self, sessions) -> None:
        pdb      = project_db_map(sessions)
        new_data = load_tracked_beads(pdb)
        changed  = new_data != self._bead_data
        self._bead_db_paths, self._bead_data = pdb, new_data
        if changed and self.app._tracker_open:
            self.rebuild()

    # Compute required pixel height for the tracker panel (mirrors _rebuild_inner row heights)
    def compute_height(self) -> int:
        h = _TOP_BAR_H + _LABEL_H   # top-bar + line separator
        if not any(self._bead_data.values()):
            return h + _LABEL_H      # "No tracked beads" label
        pw    = self.app._panel_width - 22
        btn_w = pw - _STATUS_W - _UNTRACK_W - 2 * _GRID_COL_SPC
        for project_name, beads in self._bead_data.items():
            if not beads:
                continue
            h += _LABEL_H            # project header row
            for bead in beads:
                bead_id     = bead.get('id', '')
                title       = bead.get('title', '')
                is_expanded = bead_id in self._bead_expanded
                indicator   = '▾' if is_expanded else '▸'
                row_text    = f'  {indicator} {bead_id}  {title}'   # 2-space indent prefix
                h += _bead_row_height(row_text, btn_w) + 1          # +1 for rowSpacing
                if bead_id in self._bead_expanded:
                    expand_inner_w = self.app._panel_width - 16   # mirrors _make_expand_view: w=panel_width, inner_w=w-16
                    raw_exp_h = sum(_bead_row_height(line or ' ', expand_inner_w)
                                    for line in self._bead_expanded[bead_id].split('\n'))
                    h += min(raw_exp_h, _BEAD_EXPAND_MAX_LINES * _ROW_H) + 1   # capped by scrollview
        return h

    # Full rebuild of tracker panel from self._bead_data + _bead_expanded; re-entry guard
    def rebuild(self) -> None:
        if self._rebuild_in_progress:
            return
        self._rebuild_in_progress = True
        try:
            self._rebuild_inner()
        finally:
            self._rebuild_in_progress = False

    # ONE NSGridView (3 cols): col 0 expand button, col 1 ? status, col 2 × untrack; resets tag maps
    def _rebuild_inner(self) -> None:
        app = self.app
        for sv in list(app._tracker_sv.arrangedSubviews()):
            app._tracker_sv.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists as regular subview without this
        self._bead_displayed.clear()
        self._bead_expand_tags.clear()
        self._bead_untrack_tags.clear()
        self._bead_query_tags.clear()
        state = 'ON' if app._auto_focus else 'OFF'
        app._tracker_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 RAG \u00b7 [Beads] \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        pw         = app._panel_width
        required_h = self.compute_height()
        _resize_tracker_panel(app, max(app._panel_min_height, required_h))
        app._tracker_sv.addView_inGravity_(_make_line_separator(pw), 1)
        if not any(self._bead_data.values()):
            app._tracker_sv.addView_inGravity_(_make_header_label('No tracked beads', pw), 1)
            return
        empty = NSGridCell.emptyContentView()
        grid  = NSGridView.gridViewWithNumberOfColumns_rows_(3, 0)
        grid.setColumnSpacing_(float(_GRID_COL_SPC))
        grid.setRowSpacing_(1.0)
        for i in range(3):
            grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)
        grid.columnAtIndex_(1).setWidth_(float(_STATUS_W))    # col 1 fixed: ? status button
        grid.columnAtIndex_(2).setWidth_(float(_UNTRACK_W))   # col 2 fixed: × untrack button
        grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
        row_idx = 0
        exp_tag = 100
        utr_tag = 200
        qry_tag = 300
        for project_name, beads in self._bead_data.items():
            if not beads:
                continue
            hdr = _make_header_label(project_name, pw)
            grid.addRowWithViews_([hdr, empty, empty])
            grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
            grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 3), NSRange(row_idx, 1))
            row_idx += 1
            for bead in beads:
                bead_id     = bead.get('id', '')
                is_expanded = bead_id in self._bead_expanded
                expand_btn, row_h = _make_bead_expand_btn(bead, pw, is_expanded)
                expand_btn.setTag_(exp_tag)
                expand_btn.setTarget_(app._panel_controller)
                expand_btn.setAction_(b'expandBead:')
                status_btn = _make_bead_status_btn()
                status_btn.setTag_(qry_tag)
                status_btn.setTarget_(app._panel_controller)
                status_btn.setAction_(b'queryBeadStatus:')
                x_btn = _make_bead_x_btn()
                x_btn.setTag_(utr_tag)
                x_btn.setTarget_(app._panel_controller)
                x_btn.setAction_(b'untrackBead:')
                grid.addRowWithViews_([expand_btn, status_btn, x_btn])
                grid.rowAtIndex_(row_idx).setHeight_(float(row_h))
                row_idx += 1
                self._bead_expand_tags[exp_tag]  = bead_id
                self._bead_untrack_tags[utr_tag] = (bead_id, project_name)
                self._bead_query_tags[qry_tag]   = (bead_id, project_name)
                self._bead_displayed[bead_id]    = expand_btn
                exp_tag += 1
                utr_tag += 1
                qry_tag += 1
                if is_expanded:
                    exp_view, exp_h = _make_expand_view(self._bead_expanded[bead_id], pw)
                    grid.addRowWithViews_([exp_view, empty, empty])
                    grid.rowAtIndex_(row_idx).setHeight_(float(exp_h))
                    grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 3), NSRange(row_idx, 1))
                    row_idx += 1
        app._tracker_sv.addView_inGravity_(grid, 1)
        grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)

    # Handle expand/collapse click from expandBead_ action handler
    def handle_expand(self, tag: int) -> None:
        bead_id = self._bead_expand_tags.get(tag)
        if not bead_id:
            return
        if bead_id in self._bead_expanded:
            del self._bead_expanded[bead_id]
        else:
            project_name = next(
                (pn for pn, beads in self._bead_data.items()
                 if any(b.get('id') == bead_id for b in (beads or []))), None)
            db_path = self._bead_db_paths.get(project_name) if project_name else None
            if db_path:
                self._bead_expanded[bead_id] = bd_show_text(bead_id, db_path)
        self.rebuild()

    # Handle untrack click from untrackBead_ action handler
    def handle_untrack(self, tag: int) -> None:
        info = self._bead_untrack_tags.get(tag)
        if not info:
            return
        bead_id, project_name = info
        db_path = self._bead_db_paths.get(project_name)
        if db_path:
            bd_label_remove(bead_id, db_path)
        self._bead_expanded.pop(bead_id, None)
        self._bead_data[project_name] = [
            b for b in self._bead_data.get(project_name, []) if b.get('id') != bead_id]
        self.rebuild()
