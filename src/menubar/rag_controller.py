# INFRASTRUCTURE
import errno
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from AppKit import (NSAttributedString, NSFontAttributeName,
                    NSLayoutAttributeLeading, NSStatusWindowLevel,
                    NSStackView, NSView,
                    NSUserInterfaceLayoutOrientationVertical,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowStyleMaskNonactivatingPanel, NSWindowStyleMaskResizable)
from Foundation import NSMakeRect, NSMakeSize

# From panel.py: UI constants, factories, helpers shared across panels
from .panel import (PANEL_WIDTH, PANEL_HEIGHT, PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT,
                    PANEL_GAP, _TOP_BAR_H, _LABEL_H, _MENLO,
                    _CursorlessButton, _KeyablePanel,
                    _make_line_separator, _make_header_label)

_RAG_LOCK    = Path.home() / '.rag-locks' / 'rag.lock'
_NO_INDEXING = 'no indexing currently running'

# FUNCTIONS

# Build NSPanel for RAG status panel; returns (panel, stack, toggle_btn)
def _make_rag_nspanel():
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

# Position RAG panel flush below the NSStatusItem button (same logic as queue panel)
def _reposition_rag_panel(panel, nsstatusitem) -> None:
    btn_win = nsstatusitem.button().window()
    if btn_win is None:
        return
    w  = panel.frame().size.width
    h  = panel.frame().size.height
    sr = btn_win.frame()
    px = sr.origin.x + sr.size.width / 2.0 - w / 2.0
    py = sr.origin.y - h - PANEL_GAP
    panel.setFrame_display_(NSMakeRect(px, py, w, h), False)

# True if pid exists on this system; ESRCH (no such process) → False; EPERM → True (exists, no permission)
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        return e.errno != errno.ESRCH

# Read rag lock file at lock_path; return formatted status string; all exceptions → _NO_INDEXING.
# lock_path defaults to _RAG_LOCK; accepts override for offline testing against a temp file.
def _read_rag_status(lock_path: Path = _RAG_LOCK) -> str:
    try:
        data       = json.loads(lock_path.read_text())
        pid        = data.get('pid')
        if pid is None or not _pid_alive(pid):
            return _NO_INDEXING
        command    = data.get('command', '')
        kind       = data.get('kind')
        if kind is not None:
            if kind != 'index':
                return _NO_INDEXING   # server/search/delete lock
        else:
            # backward compat: old lock without kind field
            if not command.startswith('index'):
                return _NO_INDEXING
        args         = data.get('args') or {}
        progress     = data.get('progress') or {}
        collection   = (args.get('collection')
                        or progress.get('collection')
                        or Path(args.get('input', '')).name
                        or 'unknown')
        done         = progress.get('done', 0)
        total        = progress.get('total', 0)
        chunks_done  = progress.get('chunks_done')
        chunks_total = progress.get('chunks_total')
        elapsed      = _format_elapsed(data.get('started_at', ''))
        if chunks_done is not None and chunks_total:
            # mid-document: done = completed docs; done+1 = current doc number
            return (f'{collection} \u00b7 {done + 1}/{total} docs'
                    f' \u00b7 {chunks_done}/{chunks_total} chunks'
                    f' \u00b7 {elapsed}')
        elif total > 0:
            # between docs or old-format lock (no chunk fields)
            return f'{collection} \u00b7 {done}/{total} docs \u00b7 {elapsed}'
        else:
            # no progress yet (initial lock state) or single-doc job pre-embed
            return f'{collection} \u00b7 {elapsed}'
    except Exception:
        return _NO_INDEXING

# Format elapsed time as Xm00s or Xs from an ISO-8601 started_at string; errors → '?'
def _format_elapsed(started_at: str) -> str:
    try:
        start = datetime.fromisoformat(started_at)
        now   = datetime.now(timezone.utc)
        secs  = max(0, int((now - start).total_seconds()))
        mins, s = divmod(secs, 60)
        if mins > 0:
            return f'{mins}m{s:02d}s'
        return f'{s}s'
    except Exception:
        return '?'

# Per-concern controller for RAG status panel: state ownership, tick refresh, panel render
class RagController:
    def __init__(self, app) -> None:
        self.app = app
        self._rag_open: bool = False
        self._rag_panel, self._rag_sv, self._rag_toggle_btn = _make_rag_nspanel()
        self._rag_status_label = None   # NSTextField; set on first rebuild

    # Called from CCMenuBarApp._tick; updates status label in place (cheap setAttributedStringValue_)
    def tick(self, sessions) -> None:
        if self._rag_status_label is None:
            return
        status = _read_rag_status()
        self._rag_status_label.setAttributedStringValue_(
            NSAttributedString.alloc().initWithString_attributes_(
                status, {NSFontAttributeName: _MENLO()}))

    # Full rebuild of RAG panel: clear sv, set header, add separator + status label
    def rebuild(self) -> None:
        app = self.app
        for sv in list(self._rag_sv.arrangedSubviews()):
            self._rag_sv.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists without this
        pw    = app._panel_width
        state = 'ON' if app._auto_focus else 'OFF'
        self._rag_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions \u00b7 [RAG] \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        required_h = _TOP_BAR_H + _LABEL_H + _LABEL_H   # top-bar + separator + status line
        self._resize_rag_panel(max(app._panel_min_height, required_h))
        self._rag_sv.addView_inGravity_(_make_line_separator(pw), 1)
        status = _read_rag_status()
        label  = _make_header_label(status, pw)
        self._rag_sv.addView_inGravity_(label, 1)
        self._rag_status_label = label

    # Resize RAG panel anchored at top edge; mirrors queue_controller._resize_panel pattern
    def _resize_rag_panel(self, new_h: float) -> None:
        w     = self.app._panel_width
        frame = self._rag_panel.frame()
        top_y = frame.origin.y + frame.size.height
        self._rag_panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
