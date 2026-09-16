# INFRASTRUCTURE
import contextlib
import io
import os

from p1_shared import _PROBE_LOG_PATH, check
from p1_pane_modules import (
    mod_gpu, mod_news, mod_news_log, mod_proxy, mod_tokens, mod_warnings,
    mod_worker_proxy, mod_worker_tokens,
)
from p1_loop_harness import _assert_survives, _run_poll_only_loop_and_capture


# FUNCTIONS

def test_worker_tokens_pane():
    print("\n[Test] worker-tokens pane (src/workers/worker_tokens_pane.py) — reference pattern, re-checked")
    _assert_survives('worker_tokens', mod_worker_tokens, 'run_worker_tokens_loop')


def test_proxy_pane():
    print("\n[Test] proxy pane (src/proxy_display/pane.py)")
    _assert_survives('proxy', mod_proxy, 'run_proxy_loop')


def test_worker_proxy_pane():
    print("\n[Test] worker-proxy pane (src/proxy_display/worker_proxy_pane.py)")
    _assert_survives('worker_proxy', mod_worker_proxy, 'run_worker_proxy_loop')


def test_tokens_pane():
    print("\n[Test] tokens pane (src/panes/token_pane.py)")
    _assert_survives('tokens', mod_tokens, 'run_tokens_loop')


def test_warnings_pane():
    print("\n[Test] warnings pane (src/panes/warnings_pane.py)")
    _assert_survives('warnings', mod_warnings, 'run_warnings_loop')


def test_gpu_pane():
    print("\n[Test] gpu pane (src/gpu_pane/pane.py)")
    _assert_survives('gpu', mod_gpu, 'run_gpu_loop')


def test_news_pane():
    print("\n[Test] news pane (src/news_pane/pane.py)")
    _assert_survives('news', mod_news, 'run_news_loop')


def test_news_log_pane():
    print("\n[Test] news-log pane (src/news_pane/log_pane.py) — no mouse, no finally: (never had one)")
    if os.path.exists(_PROBE_LOG_PATH):
        os.remove(_PROBE_LOG_PATH)
    r = _run_poll_only_loop_and_capture('news_log', mod_news_log, 'run_news_log_loop', 'find_log_file')
    check("[news_log] loop terminated via _ProbeStop, not an unhandled crash",
          r['stop_caught'] and r['other_exc'] is None)
    check("[news_log] survived past the crash iteration (>=2 ticks reached)",
          r['tick_calls'] >= 2)
    check("[news_log] injected exception logged with this pane's identifier",
          "[news_log]" in r['log_text'] and "ProbeInjected:news_log" in r['log_text'])
    check("[news_log] full traceback recorded (Traceback... line present)",
          "Traceback (most recent call last):" in r['log_text'])


# Test: the guard must not swallow deliberate termination — real KeyboardInterrupt and SystemExit
# both propagate out of the loop, and `finally:` cleanup still runs (checked on one representative
# pane; the _ProbeStop-based BaseException path above already proves the same MRO relationship
# for all 7, since KeyboardInterrupt/SystemExit/_ProbeStop are all BaseException, not Exception)
def test_keyboard_interrupt_and_system_exit_not_swallowed():
    print("\n[Test] KeyboardInterrupt / SystemExit propagate, finally: cleanup still runs (proxy pane)")
    for exc_cls in (KeyboardInterrupt, SystemExit):
        cleanup_calls = {'disable_mouse': 0, 'restore_terminal': 0}

        def _raise_on_first_read(_exc_cls=exc_cls):
            raise _exc_cls()

        saved = {
            name: getattr(mod_proxy, name)
            for name in ('read_keypress', 'setup_keyboard_input', 'enable_mouse',
                         'disable_mouse', 'restore_terminal', 'wait_for_input')
        }
        mod_proxy.read_keypress = _raise_on_first_read
        mod_proxy.setup_keyboard_input = lambda: None
        mod_proxy.enable_mouse = lambda: None
        mod_proxy.disable_mouse = lambda: cleanup_calls.__setitem__('disable_mouse', cleanup_calls['disable_mouse'] + 1)
        mod_proxy.restore_terminal = lambda: cleanup_calls.__setitem__('restore_terminal', cleanup_calls['restore_terminal'] + 1)
        mod_proxy.wait_for_input = lambda *_a, **_kw: None
        propagated = False
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mod_proxy.run_proxy_loop()
        except exc_cls:
            propagated = True
        except BaseException:
            propagated = False
        finally:
            for name, fn in saved.items():
                setattr(mod_proxy, name, fn)
        check(f"{exc_cls.__name__} propagates out of run_proxy_loop (not caught by except Exception)", propagated)
        check(f"{exc_cls.__name__}: finally: cleanup ran", cleanup_calls['disable_mouse'] >= 1 and cleanup_calls['restore_terminal'] >= 1)
