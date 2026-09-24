# dev/pane_error_log/

## Role
Regression coverage for `src/pane_error_log.py` (the exception-safe logging sink) and the per-loop
exception guard wrapping each pane's `run_*_loop()`. Verifies catch+log+continue without a live
tmux session by invoking each loop directly with its I/O primitives monkeypatched. Touch when
adding a pane loop or changing a loop's `while True:` shape or `pane_error_log.py` itself.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/pane_error_log/p1_pane_loop_survives_exception_probe.py`.

## Flow
Each of the 8 pane-loop functions is imported directly, driven through a few ticks with a marker
exception injected on its first I/O call, and asserted to survive, log the marker via
`pane_error_log`, and still run its cleanup path — each test function is one parallel fail-fast strand (subprocess, `dev/refactoring/strand_runner.py`), and the output is a fixed-name report in `md/`. The probe log lives in a per-process temp directory, so strands share no file; `os.get_terminal_size` is pinned to 220x50 because `news_log` calls it before the injected read.

## Modules

### p1_pane_loop_survives_exception_probe.py (38 LOC)

**Purpose:** Entry point — launches the 11 test functions (8 pane loops, the guard-does-not-swallow-termination case, 2 sink tests) as parallel strands and writes the fixed-name report.
**Reads:** nothing directly; delegates to `p1_pane_tests.py`/`p1_sink_tests.py`.
**Writes:** `md/p1_pane_loop_survives_exception_probe.md`.
**Called by:** none — manual regression guard, re-run after changing a pane loop's `while True:`
shape or `pane_error_log.py`.
**Calls out:** none directly — imports `p1_shared.py`, `p1_pane_modules.py`, `p1_pane_tests.py`,
`p1_sink_tests.py`.

---

### p1_shared.py (35 LOC)

**Purpose:** Shared probe primitives: the fail-fast `check()` (re-exported from the strand runner), the
`_ProbeInjectedError`/`_ProbeStop` marker exceptions, the per-process scratch log paths, and `_read_probe_log()`.
**Reads:** the scratch log at `_PROBE_LOG_PATH` (via `_read_probe_log`).
**Writes:** a `mkdtemp` directory removed at exit.
**Called by:** every other module in this directory.

---

### p1_pane_modules.py (28 LOC)

**Purpose:** Resolves `WORKTREE_ROOT`, loads `src.pane_error_log` and the 8 real pane modules under
test via `importlib.import_module` (package-qualified, since these modules use double-dot relative
imports), and redirects `pane_error_log.PANE_ERROR_LOG_PATH` to the scratch file for the run.
**Reads:** whatever real session/tmux/RAG state the imported pane modules touch at import time.
**Writes:** `pel.PANE_ERROR_LOG_PATH` (module attribute, redirect only).
**Called by:** `p1_loop_harness.py`, `p1_pane_tests.py`, `p1_sink_tests.py`,
`p1_pane_loop_survives_exception_probe.py` (for `WORKTREE_ROOT`).
**Calls out:** `src.pane_error_log`, `src.workers.worker_tokens_pane`, `src.proxy_display.pane`,
`src.proxy_display.worker_proxy_pane`, `src.panes.token_pane`, `src.panes.warnings_pane`,
`src.gpu_pane.pane`, `src.news_pane.pane`, `src.news_pane.log_pane`.

---

### p1_loop_harness.py (170 LOC)

**Purpose:** Drives one pane loop under monkeypatched I/O and captures the result: build fakes
(`_make_loop_fakes`), patch the module (`_patch_module_for_loop`), restore it
(`_restore_module_io`), run+capture for the 7 keyboard/mouse loops (`_run_loop_and_capture`,
`_assert_survives`) and for the keyboard/mouse-less `news_log` loop
(`_run_poll_only_loop_and_capture`).
**Reads:** the scratch log via `p1_shared._read_probe_log`.
**Writes:** nothing directly — monkeypatches the module passed in, restored before returning.
**Called by:** `p1_pane_tests.py`.

---

### p1_pane_tests.py (97 LOC)

**Purpose:** One test function per pane loop (`test_worker_tokens_pane` ... `test_news_pane`,
`test_news_log_pane`) plus `test_keyboard_interrupt_and_system_exit_not_swallowed` (verifies the
guard does not swallow deliberate termination).
**Reads:** nothing directly.
**Writes:** nothing directly.
**Called by:** `p1_pane_loop_survives_exception_probe.py`.

---

### p1_sink_tests.py (59 LOC)

**Purpose:** `test_failing_log_write_does_not_raise` and `test_log_size_capping` — test
`src/pane_error_log.py`'s own internals directly (no pane loop involved).
**Reads:** nothing directly.
**Writes:** creates/removes its own scratch files inside the per-process probe directory.
**Called by:** `p1_pane_loop_survives_exception_probe.py`.

---

## State
No module-level mutable results state. Each strand is its own process: `p1_shared.py` creates that process's scratch directory, `p1_pane_modules.py` redirects `pel.PANE_ERROR_LOG_PATH` into it and pins the terminal size; both are read by every test module.
