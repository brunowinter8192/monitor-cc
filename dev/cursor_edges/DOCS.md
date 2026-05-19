# dev/cursor_edges/

## Problem

`_PanelContentView.resetCursorRects` installs 4 cursor zones on the production NSPanel (bottom ↕, left ↔, right ↔, interior →). Bottom-edge I-Beam→Arrow transition worked in Iteration 3. Sides have never shown `↔`. As of 2026-05-20 even the bottom edge may have regressed.

**Iteration 4 hypothesis (REFUTED by probe):** Footer, TopBarView, and StackView *cover* the exact pixel strips where cursor rects should fire. AppKit's cursor-rect merge gives the *deepest* child view priority.

**Iteration 5 hypothesis (PARTIALLY CONFIRMED, 2026-05-20):** `NSWindowStyleMaskNonactivatingPanel` blocks cursor-rect dispatch entirely. `enableCursorRects()` was missing — confirmed by visual evidence: I-Beam→Arrow transition on panel entry NOW works with `--fix`. Resize `↔` at edges still does not appear → a second blocker remains.

**Iteration 6 hypothesis (active):** Subview coverage IS the remaining blocker. ContentView's edge cursor-rects are shadowed by StackView/FooterView/TopBarView which cover the same strips. Fix: install resize rects on each covering leaf subview in its own `resetCursorRects`. `--leaf-rects` flag tests this.

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
# baseline — no fix, confirms 0 cursorUpdate_ (already verified interactively 2026-05-20)
venv/bin/python3 dev/cursor_edges/probe.py

# --fix — calls enableCursorRects() after setContentView_, tests Iteration 5 hypothesis
venv/bin/python3 dev/cursor_edges/probe.py --fix

# --fix --leaf-rects — installs resize rects on covering leaf subviews, tests Iteration 6 hypothesis
venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects

# capture session to file
venv/bin/python3 dev/cursor_edges/probe.py 2>probe_$(date +%H%M%S).log
venv/bin/python3 dev/cursor_edges/probe.py --fix 2>probe_fix_$(date +%H%M%S).log
venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects 2>probe_leaf_$(date +%H%M%S).log
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

## Findings

### Iteration 4 baseline (interactive run, 2026-05-20)

| # | Position | mouseMoved_ | cursorUpdate_ | hitTest result |
|---|---|---|---|---|
| 1 | Left edge (x < 8) | ~280 fires | **0** | Correct view |

`resetCursorRects` cascade: all 10 subviews, correct order. `areCursorRectsEnabled` not checked in this run (baseline has no explicit call).

**Conclusion:** cursor-rect dispatch is not engaged at all. Iteration 4's child-view-race hypothesis was wrong — the race never runs.

### Iteration 5 --fix smoke (automated, 2026-05-20)

```
[--fix]  enableCursorRects() called — areCursorRectsEnabled=True
[--fix]  ✓ cursor-rect dispatch enabled — hover an edge to see cursorUpdate_
```

`enableCursorRects()` accepted (no AttributeError), panel confirms dispatch enabled. Interactive hover needed to verify `cursorUpdate_` fires.

### Iteration 5b — --fix partial confirm (interactive, 2026-05-20)

User ran `probe.py --fix` and hovered the left edge. Two results:

| Observation | Interpretation |
|---|---|
| I-Beam → Arrow transition NOW works on panel entry | `enableCursorRects()` was genuinely missing — confirms NonactivatingPanel hypothesis |
| Resize `↔` at left edge still does NOT appear | A second blocker remains beyond `enableCursorRects` |
| `cursorUpdate_` logged 0 times | **NOT a valid signal** — see note below |

**`cursorUpdate_` is NOT the right metric for cursor-rect verification.** `cursorUpdate_` is the NSTrackingArea callback mechanism. `addCursorRect_cursor_` dispatches directly at AppKit window level without firing `cursorUpdate_`. Zero `cursorUpdate_` count is consistent with cursor-rect dispatch working normally — the cursor rect fires directly, tracking area callback never invoked.

The correct visual signal: does the cursor shape change at the edge? It did change (I-Beam→Arrow), confirming cursor-rect dispatch works. The `↔` shape is still missing → ContentView's left-edge rect is shadowed by covering subviews.

### Iteration 6 — Leaf-Rect Test (pending user verification)

`probe.py --fix --leaf-rects` installs resize cursor rects on each leaf subview at their portion of the panel edges (super first, then leaf rects):

| View | Rects installed |
|---|---|
| `_LoggingStackView` | LEFT + RIGHT (x=0..8, x=372..380, full local h) |
| `_LoggingFooterView` | LEFT + RIGHT + BOTTOM (x=0..8, x=372..380, y=0..8 full width) |
| `_LoggingTopBarView` | LEFT + RIGHT (no top rect per spec) |
| `_LoggingButton` | LEFT (local x=0..8) if `frame.origin.x < EDGE` — Auto-Jump and session row buttons only; Kill/Restart excluded |

Smoke (2026-05-20): starts clean, all `[leaf]` lines logged in `resetCursorRects` cascade, no AttributeError, `areCursorRectsEnabled=True`.

**Pending:** user runs `venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects` and hovers left and right edges.
