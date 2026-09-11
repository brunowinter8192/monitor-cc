# dev/desktop_detection/

## Role

Read-only probes for mapping a Claude Code session (via its Ghostty tab cwd) to a Mission Control
desktop number: `cwd → UUID (Ghostty OSC-2) → CGWindowID → SpaceID → Desktop-No`, plus probes for
whether a window can be programmatically MOVED between desktops. No `src/` behavior change — this
is detection-pipeline and TCC-boundary research; production code currently shows slot-based order
(`[1]`/`[2]`/`[3]`), not spatial order. Touch this directory when extending the detection pipeline
or testing a new window-move primitive; see `process-docs/desktop_allocation/` for the full
iteration/hypothesis trail.

## Modules

### 01_probe.py (389 LOC)

**Purpose:** Proves the full pipeline (`cwd → UUID → CGWindowID → SpaceID → Desktop-No`) against
live Menubar + Ghostty state, using a 3-strategy resolution in order: `name-unique` (AppleScript
window name matches exactly one CGWindow), `space-elimination` (multiple name-matches, eliminate
spaces already claimed by a matched main), `osc2-injection` (inject an OSC-2 marker into the CC
tty and re-match).
**Reads:** live Ghostty AppleScript state, `CGWindowListCopyWindowInfo`, `CGSCopySpacesForWindows`,
and Menubar's `ghostty_cwd_uuid.json`.
**Writes:** stdout table (per-session cwd/tty/uuid/cgwindow_id/space_id/display/desktop_no) +
detection-rate/strategy-breakdown summary.
**Called by:** none — run manually; requires Menubar and Ghostty running.
**Calls out:** `objc`/`ctypes` (CGS bridge), Ghostty via AppleScript (`osascript`).

---

### 02_context_comparison_probe.py (347 LOC)

**Purpose:** Measures which CGS API fields are accessible across three execution contexts
(direct CC-Bash, launchd one-shot LaunchAgent, bundle-exec `.app`) to empirically determine the
TCC boundary. `02_bundle_stub.app/` is the minimal ad-hoc-signed bundle used for the bundle-exec
context run.
**Reads:** live CGS/AppleScript state; requires Menubar + Ghostty running.
**Writes:** `json/<tag>_<timestamp>.json` (context_diagnostics, tcc_state, detection_result,
raw_windows).
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle` per context.
**Calls out:** `Foundation` (`NSBundle`), `objc`/`ctypes` (CGS bridge).

---

### 03_field_availability_probe.py (451 LOC)

**Purpose:** Dumps every CGWindow dict field across all windows in the same three execution
contexts as `02_context_comparison_probe.py`, to determine which fields survive TCC stripping.
`03_bundle_stub.app/` is the bundle-exec stub for this probe (separate from `02_bundle_stub.app/`
since each hardcodes its own worktree path).
**Reads:** live CGS/AppleScript state; requires Ghostty running.
**Writes:** `json/<tag>_<timestamp>.json` (context_diagnostics, tcc_state, all_field_keys_observed,
field_availability_summary, ghostty_windows_detailed).
**Called by:** none — run manually with `--tag=ccbash`/`--tag=launchd`/`--tag=bundle`.
**Calls out:** `Foundation` (`NSBundle`), `objc`/`ctypes` (CGS bridge).

---

### 04_space_move_probe.py (305 LOC)

**Purpose:** Tests whether `SLSBridgedMoveWindowsToManagedSpaceOperation` +
`performWithWMBridgeDelegate` (the DockDoor/yabai window-move technique) moves a non-owned
Ghostty window to the active Mission Control space.
**Reads:** live CGS/AppleScript state; requires Ghostty running with a window on a non-active
space (≥2 spaces total).
**Writes:** PASS/FAIL line to stdout (`grep "RESULT:"`); before/after/restore screenshots under
`png/`; on-screen WID dump under `txt/`.
**Called by:** none — run manually.
**Calls out:** `objc`/`ctypes` (CGS/SkyLight bridge).

---

### 05_window_detection_probe.py (527 LOC)

**Purpose:** Pure window-detection probe (no moves) — for each newly-opened window (Ghostty via
tmux, Ghostty via OSC-2, CotEditor), checks whether it can be reliably identified (title-match vs.
frontmost-z-order) and whether its Space can be determined (3-way cross-check:
`CGSGetActiveSpace`, on-screen-list membership, `CGSCopySpacesForWindows`).
**Reads:** live CGS/AppleScript state; requires Ghostty running (CotEditor is warm-launched if
not already running).
**Writes:** `json/trial_<type>_<n>_<timestamp>.json` per trial + stdout summary table.
**Called by:** none — run manually.
**Calls out:** `objc`/`ctypes` (CGS bridge).

---

### 06_move_sweep_probe.py (435 LOC)

**Purpose:** Sweeps 4 C-level window-move primitives — `CGSMoveWindowsToManagedSpace`,
`SLSMoveWindowsToManagedSpace`, `CGSAddWindowsToSpaces`+`CGSRemoveWindowsFromSpaces`,
`SLSSpaceSetCompatID`+`SLSSetWindowListWorkspace` — to determine whether any can relocate a
CotEditor window from the active Space to a non-active non-empty Space. Runs a permission
self-check (AX + ScreenCapture + binary realpath) before any move attempt.
**Reads:** live CGS/AppleScript state; requires ≥2 Mission Control spaces with an existing window
on a non-active space.
**Writes:** permission-block + per-primitive symbol-load/in_before/in_after/moved report to
stdout; screenshots under `06_reports/`.
**Called by:** none — run manually.
**Calls out:** `objc`/`ctypes` (CGS/SkyLight bridge).

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
