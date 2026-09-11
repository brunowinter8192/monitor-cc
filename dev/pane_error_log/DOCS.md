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

### p1_pane_loop_survives_exception_probe.py (429 LOC)

**Purpose:** For 7 of the 8 pane loops (`run_proxy_loop`, `run_worker_proxy_loop`,
`run_tokens_loop`, `run_warnings_loop`, `run_gpu_loop`, `run_news_loop`, `run_workers_loop`):
injects a marker exception on the loop's first `read_keypress()` call, forces a bounded exit after 3
ticks, and asserts the exception was caught, logged with the correct pane identifier and full
traceback, and that `finally: disable_mouse(); restore_terminal()` still ran. For the 8th
(`run_news_log_loop`, no keyboard/mouse and no `finally:`), the marker exception is injected via
`find_log_file()` instead and only catch+log+continue is asserted. Also verifies a real
`KeyboardInterrupt`/`SystemExit` still propagates, that a failing log write cannot raise out of
`log_pane_error`, and that the sink truncates to its tail once it exceeds its size cap.
**Reads:** whatever real session/tmux/RAG state exists on the machine — each loop's real
data-refresh/render path runs unmocked past the injected first-call crash.
**Writes:** `md/p1_pane_loop_survives_exception_probe_<timestamp>.md`; redirects
`pane_error_log.PANE_ERROR_LOG_PATH` to a scratch file under the system temp directory for the run.
**Called by:** none — manual regression guard, re-run after changing a pane loop's `while True:`
shape or `pane_error_log.py`.
**Calls out:** `src.pane_error_log`, `src.workers.worker_pane`, `src.proxy_display.pane`,
`src.proxy_display.worker_proxy_pane`, `src.panes.token_pane`, `src.panes.warnings_pane`,
`src.gpu_pane.pane`, `src.news_pane.pane`, `src.news_pane.log_pane` — loaded via
`importlib.import_module` (package-qualified, since these modules use double-dot relative imports).
