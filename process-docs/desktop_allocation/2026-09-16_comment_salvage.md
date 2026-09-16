# process-docs/desktop_allocation/2026-09-16_comment_salvage.md

Session: dev/desktop_detection/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/desktop_detection/*.py` during this milestone, copied
verbatim before deletion, plus the full pre-rewrite content of `dev/desktop_detection/DOCS.md`.
Nothing judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File-count note: the milestone prompt stated "24 .py files"; the actual count in
`dev/desktop_detection/` is 32 `.py` files. 8 of the 32 (`01_probe.py`, `02_context_comparison_probe.py`,
`03_field_availability_probe.py`, `04_space_move_probe.py`, `05_window_detection_probe.py`,
`06_move_sweep_probe.py`, `probe01_report.py`, `probe06_report.py`) already had zero comments before
this milestone touched them — 32 minus those 8 is exactly 24, so the prompt's figure is read as
"files with at least one comment," not the true file count. The stated comment/docstring totals
(150 comments, 0 docstrings) matched exactly what AST+tokenize measured across all 32 files.

Grep for `__doc__`/`.help(`/`epilog` across `dev/desktop_detection/*.py` before deletion: zero
matches. Two files (`02_context_comparison_probe.py`, `03_field_availability_probe.py`) pass a
plain string literal to `argparse.ArgumentParser(description=...)` — not `__doc__`, not a
docstring at all (both files measure 0 docstrings). No load-bearing docstring exists anywhere in
this directory; there were 0 docstrings to begin with.

## Desktop-mutation classification (read this before touching any script here again)

Main's own classification, confirmed in this session: **4 of the 6 numbered entry scripts mutate
the real macOS desktop** and were never executed as part of this milestone's verification:
`01_probe.py` (writes a real OSC-2 escape sequence to a live tty to retitle a real terminal window
during `_osc2_inject_match` — classified as mutating regardless of the fact that it restores the
title afterward, because it changes a real window's title on the machine the user is actively
using), `04_space_move_probe.py` (really moves a live window between Mission Control Spaces via
`SLSBridgedMoveWindowsToManagedSpaceOperation`, screenshots), `05_window_detection_probe.py`
(really opens/closes tmux/Ghostty windows and CotEditor documents, some in foreground),
`06_move_sweep_probe.py` (really opens/closes a CotEditor document and invokes 4 private
window-move APIs against it, screenshots). Their behavior-preservation proof in this session used
a **static stripped-copy diff** (mechanically strip all comments/docstrings from the pre-edit
source via the same extraction script used to build this salvage file, then diff the result
against the actual post-edit file byte-for-byte) — NOT execution.

`02_context_comparison_probe.py` and `03_field_availability_probe.py` (plus their `probeNN_*.py`
support modules) are read-only — TCC/codesign/CGWindowList/read-only-AppleScript queries only —
and WERE executed before/after this session, output diffed byte-for-byte.

Comment/docstring counts confirmed via AST + tokenize before deletion: 150 comments, 0 docstrings,
matching the task's stated measured state exactly.

## Salvage from dev/desktop_detection/DOCS.md

Full content of dev/desktop_detection/DOCS.md as it stood before this rewrite (336 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / Flow / State sections added).

```markdown
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
```

## Salvage from dev/proxy/01_probe.py

## Salvage from dev/proxy/02_context_comparison_probe.py

## Salvage from dev/proxy/03_field_availability_probe.py

## Salvage from dev/proxy/04_space_move_probe.py

## Salvage from dev/proxy/05_window_detection_probe.py

## Salvage from dev/proxy/06_move_sweep_probe.py

## Salvage from dev/proxy/probe01_bridge.py

COMMENT L13:
```
# CFUNCTYPE refs at module level — GC-safe (GC'ing these corrupts the IMP pointer table)
```

COMMENT L24:
```
# CGS / CGWindow function signatures (set once at module load)
```

COMMENT L38:
```
# --- objc bridge helpers ---
```

COMMENT L66:
```
# Build NSMutableArray of unsigned-int values (for CGSCopySpacesForWindows window list)
```

## Salvage from dev/proxy/probe01_pipeline.py

COMMENT L15:
```
# works for all regular spaces
```

COMMENT L16:
```
# kCGWindowListOptionAll — all windows incl. off-screen spaces
```

COMMENT L17:
```
# kCGNullWindowID
```

COMMENT L21:
```
# --- data gathering ---
```

COMMENT L23:
```
# Return PID int of running Ghostty.app process, or None
```

COMMENT L34:
```
# Read ghostty_cwd_uuid.json → {cwd: uuid}; None if file missing (menubar not running)
```

COMMENT L40:
```
# Build {cwd: tty} for all CC processes (command contains 'claude', tty != '??')
```

COMMENT L41:
```
# One ps call + lsof per CC pid; mirrors proc_cache.py _refresh_cc_proc_cache pattern
```

COMMENT L65:
```
# AppleScript one-call: returns ({uuid: ghostty_win_id}, {ghostty_win_id: win_name})
```

COMMENT L66:
```
# Traverses all windows → tabs → terminal; one round-trip to Ghostty
```

COMMENT L98:
```
# Return {window_name: [wid, ...]} for all layer-0 named Ghostty-owned CGWindows (all spaces)
```

COMMENT L116:
```
# Return (space_map, active_space_id)
```

COMMENT L117:
```
# space_map: {space_id: (display_id_abbrev, desktop_no_1based)}
```

COMMENT L118:
```
# Defensive: probes multiple key names for display identifier and space id
```

COMMENT L143:
```
# Return list of space_ids for a single CGWindowID via CGSCopySpacesForWindows
```

COMMENT L158:
```
# OSC-2 fallback: inject unique marker to tty, re-check kCGWindowName after 150ms
```

COMMENT L159:
```
# Effective only when the injected terminal is the focused tab in its Ghostty window
```

COMMENT L168:
```
# restore shell-default title
```

COMMENT L175:
```
# Resolve CGWindowID for one Main session via three strategies (in order):
```

COMMENT L176:
```
# 1) Unique kCGWindowName match  2) Space-based elimination  3) OSC-2 injection
```

COMMENT L177:
```
# Returns (cgwindow_id, strategy_used, diagnostic_note)
```

COMMENT L193:
```
# Space-based elimination: find candidates not on spaces claimed by other mains
```

COMMENT L208:
```
# OSC-2 injection: only effective when the CC tab is the focused tab in its window
```

COMMENT L219:
```
# Build one session row: resolve cgwindow_id, then space_id/desktop_no/display if resolved
```

COMMENT L261:
```
# Gather all live state and build session rows; returns (rows, space_map, active_space)
```

## Salvage from dev/proxy/probe01_report.py

## Salvage from dev/proxy/probe02_bridge.py

COMMENT L33:
```
# proc_pidinfo flavor 58 = PROC_PIDT_RESPONSIBLE_PID
```

## Salvage from dev/proxy/probe02_diagnostics.py

COMMENT L17:
```
# Return TCC-identity diagnostics: codesign, NSBundle.mainBundle().bundleIdentifier(), env, responsible_pid
```

COMMENT L50:
```
# Best-effort read of TCC.db ScreenCapture grants; returns error info if unreadable
```

## Salvage from dev/proxy/probe02_pipeline.py

COMMENT L20:
```
# Return PID of running Ghostty.app, or None
```

COMMENT L31:
```
# Return space_ids for a single CGWindowID
```

COMMENT L43:
```
# Return (space_map {sid: (disp_abbrev, desktop_no)}, active_space_id)
```

COMMENT L61:
```
# Return all windows; space_ids only for layer=0 (key TCC comparison signal)
```

COMMENT L79:
```
# Read cwd_uuid map; returns (map, None) or (None, skip_reason)
```

COMMENT L91:
```
# AppleScript one-call: returns ({ghostty_win_id: uuid}, {ghostty_win_id: win_name})
```

COMMENT L122:
```
# Return {window_name: [wid, ...]} for all layer-0 named Ghostty CGWindows
```

COMMENT L137:
```
# Build one pipeline row (name-unique strategy only)
```

COMMENT L163:
```
# Detection pipeline: cwd_uuid → AppleScript → CGWindowList (name-unique strategy only)
```

COMMENT L164:
```
# Returns (sessions_list, skip_reason_or_None)
```

COMMENT L182:
```
# Collect detection_result section: window stats + pipeline
```

## Salvage from dev/proxy/probe02_report.py

COMMENT L12:
```
# Write report JSON to _REPORTS_DIR/<tag>_<YYYYMMDD_HHMMSS>.json
```

## Salvage from dev/proxy/probe03_bridge.py

COMMENT L68:
```
# Return human-readable string description of any NSObject via [obj description] → UTF8String
```

COMMENT L78:
```
# Return all string keys from a CF/NS dictionary via [d allKeys]
```

## Salvage from dev/proxy/probe03_diagnostics.py

COMMENT L17:
```
# Collect TCC-identity diagnostics: codesign, NSBundle.mainBundle(), env, responsible_pid
```

COMMENT L50:
```
# Best-effort read of TCC.db ScreenCapture grants
```

## Salvage from dev/proxy/probe03_ghostty_detail.py

COMMENT L44:
```
# One-shot AS query: properties of window 1 — discover what Ghostty exposes at window level
```

COMMENT L63:
```
# Attempt AS bounds for a specific window index; returns (method_str, result_or_None, error_or_None)
```

COMMENT L73:
```
# Enumerate Ghostty windows in order (layer=0 only)
```

COMMENT L96:
```
# AS bounds: attempt once for window index 1 (covers all — Ghostty has one CGWindow per window)
```

COMMENT L97:
```
# and once for window index 2 (second window if present), then reuse the single error result
```

COMMENT L107:
```
# Attach AS bounds info to each entry
```

COMMENT L123:
```
# Rect comparison (N/A when AS side returns no bounds)
```

COMMENT L125:
```
# Parse AS result like "0, 25, 1512, 1220" → [x1,y1,x2,y2]
```

COMMENT L129:
```
# AS: x1,y1,x2,y2 → CG: X,Y,Width,Height
```

COMMENT L148:
```
# Collect per-Ghostty-window detail: CG fields + AS bounds attempt
```

## Salvage from dev/proxy/probe03_report.py

COMMENT L12:
```
# Write report JSON to _REPORTS_DIR/<tag>_<YYYYMMDD_HHMMSS>.json
```

## Salvage from dev/proxy/probe03_windows.py

COMMENT L13:
```
# Dump all key/value pairs from a CGWindow dict; kCGWindowBounds handled as nested dict
```

COMMENT L38:
```
# Return kCGWindowBounds sub-dict as {X,Y,Width,Height} or None
```

COMMENT L46:
```
# Build field_availability_summary across all windows
```

COMMENT L71:
```
# Return space_ids for a single CGWindowID
```

COMMENT L83:
```
# Return PID of running Ghostty.app, or None
```

COMMENT L94:
```
# Full CGWindow dump: all windows, all keys, build field_availability_summary
```

COMMENT L102:
```
# reuse same list for Ghostty-detail pass
```

## Salvage from dev/proxy/probe04_bridge.py

COMMENT L13:
```
# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
```

COMMENT L21:
```
# bridged-op:
```

COMMENT L41:
```
# --- objc bridge helpers (verbatim from 01_probe.py) ---
```

COMMENT L85:
```
# Build NSMutableArray of NSNumber(numberWithUnsignedInt:) — correct shape for
```

COMMENT L86:
```
# initWithWindows:spaceID: (CGWindowID = uint32_t; verbatim from 01_probe.py)
```

## Salvage from dev/proxy/probe04_detection.py

COMMENT L7:
```
# kCGWindowListOptionAll — all spaces
```

COMMENT L8:
```
# kCGWindowListOptionOnScreenOnly — active space only
```

COMMENT L13:
```
# Returns ({space_id: (display_abbrev, desktop_no_1based)}, active_space_id)
```

COMMENT L35:
```
# WIDs of every window visible on the currently-active space
```

COMMENT L45:
```
# WIDs of all layer-0 named Ghostty terminal windows across all spaces.
```

COMMENT L46:
```
# Requires kCGWindowName != None — excludes tab-bar strips (name=None, h=33px).
```

COMMENT L63:
```
# Space IDs for a WID — used only to record original space before the move
```

COMMENT L64:
```
# (not part of PASS/FAIL; CGSCopySpacesForWindows may lag after moves).
```

## Salvage from dev/proxy/probe04_move.py

COMMENT L11:
```
# SLSBridgedMoveWindowsToManagedSpaceOperation — DockDoor / yabai technique.
```

COMMENT L12:
```
# Class hierarchy on 26.5: SLSBridgedMoveWindowsToManagedSpaceOperation
```

COMMENT L13:
```
#   → SLSAsynchronousBridgedWindowManagementOperation (defines performWithWMBridgeDelegate)
```

COMMENT L14:
```
# performWithWMBridgeDelegate returns void — success verified externally via on-screen list.
```

## Salvage from dev/proxy/probe04_workflow.py

COMMENT L20:
```
# --- Preconditions ---
```

COMMENT L68:
```
# --- BEFORE: snapshot + screenshot ---
```

COMMENT L75:
```
# --- MOVE: non-active -> active via bridged-op ---
```

COMMENT L80:
```
# --- AFTER: snapshot + screenshot ---
```

COMMENT L89:
```
# --- PASS/FAIL (grep-friendly) ---
```

COMMENT L104:
```
# --- RESTORE ---
```

COMMENT L129:
```
# --- Summary + on-screen dump ---
```

## Salvage from dev/proxy/probe05_bridge.py

COMMENT L13:
```
# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
```

COMMENT L37:
```
# --- ObjC bridge helpers (verbatim from 04_space_move_probe.py) ---
```

COMMENT L81:
```
# Build NSMutableArray of NSNumber(numberWithUnsignedInt:) — correct shape for
```

COMMENT L82:
```
# CGSCopySpacesForWindows (CGWindowID = uint32_t; verbatim from 04)
```

## Salvage from dev/proxy/probe05_detection.py

COMMENT L7:
```
# kCGWindowListOptionAll — all spaces
```

COMMENT L8:
```
# kCGWindowListOptionOnScreenOnly — active space only
```

COMMENT L11:
```
# Window type constants
```

COMMENT L18:
```
# require_name=True excludes unnamed intermediate windows; CotEditor document windows have names
```

COMMENT L25:
```
# Returns ({space_id: (display_abbrev, desktop_no_1based)}, active_space_id)
```

COMMENT L47:
```
# WIDs of every window visible on the currently-active space
```

COMMENT L57:
```
# Space IDs for a single WID via CGSCopySpacesForWindows
```

COMMENT L70:
```
# WIDs of all layer-0 windows of `owner`; require_name=True excludes name=None entries
```

COMMENT L87:
```
# PIDs of all processes owning windows attributed to `owner`
```

COMMENT L99:
```
# kCGWindowName + kCGWindowOwnerPID for a given WID (single CGWindowList scan)
```

COMMENT L108:
```
# True if wid appears anywhere in CGWindowList (all spaces)
```

COMMENT L116:
```
# Method A — title-match: first layer-0 window of owner whose name contains token
```

COMMENT L132:
```
# Method B — frontmost: first layer-0 window of owner in CGWindowList front-to-back order
```

## Salvage from dev/proxy/probe05_lifecycle.py

COMMENT L12:
```
# Launch a new window of the given type; foreground=False uses open -g
```

COMMENT L36:
```
# No -n (avoids cold-launch session restore); always -g (background, no focus steal)
```

COMMENT L44:
```
# Killing tmux session exits tmux-attach → Ghostty closes the terminal window
```

COMMENT L73:
```
# Poll until WID gone from CGWindowList (max timeout)
```

COMMENT L82:
```
# Fallback: SIGTERM the owning process if it is a new one (safe: separate -n instance)
```

COMMENT L91:
```
# Close window and clean up per-type side-effects.
```

COMMENT L92:
```
# pids_before: app PIDs pre-trial; a new PID is safe to SIGTERM as cleanup fallback.
```

COMMENT L93:
```
# Returns True if wid is gone from CGWindowList within 3s.
```

COMMENT L107:
```
# Warm-launch CotEditor before trials: prevents cold-launch session-restore from reopening
```

COMMENT L108:
```
# previous documents. If CotEditor is already running, returns immediately.
```

## Salvage from dev/proxy/probe05_trial.py

COMMENT L20:
```
# CotEditor always opened with 'open -g' (no cold-launch, no focus steal)
```

COMMENT L29:
```
# S1: active space snapshotted STRICTLY before open
```

COMMENT L34:
```
# Ghostty: snapshot before open (CotEditor uses token-name poll instead)
```

COMMENT L49:
```
# Token-name poll: CotEditor titles windows with filename — reliable unique key.
```

COMMENT L50:
```
# Avoids snapshot-diff which grabbed session-restored windows (cold-launch issue).
```

COMMENT L56:
```
# detection IS the token-match; agrees by construction
```

COMMENT L59:
```
# Ghostty: snapshot-diff poll — detect new WID by owner-list delta
```

COMMENT L84:
```
# let title settle after detection (OSC-2 late-set, tmux title)
```

COMMENT L89:
```
# For Ghostty: run method_a here (CotEditor: already resolved during poll)
```

COMMENT L93:
```
# Method B — frontmost among owner layer-0 windows
```

COMMENT L97:
```
# Space signals
```

COMMENT L161:
```
# Run one trial: open window, detect via ground-truth + methods A/B, measure space signals.
```

COMMENT L184:
```
# stabilize between trials
```

COMMENT L195:
```
# Format and print per-trial results as aligned summary table
```

## Salvage from dev/proxy/probe06_bridge.py

COMMENT L15:
```
# Module-level CFUNCTYPE refs — GC of these corrupts the IMP pointer table
```

COMMENT L45:
```
# --- ObjC bridge helpers (verbatim from 04_space_move_probe.py) ---
```

COMMENT L89:
```
# Build NSMutableArray of NSNumber(uint32) — window ID arrays
```

COMMENT L99:
```
# Build NSMutableArray of NSNumber(uint64) — space ID arrays
```

## Salvage from dev/proxy/probe06_coteditor.py

COMMENT L12:
```
# Ensure CotEditor is running before trials to prevent cold-launch session restore
```

COMMENT L24:
```
# Write tmpfile and open CotEditor doc for token; always -g (no focus steal, no -n)
```

COMMENT L33:
```
# Poll CGWindowList until CotEditor window with token appears in title (≤5s)
```

COMMENT L43:
```
# Close CotEditor doc by token via AppleScript — works regardless of which Space it's on
```

## Salvage from dev/proxy/probe06_detection.py

COMMENT L15:
```
# Returns ({space_id: (display_abbrev, desktop_no_1based)}, active_space_id)
```

COMMENT L37:
```
# WIDs from CGWindowList; onscreen=True → active space only, False → all spaces
```

COMMENT L48:
```
# Space IDs for a single WID via CGSCopySpacesForWindows
```

COMMENT L61:
```
# First layer-0 window of `owner` whose kCGWindowName contains token
```

COMMENT L77:
```
# Print AX + ScreenCapture + binary identity; return (ax_trusted, sc_trusted)
```

COMMENT L91:
```
# First non-active space in space_map that has at least one off-screen window
```

## Salvage from dev/proxy/probe06_primitives.py

COMMENT L13:
```
# Set argtypes + restype on a ctypes function in one call
```

COMMENT L21:
```
# Return (fn, True) if symbol `name` resolves in `lib`, else (None, False)
```

COMMENT L29:
```
# Measure one move attempt: baseline snapshot → call_fn() → post-snapshot → screenshots
```

## Salvage from dev/proxy/probe06_report.py

## Salvage from dev/proxy/probe06_workflow.py

COMMENT L13:
```
# arbitrary int32 for SLSSpaceSetCompatID / SLSSetWindowListWorkspace
```

COMMENT L49:
```
# Load symbols for all 4 primitives
```

