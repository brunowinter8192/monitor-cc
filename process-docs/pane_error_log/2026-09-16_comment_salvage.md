# 2026-09-16 — Comment/docstring salvage for dev/pane_error_log/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/pane_error_log/` (6 `.py` files, 501 LOC) into conformance with the
project's three-marker comment standard. Every comment and the one docstring below were relocated
here verbatim before deletion from the code. Zero `__doc__`/`argparse` hits, so the one docstring
found (`p1_pane_loop_survives_exception_probe.py`) was not load-bearing and deleted outright.

**Confirmed runnable and run for real, per Main's note.** `p1_pane_loop_survives_exception_probe.py`
is the entry script; the other 5 files are libraries with no `__main__`. Every real terminal I/O
primitive each of the 8 tested pane loops touches (`read_keypress`, `setup_keyboard_input`,
`enable_mouse`, `disable_mouse`, `restore_terminal`, `wait_for_input`/`time.sleep`) is monkeypatched
per-module before the loop runs — confirmed by reading `p1_loop_harness.py` in full. Only the real
render/data-refresh calls inside each loop body run for real, against whatever real session/tmux
state exists on this machine (read-only). Ran the probe before and after the edit:
**46/47 checks passed both times**, with the identical single pre-existing failure
(`[news_log] injected exception logged with this pane's identifier`) — unrelated to this milestone,
not investigated or fixed here (out of scope; the milestone is comments/docstrings only). Full
stdout diffed byte-for-byte excluding only the `Report written to: .../<timestamp>.md` line. The
timestamped report this script wrote on both verification runs was deleted by exact filename
afterward (never a wildcard) — `md/` already holds 16 pre-existing tracked reports from real prior
runs, untouched.

---

## Salvage from dev/pane_error_log/p1_shared.py

Was line 6, trailing on the `_STOP_AFTER_TICKS` assignment:
```
_STOP_AFTER_TICKS = 3  # tick #1 = crash iteration, #2 = one clean survived iteration, #3 = stop
```
(the comment token itself is `# tick #1 = crash iteration, #2 = one clean survived iteration, #3 = stop`)

Was lines 13-14 (above `_ProbeInjectedError`):
```
# Marker exception injected as the loop body's "unknown crash" — distinct per pane so the shared
# log sink's content can be attributed to the specific run that produced it
```

Was lines 19-20 (above `_ProbeStop`):
```
# Deliberate-termination stand-in (BaseException, NOT Exception — same MRO relationship as
# KeyboardInterrupt/SystemExit) used to end the otherwise-infinite `while True:` loop
```

## Salvage from dev/pane_error_log/p1_pane_modules.py

Was lines 13-14, trailing on / continuing the `_ROOT_PKG` assignment:
```
_ROOT_PKG = 'src'  # built at runtime, not a literal `import src...` — these modules need
                    # package-qualified loading for their `from ../constants import ...` imports
```
(the comment tokens themselves are `# built at runtime, not a literal \`import src...\` — these modules need`
and `# package-qualified loading for their \`from ../constants import ...\` imports`)

Was lines 26-27, trailing on / continuing the `pel.PANE_ERROR_LOG_PATH` assignment:
```
pel.PANE_ERROR_LOG_PATH = _PROBE_LOG_PATH  # redirect the shared sink so pane tests below never
                                            # touch the real /tmp/monitor_cc_error.log
```
(the comment tokens themselves are `# redirect the shared sink so pane tests below never`
and `# touch the real /tmp/monitor_cc_error.log`)

## Salvage from dev/pane_error_log/p1_loop_harness.py

Was lines 81-82 (above `_run_loop_and_capture`):
```
# Runs module.<run_fn_name>() with read_keypress/tick monkeypatched (see module docstring);
# returns a dict of everything needed to assert catch+log+continue+cleanup for one pane
```

Was line 94, trailing on an `except` clause (inside `_run_loop_and_capture`):
```
    except BaseException as e:  # noqa: BLE001 — captured for assertion, not swallowed
```
(the comment token itself is `# noqa: BLE001 — captured for assertion, not swallowed`)

Was line 111 (above `_assert_survives`):
```
# Runs the catch+log+continue+cleanup assertions shared by all 7 panes
```

Was lines 128-131 (above `_run_poll_only_loop_and_capture`):
```
# Runs a keyboard/mouse-less, finally-less loop (currently: news_pane/log_pane.py) with the
# marker exception injected via `inject_attr` instead of read_keypress, and time.sleep as the
# tick counter; returns the same shape of dict as _run_loop_and_capture minus cleanup_calls
# (there is no finally: block here to prove ran)
```

Was line 163, trailing on an `except` clause (inside `_run_poll_only_loop_and_capture`):
```
    except BaseException as e:  # noqa: BLE001 — captured for assertion, not swallowed
```
(the comment token itself is `# noqa: BLE001 — captured for assertion, not swallowed`)

## Salvage from dev/pane_error_log/p1_pane_tests.py

Was lines 66-69 (above `test_keyboard_interrupt_and_system_exit_not_swallowed`):
```
# Test: the guard must not swallow deliberate termination — real KeyboardInterrupt and SystemExit
# both propagate out of the loop, and `finally:` cleanup still runs (checked on one representative
# pane; the _ProbeStop-based BaseException path above already proves the same MRO relationship
# for all 7, since KeyboardInterrupt/SystemExit/_ProbeStop are all BaseException, not Exception)
```

## Salvage from dev/pane_error_log/p1_sink_tests.py

Was lines 11-13 (above `test_failing_log_write_does_not_raise`):
```
# Test: a failing log write itself must not kill the calling loop (deliverable 4) — exercises
# both failure points inside src/pane_error_log.py: the open()/write() in log_pane_error, and the
# seek()/truncate in _cap_log_size (forced via an artificially tiny MAX_BYTES on a tiny real file)
```

Was line 31, trailing on a statement (inside `test_failing_log_write_does_not_raise`):
```
    Path(tiny_log).write_text('short')  # 5 bytes
```
(the comment token itself is `# 5 bytes`)

Was line 33, trailing on a statement (same function):
```
    pel.PANE_ERROR_LOG_MAX_BYTES = 0             # force the truncation branch on every call
```
(the comment token itself is `# force the truncation branch on every call`)

Was line 34, trailing on a statement (same function):
```
    pel.PANE_ERROR_LOG_KEEP_BYTES = 500_000      # seek(-500000, SEEK_END) on a 5-byte file -> OSError
```
(the comment token itself is `# seek(-500000, SEEK_END) on a 5-byte file -> OSError`)

Was line 47 (above `test_log_size_capping`):
```
# Test: the sink is size-capped, not left to grow unbounded
```

## Salvage from dev/pane_error_log/p1_pane_loop_survives_exception_probe.py

Module docstring (was lines 1-29):
```
P1 — verifies all 8 pane event loops (7 previously unguarded + worker_tokens_pane.py, the reference
pattern) survive an uncaught exception raised inside the loop body, log it with a pane
identifier via the shared src/pane_error_log.py sink, and keep running — and that the guard
does NOT swallow deliberate termination (KeyboardInterrupt/SystemExit still propagate, `finally:`
cleanup still runs where one exists).

Cannot be verified with a live tmux session (no pane process to kill); instead, each loop's
run_*_loop() is loaded (via importlib, package-qualified — these modules use `from ../constants
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
```

## Salvage from dev/pane_error_log/DOCS.md

No section, subsection, or bullet in the pre-rewrite `DOCS.md` fell outside the mandated format —
it already carried only Role / Flow / Modules (5-field, some fields honestly left blank) with no
extra subsections and no trailing Gotchas-style section. Nothing to cut here; this heading exists
for completeness of the walk. The rewrite adds the two sections the pre-rewrite version lacked
(`## Public Interface`, `## State`) without removing any existing content.
