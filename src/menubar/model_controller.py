# INFRASTRUCTURE
import sys
import threading

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName)
from Foundation import NSMakeRect, NSOperationQueue

from .panel import _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO, _make_line_separator
from .model_selection import _PendingSelection
from .model_panel_ui import (_make_models_nspanel, _make_model_row_btn, _make_apply_btn,
                             _APPLY_BTN_W, _APPLY_SUCCESS_TITLE, _APPLY_SUCCESS_W,
                             _APPLY_SUCCESS_DURATION)

# FUNCTIONS

class _ModelRowButtons:
    def __init__(self):
        self.main_cycle    = None
        self.main_effort   = None
        self.main_maxtok   = None
        self.worker_cycle  = None
        self.worker_effort = None
        self.worker_maxtok = None
        self.apply         = None

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


class ModelController:
    def __init__(self, app) -> None:
        self.app = app
        self._models_open: bool = False
        self._models_panel, self._models_sv, self._models_toggle_btn = _make_models_nspanel()
        self._pending = _PendingSelection()
        self._pending.load()
        self._buttons = _ModelRowButtons()

    def open(self) -> None:
        self._pending.load()
        self.rebuild()

    def rebuild(self) -> None:
        app = self.app
        for sv in list(self._models_sv.arrangedSubviews()):
            self._models_sv.removeView_(sv)
            sv.removeFromSuperview()
        pw    = app.settings.panel_width
        state = 'ON' if app.settings.auto_focus else 'OFF'
        self._models_toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'Sessions · RAG · [Models]     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        required_h = _TOP_BAR_H + _LABEL_H + 6 * _ROW_H + 22
        self._resize_models_panel(max(app.settings.panel_min_height, required_h))
        self._models_sv.addView_inGravity_(_make_line_separator(pw), 1)
        self._buttons.build(self._models_sv, pw, app._panel_controller)
        self._buttons.refresh_titles(self._pending)

    def handle_cycle_main(self) -> None:
        try:
            self._pending.cycle_main()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model cycle (main) failed: {exc}', file=sys.stderr)

    def handle_cycle_worker(self) -> None:
        try:
            self._pending.cycle_worker()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model cycle (worker) failed: {exc}', file=sys.stderr)

    def handle_cycle_main_effort(self) -> None:
        try:
            self._pending.cycle_main_effort()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model effort cycle (main) failed: {exc}', file=sys.stderr)

    def handle_cycle_main_max_tokens(self) -> None:
        try:
            self._pending.cycle_main_max_tokens()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (main) failed: {exc}', file=sys.stderr)

    def handle_cycle_worker_effort(self) -> None:
        try:
            self._pending.cycle_worker_effort()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model effort cycle (worker) failed: {exc}', file=sys.stderr)

    def handle_cycle_worker_max_tokens(self) -> None:
        try:
            self._pending.cycle_worker_max_tokens()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (worker) failed: {exc}', file=sys.stderr)

    def handle_apply(self) -> None:
        try:
            self._pending.write()
            self._show_apply_success()
        except Exception as exc:
            print(f'[menubar] model selection apply failed: {exc}', file=sys.stderr)

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

    def _schedule_apply_revert(self) -> None:
        NSOperationQueue.mainQueue().addOperationWithBlock_(self._revert_apply_button)

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

    def _resize_models_panel(self, new_h: float) -> None:
        w     = self.app.settings.panel_width
        frame = self._models_panel.frame()
        top_y = frame.origin.y + frame.size.height
        self._models_panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
