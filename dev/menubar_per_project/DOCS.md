# dev/menubar_per_project/

## Role
Unit-test coverage for the per-project monitor button's pure/branch logic in
`src/menubar/system.py` — the launch-command construction, the kill-then-relaunch branch, and
Homebrew-`python3` resolution — without exercising the real Ghostty/`osascript` I/O. Touch this
directory when changing `_open_or_focus_monitor`, `_launch_monitor`, `_build_monitor_launch_cmd`,
or `_resolve_launch_python3`.

## Public Interface
No `__init__.py` in this directory. Entry path: `python3
dev/menubar_per_project/test_open_or_focus_monitor.py`.

## Flow
No data in — every case builds its own synthetic `cwd`/session state inline. Drives
`src.menubar.system` functions directly (with the real I/O boundary,
`_launch_monitor_ghostty_native`, monkeypatched out) and asserts on returned values, monkeypatch
call records, and one real subprocess's stdout — output is PASS/FAIL lines to stdout only.

## Modules

### test_open_or_focus_monitor.py (132 LOC)

**Purpose:** Proves session-name derivation is reused (never re-derived), an existing tmux session
is always killed then relaunched, the launch command quotes its cwd via `shlex`, `python3`
resolution reads the launchd plist's PATH, and `_launch_monitor` has no Ghostty-fallback path.
**Reads:** nothing external — monkeypatches `system.py`'s own module-level functions
(`check_session_exists`, `kill_session`, `_launch_monitor`, `_launch_monitor_ghostty_native`) and
restores them after each case; one case spawns a real subprocess with a bare launchd-shaped `PATH`.
**Writes:** stdout (`[OK]`/`[FAIL]` per check, final summary); exits 1 on any failure.
**Called by:** none — run manually (`python3 dev/menubar_per_project/test_open_or_focus_monitor.py`).
**Calls out:** `src.menubar.system`, `src.tmux_launcher` — loaded via `importlib.import_module`
(not `from src.` — see `src/hooks/block_dev_imports_src.py`).

---

## State
No persistent state. Each test monkeypatches `src.menubar.system`'s module-level functions for the
duration of its own call and restores the originals in a `finally` block before returning; nothing
survives across test cases or across runs.
