# 2026-09-16 — dev/pane_error_log/ cohesion split

## What happened

`dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` was 429 LOC (over
the 400-LOC file threshold) with one function over the 50-line function
threshold: `_run_loop_and_capture` at 75 lines. Split into six files along five
concerns that were already visible in the single file's own layout (shared
primitives / which real modules are under test / loop-harness mechanics /
per-pane test cases / `pane_error_log.py`-internals tests):

- `p1_pane_loop_survives_exception_probe.py` (96 LOC) — entry script, unchanged
  filename, module docstring kept verbatim. INFRASTRUCTURE (imports from the 5
  siblings below) + ORCHESTRATOR (`run_probe_workflow`) + FUNCTIONS
  (`_write_report` only — this is specific to how the entry point reports its
  own run, not shared by any sibling).
- `p1_shared.py` (37 LOC) — `check()`, `_RESULTS`, `_PROBE_LOG_PATH`,
  `_STOP_AFTER_TICKS`, `_ProbeInjectedError`, `_ProbeStop`, and a new
  `_read_probe_log()` helper factored out of two literally-duplicated 3-line
  "read the scratch log if it exists" blocks that already existed inside both
  harness functions in the original file (this was already duplicated code
  before the split, not something the split introduced).
- `p1_pane_modules.py` (27 LOC) — the `WORKTREE_ROOT`/`sys.path`/env bootstrap,
  the 9 `importlib.import_module` loads, and the `pel.PANE_ERROR_LOG_PATH`
  redirect.
- `p1_loop_harness.py` (177 LOC) — `_run_loop_and_capture` split into
  `_make_loop_fakes` (build the 5 fake I/O functions + 3 tracking dicts),
  `_patch_module_for_loop` (monkeypatch + save originals), `_restore_module_io`
  (the `finally:`-block restore), and a ~26-line `_run_loop_and_capture`
  composing them around the UNCHANGED try/except/finally skeleton; plus
  `_assert_survives` and `_run_poll_only_loop_and_capture` (structurally
  unchanged, just now calling the shared `_read_probe_log`). Longest function
  after the split: `_run_poll_only_loop_and_capture` at 46 lines.
- `p1_pane_tests.py` (101 LOC) — the 7 thin `test_*_pane()` wrappers,
  `test_news_log_pane`, `test_keyboard_interrupt_and_system_exit_not_swallowed`.
- `p1_sink_tests.py` (63 LOC) — `test_failing_log_write_does_not_raise`,
  `test_log_size_capping` — these never touch a pane loop, they call
  `pel.log_pane_error`/`pel._cap_log_size` directly; a clearly separate concern
  from the loop-guard tests, worth its own file even though small.

Naming: all siblings prefixed `p1_` (the entry script's own prefix), per the
`report.py`-collision lesson from the immediately preceding
`hook_error_correlation` split (documented in that area — see
`process-docs/hook_error_correlation/`) — never name a dev/ sibling module a
bare noun.

## The one real bug this split's mechanical-extraction method caught in itself

While line-slicing `_run_poll_only_loop_and_capture`'s body out of the backup,
my first draft accidentally dropped the `except _ProbeStop: / except
BaseException as e:` clauses between the `try:` and `finally:` blocks — I had
sliced lines 218-250 (stopping right after the `getattr(module,
run_fn_name)()` call, before the `except` clauses at 251-254) and then
hand-typed a `finally:` block after it, silently deleting the two `except`
clauses in between. This would have been a real behavior change: without the
`except _ProbeStop` clause, the loop-terminating `_ProbeStop` exception would
propagate all the way past the `finally:` and out of the function instead of
being caught and turned into `stop_caught = True` — the entire test would then
report a Python traceback instead of a clean PASS/FAIL. Caught by re-reading
the diff against the exact line numbers before running anything (never
trusted the first mechanical slice without a byte-for-byte side-by-side check
against the original source afterward). **Lesson for the next split: when a
try/except/finally block spans more lines than fit in one `seg(a, b)` call,
slice through the LAST line of the LAST except clause, never stop at the last
line you remember being "the interesting part" — re-verify against
`grep -n` line numbers on the actual backup file, not against a mental model
built while reading the file earlier in the same session.**

## Verification — two layers, both actually run

Unlike the previous two splits in this project (`strip_fp_tool_result`,
`hook_error_correlation`), this milestone's instructions specifically directed
running the real script end-to-end before and after, since it had already been
classified read-only-safe. Did both layers:

1. **Primary evidence — real run, before and after.** Backed up the original
   file, ran `./venv/bin/python
   dev/pane_error_log/p1_pane_loop_survives_exception_probe.py` against real
   `src.panes`/`src.gpu_pane`/`src.news_pane`/etc. modules and whatever real
   tmux/session state exists on this machine, captured full stdout + the
   written report. Then implemented the split and ran the new entry script the
   same way. Diffed both (normalizing only the one inherently-volatile line
   each side has — the `Report written to: <path>` stdout line, since the
   timestamp changes every run — and the report's own title line, which
   embeds an ISO timestamp). Result: **stdout PASS/FAIL transcript
   byte-identical after normalization, report body byte-identical after
   normalization, same exit code (`1`), same single pre-existing failure**
   (see below). Deleted both generated report files under
   `dev/pane_error_log/md/` before committing — they are verification
   artifacts, not deliverables.
2. **Secondary evidence — synthetic fake-module harness check.** Loaded the
   backup via `importlib.util.spec_from_file_location` (copied into the real
   `dev/pane_error_log/` directory under a throwaway filename first — loading
   straight from `/tmp/` breaks path-resolution-at-import-time code the same
   way it did in the `hook_error_correlation` split; see that area's
   process-docs for why). Built a `types.SimpleNamespace` fake pane module
   (not any real `src.panes.*` module) exposing exactly the attributes
   `_run_loop_and_capture`/`_run_poll_only_loop_and_capture` touch, called
   both the backup's and the new `p1_loop_harness`'s versions of both
   functions against the identical fake module, and asserted the returned
   dicts equal (with `other_exc` normalized to its exception class name, since
   two separately-raised `_ProbeStop`/`_ProbeInjectedError` instances from two
   different module objects are never `==` to each other by identity — same
   normalization concern as comparing exception objects across two isolated
   module loads). Result: **both cases equal.**

## Pre-existing failure, not caused by this split

Both the before-run and the after-run report **46/47 checks passed**, with
the exact same single failure both times: `[news_log] injected exception
logged with this pane's identifier`. This is a pre-existing flake/bug in the
probe or in `news_pane/log_pane.py`'s interaction with the shared log sink,
unrelated to this split (identical on both sides of the diff, confirming the
split did not change it). Not investigated further — out of this milestone's
scope, which is LOC/function-length only. **Whoever picks up
`dev/pane_error_log/` next: this failure already exists on the `beta`
worktree's integration branch before this split; do not treat it as something
this refactor broke.**

## Hazard classification (for the record)

Confirmed read-only with respect to real macOS desktop/window/Space/hotkey/
monitor-restart control, as stated before implementation: every I/O primitive
a pane loop could use to touch the real terminal (`setup_keyboard_input`,
`enable_mouse`, `disable_mouse`, `restore_terminal`, `read_keypress`,
`wait_for_input`/`time.sleep`) is monkeypatched to a fake/no-op before the
loop runs, and all of the loop body's stdout is captured into an in-memory
`io.StringIO()`, never reaching the real terminal. Confirmed empirically too:
running the real probe end-to-end (both before and after the split) produced
no visible desktop side effects, only file writes under `/tmp/` and
`dev/pane_error_log/md/`.
