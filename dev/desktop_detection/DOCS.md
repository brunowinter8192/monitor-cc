# dev/desktop_detection/

## Role

Read-only probes for mapping a Claude Code session (via its Ghostty tab cwd) to a Mission Control
desktop number: `cwd → UUID (Ghostty OSC-2) → CGWindowID → SpaceID → Desktop-No`, plus probes for
whether a window can be programmatically MOVED between desktops. No `src/` behavior change — this
is detection-pipeline and TCC-boundary research; production code currently shows slot-based order
(`[1]`/`[2]`/`[3]`), not spatial order. Touch this directory when extending the detection pipeline
or testing a new window-move primitive; see `process-docs/desktop_allocation/` for the full
iteration/hypothesis trail.

Each numbered entry script (`NN_*.py`) is split into unprefixed `probeNN_*.py` sibling modules
(no leading digit, since that is not a valid Python module name) that live in this same directory
and are imported by bare name. Siblings are not shared across scripts — each script owns its own
bridge/detection/lifecycle modules, even where the ctypes/objc plumbing is near-identical, so that
each script's split stays self-contained and independently readable.

## Modules

### 01_probe.py (32 LOC)

**Purpose:** Orchestrates the full pipeline (`cwd → UUID → CGWindowID → SpaceID → Desktop-No`)
against live Menubar + Ghostty state; entry point only, logic lives in `probe01_*.py`.
**Reads:** —
**Writes:** —
**Called by:** none — run manually; requires Menubar and Ghostty running.
**Calls out:** `probe01_bridge`, `probe01_pipeline`, `probe01_report`.

### probe01_bridge.py (74 LOC)

**Purpose:** ctypes/objc bridge setup (CoreGraphics + libobjc CDLL loads, argtypes/restype) and
generic NSDictionary/NSArray helpers used by `probe01_pipeline.py`.
**Reads:** —
**Writes:** —
**Called by:** probe01_pipeline.py, 01_probe.py
**Calls out:** `objc`/`ctypes` (CGS bridge).

### probe01_pipeline.py (278 LOC)

**Purpose:** Data gathering (cwd/tty, AppleScript window map, CGWindow map, Space map) and the
3-strategy CGWindowID resolution (`name-unique` → `space-elimination` → `osc2-injection`).
**Reads:** live Ghostty AppleScript state, `CGWindowListCopyWindowInfo`, `CGSCopySpacesForWindows`,
and Menubar's `ghostty_cwd_uuid.json`.
**Writes:** mutates a session's tty title transiently during OSC-2 injection (restored after read).
**Called by:** 01_probe.py
**Calls out:** Ghostty via AppleScript (`osascript`).

### probe01_report.py (42 LOC)

**Purpose:** Prints the session table, Space/display overview, and detection-rate/strategy summary.
**Reads:** —
**Writes:** stdout.
**Called by:** 01_probe.py
**Calls out:** —

---

### 02_context_comparison_probe.py (30 LOC)

**Purpose:** Orchestrates the TCC-boundary comparison (direct CC-Bash, launchd LaunchAgent,
bundle-exec `.app`); entry point only, logic lives in `probe02_*.py`. `02_bundle_stub.app/` is the
minimal ad-hoc-signed bundle used for the bundle-exec context run.
**Reads:** —
**Writes:** —
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle` per context.
**Calls out:** `probe02_bridge`, `probe02_diagnostics`, `probe02_pipeline`, `probe02_report`.

### probe02_bridge.py (71 LOC)

**Purpose:** ctypes/objc/libproc bridge setup and generic NSDictionary/NSArray helpers.
**Reads:** —
**Writes:** —
**Called by:** probe02_diagnostics.py, probe02_pipeline.py, 02_context_comparison_probe.py
**Calls out:** `objc`/`ctypes` (CGS bridge).

### probe02_diagnostics.py (69 LOC)

**Purpose:** Collects TCC-identity diagnostics (codesign, NSBundle id, responsible-pid) and
TCC.db ScreenCapture grant state.
**Reads:** `TCC.db`, `codesign`, `ps`.
**Writes:** —
**Called by:** 02_context_comparison_probe.py
**Calls out:** `Foundation` (`NSBundle`).

### probe02_pipeline.py (212 LOC)

**Purpose:** Space/window queries plus the name-unique-only detection pipeline and window-stat
aggregation for the comparison report.
**Reads:** live CGS/AppleScript state, Menubar's `ghostty_cwd_uuid.json`.
**Writes:** —
**Called by:** 02_context_comparison_probe.py
**Calls out:** Ghostty via AppleScript (`osascript`).

### probe02_report.py (25 LOC)

**Purpose:** Writes the comparison report JSON.
**Reads:** —
**Writes:** `02_reports/<tag>_<timestamp>.json`.
**Called by:** 02_context_comparison_probe.py
**Calls out:** —

---

### 03_field_availability_probe.py (52 LOC)

**Purpose:** Orchestrates the full CGWindow field dump across execution contexts; entry point
only, logic lives in `probe03_*.py`. `03_bundle_stub.app/` is this probe's bundle-exec stub
(separate from `02_bundle_stub.app/` since each hardcodes its own worktree path).
**Reads:** —
**Writes:** —
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle`.
**Calls out:** `probe03_bridge`, `probe03_diagnostics`, `probe03_windows`, `probe03_ghostty_detail`,
`probe03_report`.

### probe03_bridge.py (89 LOC)

**Purpose:** ctypes/objc/libproc bridge setup and generic NSDictionary/NSArray/reflection helpers
(`_cf_describe`, `_dict_all_keys`) used to dump arbitrary CGWindow fields.
**Reads:** —
**Writes:** —
**Called by:** probe03_diagnostics.py, probe03_windows.py, probe03_ghostty_detail.py,
03_field_availability_probe.py
**Calls out:** `objc`/`ctypes` (CGS bridge).

### probe03_diagnostics.py (69 LOC)

**Purpose:** Same TCC-identity/TCC.db diagnostics as `probe02_diagnostics.py`, kept separate per
the no-cross-script-dedup rule.
**Reads:** `TCC.db`, `codesign`, `ps`.
**Writes:** —
**Called by:** 03_field_availability_probe.py
**Calls out:** `Foundation` (`NSBundle`).

### probe03_windows.py (114 LOC)

**Purpose:** Full CGWindow field dump (all windows, all keys) and the field-availability summary
build.
**Reads:** live CGS state.
**Writes:** —
**Called by:** 03_field_availability_probe.py, probe03_ghostty_detail.py
**Calls out:** —

### probe03_ghostty_detail.py (155 LOC)

**Purpose:** Per-Ghostty-window CG-field + AppleScript-bounds detail, including the AS-vs-CG rect
comparison and the AS window-properties/bounds/position/geometry-verdict probe.
**Reads:** live CGS state, Ghostty via AppleScript.
**Writes:** —
**Called by:** 03_field_availability_probe.py
**Calls out:** Ghostty via AppleScript (`osascript`).

### probe03_report.py (18 LOC)

**Purpose:** Writes the field-availability report JSON.
**Reads:** —
**Writes:** `03_reports/<tag>_<timestamp>.json`.
**Called by:** 03_field_availability_probe.py
**Calls out:** —

---

### 04_space_move_probe.py (18 LOC)

**Purpose:** Orchestrates the `SLSBridgedMoveWindowsToManagedSpaceOperation` move test; entry
point only, logic lives in `probe04_*.py`.
**Reads:** —
**Writes:** —
**Called by:** none — run manually; MUTATES the desktop (moves a real window between Spaces).
**Calls out:** `probe04_bridge`, `probe04_detection`, `probe04_move`, `probe04_workflow`.

### probe04_bridge.py (94 LOC)

**Purpose:** ctypes/objc bridge setup and generic NSDictionary/NSArray helpers, including the
`initWithWindows:spaceID:`/`performWithWMBridgeDelegate` calling-convention typedefs.
**Reads:** —
**Writes:** —
**Called by:** probe04_detection.py, probe04_move.py, probe04_workflow.py, 04_space_move_probe.py
**Calls out:** `objc`/`ctypes` (CGS bridge).

### probe04_detection.py (75 LOC)

**Purpose:** Space map, on-screen/Ghostty-window WID queries, and per-WID Space lookup.
**Reads:** live CGS state.
**Writes:** —
**Called by:** probe04_workflow.py
**Calls out:** —

### probe04_move.py (32 LOC)

**Purpose:** The `SLSBridgedMoveWindowsToManagedSpaceOperation` move call and screenshot capture.
**Reads:** —
**Writes:** MUTATES — moves a window between Spaces; writes a screenshot PNG.
**Called by:** probe04_workflow.py
**Calls out:** `objc`/`ctypes` (SkyLight bridge), `screencapture`.

### probe04_workflow.py (148 LOC)

**Purpose:** Precondition check, before/move/after trial, restore phase, and summary/dump-file
steps that make up the probe's run — split out of the former single `probe_workflow`.
**Reads:** live CGS state.
**Writes:** stdout PASS/FAIL + `04_reports/` screenshots and on-screen WID dump `.txt`.
**Called by:** 04_space_move_probe.py
**Calls out:** —

---

### 05_window_detection_probe.py (41 LOC)

**Purpose:** Orchestrates the pure window-detection probe (tmux/OSC-2/CotEditor trials); entry
point only, logic lives in `probe05_*.py`.
**Reads:** —
**Writes:** —
**Called by:** none — run manually; MUTATES the desktop (opens/closes real windows).
**Calls out:** `probe05_bridge`, `probe05_detection`, `probe05_lifecycle`, `probe05_trial`.

### probe05_bridge.py (90 LOC)

**Purpose:** ctypes/objc bridge setup and generic NSDictionary/NSArray helpers.
**Reads:** —
**Writes:** —
**Called by:** probe05_detection.py, probe05_lifecycle.py, probe05_trial.py,
05_window_detection_probe.py
**Calls out:** `objc`/`ctypes` (CGS bridge).

### probe05_detection.py (146 LOC)

**Purpose:** Window-type constants (`_WIN_*`, `_OWNER`, `_REQUIRE_NAME`, `_TOKEN_PREFIX`) plus
Space/window/title-match(`method_a`)/frontmost(`method_b`) queries shared by lifecycle and trial.
**Reads:** live CGS state.
**Writes:** —
**Called by:** probe05_lifecycle.py, probe05_trial.py, 05_window_detection_probe.py
**Calls out:** —

### probe05_lifecycle.py (118 LOC)

**Purpose:** Opens/closes the three trial window types (tmux-Ghostty, OSC-2-Ghostty, CotEditor)
and warm-launches CotEditor.
**Reads:** live CGS state.
**Writes:** MUTATES — opens/closes real windows via `tmux`/`open`/AppleScript/`kill`.
**Called by:** probe05_trial.py, 05_window_detection_probe.py
**Calls out:** `tmux`, `open`, Ghostty/CotEditor via AppleScript (`osascript`).

### probe05_trial.py (215 LOC)

**Purpose:** Runs one detection trial (setup → snapshot → poll → measure signals → cleanup →
assemble/write result) and prints the final summary table.
**Reads:** live CGS state.
**Writes:** `05_reports/trial_<type>_<n>_<timestamp>.json`; stdout.
**Called by:** 05_window_detection_probe.py
**Calls out:** —

---

### 06_move_sweep_probe.py (25 LOC)

**Purpose:** Orchestrates the 4-primitive move sweep; entry point only, logic lives in
`probe06_*.py`.
**Reads:** —
**Writes:** —
**Called by:** none — run manually; MUTATES the desktop (opens/closes a CotEditor window and
attempts to move it).
**Calls out:** `probe06_bridge`, `probe06_detection`, `probe06_coteditor`, `probe06_primitives`,
`probe06_workflow`, `probe06_report`.

### probe06_bridge.py (107 LOC)

**Purpose:** ctypes/objc/SkyLight/ApplicationServices bridge setup (incl. AX + ScreenCapture
preflight argtypes) and generic NSDictionary/NSArray helpers.
**Reads:** —
**Writes:** —
**Called by:** probe06_detection.py, probe06_workflow.py, 06_move_sweep_probe.py
**Calls out:** `objc`/`ctypes` (CGS/SkyLight/ApplicationServices bridge).

### probe06_detection.py (100 LOC)

**Purpose:** Space map, WID/title-match queries, the AX/ScreenCapture permission self-check, and
the first-non-active-nonempty-Space finder.
**Reads:** live CGS state, `AXIsProcessTrusted`, `CGPreflightScreenCaptureAccess`.
**Writes:** stdout permission-check block.
**Called by:** probe06_coteditor.py, probe06_workflow.py, 06_move_sweep_probe.py
**Calls out:** —

### probe06_coteditor.py (51 LOC)

**Purpose:** Warm-launches CotEditor and opens/detects/closes a token-named CotEditor document
for each primitive trial.
**Reads:** live CGS state.
**Writes:** MUTATES — opens/closes a real CotEditor window via `open`/AppleScript.
**Called by:** probe06_workflow.py, 06_move_sweep_probe.py
**Calls out:** `open`, CotEditor via AppleScript (`osascript`).

### probe06_primitives.py (59 LOC)

**Purpose:** Dynamic symbol loading (`_try_sym`), argtypes setup (`_setup`), screenshot capture,
and the before/call/after measurement of one move-primitive trial.
**Reads:** live CGS state.
**Writes:** MUTATES — invokes the move primitive under test; writes screenshot PNGs under
`06_reports/`.
**Called by:** probe06_workflow.py
**Calls out:** `screencapture`.

### probe06_workflow.py (142 LOC)

**Purpose:** Probe setup, precondition validation, the 4 primitives' symbol loading and
per-primitive `call_fn` construction/execution steps that make up the sweep.
**Reads:** live CGS state.
**Writes:** stdout status lines.
**Called by:** 06_move_sweep_probe.py
**Calls out:** —

### probe06_report.py (25 LOC)

**Purpose:** Prints the per-primitive result table and the PASS/FAIL headline.
**Reads:** —
**Writes:** stdout.
**Called by:** 06_move_sweep_probe.py
**Calls out:** —

---

## Gotchas

**`kCGWindowName` is stripped to null under launchd/bundle-exec contexts without Screen
Recording permission; `kCGWindowOwnerPID`, `kCGWindowNumber`, and `CGSCopySpacesForWindows` are
NOT** — TCC only blocks the window-title field, not window enumeration or space lookup.

**AppleScript returns `-1728` for every window-geometry query** (`bounds of window`, `position of
window`) in Ghostty's AS dictionary, in all execution contexts, regardless of Screen Recording
status — this is a Ghostty AS-dictionary gap, not a TCC issue. `working directory of terminal`
also always reflects the app's launch cwd, not the current tab's cwd — do not rely on it.

**All 5 tested window-move APIs (`04_space_move_probe.py`'s ObjC path plus the 4 primitives in
`06_move_sweep_probe.py`) executed without crashing but moved nothing** on the macOS version
these probes were run against — every move call is currently a confirmed no-op; do not assume any
of them works without re-verifying on the target OS version first.
