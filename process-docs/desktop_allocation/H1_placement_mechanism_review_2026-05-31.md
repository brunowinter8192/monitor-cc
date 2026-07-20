# H1 — Placement Mechanism Review + Redesign Direction (2026-05-31)

**Status:** CONCLUDED (2026-05-31). Moving windows SIP-free between native spaces on 26.5 proven impossible (a move-primitive sweep found 5/5 move APIs are no-ops WITH full AX+SC permissions; confirmed ecosystem-wide). Dead-code rollback executed (Monitor_CC menubar + Meta/iterative-dev plugin). See "Conclusion" below. Follows the fresh space-move research (bridged-op technique, macOS version split), the bridged-op probe (FAIL), the window-detection probe (solved), and the move-sweep probe (all FAIL).

## Trigger

After the Tahoe update (macOS 26.5, build 25F71) the bridged-op was tested → FAIL. User observation during a worker spawn: the new window "landed on the main's space" → suspicion "it does work / we're doing something wrong somewhere, the version-blame theory is incoherent." This session took the production mechanism apart and separated two threads that had been conflated.

## Two Separate Threads (previously conflated by Opus)

### Thread A — bridged-op on Tahoe

- **Premise from prior research:** the bridged-op (`SLSBridgedMoveWindowsToManagedSpaceOperation` → `initWithWindows:spaceID:` → the object's own `performWithWMBridgeDelegate`) is SIP-free, externally validated on **26.4.1**: ejbills DockDoor #855 c7 verbatim *"validated working on macOS 26.4.1"*; yabai #2788; yabai maintainer #2784 (runs on their Tahoe daily driver).
- **This session's probe:** the technique was tested correctly — right class, correct `initWithWindows:spaceID:` (NSArray of NSNumber<UInt32>), correct `performWithWMBridgeDelegate`. Result: **silent no-op on 26.5**. Object created (no nil), call without crash, window doesn't move. Verified via the on-screen list (unchanged) + screenshot.
- **Class introspection (26.5):** `performWithWMBridgeDelegate` is inherited from the parent `SLSAsynchronousBridgedWindowManagementOperation`; the child overrides `invokeFallback` (= the actual move logic). Both tested directly → both no-op.
- **Open:** regression 26.4.1→26.5 OR a context/entitlement gap (in which process context did the external validator run?). The version suspicion is NOT incoherent — the validation was version-specific to 26.4.1, and 26.5/25F71 has documented WindowServer changes (a DockDoor issue reports a WindowServer crash on exactly build 25F71). A 26.4.1 counter-test is blocked (already on 26.5, downgrade impractical).

### Thread B — Production Mechanism (plain CGSMove + detection)

Production (`Meta/blank` + the iterative-dev plugin mirror, byte-identical) does **NOT** use the bridged-op, but plain `CGSMoveWindowsToManagedSpace`. Pipeline (spawn + show identical up to the open):

1. **Sidecar** (menubar-maintained): `{"<cwd>": {"space_id": N, "desktop_no": N}}`. The helper does NO space detection of its own, trusts the sidecar.
2. **find-caller-desktop** (before opening): `$PPID` → `_find_claude_ancestor` → cwd via `lsof` (`_cwd_of_pid`) → sidecar lookup → `space_id`. Log: `sidecar=hit space_id=N`.
3. **Open:** spawn = `osascript tell Ghostty create window` (**synchronous**, blocks until the window exists); show = `open`/`open -a CotEditor` (async).
4. **wait-and-move-space** (bg): `_wids_for_owner_name` snapshot (`CGWindowListCopyWindowInfo(_CGW_LIST_ALL=0, ...)` = ALL spaces, on+off-screen) → poll-diff (0.15s) until new/timeout → `_move_windows_to_space` → `CGSMoveWindowsToManagedSpace(cid, [wid], space_id)`.

**Bugs:**

- **Detection ordering (main bug, systematically breaks spawn):** osascript opens the window synchronously BEFORE the `wait-and-move-space` snapshot → the new window is already in the "before" set → `new = after − before = ∅` → `move=no-new-window` on EVERY `op=spawn` log line. The move never fires. Show: `open` is async → a timing race, sometimes `move=1_windows` (seen once in the log), mostly `no-new-window`.
- **Natural-landing illusion:** a window is born on the active space; when the main that triggers the spawn IS the active space, the window lands "correctly" WITHOUT the move having done anything. "It does work" only holds as long as the trigger sits on its own space; from a distance it falls apart.
- **plain CGSMove on 26.5 UNPROVEN:** "dead/rights-gated" comes from the earlier Sequoia 15.7 finding (old machine), never retested on 26.5. Even if detection is fixed and the move fires → no evidence the window actually moves.

## Architecture Findings

- A window ALWAYS materializes on the active space; no API creates a window directly on a different space → move-after-open is the only way.
- "Background spawn so the user sees nothing" = `open -g` (no focus steal) + move away quickly. Caveat: brief materialization on the active space is unavoidable.
- Production move direction: active space → caller-main's space (only needed when active ≠ caller's space).

## Identifying the New Window — Design Space

The core question detection must answer: WHICH of the many windows is the new one?

- **owner-PID does NOT disambiguate** — CotEditor/Ghostty = 1 process with N windows, all sharing the PID.
- **(a) Snapshot-diff** — the mechanism in place, brittle (timing, ordering bug).
- **(b) Title match** — a known unique title (filename / tmux session, assigned by US) == `kCGWindowName`. Timing-robust. Caveat: `kCGWindowName` is TCC-stripped in the launchd/bundle context (the Stage-2 finding), but available from the CC/worker context. **Favorite.**
- **(c) frontmost** — the app's first window (front-to-back order from `CGWindowListCopyWindowInfo`) right after opening.

The window-detection probe tests (b)+(c) against (a) as ground truth + reliable space detection of the new window.

## Forward Plan

1. **Window-detection probe (running):** 3 window types (tmux-Ghostty, plain-Ghostty, CotEditor), methods (b)+(c) vs (a), + reliable space detection of the new window (CGSGetActiveSpace + on-screen membership + CGSCopySpacesForWindows, cross-checked). NO move. Report: window spawned/program × detected/space.
2. **After that:** verify plain `CGSMoveWindowsToManagedSpace` on 26.5 in isolation (real move effect, on-screen list + screenshot) — the correct primitive the bridged-op probe skipped.
3. If (2) works + (1) is reliable → the detection fix (**snapshot BEFORE opening**, separating out wait-and-move-space; in blank + the plugin mirror) is the complete production fix.
4. If (2) doesn't work → a different move technique is needed, continue pursuing Thread A (regression vs context).

## Orchestration Lesson

The prior probe's mission was CORRECT relative to the earlier research plan (the bridged-op was THE technique validated on 26.4.1, tested correctly). Opus's mistake: conflating that probe's result with the user's spawn observation → prematurely concluding "wrong primitive / version-blame incoherent." Correction: two separate threads. Detection-first (user directive) is the right entry point, because Thread B is fixable AND verifiable independent of Thread A.

## Conclusion (2026-05-31)

### Detection (Thread B) — SOLVED, then rolled back
The window-detection probe: snapshot-BEFORE-opening reliably detects the new window (9/9), space determination for Ghostty 6/6 (all 3 signals agree). The CotEditor fix is source-confirmed (DockDoor `AppDelegate.performOnLaunchAction` only fires on cold launch → avoid `open -n`, use plain `open` + filename match): 3/3 detected afterward. Robust identification anchor = **filename match** (z-order independent). Detection was therefore fully feasible — but it only served the move, which is impossible → rolled back together with it.

### Move (Threads A + B) — PROVEN IMPOSSIBLE SIP-free on 26.5
The move-sweep probe: a runtime permission self-check confirmed `AXIsProcessTrusted()=True` AND `CGPreflightScreenCaptureAccess()=True` (real Homebrew python3.14, no TCC identity mix-up). Still, **all 5 move primitives no-op**: the bridged-op, `CGSMoveWindowsToManagedSpace`, `SLSMoveWindowsToManagedSpace`, `CGSAddWindowsToSpaces`+`Remove`, `SLSSpaceSetCompatID`+`SLSSetWindowListWorkspace`. → permissions are NOT the gate (the accessibility hypothesis is refuted).

DockDoor entitlements evidence: no private `com.apple.private.skylight.*` entitlements — only AppleEvents + Sparkle + Calendar. DockDoor requires `AXIsProcessTrusted()` (accessibility) + `CGPreflightScreenCaptureAccess()` (screen recording) — both of which we had. So no Apple-signing secret involved.

Ecosystem verdict (final GitHub research): a yabai issue reports that a user on 26.5 found via LLDB that `SLSPerformAsynchronousBridgedWindowManagementOperation` "just doesn't work sometimes," and had to null it out to fall back to Dock injection. Another yabai issue notes `move_space` is no longer findable in the 26.x Dock binary. A Hammerspoon issue calls `moveWindowToSpace` hacky, "unreliable until Apple ships an API." **AeroSpace** (the popular modern SIP-free window manager) deliberately does NOT use native spaces ("considerable limitations") and emulates its own workspaces via off-screen positioning (accessibility-based, SIP-free) — the most serious project in this space has given up on native-space move. Every working Tahoe move = SIP-off + a Dock scripting addition (rejected by the user: no acceptable security trade-off).

**Conclusion:** there is no SIP-free, unprivileged way to move a window between native macOS spaces on 26.5. A proven negative, not an open doubt.

### Rollback Executed
- **Monitor_CC menubar** (commits, merged): `desktop_detection.py` deleted; `discover.py` sidecar writer + `desktop_no` field removed; `paths.py` `CWD_DESKTOP_FILE` removed; `panel.py`/`panel_manager.py` reverted to sequential slot numbers `[N]`; `setup_py2app.py` `NSScreenCaptureUsageDescription` removed (detection-only). DOCS updated. Import smoke green, −450 lines.
- **Meta/blank = iterative-dev plugin source** (commits, merged, published): `src/desktop/desktop_targeting.py` + its directory deleted; `tmux_spawn.sh` `open_tmux_viewer` placement removed (signature `SESSION`, both callers); `bin/show` placement + the dead `app_name` removed. `bash -n` green, cache verified placement-free. Spawn now only opens the window (natural active-space placement).
- **Kept as evidence:** the `dev/desktop_detection/` probes 01-06, and this investigation series' process-history entries.
