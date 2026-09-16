# INFRASTRUCTURE
import contextlib
import io
import os

from p1_shared import _PROBE_LOG_PATH, _ProbeInjectedError, _ProbeStop, _STOP_AFTER_TICKS, _read_probe_log, check


# FUNCTIONS

def _make_loop_fakes(pane_id):
    read_calls = {'n': 0}
    tick_calls = {'n': 0}
    cleanup_calls = {'disable_mouse': 0, 'restore_terminal': 0}

    def _fake_read_keypress():
        read_calls['n'] += 1
        if read_calls['n'] == 1:
            raise _ProbeInjectedError(f'ProbeInjected:{pane_id}')
        return None

    def _fake_tick(*_a, **_kw):
        tick_calls['n'] += 1
        if tick_calls['n'] >= _STOP_AFTER_TICKS:
            raise _ProbeStop()

    def _noop(*_a, **_kw):
        return None

    def _fake_disable_mouse():
        cleanup_calls['disable_mouse'] += 1

    def _fake_restore_terminal():
        cleanup_calls['restore_terminal'] += 1

    fakes = {
        'read_keypress': _fake_read_keypress,
        'tick': _fake_tick,
        'noop': _noop,
        'disable_mouse': _fake_disable_mouse,
        'restore_terminal': _fake_restore_terminal,
    }
    return read_calls, tick_calls, cleanup_calls, fakes


def _patch_module_for_loop(module, use_time_sleep, fakes):
    saved = {
        name: getattr(module, name)
        for name in ('read_keypress', 'setup_keyboard_input', 'enable_mouse',
                     'disable_mouse', 'restore_terminal')
        if hasattr(module, name)
    }
    module.read_keypress = fakes['read_keypress']
    module.setup_keyboard_input = fakes['noop']
    module.enable_mouse = fakes['noop']
    module.disable_mouse = fakes['disable_mouse']
    module.restore_terminal = fakes['restore_terminal']
    saved_wait_for_input = None
    if not use_time_sleep:
        saved_wait_for_input = getattr(module, 'wait_for_input')
        module.wait_for_input = fakes['tick']

    import time as _time_mod
    saved_sleep = _time_mod.sleep
    if use_time_sleep:
        _time_mod.sleep = fakes['tick']

    return saved, saved_wait_for_input, saved_sleep


def _restore_module_io(module, saved, saved_wait_for_input, use_time_sleep, saved_sleep):
    for name, fn in saved.items():
        setattr(module, name, fn)
    if saved_wait_for_input is not None:
        module.wait_for_input = saved_wait_for_input
    if use_time_sleep:
        import time as _time_mod
        _time_mod.sleep = saved_sleep


def _run_loop_and_capture(pane_id: str, module, run_fn_name: str, use_time_sleep: bool = False) -> dict:
    read_calls, tick_calls, cleanup_calls, fakes = _make_loop_fakes(pane_id)
    saved, saved_wait_for_input, saved_sleep = _patch_module_for_loop(module, use_time_sleep, fakes)

    stop_caught = False
    other_exc = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            getattr(module, run_fn_name)()
    except _ProbeStop:
        stop_caught = True
    except BaseException as e:
        other_exc = e
    finally:
        _restore_module_io(module, saved, saved_wait_for_input, use_time_sleep, saved_sleep)

    log_text = _read_probe_log()

    return {
        'stop_caught': stop_caught,
        'other_exc': other_exc,
        'read_calls': read_calls['n'],
        'tick_calls': tick_calls['n'],
        'cleanup_calls': cleanup_calls,
        'log_text': log_text,
    }


def _assert_survives(pane_id: str, module, run_fn_name: str, use_time_sleep: bool = False) -> None:
    if os.path.exists(_PROBE_LOG_PATH):
        os.remove(_PROBE_LOG_PATH)
    r = _run_loop_and_capture(pane_id, module, run_fn_name, use_time_sleep)
    check(f"[{pane_id}] loop terminated via _ProbeStop, not an unhandled crash",
          r['stop_caught'] and r['other_exc'] is None)
    check(f"[{pane_id}] survived past the crash iteration (>=2 ticks reached)",
          r['tick_calls'] >= 2)
    check(f"[{pane_id}] injected exception logged with this pane's identifier",
          f"[{pane_id}]" in r['log_text'] and f"ProbeInjected:{pane_id}" in r['log_text'])
    check(f"[{pane_id}] full traceback recorded (Traceback... line present)",
          "Traceback (most recent call last):" in r['log_text'])
    check(f"[{pane_id}] finally: cleanup ran (disable_mouse + restore_terminal called)",
          r['cleanup_calls']['disable_mouse'] >= 1 and r['cleanup_calls']['restore_terminal'] >= 1)


def _run_poll_only_loop_and_capture(pane_id: str, module, run_fn_name: str, inject_attr: str) -> dict:
    inject_calls = {'n': 0}
    tick_calls = {'n': 0}

    orig_inject = getattr(module, inject_attr)

    def _fake_inject(*_a, **_kw):
        inject_calls['n'] += 1
        if inject_calls['n'] == 1:
            raise _ProbeInjectedError(f'ProbeInjected:{pane_id}')
        return None

    setattr(module, inject_attr, _fake_inject)

    import time as _time_mod
    saved_sleep = _time_mod.sleep

    def _fake_tick(*_a, **_kw):
        tick_calls['n'] += 1
        if tick_calls['n'] >= _STOP_AFTER_TICKS:
            raise _ProbeStop()

    _time_mod.sleep = _fake_tick

    stop_caught = False
    other_exc = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            getattr(module, run_fn_name)()
    except _ProbeStop:
        stop_caught = True
    except BaseException as e:
        other_exc = e
    finally:
        setattr(module, inject_attr, orig_inject)
        _time_mod.sleep = saved_sleep

    log_text = _read_probe_log()

    return {
        'stop_caught': stop_caught,
        'other_exc': other_exc,
        'inject_calls': inject_calls['n'],
        'tick_calls': tick_calls['n'],
        'log_text': log_text,
    }
