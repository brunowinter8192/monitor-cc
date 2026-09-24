# dev/pane_error_log/

## Role
Regression coverage for the exception-safe pane error log sink in `src/` and the per-loop exception guard wrapping each pane loop. Verifies catch, log and continue without a live tmux session. Touch when adding a pane loop or changing a loop's shape or the sink.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/pane_error_log/p1_pane_loop_survives_exception_probe.py`.

## Flow
Each pane loop is imported directly and driven through a few ticks with a marker exception injected on its first I/O call. The test asserts it survives, logs the marker and still runs cleanup. Each test is one parallel fail-fast strand with its own temp log; output is a fixed-name report in `md/`.

## Modules

### p1_pane_loop_survives_exception_probe.py (38 LOC)

**Purpose:** Entry point: launches the pane-loop, termination and sink tests as parallel strands and writes the report.
**Reads:** nothing directly; delegates to the test modules.
**Writes:** `md/p1_pane_loop_survives_exception_probe.md`.
**Called by:** none; manual guard.
**Calls out:** `p1_shared.py`, `p1_pane_modules.py`, `p1_pane_tests.py`, `p1_sink_tests.py`.

---

### p1_shared.py (35 LOC)

**Purpose:** Shared probe primitives: fail-fast check, marker exceptions, per-process scratch log paths and a log reader.
**Reads:** the scratch probe log.
**Writes:** a temp directory removed at exit.
**Called by:** every other module in this directory.
**Calls out:** none.

---

### p1_pane_modules.py (28 LOC)

**Purpose:** Loads the sink and the real pane modules under test via `importlib` and redirects the sink's log path to the scratch file.
**Reads:** whatever real session, tmux or RAG state the pane modules touch at import.
**Writes:** the sink module's log path attribute (redirect only).
**Called by:** `p1_loop_harness.py`, `p1_pane_tests.py`, `p1_sink_tests.py`, `p1_pane_loop_survives_exception_probe.py`.
**Calls out:** `src.pane_error_log` and the pane modules of `src.workers`, `src.proxy_display`, `src.panes`, `src.gpu_pane`, `src.news_pane`.

---

### p1_loop_harness.py (170 LOC)

**Purpose:** Drives one pane loop under monkeypatched I/O and captures the outcome, for keyboard and mouse loops and the poll-only log loop.
**Reads:** the scratch log via the shared reader.
**Writes:** nothing directly; monkeypatches the module under test and restores it.
**Called by:** `p1_pane_tests.py`.
**Calls out:** `p1_shared.py`, `p1_pane_modules.py`.

---

### p1_pane_tests.py (97 LOC)

**Purpose:** One test per pane loop plus a test that the guard does not swallow deliberate termination.
**Reads:** nothing directly.
**Writes:** nothing directly.
**Called by:** `p1_pane_loop_survives_exception_probe.py`.
**Calls out:** `p1_loop_harness.py`, `p1_pane_modules.py`, `p1_shared.py`.

---

### p1_sink_tests.py (59 LOC)

**Purpose:** Tests the sink's own internals directly: failing log writes do not raise, log size is capped.
**Reads:** nothing directly.
**Writes:** its own scratch files inside the per-process probe directory.
**Called by:** `p1_pane_loop_survives_exception_probe.py`.
**Calls out:** `p1_pane_modules.py`, `p1_shared.py`.

---

## State
No shared result state. Each strand is its own process with its own scratch directory, redirected sink path and pinned terminal size.
