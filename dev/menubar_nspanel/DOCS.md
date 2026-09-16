# dev/menubar_nspanel/

## Role

Probe and debug launcher for the menubar's NSPanel sticky-toggle behavior — a persistent
`NSPanel` that only closes on an explicit Cmd+L toggle or bar-icon click, replacing an
`NSMenu`-based dropdown that auto-dismisses on any outside click via
`NSEventTrackingRunLoopMode`. Background/build narrative: `process-docs/menubar_nspanel/`.

## Modules

### p1_nspanel_probe.py (206 LOC)

**Purpose:** Self-contained NSPanel menubar probe verifying: the panel stays open on an outside
click (no `NSEventTrackingRunLoopMode` auto-dismiss), `@rumps.timer` (`_tick`) keeps firing while
the panel is visible, and bar-icon click + Cmd+L both toggle the panel via the same
`togglePanel_` action. Does not modify `src/`.
**Reads:** live session data via `src.menubar.discover.list_alive_sessions` (read-only).
**Writes:** nothing — foreground GUI app, no Dock icon.
**Called by:** none — run manually; stop via the panel's Quit button or `pkill -f
p1_nspanel_probe.py`.
**Calls out:** `objc`, `rumps`, `AppKit`, `Foundation`; `p1_hotkey.py` (`_register_hotkey`).

---

### p1_hotkey.py (64 LOC)

**Purpose:** Registers Cmd+L as a real, system-wide global hotkey via Carbon
(`RegisterEventHotKey`/`InstallEventHandler`, called through `ctypes` against
`Carbon.framework`) — identical mechanism to the production menubar's own hotkey registration.
**Reads:** nothing.
**Writes:** nothing in the Python-object sense — registers a live OS-level hotkey for the
duration of the process (real desktop side effect; see Gotchas below).
**Called by:** `p1_nspanel_probe.py` (`NSPanelProbeApp.__init__`).
**Calls out:** `ctypes`, `Carbon.framework` (via `ctypes.CDLL`).

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

**Running `p1_nspanel_probe.py` (and therefore `p1_hotkey.py`'s `_register_hotkey`) registers a
real, system-wide Cmd+L hotkey and opens a real `NSPanel`** — do not run it while someone is using
this machine. `menubar_debug.py` is equally live: it stops the real production menubar service
(`launchctl bootout`) and runs the real `workflow.py --mode menubar` in the foreground, which does
the same NSPanel/hotkey registration in its production form.
