# 2026-09-16 — Comment/docstring salvage for dev/menubar_per_project/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/menubar_per_project/` (1 `.py` file, 181 LOC) into conformance with the
project's three-marker comment standard. Every comment and the one docstring below were relocated
here verbatim before deletion from the code. Zero `__doc__`/`argparse` hits, so the docstring was
not load-bearing and deleted outright.

**Confirmed safe and run for real.** I read every call site of `_launch_monitor_ghostty_native`
in `test_open_or_focus_monitor.py` (the only function anywhere in the `src/menubar/system.py`
launch chain that performs real I/O — it runs `osascript` to activate Ghostty and type into a new
window) before classifying, rather than trusting the function names alone: it is monkeypatched to
a fake in every single test path that reaches it, directly in
`_test_launch_monitor_uses_native_path_only` and one level higher (the whole `_launch_monitor`
function is stubbed instead) in `_test_existing_session_killed_then_relaunched`/
`_test_branch_launches_when_session_absent`. No real tmux session is ever created or killed
(`check_session_exists`/`kill_session` are monkeypatched fakes throughout). The one real
subprocess spawned (`_test_resolve_python3_uses_plist_path_under_bare_environ`) only imports
`src.menubar.system` and calls the pure `_resolve_launch_python3()` (reads a local plist template
file, does a PATH-based `shutil.which` lookup — no GUI, no window, no session). The one real side
effect anywhere in the file: when the real (unstubbed) `_launch_monitor` body runs in
`_test_launch_monitor_uses_native_path_only`, it appends one benign line to the real menubar
app-support log via `log_menubar(...)` — same accepted class of side effect as
`dev/timer-loop/test_abort_stamp_scope.py` and `dev/monitor_lifecycle/tests/test_monitor_sweep.py`
from earlier in this comment-salvage cycle. Ran the script before and after the edit: **all 14
checks passed both times**, full stdout diffed byte-for-byte identical (see the completion
checklist in the task response for the exact result).

---

## Salvage from dev/menubar_per_project/test_open_or_focus_monitor.py

Shebang (line 1, stays — not a comment per the standard):
```
#!/usr/bin/env python3
```

Module docstring (was lines 2-20, immediately after the shebang):
```
Unit tests for the per-project monitor button's pure/branch logic (src/menubar/system.py).

Covers: tmux session-name derivation is reused from tmux_launcher.py (never re-derived locally),
the kill-then-relaunch branch given check_session_exists (a click always ends in a fresh
_launch_monitor call; kill_session only fires when a stale session exists), the launch command
built for a cwd containing a space (quoting safety — a fixed shell string built via shlex.quote,
not raw interpolation), and python3 resolution actually reading the plist's Homebrew-first PATH
instead of falling back to a bare launchd-shaped os.environ, and that _launch_monitor uses the
native AppleScript path unconditionally — no Ghostty-version gate, no 'open -na Ghostty.app'
fallback (removed 2026-09-04; the fallback spawned a second Ghostty process instance that broke
click-to-focus for every other window). Does not exercise the actual Ghostty/osascript I/O (see
process-docs/menubar_per_project/ for the live launch verification this was paired with).

No AppKit/rumps import needed — src/menubar/system.py has no AppKit dependency (see its DOCS.md
Purpose line). importlib.import_module used for the src.menubar import, not `from src.` — see
src/hooks/block_dev_imports_src.py.

Run: python3 dev/menubar_per_project/test_open_or_focus_monitor.py
```

Was line 55 (above `_check`):
```
# Print one PASS/FAIL line; append desc to failures on mismatch
```

Was lines 62-63 (above `_test_session_name_reused_not_rederived`):
```
# system.py must import generate_session_name/check_session_exists from tmux_launcher.py — the
# same object, never a locally re-derived hash function
```

Was lines 77-78 (above `_test_launch_cmd_quotes_cwd_with_space`):
```
# A cwd with a space (and a shell metacharacter) must round-trip through shlex as ONE argument —
# proves the command is built via quoting, not raw interpolation
```

Was lines 91-92 (above `_test_existing_session_killed_then_relaunched`):
```
# Already-running session (check_session_exists → True) must be killed, then ALWAYS relaunched
# fresh — never a focus-only no-op (a stale session can outlive its Ghostty window)
```

Was line 101 (above `_test_branch_launches_when_session_absent`):
```
# No running session (check_session_exists → False) must launch a new window, no kill needed
```

Was line 109 (above `_test_empty_cwd_is_noop`):
```
# Empty cwd (an unresolved _cwd_map entry) is a no-op — mirrors focusSession_/focusWorker_'s guard
```

Was lines 115-121 (above `_test_resolve_python3_uses_plist_path_under_bare_environ`):
```
# _resolve_launch_python3 must resolve the Homebrew python3 by reading the plist template's
# PATH — NOT this process's own os.environ, which under real launchd has no Homebrew (regression
# guard: the plist template is not valid XML on its own — plistlib.load raises on its
# unsubstituted <BUNDLE_LAUNCHER>/<PROJECT_ROOT> tags — an earlier version of this function
# silently swallowed that and fell back to os.environ, passing only by accident in a dev shell
# that already had Homebrew on PATH). Spawns a real subprocess with a bare launchd-shaped PATH
# (no Homebrew) to prove the plist read, not the ambient shell, is what resolves it.
```

Was lines 135-139 (above `_test_launch_monitor_uses_native_path_only`):
```
# Regression guard (2026-09-04): the 'ghostty +version' gate + 'open -na Ghostty.app' fallback
# were removed — the fallback spawns a SEPARATE Ghostty process instance, which then answers every
# 'tell application "Ghostty"' AppleScript call instead of the real one, losing click-to-focus for
# every other window. Asserts both symbols are gone AND that _launch_monitor calls the native
# path unconditionally (stubbed — no real osascript/Ghostty I/O).
```

Was lines 164-165 (above `_run_open_or_focus_monitor_with_stubs`):
```
# Monkeypatch check_session_exists/kill_session/_launch_monitor on the real module, call
# _open_or_focus_monitor(cwd), restore originals, return what was recorded
```

## Salvage from dev/menubar_per_project/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas

**No AppKit/rumps import is needed** — `src/menubar/system.py` has no AppKit dependency, so this
suite runs headless.

**The Ghostty-fallback regression guard asserts absence, not just behavior** — it checks
`not hasattr(_system_mod, '_ghostty_version')` and `_launch_monitor_ghostty_fallback`; reintroducing
either symbol under those exact names would silently break this guard's intent even if the new code
never calls them.

**The plist-PATH test spawns a real subprocess with `PATH` reduced to `/usr/bin:/bin:/usr/sbin:/sbin`**
— it is proving `_resolve_launch_python3` reads the plist template's PATH rather than the ambient
shell's; running the assertion in-process instead (no subprocess) would pass by accident whenever
the dev shell already has Homebrew on PATH.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
