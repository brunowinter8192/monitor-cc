# CotEditor → Space Jump (selection throws to a different desktop)

## Symptom

User selects a line in a CotEditor document on desktop 1 → is immediately thrown to
desktop 2, where **Ghostty** is in the foreground (NOT CotEditor). CotEditor sits on
every space; after the jump, Ghostty is frontmost on the target space. The trigger feels
like the selection action, but the timing is fuzzy.

**Not reproducible on demand** (as of 2026-06-12) — occurs sporadically during normal
work. Parked: run the repro experiment below on next occurrence.

## Mechanism Narrowing

A jump-to-Ghostty can only come from `_focus_session(cwd)` (`src/menubar/system.py:44`).
The function builds an AppleScript `tell application "Ghostty" → activate → focus
terminal id "<UUID>"`. The `activate` is the jump: brings Ghostty forward, and if the
target terminal sits on a different space, macOS switches there.

`_focus_session` has exactly three callers:

| Caller | Location | Trigger | Log trace |
|---|---|---|---|
| `focusSession_` | `app.py:91` | manual panel click | Focus-log line only |
| digit-callback | `hotkey_controller.py:292` | cmd+digit press | `[hotkey] cmd+N → focus` + Focus-log |
| auto-focus | `focus_controller.py:54` | main-session working→idle (+3s) | Focus-log only; only when `_auto_focus`=true |

## Hypotheses

| Hypothesis | Status | Evidence |
|---|---|---|
| macOS auto-swoosh (app activation jumps to the app's window on a different space) | RULED OUT | Predicts a jump TO a CotEditor window; but the user lands on Ghostty |
| Stale menubar build (bundled code without the auto-focus gate) | RULED OUT | `diff` of bundled vs src `focus_controller.py` = identical; the `if self.app._auto_focus:` gate is present |
| `_load_settings` bug (loads auto_focus=true despite the file) | RULED OUT | `app_settings.py:_load_settings` correctly reads `bool(d.get('auto_focus', False))`; file = false |
| Auto-focus fires despite `_auto_focus=false` (runtime value diverges) | UNVERIFIED | Settings file=false, process started after → should be false; only a live repro can clarify |
| cmd+digit fires unintentionally while selecting | UNVERIFIED | Would log a `[hotkey]` line; none seen at jump time so far |
| The jump does NOT come from the menubar (`_focus_session` doesn't fire at all) | UNVERIFIED | Only a repro with log observation can confirm/rule this out |

Three hypotheses are burned — caution needed on the next one, no jumping ahead.

## Repro Experiment (on next occurrence)

1. Set markers:
   - `wc -l /tmp/monitor-cc-menubar_focus.log`
   - `wc -l ~/Library/Application\ Support/com.brunowinter.monitor-cc-menubar/menubar.log`
2. Reproduce the bug (select in CotEditor until the jump happens). **Do NOT touch the
   menubar in the meantime.**
3. Read the new lines from the marker on and classify:
   - New focus line at the jump moment **+ `[hotkey]`** → cmd+digit.
   - New focus line **without `[hotkey]`** (and no click) → auto-focus ⇒ `_auto_focus`
     is `true` at runtime.
   - **No** new focus line → the menubar is innocent, the jump comes from somewhere
     else (gesture/macOS/another app).

Focus-log line format (`system.py:_focus_session`): `<ts> OK id=<UUID>` (Path A) / `OK
cwd=<path>` (Path B) / `MISS` / `ERR` / `TIMEOUT`.

## macOS Findings

- `workspaces-auto-swoosh` (com.apple.dock): unset = default. Not the cause (see above),
  but relevant to space behavior in general.
- The menubar runs as a py2app bundle `~/Applications/monitor-cc-menubar.app` (build
  2026-06-10 03:54), reads settings from `~/Library/Application
  Support/com.brunowinter.monitor-cc-menubar/settings.json` (at the time: `auto_focus:
  false`).

## Related Topic — cmd+N brings Ghostty forward everywhere

The same `activate` in `_focus_session` was at the core of a separate cmd+N-foreground
issue (cmd+N brought Ghostty to the foreground on ALL desktops instead of only the
target desktop). There, the `activate` was removed — fixes cmd+N, but does NOT affect
this CotEditor jump (see below: the jump doesn't come from `_focus_session` at all).

## Repro Finding 2026-06-12 — Menubar as Cause RULED OUT

The bug was reproduced live (~22:03): user selected a line in CotEditor on desktop 3 →
was thrown to desktop 1 with Ghostty in the foreground. User confirmed: **selected with
mouse/trackpad only, NO cmd-digit pressed.**

Log analysis (marker diff): the focus log had **NO entry** at the jump moment (a
2.5-minute gap around 22:03; the only event was a `cmd+k` = panel toggle, not a focus).

→ Case 3 of the repro experiment: **no focus line = `_focus_session` did not fire = the
menubar is innocent.** The jump does NOT come from the menubar focus function.
Hypothesis "the jump does NOT come from the menubar" → **CONFIRMED**; the
menubar-internal candidates (auto-focus, cmd+digit) are ruled out for this case (no
event logged).

**Consequence — logging gap:** current logging only captures `_focus_session` calls
(focus log) and cmd-keypresses (`[hotkey]`). The real trigger of the CotEditor selection
jump is currently NOT logged at all. The next step needs a different way to catch the
trigger — candidates: macOS spaces behavior on focus change, a trackpad/gesture source,
another app/system mechanism (all outside the menubar).
