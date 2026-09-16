# dev/coteditor/

## Role
Standalone macOS observation probe for a sporadic Space (Mission Control desktop) jump during CotEditor drag-selection — an external-app investigation, not a `src/` regression guard. No `src/` import. Touch only to re-run or extend the same class of Space-jump observation.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `python3 dev/coteditor/07_space_jump_probe.py` (Ctrl-C or SIGTERM to stop).

## Flow
Polls mouse position, left-mouse-button state, edge proximity, active Space ID, and frontmost app at 10 Hz; on every Space-ID change, dumps the trailing ~10s rolling buffer of samples to a timestamped log file under `log/`.

## Modules

### 07_space_jump_probe.py (122 LOC)

**Purpose:** Polls mouse/Space/frontmost-app state at 10 Hz and dumps the trailing rolling buffer to the log on every Space-ID change.
**Reads:** live mouse/window state via `AppKit` (`NSEvent`, `NSScreen`, `NSWorkspace`) and the raw CoreGraphics `CGS*` bridge.
**Writes:** `dev/coteditor/log/space_jump_<timestamp>.log`; stdout (log path, one `JUMP: space X -> Y` line per jump).
**Called by:** none — run manually; Ctrl-C or SIGTERM to stop (flushes and closes the log first).
**Calls out:** `AppKit` (PyObjC); raw `ctypes.CDLL` bridge to `/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics`.

---

## State
`probe_workflow()` owns all state for the run: an in-memory rolling `deque` buffer of the last ~10s of samples and the open log file handle. Both are local to that function's call, mutated only within its polling loop, and torn down (flushed, closed) in its `finally` block on shutdown.
