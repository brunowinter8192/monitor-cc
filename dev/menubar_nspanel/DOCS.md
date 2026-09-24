# dev/menubar_nspanel/

## Role
Probe and debug launcher for the menubar's NSPanel sticky-toggle behavior: a persistent panel closing only on an explicit toggle, replacing a dropdown that auto-dismisses. Both entry scripts are live and dangerous; never run them on a machine in use.

## Public Interface
No `__init__.py`. `p1_nspanel_probe.py` and `menubar_debug.py` are entry points, each real and dangerous. `p1_hotkey.py` is a support module imported only by the probe.

## Flow
The probe polls live session data and toggles a real NSPanel through a real global hotkey. The debug launcher stops the production menubar service and restarts it in the foreground. Neither writes a file; the output is the live GUI or service state.

## Modules

### p1_nspanel_probe.py (191 LOC)

**Purpose:** NSPanel menubar probe verifying the panel stays open on outside click, timers keep firing while visible, and icon click plus hotkey both toggle.
**Reads:** live session data via `src.menubar.discover` (read-only).
**Writes:** nothing; foreground GUI app without Dock icon.
**Called by:** none. Do not run: registers a system-wide hotkey and opens a real panel.
**Calls out:** `objc`, `rumps`, `AppKit`, `Foundation`, `p1_hotkey.py`.

---

### p1_hotkey.py (62 LOC)

**Purpose:** Registers the panel hotkey as a real system-wide global hotkey via Carbon, the same mechanism the production menubar uses.
**Reads:** nothing.
**Writes:** a live OS-level hotkey registration for the process lifetime.
**Called by:** `p1_nspanel_probe.py` only. Never call it elsewhere; it is a real desktop side effect.
**Calls out:** `ctypes` (Carbon framework).

---

### menubar_debug.py (57 LOC)

**Purpose:** Boots out the real menubar launchd service, runs the menubar in the foreground with diagnostics, optionally re-bootstraps the service on exit.
**Reads:** nothing.
**Writes:** nothing; stdout and stderr are inherited.
**Called by:** none. Do not run: stops the production service.
**Calls out:** `launchctl` via `subprocess`.

---

## State
No persistent state. Both scripts act on external state they do not own: the OS hotkey table and the panel for the probe, the launchd service for the debug launcher.
