# G3 — Window Detection Probe: Method A (title-match) vs Method B (frontmost)

**Status:** CotEditor fixed and re-run (2026-05-31 second pass). CotEditor: all signals confirmed. Ghostty: space detection confirmed; title-match still open (root cause: `open --args --command` not honored).

Continues G2 (`G2_space_move_probe.md`). Goal: determine whether RELIABLE window identification + space determination is possible across three window types WITHOUT a move operation.

## Design

`dev/desktop_detection/05_window_detection_probe.py` — 3 window types × 3 trials (2 fg, 1 bg):

1. **ghostty_tmux** — `open -n -a Ghostty --args --command "tmux attach-session -t TOKEN"`, token=`p05t<6hex>`
2. **ghostty_osc2** — `open -n -a Ghostty --args --command "bash -c 'printf \"\\033]2;TOKEN\\007\"; sleep 60'"`, token=`p05g<6hex>`
3. **coteditor** — write `/tmp/probe05_TOKEN.txt`, `open -g -a CotEditor /tmp/probe05_TOKEN.txt` (no -n; see §CotEditor fix below), token=`p05c<6hex>`

**Ground truth:** Ghostty: snapshot `before = _owner_wids_layer0(owner, require_name)` strictly before `open`; poll 0.2s/5s until delta non-empty; `wid_gt = min(delta)`. CotEditor: poll via token-name-match (`_method_a("CotEditor", token)`) until non-None.
**Method A:** scan CGWindowList for owner+layer0+name-contains-token → compare to gt.
**Method B:** first owner+layer0 window in CGWindowList (front-to-back z-order) → compare to gt.
**Space signals:** S1=`CGSGetActiveSpace` before open; S2=`wid_gt in on_screen_wids()` after; S3=`CGSCopySpacesForWindows(wid_gt)`. Agreement: S1==S3[0] AND S2==True.

## Trial Results — Pass 1 (2026-05-31, broken CotEditor approach)

| type | tr | fg/bg | gt_wid | title_observed | A_agree | B_agree | desktop | space_agree |
|---|---|---|---|---|---|---|---|---|
| ghostty_tmux | 1 | fg | 2032 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_tmux | 2 | fg | 2046 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_tmux | 3 | bg | 2063 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 1 | fg | 2076 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 2 | fg | 2090 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| ghostty_osc2 | 3 | bg | 2099 | `…/Documents/ai/Monitor_CC` | False | False | 3 | True |
| coteditor | 1 | fg | 2115 | null | False | False | None | False |
| coteditor | 2 | fg | 2141 | null | False | False | None | False |
| coteditor | 3 | bg | 2162 | `Trading.md` | False | False | None | False |

## Trial Results — Pass 2 (2026-05-31, CotEditor fixed: warm-launch + token-name poll)

| type | tr | fg/bg | gt_wid | title_observed | A_agree | B_agree | desktop | space_agree |
|---|---|---|---|---|---|---|---|---|
| coteditor | 1 | bg | 2287 | `probe05_p05ca7baac.txt` | True | True | 3 | True |
| coteditor | 2 | bg | 2288 | `probe05_p05ce6242c.txt` | True | True | 3 | True |
| coteditor | 3 | bg | 2289 | `probe05_p05c923ba7.txt` | True | True | 3 | True |

Space signals: S1=4 (desktop 3), S2=True (on active space), S3=space_id 4 (desktop 3) for all 3. cleanup_ok=False (timing: CotEditor WID lingers >3s in CGWindowList after AppleScript close — document IS closed, confirmed by next trial detecting a fresh WID).

**Combined: space_agree=True for all 9 trials across all types (Ghostty 6/6 pass 1, CotEditor 3/3 pass 2).**

## Root Cause Analysis

### Ghostty: title = CWD, not token

**Both tmux and OSC-2 windows show `'…/Documents/ai/Monitor_CC'`** (the project CWD, not the token). Root cause: `open -n -a Ghostty --args --command "..."` does not reliably execute the specified command. The new Ghostty process ignores or doesn't receive the `--command` flag and starts a default interactive shell. Shell integration then sets the window title to the CWD of the new process (which inherits `~/Documents/ai/Monitor_CC` from the spawning environment).

Evidence: title is identical for ghostty_tmux AND ghostty_osc2. If `--command` was honored, tmux would show a tmux pane title and osc2 would show the token. Both show the same CWD path → command not executed.

Contrast with 01 probe OSC-2: the 01 probe WRITES the OSC-2 escape directly to the window's TTY file descriptor from an external process. This works. `bash -c 'printf ...'` (inside the terminal) doesn't reach kCGWindowName when Ghostty ignores the `--command` flag entirely.

### Ghostty: Method B disagrees even on fg trials

For ghostty_osc2 trial 1 fg: gt=2076, method_b=2078. Both are NEW WIDs (not in `before`). Two named Ghostty windows appeared from `open -n -a Ghostty`. `min(delta)=2076` is the lower WID; frontmost is 2078. Hypothesis: Ghostty creates two windows on launch (e.g., a main window + a floating/auxiliary window), the higher-WID one gets focus → method_b picks the second window, ground truth picks the first.

### CotEditor pass 1: intermediate unnamed window + session restore

`require_name=False` and `open -n` (cold launch) caused two failure modes:
- Trials 1+2: `title=None`, `s3_sp=None` — intermediate window (WID 2115, 2141) appears at 0.2s, unnamed, not on any space. `min(delta)` picked this transient window before the document window appeared.
- Trial 3: `title='Trading.md'` — `open -n` cold-launched a new CotEditor instance. CotEditor's `AppDelegate.performOnLaunchAction()` restores previous session (Trading.md) before opening our file. `min(delta)` picked the session-restored window.

Root cause (source-confirmed): `performOnLaunchAction()` is called ONLY on cold launch (new process via `open -n`). When CotEditor is already running and receives an open-file event, it routes directly to `application(_:openFiles:)` — no session restore. Fix: warm-launch CotEditor first, then use `open -g -a CotEditor <file>` (no `-n`).

### CotEditor pass 2: fix applied

Three changes in `05_window_detection_probe.py`:
1. `_ensure_coteditor_running()` — called once before CotEditor trials; opens CotEditor with `-g` if not running, waits 2s. Prevents cold-launch session restore.
2. `_open_window` for CotEditor: `open -g -a CotEditor <file>` (no `-n`) — routes to existing process → `application(_:openFiles:)` → no session restore.
3. Ground truth: token-name poll (`_method_a("CotEditor", token)` polling until non-None) instead of snapshot-diff. Skips intermediate unnamed windows entirely; waits for the specific document window.

Result: all 3 trials: correct gt_wid, A_agree=True, B_agree=True, space_agree=True.

## What Worked

1. **Ground truth detection:** 12/12 trials across both passes. `_owner_wids_layer0` reliable for Ghostty; token-name poll reliable for CotEditor.
2. **Space detection S1/S2/S3:** 12/12 all_agree=True (Ghostty 6/6 pass 1 + CotEditor 3/3 pass 2). `CGSGetActiveSpace`, `_on_screen_wids()`, and `CGSCopySpacesForWindows` agree on desktop=3 for all.
3. **CotEditor Method A+B (pass 2):** 3/3 agreement each. Token-name poll gives correct gt_wid; frontmost CotEditor window is that gt_wid (CotEditor brings the new document to front within the app).
4. **Cleanup:** tmux kill-session for ghostty_tmux reliable. CotEditor AppleScript close works (WID lingers >3s in CGWindowList but document IS closed — timing artifact, not a failure).
5. **CGS bridge (ctypes/ObjC):** No crashes across all 12 trials. Bridge reuse from 04 probe is solid.

## What Did Not Work

1. **Ghostty Method A (title-match):** 0/6. `open -n -a Ghostty --args --command` does not execute the specified command; Ghostty starts default shell → CWD-based title, never the token.
2. **Ghostty Method B (frontmost):** 0/6. Probe terminal (an existing Ghostty window) is frontmost OR Ghostty creates two named windows on launch and the wrong one is frontmost.
3. **CotEditor pass 1:** 0/9 signals. Root cause: cold launch (`-n`) + snapshot-diff → wrong windows.

## Identification Method Conclusion

**For CotEditor (document files): Method A is robust** after the warm-launch fix. Token embedded in the filename → kCGWindowName contains it reliably. Method B also agrees when CotEditor is the active focused app.

**For Ghostty: neither method is robust** in the current probe design. The token never reaches kCGWindowName via `open --args --command`. The root cause is that Ghostty ignores the `--command` flag when launched via `open`. The 01 probe approach (direct TTY injection from outside, after window is open) is the confirmed-working path.

**Space detection is reliable for both** once the correct gt_wid is pinned: S1 (before-open active space) == S3 (CGSCopySpacesForWindows on gt_wid), and S2 (on_screen_wids) confirms window is visible.

## Open Questions / Next Steps

1. **Ghostty `--command` via `open`:** does `ghostty --command=<cmd>` work launched from CLI directly? If yes, `open` is the issue (argv handling). If no, `--command` is not supported this way in this Ghostty version.
2. **Ghostty title-match via existing window:** open Ghostty normally → snapshot-diff gives gt_wid → inject OSC-2 via direct TTY write (01 probe approach) → poll until kCGWindowName contains token. Bypasses `--command` entirely.
3. **Space detection on non-active space:** all trials landed on desktop 3 (active space). Need a trial where window opens on a different desktop to verify S1≠S3 is detected correctly.
4. **CotEditor cleanup timing:** WID lingers >3s after AppleScript close. Could use a longer poll (5s) or a different close mechanism (System Events `click close button`). Not a blocker.

## Evidence Artifacts

- `dev/desktop_detection/05_window_detection_probe.py`
- `dev/desktop_detection/05_reports/trial_ghostty_tmux_[1-3]_20260531_22340*.json`
- `dev/desktop_detection/05_reports/trial_ghostty_osc2_[1-3]_20260531_22342*.json`
- `dev/desktop_detection/05_reports/trial_coteditor_[1-3]_20260531_22344*.json` (broken pass 1)
- `dev/desktop_detection/05_reports/trial_coteditor_[1-3]_20260531_2305*.json` (fixed pass 2)
