# 2026-09-16 — dev/menubar_nspanel/ cohesion split

## What happened

`dev/menubar_nspanel/p1_nspanel_probe.py` was 260 LOC (under the 400-LOC file
threshold) with one function over the 50-line function threshold:
`_register_hotkey` at 52 lines. `menubar_debug.py` (60 LOC) needed no changes
at all — every function in it is already well under 50 lines
(`menubar_debug_workflow` 12, `_bootout` 7, `_bootstrap` 10) and it does not
import anything from `p1_nspanel_probe.py`, so it was read in full (per the
milestone's instruction to read every file, since siblings may import split
targets) but left untouched.

Split `_register_hotkey` out to a new sibling module `p1_hotkey.py` (prefixed
with the entry script's own `p1_` prefix, per the naming convention
established in the two preceding splits in this project — never a bare noun
like `hotkey.py`):

- `p1_nspanel_probe.py` (206 LOC) — unchanged except: `import ctypes` removed
  (no longer used anywhere else in this file), one new line
  `from p1_hotkey import _register_hotkey`, and the `_register_hotkey`
  function body removed. Diffed the full file against the pre-split backup
  after the edit — confirmed those are the ONLY three changes, everything else
  (the app class, panel-building helpers, status-tracking helpers) is
  byte-identical.
- `p1_hotkey.py` (64 LOC) — the 52-line `_register_hotkey` split into
  `_hotkey_ctypes_defs()` (12 lines — declares `OSStatus`/`EventHotKeyID`/
  `EventTypeSpec`/`EventHandlerProcPtr`, a genuinely separate "declare the
  Carbon API's ctypes shapes" concern from "use them to register a hotkey")
  and a 43-line `_register_hotkey` that calls it and does the actual
  `GetApplicationEventTarget`/`InstallEventHandler`/`RegisterEventHotKey`
  sequence, unchanged in every other respect.

## Hazard — this one is real, not hypothetical

`_register_hotkey` calls into the real Carbon framework
(`ctypes.CDLL('/System/Library/Frameworks/Carbon.framework/Carbon')`) and its
`RegisterEventHotKey`/`InstallEventHandler` calls are real C function calls
that **register a live, system-wide Cmd+L hotkey** the moment they run —
there is no "dry" way to call the actual function without that side effect,
regardless of what fake `app` object is passed in. `p1_nspanel_probe.py`
additionally builds a real `NSPanel` and runs a real `NSApplication` event
loop via `rumps.App.run()`. `menubar_debug.py` is equally live in a different
way: it does `launchctl bootout` on the REAL production menubar launchd
service, then runs the real `workflow.py --mode menubar` in the foreground
(which does the same hotkey/panel registration in production form), blocking
until Ctrl-C, then optionally re-bootstraps the service. **Neither script was
run, at any point, for this milestone.**

## Verification — synthetic input only, `ctypes.CDLL` mocked

Since running either script (or calling `_register_hotkey` with even a fake
`app` object) triggers the real hazard, verification used the milestone's
second allowed method end to end:

1. Backed up the original file, loaded it via
   `importlib.util.spec_from_file_location`, using the project's own
   `./venv/bin/python` (system `python3` cannot `import objc`/`rumps`/
   `AppKit` — the venv can, and the whole original file imports those at
   module level even though `_register_hotkey` itself only needs `ctypes`;
   importing the module does not execute `run()`, guarded by
   `if __name__ == '__main__':`, so this is safe).
2. `unittest.mock.patch('ctypes.CDLL', return_value=MagicMock())` around each
   call — this intercepts the framework load before any real Carbon symbol is
   ever touched, so `carbon.RegisterEventHotKey(...)` calls a `MagicMock`
   attribute, not the real OS API. **This is the only way to test this
   function at all without the real side effect** — there is no fake/synthetic
   `app` that changes what `ctypes.CDLL` does.
3. Called `backup._register_hotkey(fake_app)` vs. `p1_hotkey._register_hotkey(fake_app)`
   against the identical mocked `ctypes.CDLL`, and compared the recorded
   mock-call arguments, `.restype`/`.argtypes` assignments, and the resulting
   `app._hotkey_cb`/`app._hotkey_ref` attribute types.
4. First comparison attempt (raw `repr()` of args) showed spurious
   differences — `ctypes.byref(...)` pointer reprs and `ctypes.POINTER(...)`
   type reprs differ by memory address / local-class-identity on literally
   every invocation, including two calls to the SAME unmodified function, so
   raw-repr equality is the wrong comparator here. **Lesson: for ctypes-heavy
   code, decode `ctypes.Structure` args to their field-value tuples and
   `ctypes.byref`/pointer-typed args to just "is this a pointer" before
   comparing across two invocations — comparing raw `repr()` will show false
   differences that have nothing to do with the split.** Re-compared using a
   `describe_arg()` helper that unwraps `ctypes.Structure` fields
   (`EventHotKeyID(0x4D424152, 1)` decoded to `(1296187730, 1)` both sides)
   and reduces callables/pointers to a type tag. Result: **identical call
   sequence, identical numeric arguments
   (`37, 256, (1296187730, 1), 43690, 0`), identical `.restype` values,
   identical resulting attribute types.**

## Pointers

- The `report.py`-collision naming lesson (never name a dev/ sibling module a
  bare noun) applies again here — see `process-docs/hook_error_correlation/`
  for the original incident; this split's `p1_hotkey.py` follows it directly.
- Loading a pre-split backup via `importlib.util.spec_from_file_location` for
  a file that imports `objc`/`rumps`/`AppKit` needs the project's own
  `./venv/bin/python`, not system `python3` — system `python3` cannot import
  those at all (`ModuleNotFoundError: No module named 'objc'`), it will look
  like the backup itself is broken when actually the wrong interpreter is
  running it.
