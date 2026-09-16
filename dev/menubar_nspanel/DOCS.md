# dev/menubar_nspanel/

## Role
Probe and debug launcher for the menubar's NSPanel sticky-toggle behavior — a persistent NSPanel
closing only on an explicit Cmd+L toggle or bar-icon click, replacing an NSMenu dropdown that
auto-dismisses on any outside click. Both entry scripts are live and dangerous — never run on a
machine in use.

## Public Interface
No `__init__.py` in this directory. `p1_nspanel_probe.py` and `menubar_debug.py` are entry
points, each run directly and each real and dangerous (see Modules below — do not run either).
`p1_hotkey.py` is a support module, imported only by `p1_nspanel_probe.py`.

## Flow
`p1_nspanel_probe.py` polls live CC session data and toggles a real NSPanel via a real global
Cmd+L hotkey (registered through `p1_hotkey.py`). `menubar_debug.py` stops the real production
menubar service and foreground-restarts it. Neither writes a file; the output is the live
GUI/service state itself.

## Modules

### p1_nspanel_probe.py (191 LOC)

**Purpose:** NSPanel menubar probe verifying the panel stays open on an outside click,
`@rumps.timer` keeps firing while visible, and bar-icon click + Cmd+L both toggle it.
**Reads:** live session data via `src.menubar.discover.list_alive_sessions` (read-only).
**Writes:** nothing — foreground GUI app, no Dock icon.
**Called by:** none — DO NOT RUN: registers a real, system-wide Cmd+L hotkey and opens a real
`NSPanel`.
**Calls out:** `objc`, `rumps`, `AppKit`, `Foundation`; `p1_hotkey.py` (`_register_hotkey`).

---

### p1_hotkey.py (62 LOC)

**Purpose:** Registers Cmd+L as a real, system-wide global hotkey via Carbon — identical
mechanism to the production menubar's own hotkey registration.
**Reads:** nothing.
**Writes:** nothing in the Python-object sense — registers a live OS-level hotkey for the
duration of the process.
**Called by:** `p1_nspanel_probe.py` (`NSPanelProbeApp.__init__`) — DO NOT CALL `_register_hotkey`
outside that probe; it is a real desktop side effect.
**Calls out:** `ctypes`, `Carbon.framework` (via `ctypes.CDLL`).

---

### menubar_debug.py (57 LOC)

**Purpose:** Bootout the real menubar launchd service, run `workflow.py --mode menubar` in the
foreground with diagnostics on, and optionally re-bootstrap the service on exit.
**Reads:** nothing.
**Writes:** nothing — runs the menubar app in the foreground; stdout/stderr inherited.
**Called by:** none — DO NOT RUN: stops the real production menubar service and foreground-runs
it live.
**Calls out:** `launchctl` (via `subprocess`).

---

## State
No persistent state lives in this directory's own code. Both entry scripts act on real external
state they do not own: `p1_nspanel_probe.py` on the live OS hotkey table and NSPanel it creates
for its own process lifetime; `menubar_debug.py` on the real `com.brunowinter.monitor_cc_menubar`
launchd service, which it stops and (optionally) restarts.
