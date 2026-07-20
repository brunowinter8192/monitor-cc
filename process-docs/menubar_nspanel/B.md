# NSPanel Refactor — Phase B Build Narrative

## What Was Built

`src/menubar/menubar.py` ported from NSMenu to NSPanel. 351 → 395 LOC. All seven production features preserved (Auto-Jump, sessions list, bg-task badge, blink, click-to-focus, Cmd+L, Quit).

## Per-Row Widget Choice — NSStackView + NSButton

NSButton rows for all session entries (main sessions + workers) inside a vertical NSStackView. NSTextField for project-header lines (non-interactive). Rationale vs. alternatives:

- **NSTableView rejected:** requires two ObjC protocol bridges (NSTableViewDataSource + NSTableViewDelegate). 5–20 rows that always fully-rebuild on the closed tick don't warrant the complexity.
- **NSTextField + NSClickGestureRecognizer rejected:** hit-testing on non-editable NSTextField fields with gesture recognizers is fragile in PyObjC.
- **NSButton chosen:** native target/action for click callbacks; `setAttributedTitle_` for Menlo font + color; uniform row height in the stack. In-place update calls `btn.setAttributedTitle_()` directly — same pattern as old `_menuitem.setAttributedTitle_()`, just without the `.\_menuitem` bridge layer.

## Tag → cwd Routing for Click-to-Focus

NSButton (like all PyObjC-bridged ObjC objects) rejects arbitrary Python attribute assignment — can't set `btn.cwd = s.cwd`. Solution: `NSButton.setTag_(tag)` assigns an integer tag to each clickable session button in `_rebuild_panel`. `app._cwd_map: {tag: cwd}` maps tag → cwd. `_PanelController.focusSession_` reads `sender.tag()` and looks up the cwd. Single `_PanelController` instance (no per-session ObjC objects). `_cwd_map` is reset at the top of each `_rebuild_panel` so tags are always fresh within a rebuild cycle.

## Quit Placement — Footer NSButton

NSPanel contentView has two regions: `NSScrollView` (sessions, `y=30..460`) + `NSView` footer (`y=0..30`) with a single "Quit" NSButton. Footer is outside the scroll area — Quit is always visible regardless of scroll position. The footer's Quit button target/action is wired in `_tick` lazy-init (same timing as the bar-button wiring) because `_panel_controller` exists at `__init__` time but the NSApp run loop must be running for the action dispatch to work.

`quit_button=None` passed to `rumps.App.__init__` to suppress rumps' default quit-button (which is menu-attached and would be orphaned with `setMenu_(None)`). Quit is now the footer NSButton.

## What Changed vs. Probe

| Area | Probe | Phase B |
|---|---|---|
| Content widget | NSTextView (attributed string blob) | NSStackView + NSButton / NSTextField rows |
| Click-to-focus | Not implemented | `_PanelController.focusSession_` + `_cwd_map[tag]` |
| Auto-Jump toggle | Not implemented | `_PanelController.toggleAutoJump_` + button title in-place update |
| Quit | NSMenu quit_button (not connected) | Footer NSButton → `quitApp_` |
| In-place update | Full text replace | `btn.setAttributedTitle_()` per session (preserves scroll) |
| Auto-focus debounce | Not implemented | Full production `_idle_since_ts` logic in `_tick` |
| `_MenuDelegate` | Not present | Not present (eliminated) |
| `NSRunLoopCommonModes` | Not present | Not present (eliminated) |

## Surprises

**`NSTextField.labelWithString_` is already non-editable/non-selectable/borderless** — the four `.setX_(False)` calls in the first draft were redundant. Removing them tightened `_make_header_label` from 12 to 5 lines.

**LOC ceiling hit on first draft (449 LOC).** Dead functions `_make_focus_cb` and `_make_toggle_cb` (carried from production, no longer called in the panel version) contributed 11 LOC. Removing dead code + tightening `_register_hotkey` blank lines + compressing `_make_nspanel` brought the final file to 395 LOC.

**Smoke test via `-m src.menubar.menubar` exits with code 0** (not a crash). The module has no `if __name__ == '__main__':` guard and no top-level `run()` call — the correct invocation is `workflow.py --mode menubar`. Re-running via the correct path: 5s uptime, zero stderr.

## Verification Result

```
./venv/bin/python3 workflow.py --mode menubar &
# 5s later: process still alive (kill -0 returns 0), log empty
```

Confirms: all imports resolve, `CCMenuBarApp.__init__` completes (NSPanel + NSStackView + `_PanelController` created), `@rumps.timer` starts, first `_tick` fires without crash.

## Decision-Next

Ready for merge + interactive UI verification:
1. Panel opens/closes on Cmd+L and bar-icon click
2. Outside click does NOT dismiss (the key regression test)
3. `@rumps.timer` fires while panel open (blink on session status change)
4. Click on a main session row → Ghostty terminal focus
5. Auto-Jump toggle updates label in-place
6. Quit button exits app

## Layout Surprise (Phase B follow-up)

**Discovery:** After Phase B merged and the user ran the interactive UI tests (all 6 behavioral checks passed), the visual layout was wrong. ~150 px of content rendered at the bottom of a 460 px panel; the Auto-Jump toggle appeared mid-screen with ~280 px of empty space above it.

**Root cause:** `NSStackView.addArrangedSubview_` defaults to `NSStackViewGravityBottom` (constant 3) in AppKit's gravity-well model. Items anchor to the bottom of the stack frame and pack upward. With a document view sized to `scroll_h = 430 px` but only ~150 px of rows, the remaining 280 px of whitespace lands above all rows — exactly matching the reported symptom.

**Fix chosen: Option (a) — `addView_inGravity_(view, 1)`**

`NSStackViewGravityTop = 1`. Replace every `addArrangedSubview_` call in `_rebuild_panel` with `addView_inGravity_(view, 1)`. Also replaced the cleanup `removeArrangedSubview_(sv) + sv.removeFromSuperview()` pair with `removeView_(sv)` (the gravity-API removal method, single call).

Option (b) — `isFlipped` override via NSStackView subclass — was rejected: same visual result but requires a new ObjC class definition and PyObjC `objc.objc_method` wiring, adding ~10 lines of boilerplate for no additional benefit.

**Code delta:** 6 call sites changed in `_rebuild_panel`, net -1 LOC (394 from 395).

**Smoke test:** `workflow.py --mode menubar` alive after 5 s, zero stderr. Visual verification (top-anchored layout) after merge with user.

## Layout Fix Round 2

**Constants verification (run on this worktree's venv):**

```
GravityTop= 1  GravityCenter= 2  GravityBottom= 3
DistGravityAreas= -1  DistFill= 0
```

**Root cause:** `stack.setDistribution_(0)` is `NSStackViewDistributionFill`. In Fill mode, the stack distributes views to fill available space equally — gravity metadata is **completely ignored**. The Round 1 fix correctly changed all `addArrangedSubview_` calls to `addView_inGravity_(view, 1)`, but because the distribution remained `Fill`, `NSStackView` never consulted the gravity at layout time. All views still appeared clustered at the bottom (NSStackView default gravity in Fill mode is bottom-anchoring).

**Fix:** one-line change in `_make_nspanel`:

```python
# Before (Round 1):
stack.setDistribution_(0)   # NSStackViewDistributionFill

# After (Round 2):
stack.setDistribution_(-1)   # NSStackViewDistributionGravityAreas — required for addView_inGravity_ to work
```

`NSStackViewDistributionGravityAreas = -1` is the only distribution mode that uses the gravity passed to `addView_inGravity_`. Without it, all gravity API calls are no-ops.

**Code delta:** 1 line changed in `_make_nspanel` (line 288), no LOC change (395 → 395).

**Smoke test:** `workflow.py --mode menubar` alive after 5 s, zero stderr.
