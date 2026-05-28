# B3 — CGWindow Field Availability Probe (2026-05-28)

**Status:** Probe complete. Confirms `kCGWindowBounds` is TCC-unblocked. Confirms AS geometry is entirely absent. Eliminates bounds-bridge as a path. Identifies Path D (AX/_AXUIElementGetWindow) as the only remaining low-cost candidate.

## Probe Setup

Three execution contexts, same live macOS session as B2:

| Context | Launch chain | XPC_SERVICE_NAME |
|---|---|---|
| `ccbash` | CC → zsh → venv/python (direct CLI) | `0` |
| `launchd` | launchd plist → venv/python (bare, no bundle) | `com.brunowinter.probe03ctx` |
| `bundle` | `open -n` → bash bundle launcher → `exec` venv/python | `application.com.brunowinter.monitor_cc_menubar.*` |

Script: `dev/desktop_detection/03_field_availability_probe.py` (260 LOC)  
Reports: `dev/desktop_detection/03_reports/{ccbash,launchd,bundle}_20260528_17xxxx.json`  
Total windows enumerated per context: **280**  
Ghostty windows (layer=0): **18** per context

## (a) Full CGWindow Field Availability Table

The API returns exactly **11 field keys** in every window dict. `kCGWindowBackingLocationVideoMemory` (mentioned in Apple docs) was NOT observed in any window dict across any context — likely removed in recent macOS versions.

| Field | ccbash (populated/null) | launchd (populated/null) | bundle (populated/null) | TCC-gated? |
|---|---|---|---|---|
| `kCGWindowBounds` | 280 / 0 | **280 / 0** | **280 / 0** | **NO** ✅ |
| `kCGWindowOwnerPID` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowOwnerName` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowNumber` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowLayer` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowAlpha` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowMemoryUsage` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowSharingState` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowStoreType` | 280 / 0 | 280 / 0 | 280 / 0 | NO ✅ |
| `kCGWindowIsOnscreen` | 23 / 257 | 23 / 257 | 24 / 256 | NO (sparse by design) ✅ |
| `kCGWindowName` | 168 / 112 | **10 / 270** | **10 / 270** | **YES** ❌ |
| `kCGWindowBackingLocationVideoMemory` | — | — | — | N/A (not returned) |

`kCGWindowIsOnscreen` sparsity (23 out of 280) reflects off-screen-space windows, not TCC gating — same count in all three contexts.

## (b) kCGWindowBounds in launchd context

**YES — fully available.** `kCGWindowBounds` populated for all 280 windows in all three contexts with no null entries. Sample value for a Ghostty window: `{X: 1, Y: 38, Width: 1728, Height: 998}` (consistent across ccbash/launchd/bundle for the same WID).

The CGWindow side has complete geometry data in launchd context. TCC strips ONLY `kCGWindowName`.

## (c) AS-Bounds-Query Verdict

**NOT EXPOSED — in all three contexts.**

| Query | ccbash | launchd | bundle |
|---|---|---|---|
| `bounds of window 1 of application "Ghostty"` | `-1728` | `-1728` | `-1728` |
| `position of window 1 of application "Ghostty"` | `-1700` | `-1700` | `-1700` |
| Window-level properties available | `id`, `name`, `selected tab`, `class` | same | same |

The AS behavior is not TCC-dependent — ccbash (with Screen Recording) and launchd (without) return the same errors. Ghostty simply does not implement `bounds`, `position`, or `size` in its AppleScript dictionary at any level. The exploration in Phase A confirmed this for terminal-level properties as well (`bounds of terminal id "UUID"` → `-1728`).

## (d) Rect-Equality Cross-Validation

**N/A.** The AS side returns no bounds value in any context. There is nothing on the AS side to compare against the CG bounds. Cross-validation is structurally impossible with Ghostty's current AS implementation.

## (e) Implication for Next Step

**AS-side geometry path eliminated** (confirmed in Phase A before probe build, reconfirmed by all three contexts). Bounds-bridge is dead regardless of CG-side availability: the CG side has bounds, the AS side has nothing.

`kCGWindowBounds` IS available in launchd context, but this alone is insufficient for a bridge — it gives us geometry per CGWindowID, but we still need a way to identify WHICH CGWindowID belongs to a given Ghostty terminal UUID. Without that mapping, bounds are just another unlinked metadata field alongside PID and space_id.

**Remaining bridge candidates:**

**Path A — py2app / nuitka** (established): compile Python to a native bundle. Audit token at CGWindowList call = our bundle identity. Screen Recording grant becomes effective. `kCGWindowName` readable → existing three-strategy detection works unchanged. Cost: ~30-60 min setup per B1.

**Path C — shell helper daemon** (established): helper runs from CC-Bash context (inherits Screen Recording via responsibility chain), writes `{cgwindow_id: desktop_no}` to file at ~5s cadence. Menubar reads file. No CG API call from launchd context. Cost: additional always-on process + IPC.

**Path D — AX/_AXUIElementGetWindow** (NEW — needs probe): Accessibility API (AXUIElement) is a different TCC surface from Screen Recording. `kTCCServiceAccessibility` governs it. If Accessibility permission is granted to the launchd-context process, `AXUIElementCreateApplication(ghostty_pid)` can traverse Ghostty's window tree and `_AXUIElementGetWindow(axElement, &cgWindowID)` returns the CGWindowID directly. DockDoor (`ejbills/DockDoor`) uses exactly this pattern. Bridge: AX window N → CGWindowID N → match to CGWindow list (PID + bounds + space_ids visible) → desktop_no. The UUID→window mapping would use Ghostty's window `name` property (AS) → match against the AX window's AXTitle. If AX does NOT strip window titles (unlike CGWindowList which strips `kCGWindowName`), this provides a title match path that doesn't require Screen Recording.

**Path D is the only remaining low-cost option.** Path A and C are validated but higher-cost. Next probe should empirically answer: (1) does `AXUIElementCreateApplication` + window traversal work from launchd context? (2) does `_AXUIElementGetWindow` return correct CGWindowIDs? (3) are AXWindow titles readable without Screen Recording? A yes on all three = Path D is viable and cheaper than A or C.

## Scripts Used

- `dev/desktop_detection/03_field_availability_probe.py` — probe script (260 LOC)
- `dev/desktop_detection/03_bundle_stub.app/` — bundle stub for bundle-context run
- Three output reports in `dev/desktop_detection/03_reports/`
