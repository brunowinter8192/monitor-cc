# menubar_desktop_allocation

## Status Quo (IST)

**After user installs `dist/Monitor_CC_Menubar.app/` and grants Screen Recording:**

| Component | State |
|---|---|
| Bundle location | `~/Applications/Monitor_CC_Menubar.app/` |
| Bundle type | py2app (native Mach-O, embedded Python 3.14) |
| Bundle identifier | `com.brunowinter.monitor_cc_menubar` |
| CFBundleExecutable | `Monitor_CC_Menubar` (Mach-O 64-bit arm64) |
| Embedded Python | `Python.framework/Versions/3.14/Python` (5.1MB stripped) |
| TCC permission required | Screen Recording → `com.brunowinter.monitor_cc_menubar` |
| Audit token at CGWindowList call | `com.brunowinter.monitor_cc_menubar` (native launcher, no exec chain) |

**Detection pipeline** (`src/menubar/desktop_detection.py`, 330 LOC, unchanged): three-strategy resolver per Main session window — (1) name-unique: `kCGWindowName` match in exactly one CGWindow → Hit; (2) space-elimination: multiple candidates, query `CGSCopySpacesForWindows` per candidate, eliminate already-claimed spaces → Hit; (3) OSC-2 injection: write `__DET_<hex>` marker to tty, re-match `kCGWindowName` → Hit. Results cached for 10s TTL, force-invalidated on cwd set change.

**Display** (`src/menubar/panel.py` + `src/menubar/discover.py`): mains show `[N]` slot prefix where N = macOS Mission Control desktop number. Conflict (2+ mains on same desktop) shows `[!N]` in red. `app._desktop_to_cwd` populated conflict-free → `_reregister_digit_hotkeys()` maps Cmd+N to the correct Main session.

**Launch**: via `open ~/Applications/Monitor_CC_Menubar.app`. No launchd LaunchAgent active in current production.

## Evidenz

### TCC Root Cause (from B1, B2)

B1 identified the blocker: `exec` chain (bash launcher → Python) loses bundle identity. Audit token at `CGWindowListCopyWindowInfo` call = Python.app (ad-hoc, no Screen Recording grant).

B2 (context comparison probe across 3 execution contexts):

| Metric | ccbash | launchd | bundle (bash exec) |
|---|---|---|---|
| CGWindowList total | 280 | 280 | 280 |
| Ghostty windows (PID=1250) | 17 | 17 | 17 |
| With `kCGWindowName` set | 13 | **0** | **0** |
| Mains detected | 3/3 | 0/3 | 0/3 |

TCC strips `kCGWindowName` based on audit token identity. `__CFBundleIdentifier` env var (inherited through exec) makes zero difference — TCC uses the post-exec audit token.

### CGWindow Field Availability (from B3)

Only `kCGWindowName` is TCC-gated. All other fields available without Screen Recording:

| Field | Without Screen Recording | With Screen Recording |
|---|---|---|
| `kCGWindowOwnerPID` | ✅ | ✅ |
| `kCGWindowNumber` | ✅ | ✅ |
| `kCGWindowBounds` | ✅ | ✅ |
| `CGSCopySpacesForWindows` | ✅ | ✅ |
| `CGSCopyManagedDisplaySpaces` | ✅ | ✅ |
| `kCGWindowName` | ❌ null | ✅ |

Path B (redesign without kCGWindowName) and Path D (AX API) were evaluated but not pursued: AppleScript bounds for Ghostty windows return `-1728` in all contexts (Ghostty doesn't implement `bounds` in its AS dictionary), eliminating the bounds-bridge. Path A (py2app) was chosen as the direct fix.

### Reference Implementations

- `milititskiy/screenshot-buffer/setup_py2app.py` — minimal py2app menubar with `LSUIElement=True`, `NSScreenCaptureUsageDescription`, `bundle_identifier`. Used as primary template.
- `priyadarshiutkarsh/corenous/setup_app.py` — handles setuptools conflicts with py2app; consulted for project-root placement requirement.
- `bryzhao/textback` — py2app + launchd plist combination reference.

### Build Verification (2026-05-28)

```
codesign --verify --verbose=4 dist/Monitor_CC_Menubar.app  → exit=0
CFBundleIdentifier                                          → com.brunowinter.monitor_cc_menubar
LSUIElement                                                 → true
file Contents/MacOS/Monitor_CC_Menubar                      → Mach-O 64-bit executable arm64
Functional smoke test (singleton lock exit)                 → exit=0, all imports resolved
Bundle size                                                 → 39MB
Python.framework (embedded)                                 → 5.1MB stripped
```

Script: `setup_py2app.py` (project root). Built from worktree `py2app-build`.

## Recommendation (SOLL)

Keep (no change needed) — this IS the SOLL. py2app native bundle solves the TCC audit-token issue; detection pipeline is unchanged.

## Offene Fragen

1. **Screen Recording grant on first launch**: user must toggle permission ON in System Settings → Privacy & Security → Screen Recording. If the entry already exists from the ad-hoc bundle, toggle OFF then back ON to force re-evaluation of the new binary identity. Without this step, `kCGWindowName` remains null.

2. **Rebuild invalidates the TCC grant**: if the user rebuilds the bundle via `./venv/bin/python setup_py2app.py py2app` and reinstalls, macOS may recognize the new binary as a different identity and require re-granting. Ad-hoc signature (`codesign -s -`) means each build is unique. Workaround: keep the grant toggled on and use the "Quit & Reopen" prompt.

3. **Python upgrade breaks the bundle**: if Homebrew upgrades Python 3.14 to a new patch release, the embedded framework stays on 3.14.3 (the build-time version). The bundle remains functional — the embedded Python is self-contained and not affected by Homebrew upgrades. A fresh `py2app` build would pick up the newer Python. This is intentional (`semi_standalone=False`).

4. **Restart button is broken in py2app bundle**: `restartApp_` in `app.py` invokes `sys.executable` + `_SETUP_PY` — both point to bundle-internal paths in the py2app context. The Restart button exits the app but does not re-bootstrap. Fix is a follow-on task.

## Quellen

- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B1_tcc_responsibility_chain.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B2_context_comparison_probe.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B3_field_availability_probe.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/C1_py2app_migration.md`
- GitHub: `milititskiy/screenshot-buffer/setup_py2app.py`
- GitHub: `priyadarshiutkarsh/corenous/setup_app.py`
- GitHub: `bryzhao/textback`
