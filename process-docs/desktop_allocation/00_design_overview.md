# Desktop Allocation — Design Overview (2026-05-27)

## Vision

Three user goals, all built on one shared detection foundation — the ability to know which macOS Mission-Control space (desktop) a given CC main session lives on:

1. **Menubar display**: for each main session, the menubar shows the desktop number it sits on. At the time it showed arbitrary slot numbers `[1]` `[2]` `[3]` `[4]`. Target: `[N]` = user-visible desktop number N.
2. **Worker placement**: when a main session spawns a worker, the new Ghostty window should land on the same desktop as the spawning main.
3. **File-open placement**: when the `show <file>` tool is invoked from a main session, the opened app should be on the same desktop as that main.

## Invariants (user-confirmed)

- Never 2 main sessions in the same project
- Never 2 main sessions on the same desktop
- Conflicts (accidentally 2 mains on one desktop) → error state in the menubar, no auto-resolve
- User launch pattern for mains: exclusively `./src/claude_proxy_start.sh --project <ROOT>`. PROJECT is the canonical root.

## API Foundation

Apple's private CoreGraphics Services (CGS) APIs under `SkyLight.framework`. Stable since 10.10+, used in production by yabai/AeroSpace/Amethyst/alt-tab-macos/Ice and by Ghostty itself (see Ghostty's internal `macos/Sources/Helpers/Private/CGS.swift`).

| API | Purpose |
|---|---|
| `CGSMainConnectionID() → Int32` | Connection ID, cache once |
| `CGSGetActiveSpace(cid) → SpaceID` | currently focused space (diagnostics) |
| `CGSCopySpacesForWindows(cid, mask, [windowID]) → CFArray<SpaceID>` | spaces a window appears on |
| `CGSCopyManagedDisplaySpaces(cid) → CFArray<CFDict>` | ordered space list per display; array index per display = user-visible desktop number (1-based) |
| `CGSMoveWindowsToManagedSpace(cid, [windowID], spaceID) → Void` | moves a window to a space (does not work for fullscreen windows) |

Python binding via `ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')` plus `ctypes.CDLL('/usr/lib/libobjc.A.dylib')` for CFArray/CFDict bridging via `objc_msgSend`. Pattern proven from `drussell23/JARVIS:backend/vision/macos_space_detector.py`.

## The cwd → CGWindowID Mapping Gap

Our `src/menubar/ghostty.py` maps cwd → Ghostty's internal terminal UUID via an OSC-2 title probe. This UUID is NOT the macOS CGWindowID that `CGSCopySpacesForWindows` needs.

**Mapping strategy (post-probe):**

Phase A of the probe worker found that AppleScript `bounds of (window of terminal)` does NOT exist for Ghostty (`-1728` error). Instead, this works: AppleScript `id of terminal of tab of window` returns the UUID per tab, and the CGWindow's `kCGWindowName` corresponds to Ghostty's `name` property of the window (= active tab title).

**Three-strategy resolver** (in this order):
1. **Name-unique**: `kCGWindowName` = window_name in exactly one CGWindow → hit
2. **Space-elimination**: with multiple candidates, query `CGSCopySpacesForWindows` per candidate, eliminate those on already-claimed spaces (progressive accumulation across worker iteration) → if one remains → hit
3. **OSC-2 injection**: inject marker `__DET_<hex>` via OSC-2 into the tty, wait 150ms, re-match `kCGWindowName` → effective when the CC tab is the focused tab in the window

**Detection rate empirically:** 100% in both probe runs (4/4, 3/3). Reference implementation: `dev/desktop_detection/01_probe.py`. Cross-project production variant: `Meta/blank/src/desktop/desktop_targeting.py`.

**Notable negative finding:** AppleScript `working directory of terminal` returns the app-launch path (Monitor_CC) for ALL Ghostty terminals instead of the real terminal cwd — a Ghostty bug. Retroactively explains why the menubar's `_focus_session()` Path-B fallback (`focus first terminal whose working directory is "..."`) was structurally broken. Fix landed in commit `1725bfb` (proc_cwd preference + Path B MISS detection).

## Stages

1. **Stage 1 — Detection probe** (`dev/desktop_detection/01_probe.py`, commit `fee6566`): DONE. 100% detection success, proven. Cwd-drift bug uncovered + fixed in `1725bfb`. Phase A/B log in `A1_detection_probe.md`.
2. **Stage 2 — Menubar display desktop number**: ON ICE (2026-05-28). Code-complete across commit chain `15c0319` → `5507c89` → `a719139` → `19986b9` → `3f0f0c7` (spinner-normalize + CGSCopyWindowProperty + .app-bundle wrapper). Detection pipeline cleanly architected and functionally proven — but a TCC restriction for launchd-spawned Python prevents the menubar from seeing owner PIDs for Ghostty windows. Full investigation + future refactor paths in `B1_tcc_responsibility_chain.md`. Next session: py2app or nuitka refactor.
3. **Stage 3 — Worker placement on the caller's desktop** (`Meta/blank/src/spawn/tmux_spawn.sh:open_tmux_viewer`, commit `cfd0d14`): DONE. After the osascript window spawn, `python3 desktop_targeting.py wait-and-move "$PPID" "Ghostty" 5` is invoked in the background. Functionally verified — TCC unaffected because the helper runs from a CC Bash-subprocess context (screen-recording grant inherited from CC via the responsibility chain).
4. **Stage 4 — File-open placement** (`Meta/blank/bin/show`, commit `cfd0d14`): DONE. Identical pattern: after `open`, a helper call with `app_name` (CotEditor for md/txt, empty for others → cross-app polling). See `file_open_routing.md` for details. Functionally verified via the helper call from CC context. Caveat: invoking from Terminal.app without screen recording would also fail there — doesn't affect the user-specific use case.

## Stage 2 — Phase B Implementation (2026-05-28)

### Files changed

| File | Change |
|---|---|
| `src/menubar/desktop_detection.py` | NEW (275 LOC) — port of `dev/desktop_detection/01_probe.py` detection pipeline into an importable library |
| `src/menubar/discover.py` | `SessionInfo.desktop_no: Optional[int] = None` added; `list_alive_sessions()` runs batch detection post-loop |
| `src/menubar/panel.py` | `_GRID_COL0_W` 33→40; `main_slot` counter removed; slot prefix driven by `desktop_no`; conflict set pre-computed via `Counter`; `app._desktop_to_cwd` populated |
| `src/menubar/app.py` | `_desktop_to_cwd: dict = {}` in `__init__`; `_reregister_digit_hotkeys` uses `_desktop_to_cwd` instead of `_cwd_map` |
| `src/menubar/DOCS.md` | New module entry, LOC updates, import graph + state table |

### Architecture Decisions vs Plan

- **Performance**: 10s TTL cache at module level; force-invalidated on cwd-set change; runs on the main thread (same pattern as the existing ghostty TTY probe). Detection wrapped in an outer `try/except` — any error (AppleScript failure, CGS error, Ghostty down) logs once and returns all-None for the cache TTL period.
- **Conflict UX**: `[!N]` in `NSColor.systemRedColor()` for the slot cell; star/name/dot remain orange. `_desktop_to_cwd` excludes conflicted desktops → no Cmd+N hotkey registered for them.
- **All-fail log**: `log_menubar('detection', f'all_failed n_mains=N reason=...')` fires only when ALL mains return None (3 possible reasons: `ghostty_not_running`, `all_no_match`, `error:<repr>`). Partial failures (some mains detected, some not) produce no log entry.
- **SessionInfo backward compat**: `desktop_no: Optional[int] = None` as the final field with a default — all existing `SessionInfo(name=..., ..., tmux_session_name=...)` call sites unchanged.

### Smoke Test Result

```
Mains found: 2
  desktop=3  name=Monitor_CC       cwd=.../Monitor_CC
  desktop=2  name=searxng          cwd=.../Meta/ClaudeCode/MCP/searxng
```

Detection successful, 100%, strategy breakdown expected to be `name-unique:2` or `osc2-injection:1` depending on focused-tab state.

## Status (2026-05-28 — Session End)

- **Stage 1** DONE: detection probe `dev/desktop_detection/01_probe.py` — 100% success in shell context, proven
- **Stage 2** ON ICE: code-complete, but a TCC restriction blocks detection in the launchd-spawned menubar process. User grant for the `Monitor_CC_Menubar.app` bundle was activated, still blocked — root cause identified empirically: `exec` from the Bash launcher to Python loses bundle identity (the audit token at API-call time is Python.app, not our bundle). Full investigation + three refactor paths (py2app / nuitka / shell-helper) documented in `B1_tcc_responsibility_chain.md`. **Resume next session via a tracking task.**
- **Stage 3** DONE: worker-spawn placement — verified the helper detects space_id correctly from a CC Bash-subprocess context (TCC inheritance from CC functional)
- **Stage 4** DONE: show file-open placement — identical pattern, verified the same way
- **Cwd-drift bug**: DONE — mains show the project-root name (no longer drifting via JSONL cwd), Cmd+digit focus functional
- **Hotkey logging**: DONE — all Carbon hotkeys log to `src/logs/menubar.log`
- **Main-exit detection**: DONE — exited mains disappear from the panel within ~1.5s (instead of a 1h JSONL-stale wait)
- **TCC identity architecture**: bundle wrapper under `~/Applications/Monitor_CC_Menubar.app` ad-hoc-signed; launchd plist switched to the bundle launcher. Foundation for the py2app refactor, costs nothing in the state at the time (menubar ran exactly as before).

### TCC Investigation Summary (why Stage 2 got stuck)

Sequence of fix attempts and why each failed:
1. Screen-recording grant for Homebrew `Python.app` → functional in the user-shell context, not in the launchd context (the responsibility chain roots at launchd without a grant)
2. `CGSCopyWindowProperty` private SkyLight API instead of `kCGWindowName` → identical failure pattern (the TCC gate is not API-bound but process-visibility-bound)
3. Spinner-glyph normalization → an orthogonal fix that stays; doesn't solve TCC, solves a title-matching edge case
4. `.app` bundle wrap with ad-hoc codesign → bundle identity correctly registered in TCC, user grant ON → **still blocked**, because the Bash launcher execs to Python and the audit token after `exec` = Python.app

**Root cause, final:** the TCC audit token is determined per-process at API-call time. `exec` replaces the process — bundle identity is lost. Only a native Mach-O bundle (py2app or nuitka) solves this cleanly.

**Helper-process alternative**: a separate detection helper running from a user-shell context (auto-start via Login Items) that IPCs with the menubar via a JSON file — would be a workaround without a refactor. Effort comparable to py2app. Both options open for the next session.

## Appendix — Worker-Death Note

Worker `menubar-hotkey-log` was reused after the Phase 5 recap of the hotkey-logging task, for desktop detection (aggressive reuse, thematic continuity with ghostty.py/menubar). Delivered Phase A clean at 22% context, given the go-ahead, the worker died in Phase B implementation with a "Prompt is too long" error before anything was committed. Successor inherits:

- The pre-approved Phase A plan (in this file above + in the successor prompt)
- Zero commits — so not a handoff-resume but a fresh spawn with a pre-approved plan
- The area folder already existed; `A1_detection_probe.md` was to be created by the successor in Phase B

## Sources

- `src/menubar/ghostty.py` (existing UUID mapping)
- `src/menubar/discover.py:list_alive_sessions`
- `src/menubar/proc_cache.py:_cc_proc_cache`
- `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/ghostty_cwd_uuid.json` (live cwd→UUID map written by the menubar)
- External: yabai source, alt-tab-macos `src/experimentations/PrivateApis.swift`, Ghostty's own `macos/Sources/Helpers/Private/CGS.swift`, JARVIS `backend/vision/macos_space_detector.py` (Python ctypes pattern)
