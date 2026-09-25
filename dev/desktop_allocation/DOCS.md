# dev/desktop_allocation/

## Role
Detection and window-move research mapping a Claude Code session's Ghostty tab to a Mission
Control desktop number, and testing whether a window can be programmatically moved between
desktops. No `src/` behavior change. Four of six entry scripts mutate the real desktop — read
this file before running any.

## Public Interface
No `__init__.py` in this directory. Each numbered `NN_*.py` script is its own entry point, run
directly, e.g. `python3 dev/desktop_allocation/01_probe.py`. `02_bundle_stub.app/` and
`03_bundle_stub.app/` are ad-hoc-signed `.app` bundle stubs used as one of probe02/03's execution
contexts, not Python entry points.

## Flow
Live Menubar/Ghostty/CotEditor state (a cwd-UUID map, AppleScript window queries, CGWindowList/
Space APIs) goes in. Each probe's own pipeline resolves a window's desktop, or — for 01/04/05/06 —
retitles a live tty, moves a window between Spaces, or opens/closes a real window. Output is
stdout tables, an optional JSON report under `NN_reports/`, or (04/06) screenshots plus a text
dump.

## Modules

### 01_probe.py (32 LOC)

**Purpose:** Orchestrates `cwd -> UUID -> CGWindowID -> SpaceID -> Desktop-No` against live
Menubar + Ghostty state; entry point only.
**Reads:** —. **Writes:** —.
**Called by:** none — MUTATES a live tty title via OSC-2 injection (restored after read); do not
run against your own session.
**Calls out:** `probe01_bridge`, `probe01_pipeline`, `probe01_report`.

---

### probe01_bridge.py (70 LOC)

**Purpose:** ctypes/objc bridge setup (CoreGraphics + libobjc) and NSDictionary/NSArray helpers
used by `probe01_pipeline.py`.
**Reads:** —. **Writes:** —.
**Called by:** `probe01_pipeline.py`, `01_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### probe01_pipeline.py (257 LOC)

**Purpose:** Data gathering (cwd/tty, AppleScript window map, CGWindow map, Space map) and the
3-strategy CGWindowID resolution.
**Reads:** live Ghostty AppleScript state, `CGWindowListCopyWindowInfo`, `CGSCopySpacesForWindows`,
Menubar's `ghostty_cwd_uuid.json`.
**Writes:** MUTATES — a session's tty title, transiently, during OSC-2 injection.
**Called by:** `01_probe.py`.
**Calls out:** Ghostty via AppleScript (`osascript`).

---

### probe01_report.py (42 LOC)

**Purpose:** Prints the session table, Space/display overview, and detection-rate/strategy
summary.
**Reads:** —. **Writes:** stdout.
**Called by:** `01_probe.py`.
**Calls out:** —.

---

### 02_context_comparison_probe.py (41 LOC)

**Purpose:** Orchestrates the TCC-boundary comparison across CC-Bash/launchd/bundle-exec
contexts; entry point only.
**Reads:** —. **Writes:** —.
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle`; read-only.
**Calls out:** `probe02_bridge`, `probe02_diagnostics`, `probe02_pipeline`, `probe02_report`.

---

### probe02_bridge.py (70 LOC)

**Purpose:** ctypes/objc/libproc bridge setup and NSDictionary/NSArray helpers.
**Reads:** —. **Writes:** —.
**Called by:** `probe02_diagnostics.py`, `probe02_pipeline.py`, `02_context_comparison_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### probe02_diagnostics.py (67 LOC)

**Purpose:** Collects TCC-identity diagnostics (codesign, NSBundle id, responsible-pid) and
TCC.db ScreenCapture grant state.
**Reads:** `TCC.db`, `codesign`, `ps`. **Writes:** —.
**Called by:** `02_context_comparison_probe.py`.
**Calls out:** `Foundation` (`NSBundle`).

---

### probe02_pipeline.py (201 LOC)

**Purpose:** Space/window queries plus the name-unique-only detection pipeline and window-stat
aggregation for the comparison report.
**Reads:** live CGS/AppleScript state, Menubar's `ghostty_cwd_uuid.json`.
**Writes:** —.
**Called by:** `02_context_comparison_probe.py`.
**Calls out:** Ghostty via AppleScript (`osascript`).

---

### probe02_report.py (24 LOC)

**Purpose:** Writes the comparison report JSON.
**Reads:** —. **Writes:** `02_reports/<tag>_<timestamp>.json`.
**Called by:** `02_context_comparison_probe.py`.
**Calls out:** —.

---

### 03_field_availability_probe.py (67 LOC)

**Purpose:** Orchestrates the full CGWindow field dump across execution contexts; entry point
only.
**Reads:** —. **Writes:** —.
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle`; read-only.
**Calls out:** `probe03_bridge`, `probe03_diagnostics`, `probe03_windows`, `probe03_ghostty_detail`,
`probe03_report`.

---

### probe03_bridge.py (87 LOC)

**Purpose:** ctypes/objc/libproc bridge setup plus reflection helpers used to dump arbitrary CGWindow fields.
**Reads:** —. **Writes:** —.
**Called by:** `probe03_diagnostics.py`, `probe03_windows.py`, `probe03_ghostty_detail.py`,
`03_field_availability_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### probe03_diagnostics.py (67 LOC)

**Purpose:** Same TCC-identity/TCC.db diagnostics as `probe02_diagnostics.py`, kept separate per
the no-cross-script-dedup convention in this directory.
**Reads:** `TCC.db`, `codesign`, `ps`. **Writes:** —.
**Called by:** `03_field_availability_probe.py`.
**Calls out:** `Foundation` (`NSBundle`).

---

### probe03_windows.py (108 LOC)

**Purpose:** Full CGWindow field dump (all windows, all keys) and the field-availability summary
build.
**Reads:** live CGS state. **Writes:** —.
**Called by:** `03_field_availability_probe.py`, `probe03_ghostty_detail.py`.
**Calls out:** —.

---

### probe03_ghostty_detail.py (145 LOC)

**Purpose:** Per-Ghostty-window CG-field + AppleScript-bounds detail, including the AS-vs-CG rect
comparison and the geometry-verdict probe.
**Reads:** live CGS state, Ghostty via read-only AppleScript.
**Writes:** —.
**Called by:** `03_field_availability_probe.py`.
**Calls out:** Ghostty via AppleScript (`osascript`).

---

### probe03_report.py (17 LOC)

**Purpose:** Writes the field-availability report JSON.
**Reads:** —. **Writes:** `03_reports/<tag>_<timestamp>.json`.
**Called by:** `03_field_availability_probe.py`.
**Calls out:** —.

---

### 04_space_move_probe.py (18 LOC)

**Purpose:** Orchestrates the `SLSBridgedMoveWindowsToManagedSpaceOperation` move test; entry
point only.
**Reads:** —. **Writes:** —.
**Called by:** none — MUTATES the desktop (moves a real window between Spaces); do not run.
**Calls out:** `probe04_bridge`, `probe04_detection`, `probe04_move`, `probe04_workflow`.

---

### probe04_bridge.py (89 LOC)

**Purpose:** ctypes/objc bridge setup including the `initWithWindows:spaceID:`/
`performWithWMBridgeDelegate` calling-convention typedefs.
**Reads:** —. **Writes:** —.
**Called by:** `probe04_detection.py`, `probe04_move.py`, `probe04_workflow.py`,
`04_space_move_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### probe04_detection.py (69 LOC)

**Purpose:** Space map, on-screen/Ghostty-window WID queries, and per-WID Space lookup.
**Reads:** live CGS state. **Writes:** —.
**Called by:** `probe04_workflow.py`.
**Calls out:** —.

---

### probe04_move.py (28 LOC)

**Purpose:** The `SLSBridgedMoveWindowsToManagedSpaceOperation` move call and screenshot capture.
**Reads:** —. **Writes:** MUTATES — moves a window between Spaces; writes a screenshot PNG.
**Called by:** `probe04_workflow.py`.
**Calls out:** `objc`/`ctypes` (SkyLight bridge), `screencapture`.

---

### probe04_workflow.py (141 LOC)

**Purpose:** Precondition check, before/move/after trial, restore phase, and summary/dump-file
steps that make up the probe's run.
**Reads:** live CGS state.
**Writes:** stdout PASS/FAIL, `04_reports/` screenshots and an on-screen WID dump `.txt`.
**Called by:** `04_space_move_probe.py`.
**Calls out:** —.

---

### 05_window_detection_probe.py (73 LOC)

**Purpose:** Orchestrates the tmux/OSC-2/CotEditor window-detection trials; entry point only.
**Reads:** —. **Writes:** —.
**Called by:** none — MUTATES the desktop (opens/closes real windows); do not run.
**Calls out:** `probe05_bridge`, `probe05_detection`, `probe05_lifecycle`, `probe05_trial`.

---

### probe05_bridge.py (86 LOC)

**Purpose:** ctypes/objc bridge setup and NSDictionary/NSArray helpers.
**Reads:** —. **Writes:** —.
**Called by:** `probe05_detection.py`, `probe05_lifecycle.py`, `probe05_trial.py`,
`05_window_detection_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### probe05_detection.py (135 LOC)

**Purpose:** Window-type constants plus Space/window/title-match/frontmost queries shared by
lifecycle and trial.
**Reads:** live CGS state. **Writes:** —.
**Called by:** `probe05_lifecycle.py`, `probe05_trial.py`, `05_window_detection_probe.py`.
**Calls out:** —.

---

### probe05_lifecycle.py (108 LOC)

**Purpose:** Opens/closes the three trial window types (tmux-Ghostty, OSC-2-Ghostty, CotEditor)
and warm-launches CotEditor.
**Reads:** live CGS state.
**Writes:** MUTATES — opens/closes real windows via `tmux`/`open`/AppleScript/`kill`.
**Called by:** `probe05_trial.py`, `05_window_detection_probe.py`.
**Calls out:** `tmux`, `open`, Ghostty/CotEditor via AppleScript (`osascript`).

---

### probe05_trial.py (204 LOC)

**Purpose:** Runs one detection trial (setup, snapshot, poll, measure signals, cleanup, assemble/
write result) and prints the summary table.
**Reads:** live CGS state.
**Writes:** `05_reports/trial_<type>_<n>_<timestamp>.json`; stdout.
**Called by:** `05_window_detection_probe.py`.
**Calls out:** —.

---

### 06_move_sweep_probe.py (25 LOC)

**Purpose:** Orchestrates the 4-primitive window-move sweep; entry point only.
**Reads:** —. **Writes:** —.
**Called by:** none — MUTATES the desktop (opens/closes a CotEditor window, attempts to move
it); do not run.
**Calls out:** `probe06_bridge`, `probe06_detection`, `probe06_coteditor`, `probe06_primitives`,
`probe06_workflow`, `probe06_report`.

---

### probe06_bridge.py (103 LOC)

**Purpose:** ctypes/objc/SkyLight/ApplicationServices bridge setup, incl. AX + ScreenCapture
preflight argtypes.
**Reads:** —. **Writes:** —.
**Called by:** `probe06_detection.py`, `probe06_workflow.py`, `06_move_sweep_probe.py`.
**Calls out:** `objc`/`ctypes` (CGS/SkyLight/ApplicationServices bridge).

---

### probe06_detection.py (94 LOC)

**Purpose:** Space map, WID/title-match queries, the AX/ScreenCapture permission self-check, and
the first-non-active-nonempty-Space finder.
**Reads:** live CGS state, `AXIsProcessTrusted`, `CGPreflightScreenCaptureAccess`.
**Writes:** stdout permission-check block.
**Called by:** `probe06_coteditor.py`, `probe06_workflow.py`, `06_move_sweep_probe.py`.
**Calls out:** —.

---

### probe06_coteditor.py (47 LOC)

**Purpose:** Warm-launches CotEditor and opens/detects/closes a token-named CotEditor document
per primitive trial.
**Reads:** live CGS state.
**Writes:** MUTATES — opens/closes a real CotEditor window via `open`/AppleScript.
**Called by:** `probe06_workflow.py`, `06_move_sweep_probe.py`.
**Calls out:** `open`, CotEditor via AppleScript (`osascript`).

---

### probe06_primitives.py (56 LOC)

**Purpose:** Dynamic symbol loading, argtypes setup, screenshot capture, and the before/call/
after measurement of one move-primitive trial.
**Reads:** live CGS state.
**Writes:** MUTATES — invokes the move primitive under test; writes screenshot PNGs under
`06_reports/`.
**Called by:** `probe06_workflow.py`.
**Calls out:** `screencapture`.

---

### probe06_workflow.py (141 LOC)

**Purpose:** Probe setup, precondition validation, the 4 primitives' symbol loading, and
per-primitive call construction and execution.
**Reads:** live CGS state. **Writes:** stdout status lines.
**Called by:** `06_move_sweep_probe.py`.
**Calls out:** —.

---

### probe06_report.py (25 LOC)

**Purpose:** Prints the per-primitive result table and the PASS/FAIL headline.
**Reads:** —. **Writes:** stdout.
**Called by:** `06_move_sweep_probe.py`.
**Calls out:** —.

---

## State
No persistent state lives in this directory's current code paths — each probe reads live macOS
desktop state (CGS/AppleScript/TCC.db) fresh on every run and either prints it or writes a
timestamped report under its own not-yet-created `NN_reports/` directory. `json/`, `png/`, `txt/`
hold timestamped artifacts from an earlier, pre-split version of these probes that wrote there
directly; no module in the current split produces output into those three directories anymore —
they are historical, not owned by any live module.
