# cmd+N — Ghostty comes to the front on every desktop (RESOLVED 2026-06-12)

## Symptom

A session switch via the menubar hotkeys (cmd+1..9) or a panel click brought Ghostty to
the foreground on EVERY desktop, instead of switching to only the one target terminal
on its space. Expected: switch to the target space + only there does Ghostty come
forward.

## Cause

`_focus_session(cwd)` (`src/menubar/system.py`) built the AppleScript
`tell application "Ghostty" → activate → focus terminal id "<UUID>"`.
The `activate` is Cocoa's **app-level** `NSApplication.activate` → makes Ghostty the
global foreground app → Ghostty's windows float to the front on EVERY space.

## Evidence (Ghostty sdef + live A/B test)

Ghostty Scripting Dictionary (`/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`, v1.3.1):
- `focus` command: *"Focus a terminal, **bringing its window to the front**"* — window-level.
- `activate window` command: window-level activate (exists; wasn't needed).
- The app-level `activate` in the code is NOT a Ghostty command, but Cocoa's default.

Live A/B test on the user's machine (2026-06-12):
- `focus terminal id "<UUID>"` WITHOUT `activate` → only the ONE target window came
  forward (user: "only the one in question").
- Also works when a DIFFERENT app (CotEditor) is in front → Ghostty comes over it.
- Conclusion: the `activate` is pure harm; `focus` alone is enough and switches to the
  space.

## Fix

`src/menubar/system.py:_focus_session` — removed the `activate` line from BOTH
AppleScript strings (Path A UUID + Path B cwd-match), nothing else. Merged to dev, then
baked into the compiled py2app menubar.

**Live verified** (2026-06-12, compiled menubar): cmd+N brings forward only the target
terminal, other desktops stay untouched.

## Sources
- `src/menubar/system.py:_focus_session`
- `/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef` (v1.3.1)
- Commit on dev: `c29fec8` (merge of the `_focus_session` fix)
