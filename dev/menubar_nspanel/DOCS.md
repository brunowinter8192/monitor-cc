# dev/menubar_nspanel/

## Role

Probe and debug launcher for the menubar's NSPanel sticky-toggle behavior — a persistent
`NSPanel` that only closes on an explicit Cmd+L toggle or bar-icon click, replacing an
`NSMenu`-based dropdown that auto-dismisses on any outside click via
`NSEventTrackingRunLoopMode`. Background/build narrative: `process-docs/menubar_nspanel/`.

## Modules

### p1_nspanel_probe.py (260 LOC)

**Purpose:** Self-contained NSPanel menubar probe verifying: the panel stays open on an outside
click (no `NSEventTrackingRunLoopMode` auto-dismiss), `@rumps.timer` (`_tick`) keeps firing while
the panel is visible, and bar-icon click + Cmd+L both toggle the panel via the same
`togglePanel_` action. Does not modify `src/`.
**Reads:** live session data via `src.menubar.discover.list_alive_sessions` (read-only).
**Writes:** nothing — foreground GUI app, no Dock icon.
**Called by:** none — run manually; stop via the panel's Quit button or `pkill -f
p1_nspanel_probe.py`.
**Calls out:** `objc`, `rumps`, `AppKit`, `Foundation`.

---

### menubar_debug.py (60 LOC)

**Purpose:** Bootout the real menubar launchd service, run `workflow.py --mode menubar` in the
foreground with `MENUBAR_DIAGNOSTICS=1`, and optionally re-bootstrap the launchd service on exit.
**Reads:** nothing.
**Writes:** nothing — runs the menubar app in the foreground; stdout/stderr inherited.
**Called by:** none — run manually.
**Calls out:** `launchctl` (via `subprocess`, bootout/bootstrap of the `com.brunowinter.monitor_cc_menubar` service).

---

## Gotchas

**The production NSMenu approach auto-dismisses on any outside click** (via
`NSEventTrackingRunLoopMode`) — the NSPanel replacement's whole purpose is to not do that; if
`p1_nspanel_probe.py` shows the panel disappearing on an outside click, the toggle wiring
regressed. `@rumps.timer` firing while the panel is open also proves `NSDefaultRunLoopMode` isn't
frozen by the panel (unlike `NSEventTrackingRunLoopMode` under the old NSMenu).
