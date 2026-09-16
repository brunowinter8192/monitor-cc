# process-docs/cursor_edges/2026-09-16_comment_salvage.md

Session: dev/cursor_edges/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/cursor_edges/*.py` during this milestone, copied
verbatim before deletion (via AST+tokenize text parsing only — no file in this directory was ever
imported or executed), plus the full pre-rewrite content of `dev/cursor_edges/DOCS.md`. Nothing
judged and dropped — see the milestone rules in the calling agent's prompt (module-standards
conformance: relocate then delete, decide nothing).

File count (5) and comment/docstring totals (49 comments, 8 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across `dev/cursor_edges/*.py`
before deletion: `probe.py` passes a plain string literal (`'cursor-edges probe'`) to
`argparse.ArgumentParser(description=...)` — not `__doc__`, a separate string from the module
docstring. No load-bearing docstring found anywhere in this directory. All 8 deleted outright.

## Execution-safety note for this session — read before touching this directory again

`probe.py` calls `main()` at module scope with no `if __name__ == '__main__':` guard (line 189 in
the pre-edit file). **Merely importing this file builds a real `NSApplication`, orders a real
`NSPanel` front on the real screen, and blocks in `app.run()`.** Main flagged this explicitly at
the start of this session and it was never imported or executed, in either the pre-edit or
post-edit version.

The other 4 files (`cursor_edges_constants.py`, `cursor_edges_logging.py`,
`cursor_edges_panel.py`, `cursor_edges_views.py`) don't have that specific unguarded-call defect,
but every one of them exists solely to support this one NSPanel probe: `cursor_edges_panel.py`'s
functions construct real `NSPanel`/`NSView` instances the moment they're called, and
`cursor_edges_logging.py`'s `_install_global_mouse_monitor` installs a real system `NSEvent`
local monitor. Main confirmed extending the same static-only treatment (never import, never
execute) to all 5 files for this session, rather than hand-picking which individual functions
might be safe to call. A future worker touching this directory again should re-derive the
per-function safety picture from scratch rather than assume this file's caution level, since the
constants/logging files in isolation are plausibly safe to import — this session simply chose
not to gamble on that distinction.

Behavior-preservation for all 5 files was proven by mechanically stripping comments/docstrings
from a copy of each pre-edit source file and diffing that stripped copy byte-for-byte against the
actual post-edit file — a purely textual operation (AST parse + tokenize), never an import or a
`python3 <file>.py` execution.

Comment/docstring counts confirmed via AST + tokenize before deletion: 49 comments, 8 docstrings,
matching the task's stated measured state exactly.

## Salvage from dev/cursor_edges/DOCS.md

Full content of dev/cursor_edges/DOCS.md as it stood before this rewrite (95 lines), preserved
verbatim since the whole file is being replaced with the mandated leaner format (Role capped
at 50 words, Purpose capped at 25 words per module, no Gotchas section in the new format,
Public Interface / Flow / State sections added).

```markdown
# dev/cursor_edges/

## Role

Standalone NSPanel cursor-rect investigation probe. `_PanelContentView.resetCursorRects` installs
4 cursor zones on the production NSPanel (bottom `↕`, left `↔`, right `↔`, interior `→`) — this
probe mirrors the production panel layout exactly (same geometry, z-order, autoresizing masks) in
a standalone foreground window to isolate which view wins the cursor-rect dispatch race, without
touching `src/`. Touch this directory when re-investigating NSPanel edge-hover cursor behavior;
the full iteration/hypothesis trail lives in `process-docs/menubar_build/` (see that area for
history — this probe's own current shape is documented below).

## Modules

### probe.py (189 LOC)

**Purpose:** Entry script — parses CLI flags, builds the app + panel, logs the startup banner,
runs the foreground event loop. Carries the full module docstring (flag semantics, hypotheses,
usage).
**Reads:** nothing — standalone GUI window, no file/log input.
**Writes:** nothing — stderr log lines only (capture with `2>file.log`), via the imported `_log`.
**Called by:** none — run manually, foreground only (`Cmd-Q`/`Ctrl-C` to quit).
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_panel.py`;
`AppKit` (pyobjc bridge).

**CLI flags:** `--fix` (calls `enableCursorRects()` after `setContentView_`), `--leaf-rects`
(installs resize rects on covering leaf subviews too, requires `--fix`), `--no-resizable`
(constructs the panel without `NSWindowStyleMaskResizable`) — combinable.

---

### cursor_edges_constants.py (32 LOC)

**Purpose:** Geometry constants mirroring production exactly, `NSTrackingArea` option flag
combinations, and the two mutable flags (`_LEAF_RECTS_ENABLED`, `_TRACKING_ENABLED`) `probe.py`
sets from CLI args and every other module in this directory reads.
**Reads:** nothing.
**Writes:** nothing (its two flags are mutated in place by `probe.py`, module-qualified —
`import cursor_edges_constants as cec; cec._LEAF_RECTS_ENABLED = ...` — never `from ... import`,
which would decouple the reader's copy from later writes).
**Called by:** `probe.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`,
`cursor_edges_panel.py`.
**Calls out:** `AppKit` (pyobjc bridge).

---

### cursor_edges_logging.py (49 LOC)

**Purpose:** stderr logging helpers (`_log`, `_dump_hierarchy`) and the two non-view-class
tracking helpers (`_install_tracking_area`, `_install_global_mouse_monitor`).
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `probe.py`, `cursor_edges_views.py`.
**Calls out:** `cursor_edges_constants.py`; `AppKit` (pyobjc bridge).

---

### cursor_edges_views.py (371 LOC)

**Purpose:** The 6 logging/tracking NSView-family subclasses that mirror production views
(`_LoggingContentView`, `_TrackingContentView`, `_LoggingStackView`, `_LoggingButton`,
`_LoggingFooterView`, `_LoggingTopBarView`) — each prints to stderr on `resetCursorRects`,
`cursorUpdate_`, `mouseEntered_`/`mouseExited_`, `mouseMoved_`+hitTest.
**Reads:** nothing.
**Writes:** stderr, via `_log`.
**Called by:** `cursor_edges_panel.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`; `objc`, `AppKit`,
`Foundation` (pyobjc bridge).

---

### cursor_edges_panel.py (145 LOC)

**Purpose:** Builds the probe NSPanel that mirrors production `_make_nspanel()` geometry and
z-order exactly (window, content view, footer, top bar, session-row stack).
**Reads:** nothing.
**Writes:** nothing — constructs but never shows the panel (`probe.py`'s `main()` calls
`orderFront_`).
**Called by:** `probe.py`.
**Calls out:** `cursor_edges_constants.py`, `cursor_edges_logging.py`, `cursor_edges_views.py`;
`AppKit`, `Foundation` (pyobjc bridge).

---

## Gotchas

**`cursorUpdate_` is not a reliable signal for cursor-rect dispatch.** It's the
`NSTrackingArea` callback mechanism; `addCursorRect_cursor_` dispatches directly at the AppKit
window level without firing `cursorUpdate_`. A zero `cursorUpdate_` count is consistent with
cursor-rect dispatch working normally. The correct signal is whether the visible cursor SHAPE
changes at the edge, not whether `cursorUpdate_` fired.

**`NSWindowStyleMaskNonactivatingPanel` blocks `enableCursorRects()` by default** — without an
explicit `enableCursorRects()` call after `setContentView_`, no cursor-rect dispatch happens on
a nonactivating panel at all (`--fix` tests this).
```

## Salvage from dev/proxy/cursor_edges_constants.py

COMMENT L10:
```
# Mirror production geometry constants exactly
```

COMMENT L16:
```
# cursor-rect / edge-detection width in production
```

COMMENT L19:
```
# upper clamp for custom drag resize
```

COMMENT L21:
```
# NSTrackingArea option flags for legacy (non-tracking) modes
```

COMMENT L24:
```
# NSTrackingArea option flags for --tracking mode
```

COMMENT L25:
```
# .cursorUpdate fires cursorUpdate_ regardless of key-window status (activeAlways guarantees this)
```

COMMENT L30:
```
# Module-level flags set by argparse before panel construction.
```

## Salvage from dev/proxy/cursor_edges_logging.py

DOCSTRING L29:
```
Replace all tracking areas on `view` with a fresh full-bounds area (legacy modes).
```

DOCSTRING L38:
```
NSEvent local monitor — captures mouseMoved before any view-level dispatch.
```

## Salvage from dev/proxy/cursor_edges_panel.py

COMMENT L56:
```
# Hypothesis: NonactivatingPanel never calls becomeKeyWindow → enableCursorRects
```

COMMENT L57:
```
# never invoked internally → cursor rects installed but dispatch disabled.
```

COMMENT L58:
```
# Explicit call should re-enable dispatch without requiring key-window status.
```

COMMENT L71:
```
# NSViewWidthSizable
```

COMMENT L75:
```
# NSViewMinXMargin — right-anchored
```

COMMENT L82:
```
# NSViewMinXMargin
```

COMMENT L93:
```
# NSViewWidthSizable | NSViewMinYMargin
```

COMMENT L98:
```
# NSButtonTypeMomentaryPushIn
```

COMMENT L100:
```
# NSViewWidthSizable
```

COMMENT L110:
```
# NSViewWidthSizable | NSViewHeightSizable
```

COMMENT L114:
```
# NSStackViewDistributionGravityAreas
```

COMMENT L116:
```
# Three fake session row buttons — representative of production stack content
```

DOCSTRING L133:
```
Build probe NSPanel that mirrors production _make_nspanel() geometry and z-order exactly.
```

## Salvage from dev/proxy/cursor_edges_views.py

COMMENT L19:
```
# Logging subclass for the contentView (mirrors _PanelContentView) — cursor-rect mode
```

COMMENT L20:
```
# Installs identical 4-zone cursor rects and logs every AppKit cursor signal.
```

COMMENT L63:
```
# NSTrackingArea + cursorUpdate content view — Iteration 8 pattern
```

COMMENT L64:
```
# Replaces addCursorRect_cursor_ entirely. Uses .cursorUpdate option on the tracking area
```

COMMENT L65:
```
# so cursorUpdate_ fires on mouse movement regardless of key-window status (.activeAlways).
```

COMMENT L66:
```
# hitTest_ claims L/R/bottom edge zones so child views don't intercept events there.
```

COMMENT L67:
```
# NSCursor.push()/pop() maintains cursor against child views that call super.cursorUpdate_.
```

COMMENT L68:
```
# Custom mouseDown_/mouseDragged_ handles resize when --no-resizable drops native mechanism.
```

COMMENT L69:
```
# Edges: left (x<EDGE), right (x>w-EDGE), bottom (y<EDGE) — mirrors production exactly.
```

COMMENT L76:
```
# Edge tracking state
```

COMMENT L77:
```
# None | 'left' | 'right' | 'bottom'
```

COMMENT L79:
```
# Custom drag-resize state (active when --no-resizable)
```

COMMENT L80:
```
# None | 'left' | 'right' | 'bottom'
```

DOCSTRING L107:
```
Push/pop cursor stack on edge transitions; call set() for immediate visual update.
```

COMMENT L112:
```
# nil → edge: push new cursor onto stack
```

COMMENT L116:
```
# edge → nil: pop our cursor off the stack
```

COMMENT L120:
```
# edge_a → edge_b (e.g. left→bottom): pop old, push new
```

COMMENT L125:
```
# call set() for immediate visual feedback in addition to the stack change
```

DOCSTRING L133:
```
Determine edge zone for a point in local (view) coordinates.
```

DOCSTRING L144:
```
Called by AppKit when tracking area cursor-update event fires.
```

DOCSTRING L167:
```
Claim L/R/bottom edge zones for self; interior falls through to child views.
```

COMMENT L171:
```
# Only claim the point if it's inside our bounds at all
```

COMMENT L213:
```
# positive → dragging left → panel grows
```

COMMENT L215:
```
# right edge stays fixed
```

COMMENT L218:
```
# positive → dragging right → panel grows
```

COMMENT L222:
```
# positive → dragging down → panel grows taller
```

COMMENT L224:
```
# top edge stays fixed
```

COMMENT L233:
```
# Logging subclass for the middle NSStackView (session rows live here)
```

COMMENT L267:
```
# Logging subclass for all NSButton instances (Kill, Restart, Auto-Jump, session rows)
```

COMMENT L277:
```
# Install left-edge rect only when button frame starts at panel left edge
```

COMMENT L278:
```
# (frame.origin.x < EDGE in parent coords → local x=0 maps to panel x≈0).
```

COMMENT L279:
```
# Auto-Jump and session-row buttons start at x=0; Kill/Restart do not.
```

COMMENT L303:
```
# Logging subclass for the footer NSView (bottom bar, parent of Kill+Restart)
```

COMMENT L340:
```
# Logging subclass for the top-bar NSView (parent of Auto-Jump button)
```

## Salvage from dev/proxy/probe.py

DOCSTRING L2-60:
```

dev/cursor_edges/probe.py — Foreground cursor-rect race diagnostic + NSTrackingArea probe.

Mirrors production NSPanel layout exactly (same geometry, same z-order,
same view classes where possible). Logs ALL cursor-related AppKit signals
to stderr so we can determine which view wins the cursor-rect race per
hover position.

Run from project root:
    venv/bin/python3 dev/cursor_edges/probe.py
    venv/bin/python3 dev/cursor_edges/probe.py --fix
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects
    venv/bin/python3 dev/cursor_edges/probe.py --fix --tracking
    venv/bin/python3 dev/cursor_edges/probe.py --tracking --no-resizable

--fix: calls panel.enableCursorRects() immediately after setContentView_,
       then logs areCursorRectsEnabled() to confirm the call was accepted.
       Hypothesis: NonactivatingPanel skips the becomeKeyWindow path that
       normally triggers enableCursorRects → cursor rects sit installed but
       are never dispatched. Explicit call should re-enable dispatch.

--leaf-rects (requires --fix): installs resize cursor rects directly on each
       leaf subview (StackView, FooterView, TopBarView, and left-edge Buttons)
       at their portion of the panel edges, AFTER super.resetCursorRects.
       Tests Iteration 6 hypothesis: subview coverage shadows ContentView's
       edge rects — installing rects on the covering views themselves should
       win the dispatch race.

--no-resizable: creates the panel WITHOUT NSWindowStyleMaskResizable (only
       NSWindowStyleMaskNonactivatingPanel). Combinable with --fix/--leaf-rects.
       Tests H7: WindowServer reserves edge regions for native resize, which
       for NonactivatingPanel blocks our cursor rects without showing any
       resize cursor itself. Without the resizable mask WindowServer should
       not claim the edges and our rects may fire.
       Trade-off: no native drag-resize. That is the POINT of this test.

--tracking: replaces _LoggingContentView with _TrackingContentView — uses
       NSTrackingArea with .cursorUpdate option instead of addCursorRect_cursor_.
       cursorUpdate_ fires regardless of key-window status (activeAlways).
       Bypasses the cursor-rect dispatch path entirely.
       hitTest_ override claims L/R/bottom edge zones so child views don't win.
       NSCursor.push()/pop() maintains cursor against child views that reset it.
       Ref: sw33tLie/macshot RecordingHUDPanel.swift + lifedever/PasteMemo
            RelayFloatingWindowController.swift (same nonactivatingPanel setup).

--tracking --no-resizable: full PasteMemo pattern — tracking area cursor +
       custom mouseDown_/mouseDragged_ resize (drops native NSWindowStyleMaskResizable).
       This is the production-candidate combination.

Quit: Cmd-Q or close the window. Ctrl-C also works (SIGINT handler).

All output goes to stderr. Pipe to file to capture a session:
    venv/bin/python3 dev/cursor_edges/probe.py 2>probe_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix 2>probe_fix_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects 2>probe_leaf_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --no-resizable 2>probe_noresize_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --fix --tracking 2>probe_tracking_$(date +%H%M%S).log
    venv/bin/python3 dev/cursor_edges/probe.py --tracking --no-resizable 2>probe_tracking_noresize_$(date +%H%M%S).log

```

