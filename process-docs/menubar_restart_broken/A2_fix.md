# A2 — Restart Button Fix (2026-05-28)

**Status:** Fixed. Commits 089980c + 2a7acd8 on branch `restart-fix`.

## Root Cause (Two Interacting Bugs)

### Bug 1 — `_BUNDLE_LAUNCHER` Points at a Non-Existent Binary

`setup_menubar.py:_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'menubar'`

`write_plist()` substitutes this path into `ProgramArguments` of the LaunchAgent plist.
But the installed py2app bundle contains no `Contents/MacOS/menubar`:

```
~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/
  Monitor_CC_Menubar   ← py2app native Mach-O
  python               ← py2app stub Python
```

Verified via `launchctl print gui/<uid>/com.brunowinter.monitor_cc_menubar`:
- `program = .../Contents/MacOS/menubar`
- `active count = 0`, `state = spawn scheduled`

launchd tried to respawn; the binary doesn't exist; the app only ran because it was started manually via `open`.

### Bug 2 — the Helper Subprocess Corrupts the py2app Bundle's Info.plist

`restartApp_` built the helper command:
```python
cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
```

In the py2app bundle context:
- `sys.executable` = `Contents/MacOS/python` (the bundle's internal stub Python)
- `_SETUP_PY` = `Contents/Resources/lib/python3.14/src/menubar/setup_menubar.py` (the bundle's internal copy, verified via `find`)

The helper called `setup_menubar_workflow()` → `_build_app_bundle()`, which:
1. Overwrote `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` with the ad-hoc stub
   (`CFBundleExecutable=menubar`, no `PyRuntimeLocations`, no `NSScreenCaptureUsageDescription`)
2. Created `Contents/MacOS/menubar` (Bash launcher) — next to the py2app native binary

The next `open` attempt: the py2app native binary reads the corrupt Info.plist →
"The Info.plist file must have a PyRuntimeLocations array" (fatal startup error).

Severity sharper than anticipated in A1: not just a "no-op exit" but active bundle corruption.

## Fix (Option D — Separate Plist Functions, sys.frozen Gate)

### Step 1: `setup_menubar.py` — `_BUNDLE_EXE` + `write_plist_py2app()`

```python
_BUNDLE_LAUNCHER = _BUNDLE / 'Contents' / 'MacOS' / 'menubar'           # dev/Bash bundle unchanged
_BUNDLE_EXE      = _BUNDLE / 'Contents' / 'MacOS' / 'Monitor_CC_Menubar'  # py2app native binary
```

New function `write_plist_py2app()` — identical to `write_plist()` but substitutes `_BUNDLE_EXE`
instead of `_BUNDLE_LAUNCHER`. No `print()` (no useful stdout receiver in the bundle context).
`_BUNDLE_LAUNCHER` stays unchanged → `write_plist()` + the dev restart remain correct.

### Step 2: `app.py:restartApp_` — a `sys.frozen` Gate, No Unconditional Wrong-Write

```python
def restartApp_(self, sender):
    uid = os.getuid()
    label = 'com.brunowinter.monitor_cc_menubar'
    if getattr(sys, 'frozen', False):
        # py2app: write_plist_py2app() → a pure launchctl cycle
        from .setup_menubar import write_plist_py2app
        write_plist_py2app()
        dest = str(Path.home() / 'Library' / 'LaunchAgents' / f'{label}.plist')
        cmd = (
            f'sleep 0.5 && launchctl bootout gui/{uid}/{label} 2>/dev/null ; '
            f'launchctl bootstrap gui/{uid} "{dest}"'
        )
    else:
        # dev/venv: write_plist() → setup_menubar.py subprocess
        from .setup_menubar import write_plist
        write_plist()
        cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
    subprocess.Popen(['sh', '-c', cmd], start_new_session=True)
    rumps.quit_application()
```

`sys.frozen = 'macosx_app'` is set by `__boot__.py` — verified.
No Python call in the py2app helper → the bundle's internal `setup_menubar.py` can never run.

### Why Not an Unconditional `write_plist()` at the Top

The first draft (commit 089980c) had `write_plist()` unconditionally at the top, then `write_plist_py2app()`
in the py2app branch: a redundant wrong-write (the `menubar` path, immediately overwritten by `Monitor_CC_Menubar`).
Commit 2a7acd8 corrected this: each branch calls exactly one, the correct, function.

## Open Footgun (not fixed — refactor scope)

Dev restart (`sys.frozen = False`): `setup_menubar_workflow()` calls `_build_app_bundle()`,
which overwrites `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` — corrupting an
installed py2app bundle. Inactive in practice: dev runs via `dev/menubar_debug.py`,
no restart-button click is expected from that path. The fix belongs in the `setup_menubar.py`
refactor step (remove the legacy pipeline or add a guard).

## Sources

- `src/menubar/app.py:restartApp_` (commits 089980c, 2a7acd8)
- `src/menubar/setup_menubar.py` (`_BUNDLE_EXE`, `write_plist_py2app`)
- The prior observed-corruption entry in this area
- The current-state documentation for menubar desktop allocation, § Open Questions #4
