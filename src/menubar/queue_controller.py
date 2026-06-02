# INFRASTRUCTURE
import json
import objc
import sys
from datetime import datetime, timezone

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCellPlacementFill,
                    NSGridView, NSLayoutAttributeLeading,
                    NSPanel, NSStackView, NSTextField, NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _CursorlessLabel, _KeyablePanel,
                    _make_line_separator, _make_header_label)
# From paths.py: HOOKS_FILE path for delivery guard
from .paths import HOOKS_FILE as _HOOKS_FILE
# From queue.py: queue storage + delivery
from .queue import load_queue, save_queue, deliver_message

_QUEUE_TOGGLE_W = 22   # pts — ↑/↓ toggle button width
_QUEUE_MINUS_W  = 22   # pts — × delete button width
_NSEventTypeKeyDown = 10         # NSEventTypeKeyDown
_MODIFIER_MASK      = 0xFFFF0000  # NSEventModifierFlagDeviceIndependentFlagsMask

# Plain 'q' mid-text in a queue draft field: jump cursor to end; 'q' at end/empty → insert normally
class _QueuePanel(_KeyablePanel):
    def sendEvent_(self, event):
        if (event.type() == _NSEventTypeKeyDown
                and event.modifierFlags() & _MODIFIER_MASK == 0
                and (event.characters() or '').lower() == 'q'):
            fr = self.firstResponder()
            if fr is not None and hasattr(fr, 'string'):
                text_len = len(fr.string())
                if fr.selectedRange().location < text_len:
                    fr.setSelectedRange_((text_len, 0))
                    return
        objc.super(_QueuePanel, self).sendEvent_(event)

# FUNCTIONS

# Build NSPanel for queue panel; returns (panel, stack, toggle_btn)
def _make_queue_nspanel():
    panel = _QueuePanel.alloc().initWithContentRect_styleMask_backing_defer_(
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
    top_bar.setAutoresizingMask_(10)   # NSViewWidthSizable | NSViewMinYMargin
    toggle_btn = _CursorlessButton.alloc().initWithFrame_(
        NSMakeRect(0, 0, PANEL_WIDTH - 22, _TOP_BAR_H - 1))
    toggle_btn.setBordered_(False)
    toggle_btn.setButtonType_(7)
    toggle_btn.setAutoresizingMask_(2)
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

# Position queue panel flush below the NSStatusItem button
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

# Per-concern controller for the queue panel: state ownership, tick refresh, panel render, action dispatch
class QueueController:
    def __init__(self, app) -> None:
        self.app = app
        self._queue_open: bool = False
        self._queue_panel, self._queue_sv, self._queue_toggle_btn = _make_queue_nspanel()
        self._queue_displayed_names: set = set()   # session names currently shown in queue panel
        self._queue_data: dict = {}                # {session_id: [{text,state,sent_at}]} — refreshed each tick
        self._pending_queue_tags: dict = {}        # {NSTextField tag → (session_id, idx)}; reset on each rebuild
        self._pending_queue_views: dict = {}       # {(session_id, idx) → NSTextField}; reset each rebuild
        self._queue_add_tags: dict = {}            # {+ button tag → session_id}; reset on each rebuild
        self._queue_remove_tags: dict = {}         # {× button tag → (session_id, idx)}; reset each rebuild
        self._queue_toggle_tags: dict = {}         # {↑/↓ button tag → (session_id, idx)}; reset each rebuild
        self._rebuild_in_progress: bool = False    # re-entry guard for rebuild

    # Called from CCMenuBarApp._tick; loads fresh queue data, rebuilds panel if open and changed
    def tick(self, sessions) -> None:
        new_queue = load_queue()
        queue_changed = new_queue != self._queue_data
        self._queue_data = new_queue
        if self._queue_open:
            q_names = {s.name for s in sessions if not s.is_worker}
            if queue_changed or q_names != self._queue_displayed_names:
                self.rebuild(sessions)

    # Pre-load fresh queue data and rebuild; used by _open_queue_panel before ordering panel front
    def open(self, sessions) -> None:
        self._queue_data = load_queue()
        self.rebuild(sessions)

    # Full rebuild of queue panel from self._queue_data + sessions; re-entry guard
    def rebuild(self, sessions) -> None:
        if self._rebuild_in_progress:
            return
        self._rebuild_in_progress = True
        try:
            self._rebuild_inner(sessions)
        finally:
            self._rebuild_in_progress = False

    # ONE NSGridView (1 col): every row is a full-width container NSView that owns its subviews.
    # Three-state rows: draft (gray bg, editable NSTextField, ↑ toggle, × delete),
    # queued (red bg, read-only label, ↓ toggle, × delete),
    # sent (green bg, read-only label, no toggle, × delete).
    def _rebuild_inner(self, sessions) -> None:
        app = self.app
        for sv in list(self._queue_sv.arrangedSubviews()):
            self._queue_sv.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists without this
        self._queue_add_tags.clear()
        self._queue_remove_tags.clear()
        self._pending_queue_tags.clear()
        self._pending_queue_views.clear()
        self._queue_toggle_tags.clear()
        state = 'ON' if app._auto_focus else 'OFF'
        self._queue_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 RAG \u00b7 [Queue]     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        main_sessions = sorted(
            [s for s in sessions if not s.is_worker],
            key=lambda s: (s.project_name, s.name))
        pw         = app._panel_width
        required_h = self.compute_height(sessions)
        self._resize_panel(max(app._panel_min_height, required_h))
        self._queue_sv.addView_inGravity_(_make_line_separator(pw), 1)
        if not main_sessions:
            self._queue_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
            self._queue_displayed_names = set()
            return

        # 1-column NSGridView; all rows are full-width container NSViews
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
        row_h          = _ROW_H - 1
        col0_w         = pw - _QUEUE_TOGGLE_W - _QUEUE_MINUS_W
        first_draft_tf = None

        for s in main_sessions:
            # Project › session header row (full-width label)
            hdr = _make_header_label(f'{s.project_name} \u203a {s.name}', pw)
            grid.addRowWithViews_([hdr])
            grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
            row_idx += 1

            msgs = self._queue_data.get(s.session_id, [])
            for i, entry in enumerate(msgs):
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
                    tf.setPlaceholderString_('message\u2026')
                    tf.setTarget_(app._panel_controller)
                    tf.setAction_(b'commitQueueField:')
                    tf.setDelegate_(app._panel_controller)
                    self._pending_queue_tags[tf_tag] = (s.session_id, i)
                    self._pending_queue_views[(s.session_id, i)] = tf
                    container.addSubview_(tf)
                    if first_draft_tf is None:
                        first_draft_tf = tf
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
                    symbol = '\u2191' if entry_state == 'draft' else '\u2193'   # ↑ or ↓
                    toggle.setAttributedTitle_(
                        NSAttributedString.alloc().initWithString_attributes_(
                            symbol, {NSFontAttributeName: _MENLO(),
                                     NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
                    toggle.setTag_(tog_tag)
                    toggle.setTarget_(app._panel_controller)
                    toggle.setAction_(b'toggleQueueEntry:')
                    self._queue_toggle_tags[tog_tag] = (s.session_id, i)
                    container.addSubview_(toggle)

                # Col 2: × delete button (always present for all states)
                rmv_tag = q_rmv_tag[0]; q_rmv_tag[0] += 1
                minus = _CursorlessButton.alloc().initWithFrame_(
                    NSMakeRect(col0_w + _QUEUE_TOGGLE_W, 0, _QUEUE_MINUS_W, row_h))
                minus.setBordered_(False)
                minus.setButtonType_(7)
                minus.setAttributedTitle_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        '\u00d7', {NSFontAttributeName: _MENLO(),   # ×
                                   NSForegroundColorAttributeName: NSColor.systemGrayColor()}))
                minus.setTag_(rmv_tag)
                minus.setTarget_(app._panel_controller)
                minus.setAction_(b'removeQueueEntry:')
                self._queue_remove_tags[rmv_tag] = (s.session_id, i)
                container.addSubview_(minus)

                grid.addRowWithViews_([container])
                grid.rowAtIndex_(row_idx).setHeight_(float(row_h))
                row_idx += 1

            # + add-new-draft button row
            add_tag = q_add_tag[0]; q_add_tag[0] += 1
            add_btn = _make_queue_add_btn(pw)
            add_btn.setTag_(add_tag)
            add_btn.setTarget_(app._panel_controller)
            add_btn.setAction_(b'addQueueRow:')
            self._queue_add_tags[add_tag] = s.session_id
            grid.addRowWithViews_([add_btn])
            grid.rowAtIndex_(row_idx).setHeight_(float(row_h))
            row_idx += 1

        self._queue_sv.addView_inGravity_(grid, 1)
        grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)
        self._queue_displayed_names = {s.name for s in main_sessions}
        if first_draft_tf is not None:
            self._queue_panel.makeKeyAndOrderFront_(None)
            self._queue_panel.makeFirstResponder_(first_draft_tf)

    # Compute required height: top-bar + separator + per-session header + entry rows + add-btn row
    def compute_height(self, sessions) -> int:
        h = _TOP_BAR_H + _LABEL_H
        main_sessions = [s for s in sessions if not s.is_worker]
        if not main_sessions:
            return h + _LABEL_H
        for s in main_sessions:
            h += _LABEL_H                                               # project › session header
            msgs = self._queue_data.get(s.session_id, [])
            h += len(msgs) * (_ROW_H - 1)                              # one row per entry
            h += (_ROW_H - 1)                                          # + button row
        return h

    # Resize queue NSPanel anchored at top edge
    def _resize_panel(self, new_h: float) -> None:
        w     = self.app._panel_width
        frame = self._queue_panel.frame()
        top_y = frame.origin.y + frame.size.height
        self._queue_panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)

    # Handle + button: append empty draft; guard against stacking blanks
    def handle_add_row(self, tag: int) -> None:
        session_id = self._queue_add_tags.get(tag)
        if not session_id:
            return
        q       = load_queue()
        entries = q.get(session_id, [])
        if entries and entries[-1].get("state") == "draft" and not entries[-1].get("text", "").strip():
            return
        entries.append({"text": "", "state": "draft", "sent_at": None})
        q[session_id] = entries
        save_queue(q)
        self._queue_data = q
        sessions = self.app.sessions.refresh()
        self.rebuild(sessions)

    # Handle ↑/↓ toggle: flip draft↔queued; capture live NSTextField text before flip
    def handle_toggle_entry(self, tag: int) -> None:
        info = self._queue_toggle_tags.get(tag)
        if not info:
            return
        session_id, idx = info
        # Borderless button click does NOT cause NSTextField to lose focus, so
        # controlTextDidEndEditing_ is never called. Capture live text directly here.
        tf        = self._pending_queue_views.get((session_id, idx))
        live_text = str(tf.stringValue()) if tf is not None else None
        q       = load_queue()
        entries = q.get(session_id, [])
        if 0 <= idx < len(entries):
            e         = entries[idx]
            new_state = "draft" if e.get("state") == "queued" else "queued"
            updated   = {**e, "state": new_state}
            if live_text is not None:
                updated["text"] = live_text
            entries[idx] = updated
            q[session_id] = entries
            save_queue(q)
            self._queue_data = q
            if new_state == "queued":
                self.handle_try_deliver(session_id, updated.get("text", ""), idx)
        sessions = self.app.sessions.refresh()
        self.rebuild(sessions)

    # Handle × delete button: remove entry from queue
    def handle_remove_entry(self, tag: int) -> None:
        info = self._queue_remove_tags.get(tag)
        if not info:
            return
        session_id, idx = info
        q    = load_queue()
        msgs = q.get(session_id, [])
        if 0 <= idx < len(msgs):
            del msgs[idx]
            if msgs:
                q[session_id] = msgs
            else:
                q.pop(session_id, None)
            save_queue(q)
            self._queue_data = q
        sessions = self.app.sessions.refresh()
        self.rebuild(sessions)

    # Handle Enter on a draft NSTextField: save text AND queue it (draft → queued)
    def handle_commit_field(self, tag: int, text: str) -> None:
        info = self._pending_queue_tags.get(tag)
        if not info:
            return
        session_id, idx = info
        q       = load_queue()
        entries = q.get(session_id, [])
        if 0 <= idx < len(entries) and entries[idx].get("state") == "draft":
            entries[idx] = {**entries[idx], "text": text, "state": "queued"}
            q[session_id] = entries
            save_queue(q)
            self._queue_data = q
            self.handle_try_deliver(session_id, text, idx)
            sessions = self.app.sessions.refresh()
            self.rebuild(sessions)

    # Handle focus loss on a draft NSTextField: save current text in-place, no rebuild
    def handle_text_end_editing(self, tag: int, text: str) -> None:
        info = self._pending_queue_tags.get(tag)
        if not info:
            return
        session_id, idx = info
        q       = load_queue()
        entries = q.get(session_id, [])
        if 0 <= idx < len(entries) and entries[idx].get("state") == "draft":
            entries[idx] = {**entries[idx], "text": text}
            q[session_id] = entries
            save_queue(q)
            self._queue_data = q

    # If the target session is currently idle, deliver the just-queued message immediately
    # and mark it sent in the queue file. Called after committing a draft to queued state.
    # Acceptable race with hook_writer: concurrent Stop + panel-queue both deliver → double-send;
    # second mark_sent is a no-op because state check guards against already-sent entries.
    def handle_try_deliver(self, session_id: str, text: str, idx: int) -> None:
        try:
            hook_state = json.loads(_HOOKS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"queue: handle_try_deliver read hooks.json failed: {exc}", file=sys.stderr)
            return
        entry = hook_state.get(session_id, {})
        print(f"queue: handle_try_deliver session={session_id[:12]} status={entry.get('status')!r} cwd={entry.get('cwd', '')!r}", file=sys.stderr)
        if entry.get("status") != "idle":
            print(f"queue: handle_try_deliver returning, not idle", file=sys.stderr)
            return
        cwd = entry.get("cwd", "")
        if not cwd or not text:
            return
        success = deliver_message(cwd, text)
        print(f"queue: handle_try_deliver delivered, success={success}", file=sys.stderr)
        if not success:
            return
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        q       = load_queue()
        entries = q.get(session_id, [])
        if 0 <= idx < len(entries) and entries[idx].get("state") == "queued":
            entries[idx] = {**entries[idx], "state": "sent", "sent_at": now_iso}
            q[session_id] = entries
            save_queue(q)
            self._queue_data = q
