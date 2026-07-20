# B1 — TCC Responsibility Chain Investigation (Stage 2 Blocker)

**Status:** Stage 2 (menubar shows desktop number as an `[N]` slot prefix) ON ICE due to an unresolvable macOS TCC issue. The detection pipeline works perfectly — blocked only inside the launchd-spawned menubar process. Stages 1, 3, 4 unaffected (run from the user-shell context).

## Symptom

Menubar in live operation: the `cgwindow_by_name` dict from `_cgwindow_list_ghostty()` is always empty. Granular logs show `cgw_list_empty pid=1250 iterated=264 no_names_returned` — CGWindowListCopyWindowInfo iterates 264 windows, ZERO match the Ghostty PID. Consequence: all mains get `desktop_no=None`, no `[N]` prefix, Cmd+digit allocation falls back to arbitrary slot logic (but hotkey registration finds nothing → no function).

Standalone test from a user shell with identical Python code: `cgwindow_by_name` correctly contains 3 Ghostty window names, detection 100%.

## Root Cause

macOS TCC (Transparency, Consent, Control) gates `CGWindowListCopyWindowInfo` so that owner PIDs for windows of OTHER apps are NOT exposed without screen-recording permission. The permission is checked per **audit token** at API-call time — the audit token contains the binary identity (bundle ID + path + code signature) of the CURRENTLY-executing process.

In the menubar context: launchd → `~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/menubar` (Bash) → `exec` → `/opt/homebrew/.../Python.app/Contents/MacOS/Python` → the audit token at API-call time is Python.app's identity, NOT our bundle identity. `exec` replaces the process — bundle identity is lost.

In the user-shell context: CC (Claude Code) has its own app identity with a screen-recording grant. CC spawns Bash, Bash spawns Python — the responsibility chain roots at CC, the TCC lookup finds the grant.

## What Was Tried (all failed)

| Attempt | What | Result | Reason |
|---|---|---|---|
| 1 | Grant screen recording to Homebrew `Python.app` in System Settings | Works in the user-shell context, NOT in the launchd context | TCC checks not just the binary but also the responsibility parent — under launchd there is no user grant in the chain |
| 2 | `CGSCopyWindowProperty` (private SkyLight API) instead of `kCGWindowName` from CGWindowList | In shell context: returns the title correctly. Under launchd: identical failure rate | The TCC gate sits not at the API level but at the process-visibility level — regardless of API, the owner-PID filter returns 0 hits because other apps' windows are entirely invisible |
| 3 | Spinner-glyph normalization (strip `✻` `⠂` `✳` prefix before window-name match) | An orthogonal fix that addresses real edge cases (race between the AppleScript read and the CGS read), but not the TCC blocker | Kept as hardening |
| 4 | Wrap the menubar in its own `.app` bundle, ad-hoc codesign, user grants screen recording to the bundle | TCC listing registers the bundle, toggle activated, still not effective | The Bash launcher inside the bundle execs to generic Python — the audit token at CGWindowList-call time is Python, not the bundle. Bundle identity is lost on `exec` |
| 5 | Launch via `open -na` from Finder context (instead of launchd) | Identical failure rate | Here too: the bundle launcher execs to Python → audit token = Python |

## Empirical Verification of the Root Cause

CGWindowList counts across the tested contexts:

| Launch context | Total windows | Owned by Ghostty PID 1250 |
|---|---|---|
| User shell (CC-Bash subprocess) | 271 | 19 |
| launchd → bundle wrapper → Python | 264 | 0 |
| Finder `open -na` → bundle → Python | 271 | 0 |

Confirmed: the TCC filter is applied **based on caller identity**, not API choice or launch method.

## Future Paths (for the next session)

Three options, from smallest to largest refactor:

### A) py2app — menubar as a native bundle with embedded Python

py2app bundles Python + code + dependencies into a real `.app` structure. The resulting binary is a native Mach-O executable (no generic Python wrapper). The audit token at API-call time = our bundle identity. User grants screen recording → actually effective.

Effort: ~30-60 min setup. py2app is mature, well documented. The existing `~/Applications/Monitor_CC_Menubar.app` bundle is a foundation that just needs its launcher replaced.

### B) nuitka — compile Python to a native binary

Similar to py2app but actually compiles. Result is a single Mach-O executable with our identity. More compile time, somewhat less setup friction than py2app.

### C) Separate helper process from the user-shell context

A helper script runs permanently from the user-shell context (auto-start via a `~/.zshrc` hook or Login Items). Writes detection results to a JSON file every 5s. The menubar (launchd) only reads that file — no direct CGS call from the launchd context.

Advantage: no bundle refactor. Disadvantage: an extra process must keep running, IPC via file.

## Code State at the Time (preserved for the refactor)

- `src/menubar/desktop_detection.py` (275 LOC): complete detection pipeline, three-strategy resolver (name-unique → space-elimination → OSC-2), CGSCopyWindowProperty-bypass attempt, spinner normalize. **Works in the shell context** (stages 3+4 use it transparently via `Meta/blank/src/desktop/desktop_targeting.py`).
- `src/menubar/setup_menubar.py`: extended with `_build_app_bundle()` + `_codesign_bundle()`. Bundle build is idempotent — re-run overwrites cleanly. Foundation for the py2app refactor.
- `~/Applications/Monitor_CC_Menubar.app/`: ad-hoc signed bundle with the `com.brunowinter.monitor_cc_menubar` identity. Bash launcher in `Contents/MacOS/menubar`. Stub for py2app — in that refactor the Bash launcher gets replaced by native Mach-O.
- LaunchAgent plist: ProgramArguments points at the bundle launcher, no longer directly at python. The bundle wraps the TCC identity cleanly for a later refactor.
- Granular diagnostic logs in `_cgwindow_list_ghostty` / `_cgwindow_title` / `_resolve_cgwindow_id`: kept in place — they immediately help verify at the next session start whether a refactor made TCC functional.

## What Worked At The Time

- **Stage 1**: probe `dev/desktop_detection/01_probe.py` runs from the shell context, 100% success. Verified the detection logic is correct.
- **Stage 3**: worker spawn (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer`) calls `desktop_targeting.py wait-and-move` from the CC-Bash context. TCC inheritance from CC → works.
- **Stage 4**: `show <file>` (`Meta/blank/bin/show`) calls `desktop_targeting.py wait-and-move` from the CC-Bash context. Identically functional.
- **Hotkey logging, cwd-drift fix, main-exit detection** (all separate bug fixes from this session): fully functional, independent of TCC.

## What Did NOT Work At The Time

- **Stage 2 — menubar shows the desktop-number `[N]` prefix for mains**: all desktop_no=None, the slot column stayed empty. Cmd+digit allocation didn't engage. User experience: mains were shown but without a slot number, Cmd+1..9 did nothing.

## Sources

- `src/menubar/desktop_detection.py` (detection pipeline, diagnostic logs)
- `src/menubar/setup_menubar.py` (bundle-build pipeline)
- `~/Applications/Monitor_CC_Menubar.app/` (bundle stub)
- `dev/desktop_detection/01_probe.py` (detection probe, shell-context validation)
- `Meta/blank/src/desktop/desktop_targeting.py` (helper for stages 3+4)
- `src/logs/menubar.log` — `[detection]` category holds live diagnostics from the run at the time
- External: `lwouis/alt-tab-macos:src/macos/api-wrappers/CGWindowID.swift` (CGSCopyWindowProperty pattern), `ejbills/DockDoor:DockDoor/Utilities/PrivateApis.swift` (SkyLight private APIs reference)
