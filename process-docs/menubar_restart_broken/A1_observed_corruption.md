# A1 — Menubar Restart Button Corrupts the Bundle (2026-05-28)

**Status:** Observation. Reproducible. Severity: blocks every restart-button click + requires a manual rebuild + a new screen-recording permission.

## Observation

Clicking "Restart" in the menubar panel (a modal with Kill / Restart buttons) does not lead to a clean re-launch of the py2app bundle. Instead:

1. The menubar exits (correct)
2. The bundle gets ACTIVELY corrupted — Info.plist is overwritten with the ad-hoc stub version (`CFBundleExecutable=menubar` instead of `Monitor_CC_Menubar`, no `NSScreenCaptureUsageDescription`, no `PyRuntimeLocations`)
3. The Bash launcher `Contents/MacOS/menubar` (243 bytes) is additionally created — next to the py2app native binary already sitting there
4. The next launch attempt via `open` fails with a system dialog: *"Monitor_CC_Menubar has encountered a fatal error... The Info.plist file must have a PyRuntimeLocations array..."*

The bundle ends up in a "mixed Frankenstein" state: py2app binary + Bash launcher + ad-hoc stub plist, simultaneously.

## Root Cause

`src/menubar/app.py:restartApp_` invokes:

```python
cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
```

where `_SETUP_PY = Path(__file__).resolve().parent / 'setup_menubar.py'`. In the py2app bundle context:
- `sys.executable` = the bundle's internal Python (`Contents/MacOS/python`)
- `_SETUP_PY` = the bundle's internal `setup_menubar.py` (`Contents/Resources/lib/python3.14/src/menubar/setup_menubar.py`)

`setup_menubar.py:_build_app_bundle()` rewrites `~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist` (with the old ad-hoc stub configuration from the `com.brunowinter.monitor_cc_menubar.plist` template) and creates the Bash launcher. The plist write OVERWRITES the py2app configuration the bundle needs at runtime.

This was anticipated in the current-state documentation for menubar desktop allocation, § Open Questions #4, as "restart button exits the app but does not re-bootstrap." Today this manifests as ACTIVE corruption, not just a "no-op exit" — sharper severity than originally documented.

## Workaround (at the time)

After a restart click, the following had to be done manually:
1. Re-copy the bundle from `dist/` OR rebuild via `./venv/bin/python setup_py2app.py py2app`
2. `cp -R dist/Monitor_CC_Menubar.app ~/Applications/Monitor_CC_Menubar.app` (or `rm -rf` first)
3. `open ~/Applications/Monitor_CC_Menubar.app`
4. Re-bind the screen-recording permission (new CDHASH on rebuild)

## Fix Options (to be decided at implementation)

**Option A — disable restartApp_ in the py2app context:**
- Detection via `getattr(sys, 'frozen', False)` or `os.environ.get('RESOURCEPATH')` (py2app sets these)
- In the bundle: the restart button becomes a pure quit button, or shows a dialog "Restart not available in bundled mode"
- Pro: no corruption, clear UX
- Con: restart functionality no longer available

**Option B — restartApp_ calls a py2app-conformant rebuild:**
- Instead of `setup_menubar.py` → call `subprocess.Popen` that re-launches the external `~/Applications/Monitor_CC_Menubar.app` via `open`, after the current process exits
- `setup_menubar.py` is NO LONGER triggered — no plist corruption
- Pro: restart works again
- Con: needs `open` as an external trigger + a clean exit sequence

**Option C — delete `setup_menubar.py` / mark it a no-op:**
- Remove the file from src/menubar/, consolidate functionality into setup_py2app.py
- Adjust restartApp_ accordingly
- Pro: no more dual pipeline (per the DOCS note "setup_menubar.py superseded by setup_py2app.py")
- Con: larger code intervention

## Sources

- The current-state documentation for menubar desktop allocation, § Open Questions #4 (original anticipation)
- The py2app-migration process history (py2app bundle pipeline)
- `src/menubar/app.py:restartApp_`
- `src/menubar/setup_menubar.py:_build_app_bundle`
- Observation 2026-05-28 19:27: the bundle after a restart click had `CFBundleExecutable=menubar` + missing PyRuntimeLocations
