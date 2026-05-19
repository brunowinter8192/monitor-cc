# dev/cursor_edges/

## Problem

`_PanelContentView.resetCursorRects` installs 4 cursor zones on the production NSPanel (bottom ↕, left ↔, right ↔, interior →). Bottom-edge I-Beam→Arrow transition worked in Iteration 3. Sides have never shown `↔`. As of 2026-05-20 even the bottom edge may have regressed.

**Root-cause hypothesis from Iteration 4:** Footer, TopBarView, and StackView *cover* the exact pixel strips where cursor rects should fire. AppKit's cursor-rect merge gives the *deepest* child view priority. The session-row `NSButton` subviews call `NSButton.resetCursorRects` (via super) which installs an I-Beam or Arrow over their full bounds — overriding the edge rects installed on the contentView.

## Investigation History

`decisions/OldThemes/menubar_overhaul_2026-05-19.md` § "NSPanel Cursor Rabbit Hole (4 Iterationen, DEFERRED)" — full iteration log.

## Scripts

### probe.py

Standalone foreground NSPanel that mirrors the production layout exactly (same geometry, same z-order, same autoresizingMasks). Every view is a logging subclass that prints to stderr on:

| Signal | Logged by |
|---|---|
| `resetCursorRects` | All 5 view subclasses |
| `cursorUpdate_` | All 5 view subclasses (marked `← WINNER` on buttons) |
| `mouseEntered_` / `mouseExited_` | All 5 view subclasses |
| `mouseMoved_` + hitTest result | `_LoggingContentView` only |
| Raw NSEventMaskMouseMoved | Global NSEvent monitor (pre-dispatch) |

**Subclasses:**

| Class | Mirrors |
|---|---|
| `_LoggingContentView(NSView)` | `_PanelContentView` — installs identical 4 cursor rects |
| `_LoggingStackView(NSStackView)` | production `stack` |
| `_LoggingButton(NSButton)` | Kill, Restart, Auto-Jump, session row buttons |
| `_LoggingFooterView(NSView)` | production `footer` |
| `_LoggingTopBarView(NSView)` | production `top_bar` |

**Usage:**

```bash
# from project root
venv/bin/python3 dev/cursor_edges/probe.py

# capture session to file
venv/bin/python3 dev/cursor_edges/probe.py 2>probe_$(date +%H%M%S).log
```

Runs in foreground. Panel appears on screen. Quit: **Cmd-Q** or **Ctrl-C**.

**Smoke run output (2026-05-20):** Panel starts, logs startup hierarchy, `resetCursorRects` cascade fires immediately. No crashes. See test plan below for interactive session.

**Startup observation:** `resetCursorRects` fires in child-first order on every subview:
1. ContentView (installs 4 rects)
2. FooterView → Button("Restart") → Button("Kill")
3. TopBarView → Button("Auto-Jump: ON")
4. StackView → 3 session row buttons

This confirms child views DO install cursor rects via super. The race is visible in the log.

## Test Plan

Run the probe, hover slowly at each position below, and capture which `cursorUpdate_` fires (the last one wins = what AppKit commits as the visible cursor).

| # | Position | Expected cursor | Expected winner |
|---|---|---|---|
| 1 | From outside, enter **left edge** (x < 8) | `↔` resizeLeftRight | ContentView (hypothesis: StackView or its children win instead) |
| 2 | From outside, enter **right edge** (x > 372) | `↔` resizeLeftRight | ContentView (hypothesis: StackView or Footer wins instead) |
| 3 | From outside, enter **bottom edge** (y < 8) | `↕` resizeUpDown | ContentView (was working in Iter 3; may be regressed) |
| 4 | From outside, enter **top edge** | Arrow (top_bar covers it) | TopBarView or Auto-Jump button |
| 5 | Over **Kill button** | Arrow or I-Beam | Button("Kill") |
| 6 | Over **Restart button** | Arrow or I-Beam | Button("Restart") |
| 7 | Over **session row button** | Arrow or I-Beam | Button(label) |
| 8 | Over **Auto-Jump button** in top_bar | Arrow or I-Beam | Button("Auto-Jump: ON") |
| 9 | **Interior** empty area (if any visible gap between rows) | Arrow | ContentView interior rect |

**Key question per position:** which class name appears after `cursorUpdate_` in the log? If it's a Button or StackView rather than ContentView → that view's cursor rect overrides ours.

## Findings (Phase B — fill after interactive session)

*To be filled after user reports hover results.*
