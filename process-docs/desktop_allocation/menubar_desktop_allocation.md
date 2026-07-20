# menubar_desktop_allocation

> ## MOVE PERMANENTLY ABANDONED (2026-05-31) — Detection-only display RESTORED (2026-06-13)
>
> **Window-move stays dead:** cross-space window-move is impossible on macOS 26.5 without SIP-off + Dock injection (a move-primitive sweep found 5/5 private APIs are no-ops; documented in the placement-mechanism review). This part of the feature is permanently gone.
>
> **Detection-only display restored:** `desktop_detection.py`, `SessionInfo.desktop_no`, `[N]`/`[!N]` panel slot display, and `NSScreenCaptureUsageDescription` are back. The sidecar (`CWD_DESKTOP_FILE`, `_write_cwd_desktop_sidecar`) and spawn/file-open placement (`desktop_targeting.py`) remain removed — they served the dead move feature.

## State as of 2026-06-13

**After user installs `dist/monitor-cc-menubar.app/` and grants Screen Recording:**

| Component | State |
|---|---|
| Bundle location | `~/Applications/monitor-cc-menubar.app/` |
| Bundle type | py2app (native Mach-O, embedded Python 3.14) |
| Bundle identifier | `com.brunowinter.monitor-cc-menubar` |
| CFBundleName | `monitor-cc-menubar` |
| CFBundleExecutable | `monitor-cc-menubar` (Mach-O 64-bit arm64) |
| Embedded Python | `Python.framework/Versions/3.14/Python` (5.1MB stripped) |
| TCC permission required | Screen Recording → `com.brunowinter.monitor-cc-menubar` |
| Audit token at CGWindowList call | `com.brunowinter.monitor-cc-menubar` (native launcher, no exec chain) |
| LaunchAgent | `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist` → `ProgramArguments = [.../monitor-cc-menubar]` |
| APP_SUPPORT dir | `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/` |
| Restart mechanism | `restartApp_` → `write_plist_py2app()` + `launchctl bootout` + `launchctl bootstrap`; no bundle rebuild |

**Detection pipeline** (`src/menubar/desktop_detection.py` — restored 2026-06-13): three-strategy resolver per main-session window — (1) name-unique: `kCGWindowName` match in exactly one CGWindow → hit; (2) space-elimination: multiple candidates, query `CGSCopySpacesForWindows` per candidate, eliminate already-claimed spaces → hit; (3) OSC-2 injection: write `__DET_<hex>` marker to tty, re-match `kCGWindowName` after 500ms → hit. Results cached for `_DET_CACHE_TTL=10s`, force-invalidated on cwd set change. **Transition logging** (`_last_result` module state): per-cycle comparison logs `[detection] transition <cwd_label> <old>-><new> win=<ghostty_win_name> n_cand=<N>` on desktop-number change — transition-gated, no per-cycle spam. `detect_main_desktop_numbers(cwd_uuid_map, cwd_tty_map, now)` called in `list_alive_sessions()` post-loop (single AppleScript round-trip for the whole batch); result written to `SessionInfo.desktop_no` via `_replace`. No sidecar written (cross-repo desktop_targeting stays removed).

**Display** (`src/menubar/panel.py` + `src/menubar/panel_manager.py`): mains show a `[N]` slot prefix where N = macOS Mission Control desktop number (1-based). Conflict (2+ mains on same desktop) shows `[!N]` in red. `panel._desktop_to_cwd = {dno: cwd}` populated conflict-free → `HotkeyController.reregister_digits()` maps Cmd+N to the session on desktop N. When detection fails (Screen Recording not granted / Ghostty not running): `desktop_no=None` → slot empty, `_desktop_to_cwd={}` → Cmd+N no-ops, panel renders normally without numbers. `_GRID_COL0_W=40` (up from 33) to accommodate the 4-char `[!N]` conflict label.

**Log path** (`src/menubar/menubar_log.py`): `MENUBAR_LOG = _APP_SUPPORT / 'menubar.log'` — consistent with all other APP_SUPPORT files. Both dev (venv) and bundle write to `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log`.

**Subprocess encoding** (2026-05-28): all `subprocess.run(..., text=True)` calls in `src/menubar/` carry `encoding='utf-8', errors='replace'`. Root cause: launchd sets no locale → Python defaults to ASCII → `ps -A -o command=` output containing CC worker spawn-prompts (emoji, umlauts) → `UnicodeDecodeError` → `detect_main_desktop_numbers` catch → `all_failed` → desktop number lost for all mains while any worker is running. The LaunchAgent plist template also carries `PYTHONUTF8=1`.

**Launch**: via the launchd LaunchAgent (`RunAtLoad=true`) or manually via `open ~/Applications/monitor-cc-menubar.app`. **Restart**: the restart button calls `write_plist_py2app()` then a pure launchctl bootout+bootstrap — no bundle rebuild, the TCC grant is preserved. The `sys.frozen` gate in `restartApp_` separates the py2app path from the dev/venv path.

**NOT restored (stays dead):** window-move (`CGSMoveWindowsToManagedSpace` etc.), the sidecar (`CWD_DESKTOP_FILE` / `_write_cwd_desktop_sidecar`), spawn/file-open placement (`desktop_targeting.py`) — proven impossible in the placement-mechanism review and the move-sweep probe.

## Evidence

### TCC Root Cause

The `exec` chain (bash launcher → Python) loses bundle identity. The audit token at the `CGWindowListCopyWindowInfo` call = Python.app (ad-hoc, no Screen Recording grant).

Context-comparison probe across 3 execution contexts:

| Metric | ccbash | launchd | bundle (bash exec) |
|---|---|---|---|
| CGWindowList total | 280 | 280 | 280 |
| Ghostty windows (PID=1250) | 17 | 17 | 17 |
| With `kCGWindowName` set | 13 | **0** | **0** |
| Mains detected | 3/3 | 0/3 | 0/3 |

TCC strips `kCGWindowName` based on audit-token identity. The `__CFBundleIdentifier` env var (inherited through exec) makes zero difference — TCC uses the post-exec audit token.

### CGWindow Field Availability

Only `kCGWindowName` is TCC-gated. All other fields are available without Screen Recording:

| Field | Without Screen Recording | With Screen Recording |
|---|---|---|
| `kCGWindowOwnerPID` | yes | yes |
| `kCGWindowNumber` | yes | yes |
| `kCGWindowBounds` | yes | yes |
| `CGSCopySpacesForWindows` | yes | yes |
| `CGSCopyManagedDisplaySpaces` | yes | yes |
| `kCGWindowName` | no — null | yes |

A redesign without kCGWindowName and an AX-API path were evaluated but not pursued: AppleScript bounds for Ghostty windows return `-1728` in all contexts (Ghostty doesn't implement `bounds` in its AS dictionary), eliminating the bounds-bridge. The py2app path was chosen as the direct fix.

### Reference Implementations

- `milititskiy/screenshot-buffer/setup_py2app.py` — minimal py2app menubar with `LSUIElement=True`, `NSScreenCaptureUsageDescription`, `bundle_identifier`. Used as primary template.
- `priyadarshiutkarsh/corenous/setup_app.py` — handles setuptools conflicts with py2app; consulted for the project-root placement requirement.
- `bryzhao/textback` — py2app + launchd plist combination reference.

### Build Verification (2026-05-28)

```
codesign --verify --verbose=4 dist/Monitor_CC_Menubar.app  → exit=0
CFBundleIdentifier                                          → com.brunowinter.monitor_cc_menubar
LSUIElement                                                 → true
file Contents/MacOS/Monitor_CC_Menubar                      → Mach-O 64-bit executable arm64
Functional smoke test (singleton lock exit)                 → exit=0, all imports resolved
Bundle size                                                 → 38-39 MB
Python.framework (embedded)                                 → 5.1MB stripped
```

Script: `setup_py2app.py` (project root). Built from worktrees `py2app-build` (initial) and `bloat-fix` (post-prune).

**Build bloat fix (2026-05-28):** `_prune_bundle_bloat()` runs after `setup()` when `py2app` is in
`sys.argv`. Whitelist-prunes the bundle's `src/` to `{menubar, session_finder.py, constants.py,
__init__.py, __pycache__}`. Prevents `copy_package_data()` from sweeping `src/logs/` (runtime
proxy logs, no `__init__.py`, ≥15 GB in the main repo). Build-from-main-repo is now safe — a
sentinel test confirmed a 38 MB bundle with a 50 MB fake `src/logs/` fully pruned.

## Recommendation (target state, as of 2026-06-13)

Keep (no change needed) — detection-only display is the target state. The py2app native bundle solves the TCC audit-token issue; window-move stays permanently abandoned; the sidecar stays removed.

## Open Questions

1. **Screen Recording grant on first launch**: the user must toggle the permission ON in System Settings → Privacy & Security → Screen Recording. If the entry already exists from the ad-hoc bundle, toggle OFF then back ON to force re-evaluation of the new binary identity. Without this step, `kCGWindowName` remains null.

2. **Rebuild invalidates the TCC grant**: if the user rebuilds the bundle via `./venv/bin/python setup_py2app.py py2app` and reinstalls, macOS may recognize the new binary as a different identity and require re-granting. The ad-hoc signature (`codesign -s -`) means each build is unique. Workaround: keep the grant toggled on and use the "Quit & Reopen" prompt.

3. **Python upgrade breaks the bundle**: if Homebrew upgrades Python 3.14 to a new patch release, the embedded framework stays on 3.14.3 (the build-time version). The bundle remains functional — the embedded Python is self-contained and not affected by Homebrew upgrades. A fresh `py2app` build would pick up the newer Python. This is intentional (`semi_standalone=False`).

4. **Restart button — fixed** (2026-05-28): `restartApp_` gates on `sys.frozen`; the py2app branch calls `write_plist_py2app()` (writes `ProgramArguments = [.../Monitor_CC_Menubar]`) then a pure launchctl bootout+bootstrap — no bundle rebuild, no Python invocation in the helper. Dev-mode restart footgun also fixed (2026-06-12): `setup_menubar_workflow` removed from `setup_menubar.py`; the dev branch now uses an identical pure launchctl cycle — no bundle rebuild possible.

## Sources

- GitHub: `milititskiy/screenshot-buffer/setup_py2app.py`
- GitHub: `priyadarshiutkarsh/corenous/setup_app.py`
- GitHub: `bryzhao/textback`
