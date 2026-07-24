# Space-Jump Logging Probe — Build (2026-07-24)

## Goal

A standalone observation script for the sporadic macOS Space jump during CotEditor
drag-selection (mechanism unproven at the time — Mission Control edge-drag space
switch was the working hypothesis, since prior menubar-app investigation ruled the
app itself out). Deliverable: `dev/coteditor/07_space_jump_probe.py`, polling mouse
position, left-button state, active Space ID, and frontmost app at 10 Hz, dumping a
~10 s rolling buffer to a log file on every Space change.

## Quartz Unavailable — AppKit Substitution

As of 2026-07-24, the venv (`monitor-cc/venv`) has only `pyobjc-core` +
`pyobjc-framework-Cocoa` installed (verified via `site-packages/*.dist-info` listing)
— `pyobjc-framework-Quartz` is absent, `import Quartz` raises `ModuleNotFoundError`.
The originally-suggested APIs (`CGEventCreate`/`CGEventGetLocation`,
`CGEventSourceButtonState`) live in that missing framework; installing it was out of
scope for a `dev/`-only deliverable.

Substituted with `AppKit` (already present, same no-extra-permission guarantee, no
CGEventTap):

| Need | AppKit substitute | Verified behavior |
|---|---|---|
| Mouse position | `NSEvent.mouseLocation()` | live global coords, bottom-left origin |
| Left-button state | `NSEvent.pressedMouseButtons()` (class method, bit 0) | `0` at rest, confirmed |
| Screen bounds / edge flag | `NSScreen.screens()` → `.frame()` | per-screen containment + edge-distance check |
| Frontmost app | `NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()` | returned `"Ghostty"` live |

Active-Space ID reuses the existing CGS bridge minimal subset (`CGSMainConnectionID`
+ `CGSGetActiveSpace`, `ctypes` against `CoreGraphics.framework`) from
`dev/desktop_detection/01_probe.py` / `06_move_sweep_probe.py` — no ObjC bridge
needed since only the raw space ID (change-detection), not the full display/space
map, is required here.

## Design

- 10 Hz poll loop, `collections.deque(maxlen=100)` rolling buffer (~10 s at 10 Hz).
- On `space_id` change vs. previous sample: write a `### JUMP <ts> space X -> Y`
  header + the full buffer (one line per sample, all fields) to the log file,
  flush, continue running (buffer keeps filling — multiple jumps per run land as
  separate blocks in the same file).
- Log path: `dev/coteditor/07_reports/space_jump_<run_start_ts>.log`, opened once
  per run in append mode; printed once at startup, no other console output besides
  a one-line jump notice (log file remains the primary record).
- Clean shutdown: `SIGINT`/`SIGTERM` handler sets a flag, loop exits, log closed
  with a `stopped` marker in a `finally` block.

## Verification (2026-07-24)

- **Integration:** real script run under venv python for 2.5 s, `SIGINT` sent →
  clean exit, log file present with both `started` and `stopped` markers (append
  mode confirmed — file not truncated across the run).
- **Pure-function:** `_at_edge` checked against a real `NSScreen.frame()` (left,
  right, top edges → `True`; center → `False`). `_dump_jump` exercised with two
  consecutive synthetic jumps written to one open log handle — both `### JUMP`
  blocks present, all required fields (`x, y, at_edge, left_down, space, app`)
  rendered, second block appended after the first (not overwritten).
- **NOT verified at this pass:** a real macOS Space switch triggering the probe
  live (needs an interactive edge-drag) — the buffer-dump path is proven with
  synthetic data, not with a genuine `CGSGetActiveSpace` transition during a live
  drag. That check is interactive and was left to the orchestrator.
