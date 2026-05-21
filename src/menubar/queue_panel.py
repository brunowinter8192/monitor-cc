# INFRASTRUCTURE
from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCell, NSGridCellPlacementFill,
                    NSGridCellPlacementLeading, NSGridView, NSLayoutAttributeLeading,
                    NSPanel, NSStackView, NSTextField, NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize, NSRange

from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _CursorlessLabel,
                    _make_line_separator, _make_header_label,
                    _GRID_COL_SPC)
from .queue import load_queue, save_queue

_QUEUE_MINUS_W = 18   # pts — col 1 fixed width: − remove button

# FUNCTIONS

# Build NSPanel for queue panel; returns (panel, stack, toggle_btn) — same structure as _make_bead_nspanel
def _make_queue_nspanel():
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
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

# Position queue panel flush below the NSStatusItem button (same logic as _reposition_bead_panel)
def _reposition_queue_panel(panel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    if btn_win is None:
        return
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = btn_win.frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

# Compute required height for the queue panel: top-bar + separator + per-main-session rows
def _compute_queue_height(app, sessions) -> int:
    h = _TOP_BAR_H + _LABEL_H   # top-bar + line separator
    main_sessions = [s for s in sessions if not s.is_worker]
    if not main_sessions:
        return h + _LABEL_H     # "No active sessions" label
    for s in main_sessions:
        h += _LABEL_H           # project › session header label
        msgs = app._queue_data.get(s.session_id, [])
        h += len(msgs) * (_ROW_H - 1)   # message rows
        h += _ROW_H - 1                 # add-btn or input field row
    return h

# Resize queue NSPanel anchored at top edge (same logic as _resize_tracker_panel)
def _resize_queue_panel(app, new_h: float) -> None:
    w     = app._panel_width
    frame = app._queue_panel.frame()
    top_y = frame.origin.y + frame.size.height
    app._queue_panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# NSTextField label for col 0 of a message row ("  [N] msg", truncated at tail)
def _make_queue_msg_label(msg: str, idx: int, col0_w: int) -> NSTextField:
    label = _CursorlessLabel.labelWithString_('')
    label.setFrame_(NSMakeRect(0, 0, col0_w, _ROW_H - 1))
    label.cell().setLineBreakMode_(4)   # NSLineBreakByTruncatingTail
    label.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'  [{idx}] {msg}', {NSFontAttributeName: _MENLO()}))
    return label

# − remove button for col 1 of a message row; caller wires tag/target/action
def _make_queue_minus_btn():
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, _QUEUE_MINUS_W, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '−', {NSFontAttributeName: _MENLO(),
                  NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    return btn

# + add button spanning full merged row (cols 0+1); caller wires tag/target/action
def _make_queue_add_btn(grid_w: int):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, grid_w, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '  +', {NSFontAttributeName: _MENLO(),
                    NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    return btn

# Editable NSTextField for inline queue message input (merged row); caller wires tag/target/delegate
def _make_queue_input_field(grid_w: int, tag: int):
    row_h = _ROW_H - 1
    tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, grid_w, row_h))
    tf.setFont_(_MENLO())
    tf.setEditable_(True)
    tf.setSelectable_(True)
    tf.setBezeled_(True)
    tf.setDrawsBackground_(True)
    tf.setTag_(tag)
    tf.setPlaceholderString_('message…')
    tf.heightAnchor().constraintEqualToConstant_(float(row_h)).setActive_(True)   # explicit height — NSGridView turns off TAMIC; bezeled NSTextField intrinsicContentSize may exceed row height
    return tf

# Full rebuild of queue panel from app._queue_data + sessions; resets tag maps.
# ONE NSGridView (2 cols): col 0 = message label (fill, for truncation) OR merged content;
# col 1 = − button (18pt fixed). Session headers, add-btn, and input rows are merged across both cols.
# NSWindowStyleMaskNonactivatingPanel prevents app activation but allows makeKeyAndOrderFront_
# to give the panel keyboard focus for NSTextField input without stealing app activation.
def _rebuild_queue_panel(app, sessions) -> None:
    for sv in list(app._queue_sv.arrangedSubviews()):
        app._queue_sv.removeView_(sv)
    app._queue_add_tags.clear()
    app._queue_remove_tags.clear()
    app._pending_queue_tags.clear()
    state = 'ON' if app._auto_focus else 'OFF'
    app._queue_toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'Sessions \u00b7 Beads \u00b7 [Queue]     Auto-Jump: {state}',
            {NSFontAttributeName: _MENLO()}))
    main_sessions = sorted(
        [s for s in sessions if not s.is_worker],
        key=lambda s: (s.project_name, s.name))
    pw         = app._panel_width
    required_h = _compute_queue_height(app, sessions)
    _resize_queue_panel(app, max(app._panel_min_height, required_h))
    app._queue_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if not main_sessions:
        app._queue_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        app._queue_displayed_names = set()
        return
    empty     = NSGridCell.emptyContentView()
    grid      = NSGridView.gridViewWithNumberOfColumns_rows_(2, 0)
    grid.setColumnSpacing_(float(_GRID_COL_SPC))
    grid.setRowSpacing_(1.0)
    grid.columnAtIndex_(0).setXPlacement_(NSGridCellPlacementFill)      # fill for label truncation
    grid.columnAtIndex_(1).setXPlacement_(NSGridCellPlacementLeading)
    grid.columnAtIndex_(1).setWidth_(float(_QUEUE_MINUS_W))
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    row_idx    = 0
    q_add_tag  = [2000]
    q_rmv_tag  = [3000]
    q_tf_tag   = [4000]
    pending_tf = None
    col0_w     = pw - _QUEUE_MINUS_W - _GRID_COL_SPC
    for s in main_sessions:
        session_label = f'{s.project_name} \u203a {s.name}'
        hdr = _make_header_label(session_label, pw)
        grid.addRowWithViews_([hdr, empty])
        grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
        grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 2), NSRange(row_idx, 1))
        row_idx += 1
        msgs = app._queue_data.get(s.session_id, [])
        for i, msg in enumerate(msgs):
            lbl   = _make_queue_msg_label(msg, i + 1, col0_w)
            minus = _make_queue_minus_btn()
            rmv_tag = q_rmv_tag[0]; q_rmv_tag[0] += 1
            minus.setTag_(rmv_tag)
            minus.setTarget_(app._panel_controller)
            minus.setAction_(b'removeQueueMsg:')
            app._queue_remove_tags[rmv_tag] = (s.session_id, i)
            grid.addRowWithViews_([lbl, minus])
            grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
            row_idx += 1
        is_pending = s.session_id in app._pending_queue_sessions
        if is_pending:
            tf_tag = q_tf_tag[0]; q_tf_tag[0] += 1
            tf = _make_queue_input_field(pw, tf_tag)
            tf.setTarget_(app._panel_controller)
            tf.setAction_(b'commitQueueField:')
            tf.setDelegate_(app._panel_controller)
            app._pending_queue_tags[tf_tag] = s.session_id
            grid.addRowWithViews_([tf, empty])
            grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
            grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 2), NSRange(row_idx, 1))
            row_idx += 1
            pending_tf = tf
        else:
            add_tag = q_add_tag[0]; q_add_tag[0] += 1
            add_btn = _make_queue_add_btn(pw)
            add_btn.setTag_(add_tag)
            add_btn.setTarget_(app._panel_controller)
            add_btn.setAction_(b'addQueueRow:')
            app._queue_add_tags[add_tag] = s.session_id
            grid.addRowWithViews_([add_btn, empty])
            grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
            grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 2), NSRange(row_idx, 1))
            row_idx += 1
    app._queue_sv.addView_inGravity_(grid, 1)
    grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
    app._queue_displayed_names = {s.name for s in main_sessions}
    if pending_tf is not None:
        app._queue_panel.makeKeyAndOrderFront_(None)
        app._queue_panel.makeFirstResponder_(pending_tf)
