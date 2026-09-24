# pane_error_log probe: 8 pane loops survive an uncaught exception

11/11 strands passed

## PASS test_worker_tokens_pane


[Test] worker-tokens pane (src/workers/worker_tokens_pane.py) — reference pattern, re-checked
  PASS  [worker_tokens] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [worker_tokens] survived past the crash iteration (>=2 ticks reached)
  PASS  [worker_tokens] injected exception logged with this pane's identifier
  PASS  [worker_tokens] full traceback recorded (Traceback... line present)
  PASS  [worker_tokens] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_proxy_pane


[Test] proxy pane (src/proxy_display/pane.py)
  PASS  [proxy] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [proxy] survived past the crash iteration (>=2 ticks reached)
  PASS  [proxy] injected exception logged with this pane's identifier
  PASS  [proxy] full traceback recorded (Traceback... line present)
  PASS  [proxy] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_worker_proxy_pane


[Test] worker-proxy pane (src/proxy_display/worker_proxy_pane.py)
  PASS  [worker_proxy] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [worker_proxy] survived past the crash iteration (>=2 ticks reached)
  PASS  [worker_proxy] injected exception logged with this pane's identifier
  PASS  [worker_proxy] full traceback recorded (Traceback... line present)
  PASS  [worker_proxy] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_tokens_pane


[Test] tokens pane (src/panes/token_pane.py)
  PASS  [tokens] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [tokens] survived past the crash iteration (>=2 ticks reached)
  PASS  [tokens] injected exception logged with this pane's identifier
  PASS  [tokens] full traceback recorded (Traceback... line present)
  PASS  [tokens] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_warnings_pane


[Test] warnings pane (src/panes/warnings_pane.py)
  PASS  [warnings] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [warnings] survived past the crash iteration (>=2 ticks reached)
  PASS  [warnings] injected exception logged with this pane's identifier
  PASS  [warnings] full traceback recorded (Traceback... line present)
  PASS  [warnings] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_gpu_pane


[Test] gpu pane (src/gpu_pane/pane.py)
  PASS  [gpu] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [gpu] survived past the crash iteration (>=2 ticks reached)
  PASS  [gpu] injected exception logged with this pane's identifier
  PASS  [gpu] full traceback recorded (Traceback... line present)
  PASS  [gpu] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_news_pane


[Test] news pane (src/news_pane/pane.py)
  PASS  [news] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [news] survived past the crash iteration (>=2 ticks reached)
  PASS  [news] injected exception logged with this pane's identifier
  PASS  [news] full traceback recorded (Traceback... line present)
  PASS  [news] finally: cleanup ran (disable_mouse + restore_terminal called)

## PASS test_news_log_pane


[Test] news-log pane (src/news_pane/log_pane.py) — no mouse, no finally: (never had one)
  PASS  [news_log] loop terminated via _ProbeStop, not an unhandled crash
  PASS  [news_log] survived past the crash iteration (>=2 ticks reached)
  PASS  [news_log] injected exception logged with this pane's identifier
  PASS  [news_log] full traceback recorded (Traceback... line present)

## PASS test_keyboard_interrupt_and_system_exit_not_swallowed


[Test] KeyboardInterrupt / SystemExit propagate, finally: cleanup still runs (proxy pane)
  PASS  KeyboardInterrupt propagates out of run_proxy_loop (not caught by except Exception)
  PASS  KeyboardInterrupt: finally: cleanup ran
  PASS  SystemExit propagates out of run_proxy_loop (not caught by except Exception)
  PASS  SystemExit: finally: cleanup ran

## PASS test_failing_log_write_does_not_raise


[Test] a failing log write cannot raise out of log_pane_error (deliverable 4)
  PASS  open() failure (nonexistent parent dir) does not raise out of log_pane_error
  PASS  _cap_log_size seek-underflow (OSError) does not raise out of log_pane_error

## PASS test_log_size_capping


[Test] sink truncates to its tail once it exceeds the size cap
  PASS  oversized sink truncated below the pre-cap size
  PASS  truncated sink kept the TAIL (most recent bytes), not the head
