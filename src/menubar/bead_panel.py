# INFRASTRUCTURE
from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSLayoutAttributeLeading,
                    NSPanel, NSStackView, NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

from .bead_data import bd_show_text, bd_label_remove
from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _CursorlessLabel,
                    _make_line_separator, _make_header_label)

_UNTRACK_W     = 22   # pts — width of × untrack button at right edge of each row

# FUNCTIONS

# Build NSPanel for bead tracker; returns (panel, stack, toggle_btn)
# toggle_btn: top-bar button wired to toggleAutoJump: — same style as main panel's toggle_btn
def _make_bead_nspanel():
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

# NSView row container: expand button (most width) + × untrack button (right edge)
# Returns (container, expand_btn, x_btn) — caller sets tag + wires target/action
def _make_bead_row(bead: dict, panel_width: int, is_expanded: bool):
    pw        = panel_width - 22
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, _ROW_H - 1))
    container.heightAnchor().constraintEqualToConstant_(float(_ROW_H - 1)).setActive_(True)
    bead_id = bead.get('id', '')
    title   = bead.get('title', '')
    btn_w   = pw - _UNTRACK_W - 4
    # Approximate title chars that fit; Menlo ~7px/char
    max_ch      = max(0, (btn_w - len(bead_id) * 7 - 24) // 7)
    short_title = title if len(title) <= max_ch else title[:max_ch - 1] + '…'
    indicator   = '▾' if is_expanded else '▸'
    row_text    = f'{indicator} {bead_id}  {short_title}'
    expand_btn  = _CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, btn_w, _ROW_H - 1))
    expand_btn.setBordered_(False)
    expand_btn.setButtonType_(7)   # NSButtonTypeMomentaryPushIn
    expand_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            row_text, {NSFontAttributeName: _MENLO(),
                       NSForegroundColorAttributeName: NSColor.systemBlueColor()}))
    container.addSubview_(expand_btn)
    x_btn = _CursorlessButton.alloc().initWithFrame_(
        NSMakeRect(pw - _UNTRACK_W, 0, _UNTRACK_W, _ROW_H - 1))
    x_btn.setBordered_(False)
    x_btn.setButtonType_(7)
    x_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            '×', {NSFontAttributeName: _MENLO(),
                  NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
    container.addSubview_(x_btn)
    return container, expand_btn, x_btn

# NSView container with one NSTextField per expand-text line; indented under bead row
def _make_expand_view(text: str, panel_width: int) -> NSView:
    w       = panel_width - 22          # matches standard stack item width
    inner_x = 16                        # inset to visually nest under bead row
    inner_w = w - inner_x
    lines   = text.split('\n')
    row_h   = _ROW_H - 1
    total   = len(lines) * row_h
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, total))
    container.heightAnchor().constraintEqualToConstant_(float(total)).setActive_(True)
    y = total - row_h   # first line at top (NSView y=0 is bottom)
    for line in lines:
        tf = _CursorlessLabel.labelWithString_('')
        tf.setFrame_(NSMakeRect(inner_x, y, inner_w, row_h))
        tf.setAttributedStringValue_(
            NSAttributedString.alloc().initWithString_attributes_(
                line or ' ', {NSFontAttributeName: _MENLO(),
                              NSForegroundColorAttributeName: NSColor.secondaryLabelColor()}))
        container.addSubview_(tf)
        y -= row_h
    return container

# Compute required height for the bead tracker panel
def _compute_bead_height(app) -> int:
    h = _TOP_BAR_H + _LABEL_H   # top-bar + line separator
    if not any(app._bead_data.values()):
        return h + _LABEL_H      # "No tracked beads" label
    for project_name, beads in app._bead_data.items():
        if not beads:
            continue
        h += _LABEL_H            # project header label
        for bead in beads:
            h += _ROW_H          # bead row
            bead_id = bead.get('id', '')
            if bead_id in app._bead_expanded:
                h += len(app._bead_expanded[bead_id].split('\n')) * (_ROW_H - 1)
    return h

# Resize tracker NSPanel anchored at top edge (same logic as _resize_panel for main panel)
def _resize_tracker_panel(app, new_h: float) -> None:
    w     = app._panel_width
    frame = app._tracker_panel.frame()
    top_y = frame.origin.y + frame.size.height
    app._tracker_panel.setFrame_display_(
        NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

# Full rebuild of tracker panel from app._bead_data + _bead_expanded; resets tag maps
def _rebuild_bead_panel(app) -> None:
    for sv in list(app._tracker_sv.arrangedSubviews()):
        app._tracker_sv.removeView_(sv)
    app._bead_displayed.clear()
    app._bead_expand_tags.clear()
    app._bead_untrack_tags.clear()
    state = 'ON' if app._auto_focus else 'OFF'
    app._tracker_toggle_btn.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(
            f'Sessions \u00b7 [Beads]     Auto-Jump: {state}', {NSFontAttributeName: _MENLO()}))
    pw         = app._panel_width
    required_h = _compute_bead_height(app)
    _resize_tracker_panel(app, max(app._panel_min_height, required_h))
    app._tracker_sv.addView_inGravity_(_make_line_separator(pw), 1)
    if not any(app._bead_data.values()):
        app._tracker_sv.addView_inGravity_(_make_header_label('No tracked beads', pw), 1)
        return
    exp_tag = 100
    utr_tag = 200
    for project_name, beads in app._bead_data.items():
        if not beads:
            continue
        app._tracker_sv.addView_inGravity_(_make_header_label(project_name, pw), 1)
        for bead in beads:
            bead_id    = bead.get('id', '')
            is_expanded = bead_id in app._bead_expanded
            row, expand_btn, x_btn = _make_bead_row(bead, pw, is_expanded)
            expand_btn.setTag_(exp_tag)
            expand_btn.setTarget_(app._panel_controller)
            expand_btn.setAction_(b'expandBead:')
            x_btn.setTag_(utr_tag)
            x_btn.setTarget_(app._panel_controller)
            x_btn.setAction_(b'untrackBead:')
            app._bead_expand_tags[exp_tag]  = bead_id
            app._bead_untrack_tags[utr_tag] = (bead_id, project_name)
            app._bead_displayed[bead_id]    = expand_btn
            app._tracker_sv.addView_inGravity_(row, 1)
            exp_tag += 1
            utr_tag += 1
            if is_expanded:
                app._tracker_sv.addView_inGravity_(
                    _make_expand_view(app._bead_expanded[bead_id], pw), 1)

# Handle expand/collapse click from expandBead_ controller method
def _handle_expand_bead(app, tag: int) -> None:
    bead_id = app._bead_expand_tags.get(tag)
    if not bead_id:
        return
    if bead_id in app._bead_expanded:
        del app._bead_expanded[bead_id]
    else:
        project_name = next(
            (pn for pn, beads in app._bead_data.items()
             if any(b.get('id') == bead_id for b in (beads or []))), None)
        db_path = app._bead_db_paths.get(project_name) if project_name else None
        if db_path:
            app._bead_expanded[bead_id] = bd_show_text(bead_id, db_path)
    _rebuild_bead_panel(app)

# Handle untrack click from untrackBead_ controller method
def _handle_untrack_bead(app, tag: int) -> None:
    info = app._bead_untrack_tags.get(tag)
    if not info:
        return
    bead_id, project_name = info
    db_path = app._bead_db_paths.get(project_name)
    if db_path:
        bd_label_remove(bead_id, db_path)
    app._bead_expanded.pop(bead_id, None)
    app._bead_data[project_name] = [
        b for b in app._bead_data.get(project_name, []) if b.get('id') != bead_id]
    _rebuild_bead_panel(app)
