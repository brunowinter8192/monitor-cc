# G4 — Move Sweep Probe (06_move_sweep_probe.py)

**Date:** 2026-05-31  
**Script:** `dev/desktop_detection/06_move_sweep_probe.py`  
**Context:** macOS 26.5 (Tahoe), Apple Silicon, 6 Mission Control spaces

## What Was Done

Systematic sweep of 4 C-level window-move primitives to determine whether any of them can relocate a CotEditor window from the active Space to a non-active non-empty Space, with full AX + ScreenCapture permissions held at runtime.

Prior results before this probe:
- `SLSBridgedMoveWindowsToManagedSpaceOperation` (ObjC path, G2) → confirmed no-op on 26.5
- `CGSCopySpacesForWindows` unreliable as post-move verification signal → replaced by on-screen-list membership (this probe uses that correctly)

## Permission Self-Check

```
AXIsProcessTrusted()             : True
CGPreflightScreenCaptureAccess() : True
sys.executable                   : /Users/brunowinter2000/Documents/ai/Monitor_CC/venv/bin/python
realpath(executable)             : /opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/bin/python3.14
```

Both Accessibility and Screen Recording are held by the venv-python invocation. The TCC identity is the Homebrew python3.14 binary (not a symlink-identity mismatch). Permissions are not the blocker.

## Test Setup

- active_space=4 (desktop 2), target_space=5 (desktop 3)
- 6 spaces total: [3, 4, 5, 6, 7, 8]
- Test window: fresh CotEditor doc per primitive (token-named, `open -g`, no `-n`)
- Verification: `CGWindowListCopyWindowInfo(onscreen_only=1)` membership
- Screenshots: before + after per primitive in `dev/desktop_detection/06_reports/`

## Primitive Results

| Prim | Symbol | Loaded | in_before | in_after | Moved | Screenshot |
|------|--------|--------|-----------|----------|-------|------------|
| A | `CGSMoveWindowsToManagedSpace` (CoreGraphics) | ✅ | True | True | ❌ | 06_A_after_20260531_235916.png |
| B | `SLSMoveWindowsToManagedSpace` (SkyLight) | ✅ | True | True | ❌ | 06_B_after_20260531_235918.png |
| C | `CGSAddWindowsToSpaces` + `CGSRemoveWindowsFromSpaces` (CoreGraphics pair) | ✅ | True | True | ❌ | 06_C_after_20260531_235921.png |
| D | `SLSSpaceSetCompatID` + `SLSSetWindowListWorkspace` (SkyLight CompatID route) | ✅ | True | True | ❌ | 06_D_after_20260531_235924.png |

```
HEADLINE: NO primitive moved the window  |  AX=True  ScreenCapture=True
```

## What Was Found

**All 4 C-level primitives are no-ops on macOS 26.5 when moving active→non-active.** This is true even with full Accessibility + Screen Recording permissions held by the calling process.

Combined with G2 (ObjC bridged-op), the complete picture is:
- `SLSBridgedMoveWindowsToManagedSpaceOperation` (ObjC) → no-op
- `CGSMoveWindowsToManagedSpace` (CGS) → no-op
- `SLSMoveWindowsToManagedSpace` (SkyLight) → no-op
- `CGSAddWindowsToSpaces` + `CGSRemoveWindowsFromSpaces` (CGS add/remove pair) → no-op
- `SLSSpaceSetCompatID` + `SLSSetWindowListWorkspace` (SkyLight CompatID) → no-op

The window IDs were valid, space IDs were real managed spaces, `uint32` window arrays and `uint64` space arrays were constructed correctly. The symbols resolve and execute without crash or error. The calls are accepted silently and have no effect on window placement.

## Direction and Next Step

The freeze appears to be a security hardening change in macOS 26 (Tahoe) that blocks all private Space-move APIs for out-of-process callers. This is consistent with Apple's progressive TCC tightening across OS releases.

**Open question:** Does the Dock process (`/System/Library/CoreServices/Dock.app`) retain the ability to perform these moves (as the on-screen Space management authority), and can it be reached via a mach port or XPC call without requiring a privileged entitlement?

**Possible next direction:**
- Research whether `com.apple.dock.fullscreenanimation` or `com.apple.private.spaces` entitlements gate the space-move APIs specifically in 26.5
- Check if any accessibility/automation entitlement (like `com.apple.security.automation.apple-events`) exposes a high-level route through System Events / Dock
- AppleScript `System Events → Process → Windows` path (different TCC surface than CGS)
- Accept the constraint and switch to a detection-only model: detect which Space a window is on, don't try to move it programmatically
