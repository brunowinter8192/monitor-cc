"""
P1 — verifies all 8 pane event loops (7 previously unguarded + worker_tokens_pane.py, the reference
pattern) survive an uncaught exception raised inside the loop body, log it with a pane
identifier via the shared src/pane_error_log.py sink, and keep running — and that the guard
does NOT swallow deliberate termination (KeyboardInterrupt/SystemExit still propagate, `finally:`
cleanup still runs where one exists).

Cannot be verified with a live tmux session (no pane process to kill); instead, each loop's
run_*_loop() is loaded (via importlib, package-qualified — these modules use `from ..constants
import ...` double-dot relative imports, so they must be loaded as real `src.<pkg>.<mod>`
submodules, not path-inserted top-level modules) and invoked directly with its I/O primitives
monkeypatched per-module:
  - 7 of the 8 loops have keyboard/mouse: read_keypress raises a distinctive marker exception on
    its 1st call only, then returns None; setup_keyboard_input/enable_mouse are no-op'd;
    disable_mouse/restore_terminal are counted, to prove the existing `finally:` cleanup still runs
  - the 8th (news_pane/log_pane.py::run_news_log_loop) has NO keyboard/mouse and NO `finally:` —
    it never had one and this milestone does not invent one — so the marker exception is injected
    via find_log_file() instead, and only the catch+log+continue behavior is asserted, not cleanup
  - the tick function (wait_for_input, or time.sleep for news_pane/log_pane.py) counts calls and
    raises _ProbeStop (a BaseException, like Ctrl-C) on the 3rd call — guarantees the loop cannot
    hang, and proves the loop survived 2 full iterations past the injected crash
Real render/data-refresh calls run for real (against whatever real session/tmux state exists on
this machine) — any exception they raise is caught by the SAME new guard and logged with the
SAME pane id, which is harmless to the assertions below (they only check for the specific
injected marker, not for an empty log).

Run from project root or worktree root:
    ./venv/bin/python dev/pane_error_log/p1_pane_loop_survives_exception_probe.py
"""

# INFRASTRUCTURE
import contextlib
import importlib
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'  # built at runtime, not a literal `import src...` — these modules need
                    # package-qualified loading for their `from ..constants import ...` imports

pel = importlib.import_module(f'{_ROOT_PKG}.pane_error_log')
mod_worker_tokens = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
mod_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_worker_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
mod_tokens = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
mod_warnings = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_gpu = importlib.import_module(f'{_ROOT_PKG}.gpu_pane.pane')
mod_news = importlib.import_module(f'{_ROOT_PKG}.news_pane.pane')
mod_news_log = importlib.import_module(f'{_ROOT_PKG}.news_pane.log_pane')

_PROBE_LOG_PATH = '/tmp/_pane_error_log_probe.log'
pel.PANE_ERROR_LOG_PATH = _PROBE_LOG_PATH  # redirect the shared sink so pane tests below never
                                            # touch the real /tmp/monitor_cc_error.log
_STOP_AFTER_TICKS = 3  # tick #1 = crash iteration, #2 = one clean survived iteration, #3 = stop

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# Marker exception injected as the loop body's "unknown crash" — distinct per pane so the shared
# log sink's content can be attributed to the specific run that produced it
class _ProbeInjectedError(Exception):
    pass


# Deliberate-termination stand-in (BaseException, NOT Exception — same MRO relationship as
# KeyboardInterrupt/SystemExit) used to end the otherwise-infinite `while True:` loop
class _ProbeStop(BaseException):
    pass


# FUNCTIONS

# Runs module.<run_fn_name>() with read_keypress/tick monkeypatched (see module docstring);
# returns a dict of everything needed to assert catch+log+continue+cleanup for one pane
def _run_loop_and_capture(pane_id: str, module, run_fn_name: str, use_time_sleep: bool = False) -> dict:
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

    saved = {
        name: getattr(module, name)
        for name in ('read_keypress', 'setup_keyboard_input', 'enable_mouse',
                     'disable_mouse', 'restore_terminal')
        if hasattr(module, name)
    }
    module.read_keypress = _fake_read_keypress
    module.setup_keyboard_input = _noop
    module.enable_mouse = _noop
    module.disable_mouse = _fake_disable_mouse
    module.restore_terminal = _fake_restore_terminal
    saved_wait_for_input = None
    if not use_time_sleep:
        saved_wait_for_input = getattr(module, 'wait_for_input')
        module.wait_for_input = _fake_tick

    import time as _time_mod
    saved_sleep = _time_mod.sleep
    if use_time_sleep:
        _time_mod.sleep = _fake_tick

    stop_caught = False
    other_exc = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            getattr(module, run_fn_name)()
    except _ProbeStop:
        stop_caught = True
    except BaseException as e:  # noqa: BLE001 — captured for assertion, not swallowed
        other_exc = e
    finally:
        for name, fn in saved.items():
            setattr(module, name, fn)
        if saved_wait_for_input is not None:
            module.wait_for_input = saved_wait_for_input
        if use_time_sleep:
            _time_mod.sleep = saved_sleep

    log_text = ''
    if os.path.exists(_PROBE_LOG_PATH):
        log_text = Path(_PROBE_LOG_PATH).read_text()

    return {
        'stop_caught': stop_caught,
        'other_exc': other_exc,
        'read_calls': read_calls['n'],
        'tick_calls': tick_calls['n'],
        'cleanup_calls': cleanup_calls,
        'log_text': log_text,
    }


# Runs the catch+log+continue+cleanup assertions shared by all 7 panes
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


# Runs a keyboard/mouse-less, finally-less loop (currently: news_pane/log_pane.py) with the
# marker exception injected via `inject_attr` instead of read_keypress, and time.sleep as the
# tick counter; returns the same shape of dict as _run_loop_and_capture minus cleanup_calls
# (there is no finally: block here to prove ran)
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
    except BaseException as e:  # noqa: BLE001 — captured for assertion, not swallowed
        other_exc = e
    finally:
        setattr(module, inject_attr, orig_inject)
        _time_mod.sleep = saved_sleep

    log_text = ''
    if os.path.exists(_PROBE_LOG_PATH):
        log_text = Path(_PROBE_LOG_PATH).read_text()

    return {
        'stop_caught': stop_caught,
        'other_exc': other_exc,
        'inject_calls': inject_calls['n'],
        'tick_calls': tick_calls['n'],
        'log_text': log_text,
    }


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


# Test: a failing log write itself must not kill the calling loop (deliverable 4) — exercises
# both failure points inside src/pane_error_log.py: the open()/write() in log_pane_error, and the
# seek()/truncate in _cap_log_size (forced via an artificially tiny MAX_BYTES on a tiny real file)
def test_failing_log_write_does_not_raise():
    print("\n[Test] a failing log write cannot raise out of log_pane_error (deliverable 4)")

    orig_path = pel.PANE_ERROR_LOG_PATH
    pel.PANE_ERROR_LOG_PATH = '/nonexistent_dir_xyz_probe/monitor_cc_error.log'
    try:
        raised = False
        try:
            pel.log_pane_error('probe')
        except Exception:
            raised = True
    finally:
        pel.PANE_ERROR_LOG_PATH = orig_path
    check("open() failure (nonexistent parent dir) does not raise out of log_pane_error", not raised)

    orig_path, orig_max, orig_keep = pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES
    tiny_log = '/tmp/_pane_error_log_probe_tiny.log'
    Path(tiny_log).write_text('short')  # 5 bytes
    pel.PANE_ERROR_LOG_PATH = tiny_log
    pel.PANE_ERROR_LOG_MAX_BYTES = 0             # force the truncation branch on every call
    pel.PANE_ERROR_LOG_KEEP_BYTES = 500_000      # seek(-500000, SEEK_END) on a 5-byte file -> OSError
    try:
        raised = False
        try:
            pel.log_pane_error('probe')
        except Exception:
            raised = True
    finally:
        pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES = orig_path, orig_max, orig_keep
        os.remove(tiny_log)
    check("_cap_log_size seek-underflow (OSError) does not raise out of log_pane_error", not raised)


# Test: the sink is size-capped, not left to grow unbounded
def test_log_size_capping():
    print("\n[Test] sink truncates to its tail once it exceeds the size cap")
    orig_path, orig_max, orig_keep = pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES
    cap_log = '/tmp/_pane_error_log_probe_cap.log'
    Path(cap_log).write_text('X' * 1000 + 'TAIL_MARKER')
    pel.PANE_ERROR_LOG_PATH = cap_log
    pel.PANE_ERROR_LOG_MAX_BYTES = 500
    pel.PANE_ERROR_LOG_KEEP_BYTES = 20
    try:
        pel._cap_log_size()
        text = Path(cap_log).read_text()
    finally:
        pel.PANE_ERROR_LOG_PATH, pel.PANE_ERROR_LOG_MAX_BYTES, pel.PANE_ERROR_LOG_KEEP_BYTES = orig_path, orig_max, orig_keep
        os.remove(cap_log)
    check("oversized sink truncated below the pre-cap size", len(text) < 1011)
    check("truncated sink kept the TAIL (most recent bytes), not the head", text.endswith('TAIL_MARKER'))


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("pane_error_log probe — 8 pane loops survive an uncaught exception")
    print("=" * 70)
    test_worker_tokens_pane()
    test_proxy_pane()
    test_worker_proxy_pane()
    test_tokens_pane()
    test_warnings_pane()
    test_gpu_pane()
    test_news_pane()
    test_news_log_pane()
    test_keyboard_interrupt_and_system_exit_not_swallowed()
    test_failing_log_write_does_not_raise()
    test_log_size_capping()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "pane_error_log" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p1_pane_loop_survives_exception_probe_{stamp}.md"
    lines = [
        f"# P1 — pane_error_log probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
