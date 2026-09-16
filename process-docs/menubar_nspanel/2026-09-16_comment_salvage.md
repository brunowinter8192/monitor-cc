# process-docs/menubar_nspanel/2026-09-16_comment_salvage.md

Session: dev/menubar_nspanel/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/menubar_nspanel/*.py` during this milestone, copied
verbatim before deletion (via AST+tokenize text parsing only — no file in this directory was ever
imported or executed), plus the full pre-rewrite content of `dev/menubar_nspanel/DOCS.md`.
Nothing judged and dropped — see the milestone rules in the calling agent's prompt
(module-standards conformance: relocate then delete, decide nothing).

File count (3) and comment/docstring totals (30 comments, 0 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/menubar_nspanel/*.py`
before deletion: `menubar_debug.py` passes a plain string literal to
`argparse.ArgumentParser(description=...)` — not `__doc__`. No load-bearing docstring found; 0
docstrings existed to begin with.

## Execution-safety note for this session

Main's own warning at the start of this session: `p1_nspanel_probe.py` registers a real,
system-wide Cmd+L hotkey (via `p1_hotkey.py`'s `_register_hotkey`, called unconditionally from
`NSPanelProbeApp.__init__`) and opens a real `NSPanel`; `menubar_debug.py` runs a real
`launchctl bootout` against the live production menubar launchd service and then foreground-runs
the real `workflow.py --mode menubar`. Neither was imported or executed, in either the pre-edit or
post-edit version. `p1_hotkey.py` has no dangerous top-level code of its own (only `def`
statements) but exists solely to support the forbidden probe above, and its one real function
performs the exact hotkey registration described — the same static-only treatment was extended to
it too, for consistency (matching the precedent already set for `dev/cursor_edges/` earlier this
cycle).

## Verification method for this session — token-skeleton diff (stronger than a text diff)

Per main's explicit instruction, behavior-preservation for all 3 files was proven by a
**token-skeleton diff**, not a text diff of a stripped copy: each file (pre-edit and post-edit)
was run through `tokenize.generate_tokens`, and the token stream was filtered to drop `COMMENT`
tokens, `NL` tokens (the non-logical newline that trails a comment-only or blank line), the
`ENCODING` token, and — via `ast.get_docstring`'s exact `lineno`/`col_offset` per docstring node —
every `STRING` token that IS a docstring. The remaining `(token_type, token_string)` sequence was
compared for exact equality between the pre-edit and post-edit version of each file. This is
stronger than a text diff because it is insensitive to any incidental whitespace/blank-line
reformatting the stripping pass might have introduced, and it directly proves no non-comment,
non-docstring token was added, removed, or reordered — not just that the byte sequence happens to
match. All 3 files: token skeletons identical.

Comment/docstring counts confirmed via AST + tokenize before deletion: 30 comments, 0
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/menubar_nspanel/DOCS.md

Full content of dev/menubar_nspanel/DOCS.md as it stood before this rewrite (62 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / Flow / State sections added).

```markdown
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
```

## Salvage from dev/proxy/menubar_debug.py

COMMENT L17:
```
# Bootout launchd service, run menubar in foreground with diagnostics enabled; re-bootstrap on exit
```

COMMENT L33:
```
# launchctl bootout — print result, ignore failure
```

COMMENT L42:
```
# launchctl bootstrap from installed plist
```

## Salvage from dev/proxy/p1_hotkey.py

COMMENT L21:
```
# Register Cmd+L as global hotkey via Carbon — identical to production _register_hotkey
```

COMMENT L27:
```
# With setMenu_(None), performClick_ fires the button's action → togglePanel_
```

## Salvage from dev/proxy/p1_nspanel_probe.py

COMMENT L8:
```
# Project root on path so 'src.menubar.discover' resolves when run from any CWD
```

COMMENT L23:
```
# From discover.py: Live session discovery
```

COMMENT L25:
```
# From bg_timer.py: Background sleep-timer scanning
```

COMMENT L43:
```
# pts below the status bar
```

COMMENT L48:
```
# Entry point: suppress Dock icon, create probe app, start run loop
```

COMMENT L57:
```
# NSObject target for NSStatusBarButton action and Cmd+L performClick_
```

COMMENT L77:
```
# NSPanel probe app — polls CC sessions every 1.5s, panel toggles via Cmd+L / bar click
```

COMMENT L84:
```
# NSPanel + its NSTextView
```

COMMENT L90:
```
# Lazy-init: null NSMenu, wire button target/action to _PanelController
```

COMMENT L99:
```
# _nsapp not ready yet; retry next tick
```

COMMENT L114:
```
# True if any session's status differs from last snapshot
```

COMMENT L120:
```
# Flash icon to ICON_BLINK for BLINK_DURATION seconds, then restore
```

COMMENT L126:
```
# Restore normal icon after blink
```

COMMENT L131:
```
# Badge for sessions with active background tasks
```

COMMENT L139:
```
# Section header line: ─── ProjectName ──────────
```

COMMENT L145:
```
# Build NSPanel (nonactivatingPanel, statusBar level) + NSTextView; return (panel, tv)
```

COMMENT L149:
```
# 128 — no focus steal, no auto-dismiss
```

COMMENT L150:
```
# NSBackingStoreBuffered
```

COMMENT L153:
```
# 25 — flush under menu bar
```

COMMENT L155:
```
# 1
```

COMMENT L156:
```
# 64
```

COMMENT L171:
```
# NSPanel is an ObjC object; store textview ref on Python app instance
```

COMMENT L174:
```
# Position panel flush under the status bar button
```

COMMENT L177:
```
# button's window frame is already in screen coordinates
```

COMMENT L184:
```
# Rebuild NSTextView attributed string from current session list (full replace, no flicker)
```

