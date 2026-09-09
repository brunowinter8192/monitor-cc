# P1 — pane_error_log probe run (2026-09-09T13:33:32.520413+00:00)

**Result: 47/47 checks passed**

| Check | Result |
|---|---|
| [workers] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [workers] survived past the crash iteration (>=2 ticks reached) | PASS |
| [workers] injected exception logged with this pane's identifier | PASS |
| [workers] full traceback recorded (Traceback... line present) | PASS |
| [workers] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [proxy] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [proxy] survived past the crash iteration (>=2 ticks reached) | PASS |
| [proxy] injected exception logged with this pane's identifier | PASS |
| [proxy] full traceback recorded (Traceback... line present) | PASS |
| [proxy] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [worker_proxy] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [worker_proxy] survived past the crash iteration (>=2 ticks reached) | PASS |
| [worker_proxy] injected exception logged with this pane's identifier | PASS |
| [worker_proxy] full traceback recorded (Traceback... line present) | PASS |
| [worker_proxy] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [tokens] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [tokens] survived past the crash iteration (>=2 ticks reached) | PASS |
| [tokens] injected exception logged with this pane's identifier | PASS |
| [tokens] full traceback recorded (Traceback... line present) | PASS |
| [tokens] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [warnings] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [warnings] survived past the crash iteration (>=2 ticks reached) | PASS |
| [warnings] injected exception logged with this pane's identifier | PASS |
| [warnings] full traceback recorded (Traceback... line present) | PASS |
| [warnings] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [gpu] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [gpu] survived past the crash iteration (>=2 ticks reached) | PASS |
| [gpu] injected exception logged with this pane's identifier | PASS |
| [gpu] full traceback recorded (Traceback... line present) | PASS |
| [gpu] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [news] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [news] survived past the crash iteration (>=2 ticks reached) | PASS |
| [news] injected exception logged with this pane's identifier | PASS |
| [news] full traceback recorded (Traceback... line present) | PASS |
| [news] finally: cleanup ran (disable_mouse + restore_terminal called) | PASS |
| [news_log] loop terminated via _ProbeStop, not an unhandled crash | PASS |
| [news_log] survived past the crash iteration (>=2 ticks reached) | PASS |
| [news_log] injected exception logged with this pane's identifier | PASS |
| [news_log] full traceback recorded (Traceback... line present) | PASS |
| KeyboardInterrupt propagates out of run_proxy_loop (not caught by except Exception) | PASS |
| KeyboardInterrupt: finally: cleanup ran | PASS |
| SystemExit propagates out of run_proxy_loop (not caught by except Exception) | PASS |
| SystemExit: finally: cleanup ran | PASS |
| open() failure (nonexistent parent dir) does not raise out of log_pane_error | PASS |
| _cap_log_size seek-underflow (OSError) does not raise out of log_pane_error | PASS |
| oversized sink truncated below the pre-cap size | PASS |
| truncated sink kept the TAIL (most recent bytes), not the head | PASS |
