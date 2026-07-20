# dev/desktop_detection/

## Problem

**What happens:** Monitor_CC Menubar displays arbitrary slot-numbers `[1]` `[2]` `[3]` instead of user-visible Mission Control Desktop numbers for each Main CC session. Worker windows spawn on random desktops. `show <file>` opens apps on wrong desktops.

**Manifestation:** No production impact yet (Menubar shows slot-based order, not spatial order). Detection pipeline missing — this investigation builds it.

**Production code status:** No changes yet. Detection probe only. See `process-docs/desktop_allocation/` for design and iteration history.

## Investigation

### Code Analysis

Existing production code relevant to the pipeline:

| File | What it provides |
|---|---|
| `src/menubar/ghostty.py` | cwd → UUID via OSC-2 title-probe; writes `ghostty_cwd_uuid.json` |
| `src/menubar/proc_cache.py:_cc_proc_cache` | pid → (tty, cwd) cache for CC processes |
| `src/menubar/discover.py:list_alive_sessions()` | returns `SessionInfo` including cwd for Mains |
| `~/Library/.../ghostty_cwd_uuid.json` | live {cwd: uuid} map written by Menubar at 1.5s cadence |

Pipeline gap: UUID is Ghostty-internal; macOS CGS APIs need `CGWindowID` (kCGWindowNumber). No direct Ghostty → CGWindowID link exposed.

### External Research

| Source | Result | Relevance |
|---|---|---|
| Ghostty AppleScript: `bounds of terminal id "UUID"` | -1728 error ❌ | Primary strategy (bounds-match) not available |
| Ghostty AppleScript: `window of terminal id "UUID"` | -1728 error ❌ | Direct UUID→window nav not exposed |
| Ghostty AppleScript: `working directory of terminal` | Returns Monitor_CC for ALL terminals ❌ | Bug in Ghostty AS dictionary — always reflects app launch dir, not tab cwd |
| Ghostty AppleScript: `id of terminal of tab of window` | Works ✅ | Gives UUID per tab → UUID→window_id mapping |
| `CGWindowListCopyWindowInfo(0, 0)` (option=0) | 279 windows incl. off-screen ✅ | `kCGWindowListOptionAll=0` = all spaces; `1` = OnScreenOnly |
| `CGWindowListCopyWindowInfo(1, 0)` (option=1) | 26 windows (on-screen only) | NOT "all" — maps to `kCGWindowListOptionOnScreenOnly` |
| `CGSCopyManagedDisplaySpaces` dict keys | `Display Identifier`, `Spaces`, `ManagedSpaceID` ✅ | Not `DisplayIdentifier` or `id` |
| `CGSCopySpacesForWindows(cid, 0x7, arr)` | Returns [space_id] per WID ✅ | mask=0x7 works; returns [] for invalid WIDs |

### Hypotheses

| Hypothesis | Status | Evidence |
|---|---|---|
| AppleScript bounds → bounds-match → CGWindowID | **Excluded** | `-1728` on `bounds of terminal id "UUID"`, `bounds of window 1`, `position of window 1` — AS has zero geometry at any level |
| AppleScript tab traversal → UUID→window_id → kCGWindowName match | **Confirmed** ✅ | `id of terminal of tab` works; kCGWindowName = focused tab title |
| CGS space detection pipeline (CGSCopyManagedDisplaySpaces + CGSCopySpacesForWindows) | **Confirmed** ✅ | Returns correct desktop_no for all tested WIDs |
| OSC-2 injection required for ambiguous window names | **Active** | Fires when CC tab is not the focused tab in its Ghostty window |
| TCC blocks window enumeration (kCGWindowOwnerPID) in launchd/bundle context | **Excluded** ❌ | 02_context_comparison_probe: all 3 contexts return 17 Ghostty windows with correct PID |
| TCC strips kCGWindowName in launchd/bundle context | **Confirmed** ✅ | kCGWindowName=null for all Ghostty+Finder windows in launchd/bundle; CC-Bash has full titles |
| kCGWindowBounds available without Screen Recording | **Confirmed** ✅ | 03_field_availability_probe: 280/280 populated in launchd and bundle contexts |
| AX/_AXUIElementGetWindow viable in launchd context | **Pending** | Next probe — different TCC surface (Accessibility vs Screen Recording) |

## Scripts

### `01_probe.py` (389 LOC)

Proves the full pipeline: `cwd → UUID → CGWindowID → SpaceID → Desktop-No`. Read-only. No src/ changes.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
./venv/bin/python dev/desktop_detection/01_probe.py
```

**Requires:** Menubar running (writes `ghostty_cwd_uuid.json`), Ghostty running.

**Output:** Per-main-session table with session_name / cwd / tty / uuid / cgwindow_id / space_id / display / desktop_no, then active-space diagnostics, spaces-per-display summary, detection rate, strategy breakdown.

**Three-strategy resolution (in order):**
1. `name-unique` — Ghostty AppleScript `name of window` for the UUID's window matches exactly one CGWindow's `kCGWindowName`
2. `space-elimination` — multiple candidates with same name; eliminate those whose space is already claimed by a matched main; fires when main sessions share a window name (e.g., all showing `/Users/.../cwd`)
3. `osc2-injection` — inject OSC-2 marker to CC process tty, 150ms wait, re-match kCGWindowName; fires when both above fail (CC tab is background tab in its Ghostty window)

### `02_context_comparison_probe.py` (347 LOC)

Measures which CGS API fields are accessible across three execution contexts to empirically determine TCC boundary for Etappe 2. Read-only on macOS state.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
# Context 1 — CC-Bash (direct):
.claude/worktrees/probe02-context/venv/bin/python \
  .claude/worktrees/probe02-context/dev/desktop_detection/02_context_comparison_probe.py --tag=ccbash

# Context 2 — launchd (one-shot LaunchAgent plist, see B2_context_comparison_probe.md)
# Context 3 — bundle (open -n 02_bundle_stub.app/, see B2_context_comparison_probe.md)
```

**Requires:** Menubar running (for detection pipeline), Ghostty running.

**Output:** JSON report in `json/<tag>_<YYYYMMDD_HHMMSS>.json` with context_diagnostics, tcc_state, detection_result, raw_windows.

**Key finding:** `kCGWindowOwnerPID`, `kCGWindowNumber`, `CGSCopySpacesForWindows` work in ALL contexts. `kCGWindowName` returns null without Screen Recording. See `process-docs/desktop_allocation/B2_context_comparison_probe.md`.

### `02_bundle_stub.app/`

Minimal `.app` bundle (CFBundleIdentifier=`com.brunowinter.monitor_cc_menubar`, ad-hoc signed) used to run the probe in bundle-exec context (same exec chain as production menubar). Launcher: `Contents/MacOS/launcher` → `exec venv/bin/python3 02_context_comparison_probe.py --tag=bundle`.

### `03_field_availability_probe.py` (260 LOC)

Dumps ALL CGWindow dict fields across all windows in three contexts to determine which fields survive TCC stripping. Adds AS geometry query documentation. Builds on probe02's ObjC bridge; adds `_dict_all_keys()` + `_cf_describe()` helpers for full-dict enumeration.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
# Context 1 — CC-Bash (direct):
.claude/worktrees/probe03-fields/venv/bin/python \
  .claude/worktrees/probe03-fields/dev/desktop_detection/03_field_availability_probe.py --tag=ccbash

# Context 2 — launchd (one-shot LaunchAgent plist, see B3_field_availability_probe.md)
# Context 3 — bundle (open -n 03_bundle_stub.app/, see B3_field_availability_probe.md)
```

**Requires:** Ghostty running.

**Output:** JSON report in `json/<tag>_<YYYYMMDD_HHMMSS>.json` with context_diagnostics, tcc_state, all_field_keys_observed, field_availability_summary, ghostty_windows_detailed, ghostty_as_window_properties.

**Key findings:** `kCGWindowBounds` fully populated (280/280) in all three contexts including launchd — TCC-unblocked. AS returns `-1728` for `bounds of window N` in all contexts regardless of Screen Recording status — not a TCC issue, simply not implemented in Ghostty's AS dictionary. `kCGWindowBackingLocationVideoMemory` not returned by the API on macOS 15.7.7. See `process-docs/desktop_allocation/B3_field_availability_probe.md`.

### `03_bundle_stub.app/`

Minimal `.app` bundle (CFBundleIdentifier=`com.brunowinter.monitor_cc_menubar`, ad-hoc signed) for probe03 bundle-context run. Launcher points to probe03-fields worktree venv + `03_field_availability_probe.py --tag=bundle`. Separate from `02_bundle_stub.app/` because each stub hardcodes its worktree path.

### `04_space_move_probe.py` (305 LOC)

Tests whether `SLSBridgedMoveWindowsToManagedSpaceOperation` + `performWithWMBridgeDelegate` (DockDoor/yabai technique, validated on 26.4.1) moves a non-owned Ghostty window to the active space on macOS 26.5.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
./venv/bin/python dev/desktop_detection/04_space_move_probe.py
```

**Requires:** Ghostty running with ≥ 1 window on a non-active Mission Control space (≥ 2 spaces total).

**Output:** PASS/FAIL line (`grep "RESULT:"`) + before/after/restore screenshots in `png/` + on-screen WID dump in `txt/`. Precondition-not-met messages if setup is insufficient.

**Move direction:** non-active space → active space (positive presence assertion — window appears in `CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly=1, 0)` after the call).

**Key implementation notes:**
- `_ghostty_wids_all()` filters `kCGWindowName != None` — excludes Ghostty tab-bar strips (33px height, name=None) which cannot be moved between spaces.
- Two new CFUNCTYPEs: `_FT_0vv` (void, self+sel) for `performWithWMBridgeDelegate`; `_FT_vvvu64` (id, self, sel, NSArray*, uint64) for `initWithWindows:spaceID:`.
- `performWithWMBridgeDelegate` is inherited from parent `SLSAsynchronousBridgedWindowManagementOperation` (not defined directly on the child class on 26.5).
- On macOS 26.5: **FAIL** — ObjC chain executes without crash but window does not move. See `process-docs/desktop_allocation/G2_space_move_probe.md` for hypotheses.

### `06_move_sweep_probe.py` (435 LOC)

Sweeps 4 C-level window-move primitives (CGS + SkyLight) to determine whether any can relocate a CotEditor window from the active Space to a non-active non-empty Space on macOS 26.5. Includes a permission self-check (AX + ScreenCapture + binary realpath) before any move attempt.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
./venv/bin/python dev/desktop_detection/06_move_sweep_probe.py
```

**Requires:** ≥ 2 Mission Control spaces with at least one existing window on a non-active space. CotEditor: probe opens fresh docs per primitive (no warm-launch required, though CotEditor must be running for reliable doc detection; add `_ensure_coteditor_running()` if cold-launch is possible).

**Output:** Permission block (AX / ScreenCapture / binary path), symbol-load status for all 4 primitives, per-primitive in_before/in_after/moved with screenshot paths in `06_reports/`, HEADLINE line.

**Primitives tested (A/B/C/D):**
- A: `CGSMoveWindowsToManagedSpace` (CoreGraphics)
- B: `SLSMoveWindowsToManagedSpace` (SkyLight)
- C: `CGSAddWindowsToSpaces` + `CGSRemoveWindowsFromSpaces` (CoreGraphics add/remove pair)
- D: `SLSSpaceSetCompatID` + `SLSSetWindowListWorkspace` (SkyLight CompatID route)

**Key design:**
- Fresh CotEditor doc per primitive (`open -g`, no `-n`); closed via AppleScript by token name regardless of which Space it ends up on — no restore mechanism, no stranding risk.
- Verification via `CGWindowListCopyWindowInfo(onscreen_only=1)` membership (NOT `CGSCopySpacesForWindows` which lags).
- `_wids(onscreen=False)` parameterizes the on-screen/all-spaces scan into a single function.
- `_try_sym` uses `ctypes.c_void_p.in_dll(lib, name)` for reliable symbol existence check (ctypes attribute access does NOT raise AttributeError for missing symbols).
- uint32 window ID arrays (`_make_uint_array`) and uint64 space ID arrays (`_make_uint64_array` with `numberWithUnsignedLongLong:`) constructed separately.

**Key findings (macOS 26.5, run 2026-05-31):**
- AX=True, ScreenCapture=True — full permissions held; TCC is not the blocker.
- All 4 symbols resolve (no MISSING); all 4 calls execute silently without crash.
- **ALL 4 primitives are no-ops** — `in_after=True` for all, no window left the active Space.
- Combined with G2 (ObjC `SLSBridgedMoveWindowsToManagedSpaceOperation`): 5/5 move APIs tested on 26.5, 0/5 functional.
- See `process-docs/desktop_allocation/G4_move_sweep_probe.md`.

### `05_window_detection_probe.py` (527 LOC)

Pure window-detection probe: for each new window, can we RELIABLY (a) identify the SPECIFIC window and (b) determine which Space it appeared on. NO window moves. Three window types × 3 trials (9 total). Two passes: pass 1 baseline, pass 2 CotEditor fixed.

**Usage:**
```bash
cd /Users/brunowinter2000/Documents/ai/Monitor_CC
./venv/bin/python dev/desktop_detection/05_window_detection_probe.py
```

**Requires:** Ghostty running. CotEditor: probe warm-launches it if not running.

**Output:** per-trial JSON in `json/trial_<type>_<n>_<ts>.json` + stdout summary table (`type × trial × fg/bg × gt_wid × A_agree × B_agree × desktop × space_agree`).

**Window types:**
1. `ghostty_tmux` — `open -n -a Ghostty --args --command "tmux attach-session -t <tok>"`, token prefix `p05t`
2. `ghostty_osc2` — `open -n -a Ghostty --args --command "bash -c 'printf OSC-2-tok; sleep 60'"`, token prefix `p05g`
3. `coteditor` — write `/tmp/probe05_<tok>.txt`, `open -g -a CotEditor <file>` (no -n; warm-launch required), token prefix `p05c`

**Ground truth:** Ghostty: snapshot-diff (`_owner_wids_layer0` before/after, `min(delta)`). CotEditor: token-name poll (`_method_a("CotEditor", token)` until non-None) — avoids cold-launch session-restore contamination.

**Two identification methods measured:**
- **Method A (title-match):** kCGWindowName contains token → compare to gt_wid
- **Method B (frontmost):** first owner+layer0 window in CGWindowList z-order → compare to gt_wid

**Space signals (3-way cross-check):**
- S1: `CGSGetActiveSpace` before open
- S2: gt_wid in `_on_screen_wids()` after open (on active space?)
- S3: `CGSCopySpacesForWindows(gt_wid)` → space_id

**Key findings (macOS 26.5, run 2026-05-31):**
- Space detection S1/S2/S3: **WORKS for all types** — 12/12 all_agree=True (Ghostty 6/6 + CotEditor 3/3 after fix)
- CotEditor Method A+B (pass 2 fixed): **WORKS** 3/3 — token in filename → kCGWindowName reliable; warm-launch prevents session restore
- Ghostty Method A: **FAILS** 0/6 — `open --args --command` not honored; Ghostty starts default shell → CWD title
- Ghostty Method B: **FAILS** 0/6 — probe terminal stays frontmost among Ghostty windows
- See `process-docs/desktop_allocation/G3_window_detection_probe.md` for full analysis.
