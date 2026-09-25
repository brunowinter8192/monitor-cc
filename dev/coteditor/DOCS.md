# dev/coteditor/

## Role
Standalone macOS observation probe for a sporadic Space (Mission Control desktop) jump during CotEditor drag-selection. An external-app investigation, not a `src/` regression guard. Touch only to re-run or extend the same class of Space-jump observation.

## Public Interface
No `__init__.py`. Entry point is direct invocation: `python3 dev/coteditor/07_space_jump_probe.py` (Ctrl-C or SIGTERM to stop).

## Flow
The probe samples mouse, Space and frontmost-app state at 10 Hz and keeps a short rolling buffer. On every Space change it dumps the buffer to a timestamped log under `log/`.

## Modules

### 07_space_jump_probe.py (143 LOC)

**Purpose:** Polls mouse, Space and frontmost-app state at 10 Hz and dumps the trailing rolling buffer on every Space change.
**Reads:** live mouse and window state through AppKit and the raw CoreGraphics bridge.
**Writes:** `dev/coteditor/log/space_jump_<timestamp>.log`; stdout (log path, one line per jump).
**Called by:** none; run manually.
**Calls out:** `AppKit` (PyObjC); CoreGraphics via `ctypes`.

---

## State
All state is local to one probe run: an in-memory rolling buffer and the open log file, closed on shutdown. Nothing persists except the log files.
