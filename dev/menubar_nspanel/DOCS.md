# dev/menubar_nspanel/

## Purpose

Probe suite for the NSPanel sticky-toggle refactor of the menubar app. Replaces the `NSMenu`-based dropdown (which auto-dismisses on any outside click via `NSEventTrackingRunLoopMode`) with a persistent `NSPanel` that only closes on an explicit Cmd+L toggle or bar-icon click.

Background and design rationale: `process-docs/menubar_nspanel/A1.md`.
Build narrative: `process-docs/menubar_nspanel/A2.md`.

## Scripts

### p1_nspanel_probe.py

Self-contained NSPanel menubar probe. Does **not** modify `src/`. Imports `src.menubar.discover` (read-only) for live session data.

**Purpose:** Verify three things that the production NSMenu approach cannot provide:
1. Panel stays open on outside click (no `NSEventTrackingRunLoopMode` auto-dismiss).
2. `@rumps.timer` (`_tick`) keeps firing while the panel is visible — no runloop freeze.
3. Bar-icon click and Cmd+L both toggle the panel via the same `togglePanel_` action.

**Usage (run from project root):**
```bash
./venv/bin/python3 dev/menubar_nspanel/p1_nspanel_probe.py
```

The probe launches as a menubar app (no Dock icon). A `◉` icon appears in the status bar.

**To stop:** Click the `◉` icon to open the panel → click Quit, or send SIGTERM:
```bash
pkill -f p1_nspanel_probe.py
```

## Verification Checklist

Run through these steps after launch to confirm the probe is functional:

1. **Panel opens on Cmd+L** — press Cmd+L → panel appears directly below the `◉` bar icon.
2. **Panel stays open on outside click** — with panel visible, click anywhere on the desktop or another app window → panel remains open (does NOT auto-dismiss).
3. **Panel closes on second Cmd+L** — press Cmd+L again → panel disappears.
4. **Bar-icon click toggles** — click the `◉` icon → panel appears; click `◉` again → panel disappears.
5. **`@rumps.timer` fires while panel is open** — open panel, wait 5+ seconds while a Claude Code session changes status (working ↔ idle) → `◉` blinks and panel text updates. Proves `NSDefaultRunLoopMode` is not frozen (unlike NSMenu which triggered `NSEventTrackingRunLoopMode`).
6. **Panel positions correctly** — panel appears flush below the bar icon, not at screen origin (0,0) or off-screen.
7. **No focus steal** — open panel while typing in another app window → other window retains keyboard focus (`.nonactivatingPanel` styleMask working).
8. **Quit works** — open panel, click Quit → app exits cleanly.
