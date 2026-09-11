# dev/coteditor/

## Role

Standalone macOS observation probe for a sporadic Space (Mission Control desktop) jump during
CotEditor drag-selection — an external-app investigation, not a `src/` regression guard. No `src/`
import. Touch this directory only if re-running or extending the same class of Space-jump
observation.

## Modules

### 07_space_jump_probe.py (132 LOC)

**Purpose:** Polls mouse position, left-mouse-button state, whether the cursor sits within 3px of
a screen edge, the active Space ID (via a raw `CGSMainConnectionID`/`CGSGetActiveSpace` bridge),
and the frontmost app at 10 Hz; on every Space-ID change, dumps the trailing ~10 s rolling buffer
of samples to the log file.
**Reads:** live mouse/window state via `AppKit` (`NSEvent`, `NSScreen`, `NSWorkspace`) and the raw
CoreGraphics `CGS*` bridge.
**Writes:** `dev/coteditor/log/space_jump_<timestamp>.log` (startup line, one line per sample inside
a `### JUMP ...` block, stop line); stdout (log path, one `JUMP: space X -> Y` line per jump).
**Called by:** none — run manually; Ctrl-C or SIGTERM to stop (flushes and closes the log first).
**Calls out:** `AppKit` (PyObjC); raw `ctypes.CDLL` bridge to
`/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics`.

---

## Gotchas

**The `CGS*` symbols are undocumented, private CoreGraphics/SkyLight APIs**, loaded via a raw
`ctypes.CDLL` bridge rather than a PyObjC framework binding — no `import Quartz` fallback exists in
this probe (the venv it was built against had only `pyobjc-core`/`pyobjc-framework-Cocoa`
installed, not `pyobjc-framework-Quartz`).

**Edge detection (`_EDGE_PX = 3`) treats "no containing screen" as also at-edge** — a cursor pushed
past every `NSScreen`'s bounds returns `True`, not `False`, from `_at_edge`.
