# INFRASTRUCTURE
from unittest import mock

from p5_common import load, tmpdir, check, point_log, log_text

_HANDLERS = {
    'handle_cycle_main': 'cycle_main', 'handle_cycle_worker': 'cycle_worker',
    'handle_cycle_main_effort': 'cycle_main_effort', 'handle_cycle_main_max_tokens': 'cycle_main_max_tokens',
    'handle_cycle_worker_effort': 'cycle_worker_effort', 'handle_cycle_worker_max_tokens': 'cycle_worker_max_tokens',
    'handle_cycle_main_thinking': 'cycle_main_thinking', 'handle_cycle_worker_thinking': 'cycle_worker_thinking',
}

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    mc = load('model_controller')
    cls = mc.ModelController
    dispatch_and_refresh(cls)
    if hasattr(cls, '_guarded_cycle'):
        failures_logged(cls, mlog)
        flash_defect_visible(mc, cls, mlog)

# FUNCTIONS

class _Fake:
    def __init__(self, cls):
        self._pending = mock.MagicMock()
        self._buttons = mock.MagicMock()
        self.app = mock.MagicMock()
        if hasattr(cls, '_guarded_cycle'):
            self._guarded_cycle = lambda label, fn: cls._guarded_cycle(self, label, fn)

def dispatch_and_refresh(cls) -> None:
    for handler, pending_method in _HANDLERS.items():
        fake = _Fake(cls)
        getattr(cls, handler)(fake)
        called = [c[0] for c in fake._pending.method_calls]
        refreshed = fake._buttons.refresh_titles.call_args_list == [mock.call(fake._pending)]
        check(f'g7.{handler}.dispatch_normal', called == [pending_method] and refreshed)
    fake = _Fake(cls)
    cls.handle_apply(fake)
    check('g7.handle_apply.writes_normal', [c[0] for c in fake._pending.method_calls] == ['write'])

def failures_logged(cls, mlog) -> None:
    labels = {}
    for handler, pending_method in _HANDLERS.items():
        fake = _Fake(cls)
        getattr(fake._pending, pending_method).side_effect = RuntimeError(f'boom {handler}')
        getattr(cls, handler)(fake)
        check(f'g7.{handler}.failure_logged', f'boom {handler}' in log_text(mlog) and not fake._buttons.refresh_titles.called)
    fake = _Fake(cls)
    fake._pending.write.side_effect = OSError('disk')
    cls.handle_apply(fake)
    check('g7.handle_apply.failure_logged', 'model selection apply failed: OSError' in log_text(mlog))

def flash_defect_visible(mc, cls, mlog) -> None:
    fake = _Fake(cls)
    class _Btn:
        def frame(self):
            return mock.Mock()
    fake._buttons.apply = _Btn()
    cls._show_apply_success(fake)
    check('g7.apply_flash_defect_visible_in_menubar_log', 'apply success flash failed' in log_text(mlog))


if __name__ == '__main__':
    main()
