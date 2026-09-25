# INFRASTRUCTURE
import threading

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName)
from Foundation import NSMakeRect, NSOperationQueue

from src.menubar.menubar_log import log_menubar
from src.menubar.panel import (_TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO, _make_line_separator,
                    _make_tab_nspanel, _resize_panel_keep_top)
from src.menubar.model_selection import _PendingSelection, _thinking_is_enabled
from src.menubar.model_panel_ui import (_make_model_row_btn, _make_apply_btn,
                             _APPLY_BTN_W, _APPLY_SUCCESS_TITLE, _APPLY_SUCCESS_W,
                             _APPLY_SUCCESS_DURATION)

# FUNCTIONS

class _ModelRowButtons:
    def __init__(self):
        self.main_cycle      = None
        self.main_effort     = None
        self.main_maxtok     = None
        self.main_thinking   = None
        self.worker_cycle    = None
        self.worker_effort   = None
        self.worker_maxtok   = None
        self.worker_thinking = None
        self.apply           = None

    def build(self, sv, pw: int, target) -> None:
        self.main_cycle      = _make_model_row_btn(pw)
        self.main_effort     = _make_model_row_btn(pw)
        self.main_maxtok     = _make_model_row_btn(pw)
        self.main_thinking   = _make_model_row_btn(pw)
        self.worker_cycle    = _make_model_row_btn(pw)
        self.worker_effort   = _make_model_row_btn(pw)
        self.worker_maxtok   = _make_model_row_btn(pw)
        self.worker_thinking = _make_model_row_btn(pw)
        self.apply           = _make_apply_btn()
        self.main_cycle.setTarget_(target)
        self.main_cycle.setAction_(b'cycleMainModel:')
        self.main_effort.setTarget_(target)
        self.main_effort.setAction_(b'cycleMainEffort:')
        self.main_maxtok.setTarget_(target)
        self.main_maxtok.setAction_(b'cycleMainMaxTokens:')
        self.main_thinking.setTarget_(target)
        self.main_thinking.setAction_(b'cycleMainThinking:')
        self.worker_cycle.setTarget_(target)
        self.worker_cycle.setAction_(b'cycleWorkerModel:')
        self.worker_effort.setTarget_(target)
        self.worker_effort.setAction_(b'cycleWorkerEffort:')
        self.worker_maxtok.setTarget_(target)
        self.worker_maxtok.setAction_(b'cycleWorkerMaxTokens:')
        self.worker_thinking.setTarget_(target)
        self.worker_thinking.setAction_(b'cycleWorkerThinking:')
        self.apply.setTarget_(target)
        self.apply.setAction_(b'applyModelSelection:')
        for btn in (self.main_cycle, self.main_effort, self.main_maxtok, self.main_thinking,
                    self.worker_cycle, self.worker_effort, self.worker_maxtok, self.worker_thinking,
                    self.apply):
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
        self.main_thinking.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Main thinking:    {"on" if _thinking_is_enabled(pending.main_thinking) else "off"}',
                {NSFontAttributeName: _MENLO()}))
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
        self.worker_thinking.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'  Worker thinking:  {"on" if _thinking_is_enabled(pending.worker_thinking) else "off"}',
                {NSFontAttributeName: _MENLO()}))


class ModelController:
    def __init__(self, app) -> None:
        self.app = app
        self._models_open: bool = False
        self._models_panel, self._models_sv, self._models_header = _make_tab_nspanel('Models')
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
        pw = app.settings.panel_width
        required_h = _TOP_BAR_H + _LABEL_H + 8 * _ROW_H + 22
        _resize_panel_keep_top(self._models_panel, app.settings.panel_width, max(app.settings.panel_min_height, required_h))
        self._models_sv.addView_inGravity_(_make_line_separator(pw), 1)
        self._buttons.build(self._models_sv, pw, app._panel_controller)
        self._buttons.refresh_titles(self._pending)

    def handle_cycle_main(self) -> None:
        self._guarded_cycle('model cycle (main)', self._pending.cycle_main)

    def handle_cycle_worker(self) -> None:
        self._guarded_cycle('model cycle (worker)', self._pending.cycle_worker)

    def handle_cycle_main_effort(self) -> None:
        self._guarded_cycle('model effort cycle (main)', self._pending.cycle_main_effort)

    def handle_cycle_main_max_tokens(self) -> None:
        self._guarded_cycle('model max_tokens cycle (main)', self._pending.cycle_main_max_tokens)

    def handle_cycle_worker_effort(self) -> None:
        self._guarded_cycle('model effort cycle (worker)', self._pending.cycle_worker_effort)

    def handle_cycle_worker_max_tokens(self) -> None:
        self._guarded_cycle('model max_tokens cycle (worker)', self._pending.cycle_worker_max_tokens)

    def handle_cycle_main_thinking(self) -> None:
        self._guarded_cycle('model thinking cycle (main)', self._pending.cycle_main_thinking)

    def handle_cycle_worker_thinking(self) -> None:
        self._guarded_cycle('model thinking cycle (worker)', self._pending.cycle_worker_thinking)

    def handle_apply(self) -> None:
        try:
            self._pending.write()
            self._show_apply_success()
        except Exception as exc:
            log_menubar('model', f'model selection apply failed: {exc!r}')

    def _guarded_cycle(self, label: str, cycle) -> None:
        try:
            cycle()
            self._buttons.refresh_titles(self._pending)
        except Exception as exc:
            log_menubar('model', f'{label} failed: {exc!r}')

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
            log_menubar('model', f'apply success flash failed: {exc!r}')

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
            log_menubar('model', f'apply success revert failed: {exc!r}')
