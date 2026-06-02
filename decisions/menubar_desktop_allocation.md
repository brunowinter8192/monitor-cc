# menubar_desktop_allocation

> ## ⚠️ ABANDONED / ROLLED BACK (2026-05-31)
> Die Desktop-Allocation hing am Verschieben neuer Fenster auf den nativen Space der Caller-Main. Dieser Cross-Space-**Move ist auf macOS 26.5 SIP-frei bewiesen unmöglich** (5/5 private Move-APIs no-op trotz voller Accessibility+Screen-Recording-Rechte; ökosystemweit bestätigt — yabai/DockDoor/Hammerspoon brauchen SIP-off + Dock-Injektion, AeroSpace meidet native Spaces ganz). Rationale + Beweis: `decisions/OldThemes/desktop_allocation/H1_placement_mechanism_review_2026-05-31.md` + `G4_move_sweep_probe.md`.
>
> **Aktueller IST (post-Rollback):** Menubar zeigt wieder **sequenzielle Slot-Nummern `[N]`**, keine Desktop-Erkennung. `desktop_detection.py`, der cwd→space-Sidecar (`CWD_DESKTOP_FILE`) und das `desktop_no`-Feld sind entfernt. Screen-Recording wird vom Menubar nicht mehr benötigt (`NSScreenCaptureUsageDescription` aus py2app-Plist raus). Spawn-/File-Open-Placement (Meta/blank `tmux_spawn.sh` + `bin/show` + `desktop_targeting.py`) ebenfalls zurückgebaut.
>
> **Alles unterhalb beschreibt die ENTFERNTE Detection-Implementierung** — als historischer Record erhalten (TCC-Befunde bleiben wertvoll), NICHT der aktuelle Stand.

## Status Quo (IST)

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

**Detection pipeline** (`src/menubar/desktop_detection.py`, 343 LOC): three-strategy resolver per Main session window — (1) name-unique: `kCGWindowName` match in exactly one CGWindow → Hit; (2) space-elimination: multiple candidates, query `CGSCopySpacesForWindows` per candidate, eliminate already-claimed spaces → Hit; (3) OSC-2 injection: write `__DET_<hex>` marker to tty, re-match `kCGWindowName` → Hit. Results cached for 10s TTL, force-invalidated on cwd set change. **Transition logging** (`_last_result` module state): per-cycle comparison logs `[detection] transition <cwd_label> <old>-><new> win=<ghostty_win_name> n_cand=<N>` on desktop-number change — transition-gated, no per-cycle spam. Detection algorithm unchanged.

**Log path** (`src/menubar/menubar_log.py`): `MENUBAR_LOG = _APP_SUPPORT / 'menubar.log'` — consistent with all other APP_SUPPORT files. Both dev (venv) and bundle write to `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log`.

**Subprocess encoding** (2026-05-28): all 13 `subprocess.run(..., text=True)` calls in `src/menubar/` now carry `encoding='utf-8', errors='replace'`. Root cause: launchd sets no locale → Python defaults to ASCII → `ps -A -o command=` output containing CC worker spawn-prompts (emoji, umlauts) → `UnicodeDecodeError` → `detect_main_desktop_numbers` catch → `all_failed` → desktop number lost for all mains while any worker is running. Confirmed by live log: crash at 22:39 (ps, `b'...\xe2\xa0\x90 Offene Tasks...'`), crash at 22:40:59 (osascript, `'⠐ Offene Tasks'`). LaunchAgent plist template also gains `PYTHONUTF8=1` as belt-and-suspenders for launchd context.

**Display** (`src/menubar/panel.py` + `src/menubar/discover.py`): mains show `[N]` slot prefix where N = macOS Mission Control desktop number. Conflict (2+ mains on same desktop) shows `[!N]` in red. `panel._desktop_to_cwd` populated conflict-free → `HotkeyController.reregister_digits()` (hotkey_controller.py) maps Cmd+N to the correct Main session.

**Launch**: via launchd LaunchAgent (`RunAtLoad=true`) or manually via `open ~/Applications/monitor-cc-menubar.app`. **Restart**: Restart-Button ruft `write_plist_py2app()` (schreibt `ProgramArguments = [.../monitor-cc-menubar]`) dann reinen launchctl bootout+bootstrap — kein Bundle-Rebuild, TCC-Grant bleibt erhalten. `sys.frozen`-Gate in `restartApp_` trennt py2app-Pfad von dev/venv-Pfad.

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
Bundle size                                                 → 38–39 MB
Python.framework (embedded)                                 → 5.1MB stripped
```

Script: `setup_py2app.py` (project root). Built from worktrees `py2app-build` (initial) and `bloat-fix` (post-prune).

**Build bloat fix (2026-05-28):** `_prune_bundle_bloat()` runs after `setup()` when `py2app` in
`sys.argv`. Whitelist-prunes the bundle's `src/` to `{menubar, session_finder.py, constants.py,
__init__.py, __pycache__}`. Prevents `copy_package_data()` from sweeping `src/logs/` (runtime
proxy logs, no `__init__.py`, ≥15 GB in main repo). Build-from-main-repo is now safe — sentinel
test confirms 38 MB bundle with 50 MB fake `src/logs/` fully pruned. See
`decisions/OldThemes/desktop_allocation/C2_build_bloat.md`.

## Recommendation (SOLL)

Keep (no change needed) — this IS the SOLL. py2app native bundle solves the TCC audit-token issue; detection pipeline is unchanged.

## Offene Fragen

1. **Screen Recording grant on first launch**: user must toggle permission ON in System Settings → Privacy & Security → Screen Recording. If the entry already exists from the ad-hoc bundle, toggle OFF then back ON to force re-evaluation of the new binary identity. Without this step, `kCGWindowName` remains null.

2. **Rebuild invalidates the TCC grant**: if the user rebuilds the bundle via `./venv/bin/python setup_py2app.py py2app` and reinstalls, macOS may recognize the new binary as a different identity and require re-granting. Ad-hoc signature (`codesign -s -`) means each build is unique. Workaround: keep the grant toggled on and use the "Quit & Reopen" prompt.

3. **Python upgrade breaks the bundle**: if Homebrew upgrades Python 3.14 to a new patch release, the embedded framework stays on 3.14.3 (the build-time version). The bundle remains functional — the embedded Python is self-contained and not affected by Homebrew upgrades. A fresh `py2app` build would pick up the newer Python. This is intentional (`semi_standalone=False`).

4. **Restart button — fixed** (2026-05-28): `restartApp_` gates on `sys.frozen`; py2app branch calls `write_plist_py2app()` (writes `ProgramArguments = [.../Monitor_CC_Menubar]`) then pure launchctl bootout+bootstrap — no bundle rebuild, no Python invocation in helper. See `decisions/OldThemes/menubar_restart_broken/A2_fix.md`. Residual open: dev-mode restart (`sys.frozen=False`) calls `setup_menubar_workflow()` which overwrites an installed py2app bundle — Refactor-Scope, not fixed here.

## Quellen

- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B1_tcc_responsibility_chain.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B2_context_comparison_probe.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/B3_field_availability_probe.md`
- `Monitor_CC-docs: decisions/OldThemes/desktop_allocation/C1_py2app_migration.md`
- GitHub: `milititskiy/screenshot-buffer/setup_py2app.py`
- GitHub: `priyadarshiutkarsh/corenous/setup_app.py`
- GitHub: `bryzhao/textback`
