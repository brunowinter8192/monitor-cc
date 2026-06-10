# INFRASTRUCTURE
import json
import objc
import sys
from datetime import datetime, timezone

from AppKit import (NSLayoutAttributeLeading,
                    NSStackView, NSView, NSStatusWindowLevel,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _CursorlessButton, _KeyablePanel)
# From paths.py: HOOKS_FILE path for delivery guard
from .paths import HOOKS_FILE as _HOOKS_FILE
# From queue.py: queue storage + delivery
from .queue import load_queue, save_queue, deliver_message

# From queue_panel_render.py: render-concern functions (module-level, controller as first arg)
from .queue_panel_render import (_rebuild_inner as _qpr_rebuild_inner,
                                  _compute_height, _resize_panel)
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
        _qpr_rebuild_inner(self, sessions)

    # Compute required height: top-bar + separator + per-session header + entry rows + add-btn row
    def compute_height(self, sessions) -> int:
        return _compute_height(self, sessions)

    # Resize queue NSPanel anchored at top edge
    def _resize_panel(self, new_h: float) -> None:
        _resize_panel(self, new_h)

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
