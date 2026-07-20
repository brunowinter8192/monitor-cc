# G1 — Space-Move Fresh Research: bridged-Op + macOS Version Split (2026-05-30)

**Status:** Research complete. Partially supersedes the earlier "all move APIs are dead" finding — the bridged path is alive, but version-dependent. **Probe result (2026-05-31, G2): bridged-op is a no-op on 26.5** (regression vs context still open; the production thread is plain CGSMove + detection kept separate).

Follows on from the earlier Cmd+B move-API dead-end finding and a prior blank-side probe + dead-end log from an earlier session.

## Question

The earlier session parked the space move as "a dead end, all 4 move APIs fail, resume via GitHub research." This session did the thorough GitHub research (issues + discussions indexed across yabai, Hammerspoon, DockDoor, AeroSpace).

## Root Cause (now precisely evidenced)

Move-window-to-space fails on Sequoia 15.7 because of **WindowServer connection rights-checking**, which Apple introduced in Sequoia: the caller must be the **owner of the window** OR **Dock.app** (= the system-wide manager of all spaces; yabai's scripting addition injects into Dock.app → needs SIP). "Owner" = the process that created the window (WindowServer records the owner PID per window).

Our move helper (`desktop_targeting.py`, its own Python process) owns neither the Ghostty nor the CotEditor window → blocked on Sequoia. That's the real reason, not "API gone."

Sources: Hammerspoon #3636 comment 15 (spaces-extension maintainer, verbatim: *"rights checking on the WindowServer connection. You either need to be the owner of the window, or the system universal owner (Dock.app)"*); yabai discussion #803 (maintainer: *"the entire workspaces functionality is implemented inside Dock.app"*); yabai issues #2380/#2425/#2500/#2784 (move needs SIP+SA since Sequoia).

## The Missing Technique (why the earlier probe failed)

The correct path is `SLSBridgedMoveWindowsToManagedSpaceOperation` + the operation object's **own method `performWithWMBridgeDelegate`** — reference: `ejbills/DockDoor:DockDoor/Utilities/PrivateApis.swift` `func SLSMoveWindowsToManagedSpace`. Pure ObjC runtime (`NSClassFromString` + `initWithWindows:spaceID:` + `performWithWMBridgeDelegate`), no Mach-O parsing.

The earlier probe failed on two things:
1. It called `.start` directly on the class → SIGSEGV (wrong selector).
2. It looked for the external dispatcher `SLSPerformAsynchronousBridgedWindowManagementOperation` via `dlsym` → MISSING (a local `_ZL` symbol, dlsym never finds it; yabai resolves it via `macho_find_symbol`, DockDoor bypasses the dispatcher entirely via `performWithWMBridgeDelegate`).

The correct selector `performWithWMBridgeDelegate` was NEVER tested in the earlier probe.

## macOS Version Split (the core finding)

| macOS | Move-to-space (non-owned, SIP-free) | Evidence |
|---|---|---|
| ≤ 14.4 | works | yabai #803, kasper/phoenix |
| 14.5 (Sonoma) | API changed, then NOP'd | Hammerspoon #3636 c24, phoenix PHSpace.m ("only works prior to 14.5") |
| 15.x (Sequoia) | rights-gated (owner-or-Dock); same-display cross-space dead, only cross-**display** works | yabai #2380/#2784 (15.7.5), DockDoor #855/#451/#953 (15.2/15.5) |
| 26.4.1 (Tahoe) | **bridged-op SIP-free** | yabai #2788 + DockDoor #855 c7 (ejbills validated, "validated working on macOS 26.4.1"); yabai maintainer #2784 c3 (move runs on their Tahoe daily driver) |

yabai is living proof that the bridged-op moves non-owned windows on Tahoe (yabai manages other apps' windows). Edge case (yabai #2789): move onto an **empty** space fails on 26.4.1 — our target (the caller's desktop) is never empty → unaffected.

## Discarded SIP-Free Workarounds (all disruptive)

- Grab the title bar + Ctrl-arrow (native shortcut, Hammerspoon #3636 jdtsmith hack, confirmed on 15.0.1) — switches the space.
- Mission-Control drag automation (`mogenson/Drag.spoon`) — tears open Mission Control.
- MC keyboard shortcuts via osascript/skhd (yabai #803) — switches the space.

All violate "place silently without disturbing the user."

## Reference Repos + Patterns

- `asmvik/yabai` — `src/space_manager.c:665-700` (3 move paths), `src/yabai.c:149` (macho symbol resolution for the dispatcher). Issues = ground truth on SIP/version status.
- `ejbills/DockDoor` — `DockDoor/Utilities/PrivateApis.swift` `SLSMoveWindowsToManagedSpace` (clean Swift reference via `performWithWMBridgeDelegate`). Issue #855 = validation source.
- `Hammerspoon/hammerspoon` — #3698/#3636 (spaces-extension status, owner-or-Dock explanation).
- `nikitabobko/AeroSpace` — deliberately avoids native spaces (reference in case "give up on native spaces" is ever reconsidered).

## Target / Next Step

**User decision 2026-05-30: Tahoe route, no Sequoia tweaking.** The Sequoia probe with `performWithWMBridgeDelegate` will NOT be done — Sequoia is rights-gated, Tahoe is the only confirmed SIP-free path, effort on 15.7 doesn't pay off.

1. **Software update to Tahoe 26.4+** (bridged-op confirmed SIP-free there: yabai #2788, ejbills/DockDoor #855 c7, yabai maintainer #2784).
2. Then a **dev/ probe on Tahoe**: actually move a non-owned window (Ghostty) to a target space via `SLSBridgedMoveWindowsToManagedSpaceOperation` + `performWithWMBridgeDelegate` (DockDoor `PrivateApis.swift` as the Swift reference). Reliable measurement: on-screen list (`CGWindowListCopyWindowInfo` kCGWindowListOptionOnScreenOnly) + screenshot, NOT `SLSCopySpacesForWindows`.
3. Probe green → port the bridged-op technique into `Meta/blank/src/desktop/desktop_targeting.py`. Probe-first: dev/ first, then `src/`.

## Indexed Sources (RAG)

- `github_issues`: yabai (#2380/#2425/#2500/#2636/#2741/#2784/#2788/#2789/#2707/#2634), Hammerspoon (#3698/#3636/#3111/#2111), DockDoor (#855/#451/#953/#466/#9/#1177).
- `github_discussions`: yabai (#803/#1553/#2667), AeroSpace (native-spaces rationale).
