# B2 — Context Comparison Probe Results (2026-05-28)

**Status:** Probe complete. Empirically refines B1's root cause. Clarifies exact TCC boundary and opens a no-py2app fix path.

## Probe Setup

Three execution contexts tested against same live macOS session:

| Context | Launch chain | XPC_SERVICE_NAME |
|---|---|---|
| `ccbash` | CC → zsh → venv/python (direct CLI) | `0` |
| `launchd` | launchd plist → venv/python (bare, no bundle) | `com.brunowinter.probe02ctx` |
| `bundle` | `open -n` → bash bundle launcher → `exec` venv/python | `application.com.brunowinter.monitor_cc_menubar.*` |

Script: `dev/desktop_detection/02_context_comparison_probe.py` (347 LOC)  
Reports: `dev/desktop_detection/02_reports/{ccbash,launchd,bundle}_20260528_17xxxx.json`  
macOS version: 15.7.7 (24G720)

## Raw Numbers

| Metric | ccbash | launchd | bundle |
|---|---|---|---|
| `CGWindowListCopyWindowInfo` total | 280 | 280 | 280 |
| Ghostty windows (layer=0, PID=1250) | 17 | 17 | 17 |
| Ghostty windows with `kCGWindowName` set | 13 | **0** | **0** |
| layer=0 windows with `window_name=None` | 107 | 148 | 148 |
| `CGSCopySpacesForWindows` functional | ✅ | ✅ | ✅ |
| `CGSCopyManagedDisplaySpaces` functional | ✅ | ✅ | ✅ |
| Mains detected (name-unique) | 3/3 | 0/3 | 0/3 |

## Critical Finding: B1 Was Partially Wrong

B1 diagnosed the failure as "TCC blocks kCGWindowOwnerPID — other apps' windows are completely invisible to launchd/bundle Python." This is **incorrect on macOS 15.7.7**.

**Actual TCC behavior:** Screen Recording permission gates specifically `kCGWindowName` (window content / title text). All window *metadata* is visible without the grant:

| Field | Without Screen Recording | With Screen Recording |
|---|---|---|
| `kCGWindowOwnerName` (app name) | ✅ visible | ✅ visible |
| `kCGWindowOwnerPID` | ✅ visible | ✅ visible |
| `kCGWindowNumber` (CGWindow ID) | ✅ visible | ✅ visible |
| `kCGWindowLayer` | ✅ visible | ✅ visible |
| `CGSCopySpacesForWindows` | ✅ functional | ✅ functional |
| `CGSCopyManagedDisplaySpaces` | ✅ functional | ✅ functional |
| `kCGWindowName` (window title) | ❌ **null** | ✅ visible |

**Why B1's log said "ZERO match Ghostty PID":** `_cgwindow_list_ghostty` filtered `if name is None or wid is None: continue` — Ghostty windows DO have the correct PID=1250 and ARE returned by CGWindowList, but their `kCGWindowName` is null, so the name filter dropped them. `by_name` ended up empty; all mains → no-match. The Ghostty windows weren't invisible — their titles were stripped.

## Context Identity Comparison

| Diagnostic | ccbash | launchd | bundle |
|---|---|---|---|
| `kCGWindowName` stripped | No | Yes | Yes |
| `__CFBundleIdentifier` env | `com.mitchellh.ghostty` (from Ghostty shell parent) | `None` | `com.brunowinter.monitor_cc_menubar` |
| `XPC_SERVICE_NAME` | `0` | `com.brunowinter.probe02ctx` | `application.com.brunowinter.monitor_cc_menubar.*` |
| `NSBundle.mainBundle().bundleIdentifier()` | `org.python.python` | `org.python.python` | `org.python.python` |
| `codesign_identity` (sys.executable) | `python3-5555...` (adhoc) | `python3-5555...` (adhoc) | `python3-5555...` (adhoc) |
| `parent_pid / parent_name` | zsh | launchd | launchd |

**Key observation:** `__CFBundleIdentifier=com.brunowinter.monitor_cc_menubar` IS set in the bundle context (env inherited through bash → exec), but it makes **zero difference** to TCC behavior. The launchd and bundle contexts produce identical window results (both strip `kCGWindowName`). TCC uses the post-`exec` audit token (Python.app's identity), not the `__CFBundleIdentifier` env var.

**TCC grant on `com.brunowinter.monitor_cc_menubar`** (the bundle stub's identity) is irrelevant after exec — the audit token becomes Python.app (`python3-5555...`).

**CC-Bash works** because CC's Screen Recording grant flows via TCC responsibility chain: Claude Code → zsh → Python. CC itself (not Python) holds the grant; the chain back to a trusted app is what the kernel checks.

## Refined Root Cause

The exact failure in the production menubar:

```
launchd → bundle_launcher.sh → exec venv/python3 → menubar
                                 ↑
                          audit token = python3-5555... (ad-hoc, no Screen Recording grant)
                          kCGWindowName stripped for all non-own-process windows
                          by_name = {}  →  all mains desktop_no=None
```

The TCC check is: "does the audit token's code identity have Screen Recording permission?" Python.app (Homebrew, ad-hoc signed) does not. The grant on `com.brunowinter.monitor_cc_menubar` is ignored because the bundle identity was lost at `exec`.

## Implications for Fix Paths

**Path A — py2app / nuitka (B1's recommendation, still valid)**  
Audit token at API call time = our bundle identity → Screen Recording grant effective → `kCGWindowName` visible → existing detection works unchanged.

**Path B — Redesign detection without kCGWindowName (NEW, unlocked by this probe)**  
All metadata except title is available without Screen Recording. A new detection strategy can use:
- `kCGWindowOwnerPID` (identifies Ghostty's windows) ✅ available
- `CGSCopySpacesForWindows` (maps window → desktop) ✅ available
- AppleScript `bounds of window <wid>` ← needs verification (separate investigation)
- Match via window bounds (`kCGWindowBounds` ↔ AppleScript bounds) without needing titles

This path would make Etappe 2 work without any compilation step, from the current launchd/bash-exec context. `kCGWindowBounds` availability (without Screen Recording) is the open question.

**Path C — Shell helper (B1's workaround option)**  
Still valid; unchanged from B1 analysis.

## Open Questions

1. Is `kCGWindowBounds` available without Screen Recording (like PID/layer/space_ids)? If yes, Path B is viable with no native bundle needed.
2. Does AppleScript `bounds of window <wid>` return a value usable for bounds-matching (vs `-1728` error seen for `bounds of terminal id UUID`)?

## Scripts Used

- `dev/desktop_detection/02_context_comparison_probe.py` — probe script (347 LOC)
- Three output reports in `dev/desktop_detection/02_reports/`
