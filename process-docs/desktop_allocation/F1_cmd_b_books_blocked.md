# F1 — Cmd+B "Books to current desktop" — BLOCKED (dead end)

**Date:** 2026-05-29 · **Status:** Parked, blocked by a dead move API · **Tracking task closed.**

## Feature Intent

A global Carbon hotkey Cmd+B that brings the macOS Books app to the user's currently active desktop — regardless of where Books currently lives. Not just foreground: if Books windows sit on desktop 1 and the user presses Cmd+B on desktop 2, the Books windows should appear on desktop 2.

## Planned Implementation (NOT built)

- `src/menubar/hotkey.py`: `register_cmd_b()` analogous to `register_cmd_k` (Carbon pattern)
- `src/menubar/app.py`: init hook for registration + callback wiring
- New module `src/menubar/desktop_actions.py` (~80 LOC): `CGSGetActiveSpace` → `CGWindowList` filter `kCGWindowOwnerName==Books` → `CGSMoveWindowsToManagedSpace` to active_space → `osascript activate Books`

## Blocker — Why It's a Dead End

The plan lives and dies with `CGSMoveWindowsToManagedSpace` (moving a window to the active space). This API is **dead on macOS 15.7** — empirically demonstrated 2026-05-29 (probe + independent screenshot/on-screen verification). The plan had assumed the only risk was TCC (`kCGWindowOwnerName` needs no screen recording) — but the actual problem is the API itself, not permissions. Cmd+B would activate Books, but the window would stay on its old desktop.

All four move APIs tested FAIL on macOS 15.7; no yabai-style bridged-op dispatcher is available on this OS version, and there is no non-SIP-disabling path found.

## Discarded Workarounds (user decision, 2026-05-29)

- `activate` without move = the user gets jumped to Books' desktop instead → rejected (unwanted desktop switch)
- Dock-scripting addition + partial SIP disable (yabai path) → rejected (no acceptable security trade-off)

## Resumption

Together with the rest of the desktop-move topic, once the Reddit/gh-cli research tooling is more mature → fresh research into macOS-15 space placement. Until then, do not build — otherwise a worker rebuilds the same dead path.

## Architecture Debt (if ever built)

CGS bridging would then live in three places: `src/menubar/desktop_detection.py`, `src/menubar/desktop_actions.py`, `Meta/blank/src/desktop/desktop_targeting.py`. Cleanup idea: a shared helper module, or Monitor_CC's `src/` as the single source of truth with `blank/` shelling out to it.
