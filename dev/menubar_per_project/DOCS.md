# dev/menubar_per_project/

## Role

Unit-test coverage for the per-project monitor button's pure/branch logic in
`src/menubar/system.py` — the launch-command construction, the kill-then-relaunch branch, and
Homebrew-`python3` resolution — without exercising the real Ghostty/`osascript` I/O. Touch this
directory when changing `_open_or_focus_monitor`, `_launch_monitor`, `_build_monitor_launch_cmd`,
or `_resolve_launch_python3`.

## Modules

### test_open_or_focus_monitor.py (181 LOC)

**Purpose:** Proves `system.generate_session_name`/`check_session_exists` are the same objects
`tmux_launcher.py` defines (never re-derived locally); an existing tmux session is always killed
then relaunched (never a focus-only no-op); the launch command quotes a cwd containing shell
metacharacters via `shlex`, not raw interpolation; `_resolve_launch_python3` reads the Homebrew
path out of the launchd plist template rather than falling back to a bare `os.environ`; and that
`_launch_monitor` calls the native AppleScript path unconditionally, with no Ghostty-version gate
or `open -na Ghostty.app` fallback.
**Reads:** nothing external — monkeypatches `system.py`'s own module-level functions
(`check_session_exists`, `kill_session`, `_launch_monitor`, `_launch_monitor_ghostty_native`) and
restores them after each case; one case spawns a real subprocess with a bare launchd-shaped `PATH`.
**Writes:** stdout (`[OK]`/`[FAIL]` per check, final summary); exits 1 on any failure.
**Called by:** none — run manually (`python3 dev/menubar_per_project/test_open_or_focus_monitor.py`).
**Calls out:** `src.menubar.system`, `src.tmux_launcher` — loaded via `importlib.import_module`
(not `from src.` — see `src/hooks/block_dev_imports_src.py`).

---

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
