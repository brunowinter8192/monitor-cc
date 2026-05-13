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
