# INFRASTRUCTURE
import sys
import threading

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName)
from Foundation import NSMakeRect, NSOperationQueue

# From panel.py: UI constants + helpers shared across panels
from .panel import _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO, _make_line_separator
# From model_selection.py: pure model-selection persistence (load/cycle/write, no AppKit) — the
# dev/model_selector/verify_model_cycle_and_io.py contract for these names now targets that
# module directly (re-pointed, not re-exported here — none of them are called from this module).
from .model_selection import _PendingSelection
# From model_panel_ui.py: NSPanel/NSButton construction factories + Apply button constants
from .model_panel_ui import (_make_models_nspanel, _make_model_row_btn, _make_apply_btn,
                             _APPLY_BTN_W, _APPLY_SUCCESS_TITLE, _APPLY_SUCCESS_W,
                             _APPLY_SUCCESS_DURATION)

# ORCHESTRATOR

# Set of the 7 Models-panel row-button NSButton refs + the two AppKit operations that touch all
# of them together: (re)build (create + wire target/action + add to stack view) and title refresh.
class _ModelRowButtons:
    def __init__(self):
        self.main_cycle    = None   # NSButton; set on first build
        self.main_effort   = None   # NSButton; set on first build
        self.main_maxtok   = None   # NSButton; set on first build
        self.worker_cycle  = None   # NSButton; set on first build
        self.worker_effort = None   # NSButton; set on first build
        self.worker_maxtok = None   # NSButton; set on first build
        self.apply         = None   # NSButton; set on first build

    # Create all 7 buttons, wire target/action (fixed ObjC selectors), add to stack view — in
    # that exact order (create-all, wire-all, add-all), matching the pre-split rebuild() body.
    def build(self, sv, pw: int, target) -> None:
        self.main_cycle    = _make_model_row_btn(pw)
        self.main_effort   = _make_model_row_btn(pw)
        self.main_maxtok   = _make_model_row_btn(pw)
        self.worker_cycle  = _make_model_row_btn(pw)
        self.worker_effort = _make_model_row_btn(pw)
        self.worker_maxtok = _make_model_row_btn(pw)
        self.apply         = _make_apply_btn()
        self.main_cycle.setTarget_(target)
        self.main_cycle.setAction_(b'cycleMainModel:')
        self.main_effort.setTarget_(target)
        self.main_effort.setAction_(b'cycleMainEffort:')
        self.main_maxtok.setTarget_(target)
        self.main_maxtok.setAction_(b'cycleMainMaxTokens:')
        self.worker_cycle.setTarget_(target)
        self.worker_cycle.setAction_(b'cycleWorkerModel:')
        self.worker_effort.setTarget_(target)
        self.worker_effort.setAction_(b'cycleWorkerEffort:')
        self.worker_maxtok.setTarget_(target)
        self.worker_maxtok.setAction_(b'cycleWorkerMaxTokens:')
        self.apply.setTarget_(target)
        self.apply.setAction_(b'applyModelSelection:')
        for btn in (self.main_cycle, self.main_effort, self.main_maxtok,
                    self.worker_cycle, self.worker_effort, self.worker_maxtok, self.apply):
            sv.addView_inGravity_(btn, 1)

    # Update all 6 cycle-button titles from pending state; no full rebuild. The two MODEL rows
    # (Main/Worker) render in NSColor.systemOrangeColor() — same established attribute pattern
    # panel.py:_make_grid_cell_btn's attrs-dict shape uses for session rows; the 4 parameter rows
    # keep the plain Menlo-only look.
    def refresh_titles(self, pending: _PendingSelection) -> None:
        self.main_cycle.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Main:    {pending.main}',
                {NSFontAttributeName: _MENLO(), NSForegroundColorAttributeName: NSColor.systemOrangeColor()}))
        self.main_effort.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Main effort:      {pending.main_effort}', {NSFontAttributeName: _MENLO()}))
        self.main_maxtok.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Main max_tokens:  {pending.main_max_tokens}', {NSFontAttributeName: _MENLO()}))
        self.worker_cycle.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Worker:  {pending.worker}',
                {NSFontAttributeName: _MENLO(), NSForegroundColorAttributeName: NSColor.systemOrangeColor()}))
        self.worker_effort.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Worker effort:    {pending.worker_effort}', {NSFontAttributeName: _MENLO()}))
        self.worker_maxtok.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Worker max_tokens:{pending.worker_max_tokens}', {NSFontAttributeName: _MENLO()}))


# Per-concern controller for the Models panel: state ownership, panel render, cycle + apply actions
class ModelController:
    def __init__(self, app) -> None:
        self.app = app
        self._models_open: bool = False
        self._models_panel, self._models_sv, self._models_toggle_btn = _make_models_nspanel()
        self._pending = _PendingSelection()
        self._pending.load()
        self._buttons = _ModelRowButtons()

    # Reload pending state from disk and rebuild; used by _open_models_panel
    def open(self) -> None:
        self._pending.load()
        self.rebuild()

    # Full rebuild of Models panel: clear sv, set header, add separator + 6 cycle rows + apply row
    # (Main model/effort/max_tokens, Worker model/effort/max_tokens, Apply). Target/action for the
    # 7 row buttons are (re)wired here every call, not in app.py's one-time init block — these
    # buttons are recreated on each rebuild, so a one-time wire would go stale.
    def rebuild(self) -> None:
        app = self.app
        for sv in list(self._models_sv.arrangedSubviews()):
            self._models_sv.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists without this
        pw    = app.settings.panel_width
        state = 'ON' if app.settings.auto_focus else 'OFF'
        self._models_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions · RAG · [Models]     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        required_h = _TOP_BAR_H + _LABEL_H + 6 * _ROW_H + 22   # top-bar + separator + 6 cycle rows + apply row
        self._resize_models_panel(max(app.settings.panel_min_height, required_h))
        self._models_sv.addView_inGravity_(_make_line_separator(pw), 1)
        self._buttons.build(self._models_sv, pw, app._panel_controller)
        self._buttons.refresh_titles(self._pending)

    # Advance pending main model to the next fixed-order value; refreshes the main effort/
    # max_tokens rows to the new model's current on-disk values (or defaults). In-place title
    # update only. AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_main(self) -> None:
        try:
            self._pending.cycle_main()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model cycle (main) failed: {exc}', file=sys.stderr)

    # Advance pending worker model to the next fixed-order value; refreshes the worker effort/
    # max_tokens rows to the new model's current on-disk values (or defaults). In-place title
    # update only. AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_worker(self) -> None:
        try:
            self._pending.cycle_worker()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model cycle (worker) failed: {exc}', file=sys.stderr)

    # Advance pending main effort to the next fixed-order value; in-place title update only.
    # AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_main_effort(self) -> None:
        try:
            self._pending.cycle_main_effort()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model effort cycle (main) failed: {exc}', file=sys.stderr)

    # Advance pending main max_tokens to the next fixed-order value; in-place title update only.
    # AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_main_max_tokens(self) -> None:
        try:
            self._pending.cycle_main_max_tokens()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (main) failed: {exc}', file=sys.stderr)

    # Advance pending worker effort to the next fixed-order value; in-place title update only.
    # AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_worker_effort(self) -> None:
        try:
            self._pending.cycle_worker_effort()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model effort cycle (worker) failed: {exc}', file=sys.stderr)

    # Advance pending worker max_tokens to the next fixed-order value; in-place title update only.
    # AppKit-safety boundary: catches + logs, never raises — same shape as handle_apply.
    def handle_cycle_worker_max_tokens(self) -> None:
        try:
            self._pending.cycle_worker_max_tokens()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (worker) failed: {exc}', file=sys.stderr)

    # Persist the currently displayed pair to model_selection.json, and the currently displayed
    # effort/max_tokens for both selected models into proxy_rules.json's model_params table.
    # AppKit-safety boundary: catches + logs, never raises, so a write failure cannot propagate
    # into the ObjC action-dispatch chain. Success feedback (_show_apply_success) is the LAST
    # statement in the try block — a write exception skips it, so a failed Apply never shows the
    # confirmation, with no separate success flag needed.
    def handle_apply(self) -> None:
        try:
            self._pending.write()
            self._show_apply_success()
        except Exception as exc:
            print(f'[menubar] model selection apply failed: {exc}', file=sys.stderr)

    # Flash the Apply button to a success confirmation, then schedule its revert. Runs synchronously
    # on the main thread (called from the same ObjC action dispatch as the click), so self._buttons.apply
    # is guaranteed live here — the stale-ref concern only applies to the DELAYED revert below.
    # Own try/except (same shape as every other handler in this file) so a pure UI-feedback hiccup
    # here can never get mislabeled as an apply failure by the caller's try block.
    def _show_apply_success(self) -> None:
        try:
            btn = self._buttons.apply
            if btn is None:
                return
            frame = btn.frame()
            btn.setFrame_display_(
                NSMakeRect(frame.origin.x, frame.origin.y, _APPLY_SUCCESS_W, frame.size.height), True)
            btn.setTitle_(_APPLY_SUCCESS_TITLE)
            threading.Timer(_APPLY_SUCCESS_DURATION, self._schedule_apply_revert).start()
        except Exception as exc:
            print(f'[menubar] apply success flash failed: {exc}', file=sys.stderr)

    # Timer-thread callback (off the main thread) — hops back onto the main thread before touching
    # any AppKit object, same pattern as app.py's _blink/_restore (the only other delayed-revert in
    # this package).
    def _schedule_apply_revert(self) -> None:
        NSOperationQueue.mainQueue().addOperationWithBlock_(self._revert_apply_button)

    # Revert the Apply button to its normal title/width. Looks up self._buttons.apply DYNAMICALLY at
    # fire time rather than closing over the button object captured at flash time — if a rebuild()
    # happened in between, self._buttons now points at a freshly-built button set whose apply title is
    # already 'Apply' (_make_apply_btn's own default), so reverting it is a harmless no-op, never a
    # crash on a detached/replaced object. Own try/except: an AppKit call failing here (or the panel
    # having been torn down some other way) must not propagate into the timer-thread callback chain.
    def _revert_apply_button(self) -> None:
        try:
            btn = self._buttons.apply
            if btn is None:
                return
            frame = btn.frame()
            btn.setFrame_display_(
                NSMakeRect(frame.origin.x, frame.origin.y, _APPLY_BTN_W, frame.size.height), True)
            btn.setTitle_('Apply')
        except Exception as exc:
            print(f'[menubar] apply success revert failed: {exc}', file=sys.stderr)

    # Resize Models NSPanel anchored at top edge; mirrors rag_controller._resize_rag_panel pattern
    def _resize_models_panel(self, new_h: float) -> None:
        w     = self.app.settings.panel_width
        frame = self._models_panel.frame()
        top_y = frame.origin.y + frame.size.height
        self._models_panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
