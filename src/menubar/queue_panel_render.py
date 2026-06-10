# INFRASTRUCTURE
from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCellPlacementFill,
                    NSGridView, NSTextField, NSView)
from Foundation import NSMakeRect

from .panel import (_TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _CursorlessLabel,
                    _make_line_separator, _make_header_label)

_QUEUE_TOGGLE_W = 22   # pts — ↑/↓ toggle button width
_QUEUE_MINUS_W  = 22   # pts — × delete button width

# FUNCTIONS

# Rebuild queue panel: clear state, set toggle title, size panel, build session grid
def _rebuild_inner(controller, sessions) -> None:
    app = controller.app
    for sv in list(controller._queue_sv.arrangedSubviews()):
        controller._queue_sv.removeView_(sv)
        sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists without this
    controller._queue_add_tags.clear()
    controller._queue_remove_tags.clear()
    controller._pending_queue_tags.clear()
    controller._pending_queue_views.clear()
    controller._queue_toggle_tags.clear()
    state = 'ON' if app._auto_focus else 'OFF'
    controller._queue_toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'Sessions · RAG · [Queue]     Auto-Jump: {state}',
            {NSFontAttributeName: _MENLO()}))
    main_sessions = sorted(
        [s for s in sessions if not s.is_worker],
        key=lambda s: (s.project_name, s.name))
    pw         = app._panel_width
    required_h = _compute_height(controller, sessions)
    _resize_panel(controller, max(app._panel_min_height, required_h))
    controller._queue_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if not main_sessions:
        controller._queue_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
        controller._queue_displayed_names = set()
        return
    row_h  = _ROW_H - 1
    col0_w = pw - _QUEUE_TOGGLE_W - _QUEUE_MINUS_W
    grid, first_draft_tf = _build_session_grid(
        controller, main_sessions, pw, col0_w, row_h, app._panel_controller)
    controller._queue_sv.addView_inGravity_(grid, 1)
    grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
    controller._queue_displayed_names = {s.name for s in main_sessions}
    if first_draft_tf is not None:
        controller._queue_panel.makeKeyAndOrderFront_(None)
        controller._queue_panel.makeFirstResponder_(first_draft_tf)

# Compute required height: top-bar + separator + per-session header + entry rows + add-btn row
def _compute_height(controller, sessions) -> int:
    h = _TOP_BAR_H + _LABEL_H
    main_sessions = [s for s in sessions if not s.is_worker]
    if not main_sessions:
        return h + _LABEL_H
    for s in main_sessions:
        h += _LABEL_H                                               # project › session header
        msgs = controller._queue_data.get(s.session_id, [])
        h += len(msgs) * (_ROW_H - 1)                              # one row per entry
        h += (_ROW_H - 1)                                          # + button row
    return h

# Resize queue NSPanel anchored at top edge
def _resize_panel(controller, new_h: float) -> None:
    w     = controller.app._panel_width
    frame = controller._queue_panel.frame()
    top_y = frame.origin.y + frame.size.height
    controller._queue_panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# ONE NSGridView (1 col): all rows are full-width container NSViews; returns (grid, first_draft_tf)
def _build_session_grid(controller, main_sessions, pw, col0_w, row_h, panel_controller):
    grid = NSGridView.gridViewWithNumberOfColumns_rows_(1, 0)
    grid.setColumnSpacing_(0.0)
    grid.setRowSpacing_(1.0)
    grid.columnAtIndex_(0).setXPlacement_(NSGridCellPlacementFill)
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    row_idx        = 0
    q_add_tag      = [2000]
    q_rmv_tag      = [3000]
    q_tf_tag       = [4000]
    q_tog_tag      = [5000]
    first_draft_tf = None
    for s in main_sessions:
        # Project › session header row (full-width label)
        hdr = _make_header_label(f'{s.project_name} › {s.name}', pw)
        grid.addRowWithViews_([hdr])
        grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
        row_idx += 1
        msgs = controller._queue_data.get(s.session_id, [])
        for i, entry in enumerate(msgs):
            container, draft_tf = _build_entry_row_view(
                controller, s, i, entry, pw, row_h, col0_w,
                panel_controller, q_tf_tag, q_tog_tag, q_rmv_tag)
            if draft_tf is not None and first_draft_tf is None:
                first_draft_tf = draft_tf
            grid.addRowWithViews_([container])
            grid.rowAtIndex_(row_idx).setHeight_(float(row_h))
            row_idx += 1
        # + add-new-draft button row
        add_tag = q_add_tag[0]; q_add_tag[0] += 1
        add_btn = _make_queue_add_btn(pw)
        add_btn.setTag_(add_tag)
        add_btn.setTarget_(panel_controller)
        add_btn.setAction_(b'addQueueRow:')
        controller._queue_add_tags[add_tag] = s.session_id
        grid.addRowWithViews_([add_btn])
        grid.rowAtIndex_(row_idx).setHeight_(float(row_h))
        row_idx += 1
    return grid, first_draft_tf

# + add button spanning full row width; caller wires tag/target/action
def _make_queue_add_btn(grid_w: int):
    btn = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, grid_w, _ROW_H - 1))
    btn.setBordered_(False)
    btn.setButtonType_(7)
    btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '  +', {NSFontAttributeName: _MENLO(),
                    NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    btn.heightAnchor().constraintEqualToConstant_(float(_ROW_H - 1)).setActive_(True)   # NSGridView turns off TAMIC
    return btn

# Build container NSView for one queue entry row; returns (container, draft_tf | None)
def _build_entry_row_view(controller, s, i, entry, pw, row_h, col0_w,
                           panel_controller, q_tf_tag, q_tog_tag, q_rmv_tag):
    entry_state = entry.get("state", "queued")
    text        = entry.get("text", "")
    # Container NSView with per-state background layer tint
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, row_h))
    container.setWantsLayer_(True)
    if entry_state == "queued":
        container.layer().setBackgroundColor_(
            NSColor.systemRedColor().colorWithAlphaComponent_(0.18).CGColor())
    elif entry_state == "sent":
        container.layer().setBackgroundColor_(
            NSColor.systemGreenColor().colorWithAlphaComponent_(0.18).CGColor())
    # NSGridView turns off TAMIC on direct content views → explicit size constraints
    container.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
    container.heightAnchor().constraintEqualToConstant_(float(row_h)).setActive_(True)
    draft_tf = None
    # Col 0: editable NSTextField (draft) or read-only label (queued/sent)
    if entry_state == "draft":
        tf_tag = q_tf_tag[0]; q_tf_tag[0] += 1
        tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, col0_w, row_h))
        tf.setFont_(_MENLO())
        tf.setEditable_(True)
        tf.setSelectable_(True)
        tf.setBezeled_(True)
        tf.setDrawsBackground_(True)
        tf.setTag_(tf_tag)
        tf.setStringValue_(text)
        tf.setPlaceholderString_('message…')
        tf.setTarget_(panel_controller)
        tf.setAction_(b'commitQueueField:')
        tf.setDelegate_(panel_controller)
        controller._pending_queue_tags[tf_tag] = (s.session_id, i)
        controller._pending_queue_views[(s.session_id, i)] = tf
        container.addSubview_(tf)
        draft_tf = tf
    else:
        lbl = _CursorlessLabel.labelWithString_('')
        lbl.setFrame_(NSMakeRect(0, 0, col0_w, row_h))
        lbl.cell().setLineBreakMode_(4)   # NSLineBreakByTruncatingTail
        lbl.setAttributedStringValue_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  [{i + 1}] {text}',
                {NSFontAttributeName: _MENLO(),
                 NSForegroundColorAttributeName: NSColor.labelColor()}))
        container.addSubview_(lbl)
    # Col 1: toggle button (↑ draft→queued, ↓ queued→draft); sent has no toggle
    if entry_state in ("draft", "queued"):
        tog_tag = q_tog_tag[0]; q_tog_tag[0] += 1
        toggle = _CursorlessButton.alloc().initWithFrame_(
            NSMakeRect(col0_w, 0, _QUEUE_TOGGLE_W, row_h))
        toggle.setBordered_(False)
        toggle.setButtonType_(7)
        symbol = '↑' if entry_state == 'draft' else '↓'   # ↑ or ↓
        toggle.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                symbol, {NSFontAttributeName: _MENLO(),
                         NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
        toggle.setTag_(tog_tag)
        toggle.setTarget_(panel_controller)
        toggle.setAction_(b'toggleQueueEntry:')
        controller._queue_toggle_tags[tog_tag] = (s.session_id, i)
        container.addSubview_(toggle)
    # Col 2: × delete button (always present for all states)
    rmv_tag = q_rmv_tag[0]; q_rmv_tag[0] += 1
    minus = _CursorlessButton.alloc().initWithFrame_(
        NSMakeRect(col0_w + _QUEUE_TOGGLE_W, 0, _QUEUE_MINUS_W, row_h))
    minus.setBordered_(False)
    minus.setButtonType_(7)
    minus.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '×', {NSFontAttributeName: _MENLO(),   # ×
                       NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    minus.setTag_(rmv_tag)
    minus.setTarget_(panel_controller)
    minus.setAction_(b'removeQueueEntry:')
    controller._queue_remove_tags[rmv_tag] = (s.session_id, i)
    container.addSubview_(minus)
    return container, draft_tf
