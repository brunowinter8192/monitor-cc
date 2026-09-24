# timer-loop test structure, Phase 3 fix (2026-09-24)

`test_abort_stamp_scope.py` read the size of the live menubar log (`~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log`), ran production code that appends to it, and asserted on the appended tail. The menubar app appends latency lines to the same file every few seconds (observed: 161 bytes of growth during one test run), so the tail assertion depended on the app being idle.

Fix: `src.menubar.menubar_log.MENUBAR_LOG` is a module global read at call time by `log_menubar`, so `unittest.mock.patch.object(menubar_log_mod, 'MENUBAR_LOG', scratch)` redirects the abort log line into the test's temp dir. The `time.sleep(0.3)` after spawning the fixture processes became polling on `bg_timer._resolve_pid_output_file(pid)` until lsof sees each output file (10 s deadline, raises RuntimeError otherwise). The script is now one fail-fast strand via `dev/refactoring/strand_runner.py`.

Proof: the last `abort_stamp_scope` line in the live log is from 2026-09-16 (earlier runs); runs on 2026-09-24 left none. 6 of 6 checks pass, three consecutive runs.
