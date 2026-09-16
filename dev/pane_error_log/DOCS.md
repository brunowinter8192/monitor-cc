# dev/pane_error_log/

## Role
Regression coverage for `src/pane_error_log.py` (the shared exception-safe logging sink) and the
per-loop exception guard wrapping each pane's `run_*_loop()` function. Verifies catch+log+continue
end to end without a live tmux session, since a pane crash cannot be reproduced by killing a real
pane process — each loop is invoked directly with its I/O primitives monkeypatched. Touch when
adding a new pane loop or changing an existing loop's `while True:` shape or `pane_error_log.py`
itself. `md/` holds every run's report.

## Flow
Each of the 8 pane-loop functions is imported directly, driven through a few ticks with a marker
exception injected on its first I/O call, and asserted to survive, log the marker via
`pane_error_log`, and still run its cleanup path — output goes to a timestamped report in `md/`.

## Modules

### p1_pane_loop_survives_exception_probe.py (96 LOC)

**Purpose:** Entry point — module docstring documents the full probe design (see there). Runs the
9 test functions in order, tallies `_RESULTS`, writes the timestamped report.
**Reads:** nothing directly; delegates to `p1_pane_tests.py`/`p1_sink_tests.py`.
**Writes:** `md/p1_pane_loop_survives_exception_probe_<timestamp>.md`.
**Called by:** none — manual regression guard, re-run after changing a pane loop's `while True:`
shape or `pane_error_log.py`.
**Calls out:** none directly — imports `p1_shared.py`, `p1_pane_modules.py`, `p1_pane_tests.py`,
`p1_sink_tests.py`.

---

### p1_shared.py (37 LOC)

**Purpose:** Shared probe primitives: `check()` (records + prints one PASS/FAIL), `_RESULTS`, the
`_ProbeInjectedError`/`_ProbeStop` marker exceptions, the scratch log path, and `_read_probe_log()`.
**Reads:** the scratch log at `_PROBE_LOG_PATH` (via `_read_probe_log`).
**Writes:** appends to `_RESULTS` (via `check`).
**Called by:** every other module in this directory.

---

### p1_pane_modules.py (27 LOC)

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

### p1_loop_harness.py (177 LOC)

**Purpose:** Drives one pane loop under monkeypatched I/O and captures the result: build fakes
(`_make_loop_fakes`), patch the module (`_patch_module_for_loop`), restore it
(`_restore_module_io`), run+capture for the 7 keyboard/mouse loops (`_run_loop_and_capture`,
`_assert_survives`) and for the keyboard/mouse-less `news_log` loop
(`_run_poll_only_loop_and_capture`).
**Reads:** the scratch log via `p1_shared._read_probe_log`.
**Writes:** nothing directly — monkeypatches the module passed in, restored before returning.
**Called by:** `p1_pane_tests.py`.

---

### p1_pane_tests.py (101 LOC)

**Purpose:** One test function per pane loop (`test_worker_tokens_pane` ... `test_news_pane`,
`test_news_log_pane`) plus `test_keyboard_interrupt_and_system_exit_not_swallowed` (verifies the
guard does not swallow deliberate termination).
**Reads:** nothing directly.
**Writes:** appends to `_RESULTS` (via `check`, from the harness's assertion helpers).
**Called by:** `p1_pane_loop_survives_exception_probe.py`.

---

### p1_sink_tests.py (63 LOC)

**Purpose:** `test_failing_log_write_does_not_raise` and `test_log_size_capping` — test
`src/pane_error_log.py`'s own internals directly (no pane loop involved).
**Reads:** nothing directly.
**Writes:** creates/removes its own scratch files under `/tmp/`; appends to `_RESULTS`.
**Called by:** `p1_pane_loop_survives_exception_probe.py`.
